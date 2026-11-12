import json
import logging
import os
import re

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

agent = boto3.client("bedrock-agent-runtime")
KNOWLEDGE_BASE_ID = os.environ["KNOWLEDGE_BASE_ID"]
MODEL_ARN = os.environ["MODEL_ARN"]
MAX_QUESTION = 1000  # the endpoint is public until sign-in (ch 7); long input costs money
MAX_EXCERPT = 300
# Only pages from the policy folder are passed to the browser, whatever the knowledge base returns.
PAGE_KEY = re.compile(r"^policies/[A-Za-z0-9._-]+\.html$")


def reply(status, body):
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


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
                found[key] = {"page": key, "excerpt": text[:MAX_EXCERPT]}
    return list(found.values())


def handler(event, context):
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
                        "inferenceConfig": {
                            "textInferenceConfig": {"maxTokens": 400, "temperature": 0.2}
                        }
                    },
                },
            },
        )
        answer = response["output"]["text"]
        cited = sources(response.get("citations", []))
    except Exception:
        logger.exception("knowledge base call failed")
        return reply(502, {"error": "The assistant is unavailable. Try again."})

    logger.info("answered a question of %d characters from %d pages", len(question), len(cited))
    return reply(200, {"answer": answer, "sources": cited})
