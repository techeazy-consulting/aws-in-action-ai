import json
import logging
import os

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock = boto3.client("bedrock-runtime")
MODEL_ID = os.environ["MODEL_ID"]
MAX_QUESTION = 1000  # the endpoint is public until sign-in (ch 7); long input costs money
SYSTEM_PROMPT = (
    "You are the IT helpdesk assistant for a company. Answer in at most five short "
    "steps. If you are not sure, say so and suggest contacting the IT team."
)


def reply(status, body):
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


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
        response = bedrock.converse(
            modelId=MODEL_ID,
            system=[{"text": SYSTEM_PROMPT}],
            messages=[{"role": "user", "content": [{"text": question}]}],
            inferenceConfig={"maxTokens": 400, "temperature": 0.2},
        )
        answer = response["output"]["message"]["content"][0]["text"]
    except Exception:
        logger.exception("model call failed")
        return reply(502, {"error": "The assistant is unavailable. Try again."})

    logger.info("answered a question of %d characters", len(question))
    return reply(200, {"answer": answer})
