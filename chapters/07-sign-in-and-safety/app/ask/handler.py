import json
import logging
import os
import re
import unicodedata

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

agent = boto3.client("bedrock-agent-runtime")
KNOWLEDGE_BASE_ID = os.environ["KNOWLEDGE_BASE_ID"]
MODEL_ARN = os.environ["MODEL_ARN"]
GUARDRAIL_ID = os.environ["GUARDRAIL_ID"]  # no default: without a guardrail the function must not start
GUARDRAIL_VERSION = os.environ["GUARDRAIL_VERSION"]
MAX_QUESTION = 1000  # long input costs money
MAX_EXCERPT = 300
# Only pages from the policy folder are passed to the browser, whatever the knowledge base returns.
PAGE_KEY = re.compile(r"^policies/[A-Za-z0-9._-]+\.html$")


def reply(status, body):
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }

# Secrets that a guardrail does not catch in the places our own code reads from or writes to.
# Best effort, a second line of defence: the guardrail is the first (see the chapter notes).
SECRET_PATTERNS = (
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)"), "[removed key]"),
    (re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"), "[removed key]"),
    (
        re.compile(r"(?i)\b(pass(?:word|wd)?|pwd|secret|token|api[ _-]?key)(\s*(?:is|are|=|:)\s*)\S+"),
        r"\1\2[removed]",
    ),
    (
        re.compile(
            r"(?<![A-Za-z0-9/+=])(?=[A-Za-z0-9/+=]*\d)(?=[A-Za-z0-9/+=]*[A-Z])"
            r"(?=[A-Za-z0-9/+=]*[a-z])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])"
        ),
        "[removed key]",
    ),
)


def scrub(text):
    """Replace anything that looks like a pasted password or key with a marker."""
    text = unicodedata.normalize("NFKC", text)
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text

GROUPS = ("employee", "it-staff")  # the only groups the helpdesk knows; the template creates both
SUB = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
MAX_EMAIL = 254


def read_groups(value):
    """The caller's known groups from the cognito:groups claim, as a set.

    The claim is an array in the token. Some gateways hand a list claim on as one string such as
    "[employee it-staff]", so both shapes are read. Any name that is not in GROUPS is dropped.
    """
    if isinstance(value, str):
        value = re.split(r"[\s,\[\]]+", value)
    if not isinstance(value, (list, tuple)):
        return set()
    return {name for name in value if isinstance(name, str) and name in GROUPS}


def caller(event):
    """Who is calling, from the claims the gateway has already checked. None if anything is off.

    The token's signature, issuer, audience and expiry are checked by the API's JWT authorizer
    before this runs. This reads the claims again and trusts nothing it cannot validate: it must
    be an ID token, the subject must look like a user id, and the caller must be in a known group.
    """
    context = event.get("requestContext") if isinstance(event, dict) else None
    authorizer = context.get("authorizer") if isinstance(context, dict) else None
    jwt = authorizer.get("jwt") if isinstance(authorizer, dict) else None
    claims = jwt.get("claims") if isinstance(jwt, dict) else None
    if not isinstance(claims, dict) or claims.get("token_use") != "id":
        return None
    sub = claims.get("sub")
    groups = read_groups(claims.get("cognito:groups"))
    if not isinstance(sub, str) or not SUB.fullmatch(sub) or not groups:
        return None
    # The email claim is the one thing a user may be able to change, so it only counts when the
    # pool says it is verified. The user id (sub) is the identity; the email is for display.
    # The gateway hands booleans on as strings, so both True and "true" are read.
    verified = claims.get("email_verified")
    verified = verified is True or (isinstance(verified, str) and verified.lower() == "true")
    email = claims.get("email")
    if not verified or not isinstance(email, str) or len(email) > MAX_EMAIL or not email.isprintable():
        email = ""
    return {"sub": sub, "email": email, "groups": groups, "staff": "it-staff" in groups}


def not_signed_in():
    return reply(403, {"error": "Your account is not set up for the helpdesk. Ask IT."})


def sources(citations):
    """The distinct policy pages behind an answer, each with the passage that was used."""
    found = {}
    for citation in citations:
        for reference in citation.get("retrievedReferences", []):
            uri = ((reference.get("location") or {}).get("s3Location") or {}).get("uri") or ""
            parts = uri.split("/", 3)
            key = parts[3] if uri.startswith("s3://") and len(parts) == 4 else ""
            if PAGE_KEY.match(key) and key not in found:
                text = (reference.get("content") or {}).get("text") or ""
                # The guardrail never sees retrieved passages, so this code cleans them itself.
                found[key] = {"page": key, "excerpt": scrub(text)[:MAX_EXCERPT]}
    return list(found.values())


def handler(event, context):
    if caller(event) is None:
        return not_signed_in()
    try:
        question = json.loads(event.get("body") or "{}").get("question")
    except (ValueError, AttributeError):
        question = None
    if not isinstance(question, str) or not question.strip():
        return reply(400, {"error": 'Send JSON like {"question": "..."}'})
    if len(question) > MAX_QUESTION:
        return reply(400, {"error": f"Keep the question under {MAX_QUESTION} characters"})

    try:
        response = agent.retrieve_and_generate(
            input={"text": question},
            retrieveAndGenerateConfiguration={
                "type": "KNOWLEDGE_BASE",
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": KNOWLEDGE_BASE_ID,
                    "modelArn": MODEL_ARN,
                    "generationConfiguration": {
                        "guardrailConfiguration": {
                            "guardrailId": GUARDRAIL_ID,
                            "guardrailVersion": GUARDRAIL_VERSION,
                        },
                        "inferenceConfig": {
                            "textInferenceConfig": {"maxTokens": 400, "temperature": 0.2}
                        }
                    },
                },
            },
        )
        answer = response["output"]["text"]
        if not isinstance(answer, str) or not answer:
            raise ValueError("the knowledge base returned no text")
        intervened = response.get("guardrailAction") == "INTERVENED"
        cited = sources(response.get("citations", []))
    except Exception:
        logger.exception("knowledge base call failed")
        return reply(502, {"error": "The assistant is unavailable. Try again."})

    if intervened:  # the text is the guardrail's own message; show no sources for a blocked answer
        logger.info("the guardrail stepped in")
        return reply(200, {"answer": answer, "sources": [], "blocked": True})
    logger.info("answered a question of %d characters from %d pages", len(question), len(cited))
    return reply(200, {"answer": answer, "sources": cited})
