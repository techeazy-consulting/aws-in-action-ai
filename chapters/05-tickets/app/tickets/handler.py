import json
import logging
import os
import re

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock = boto3.client("bedrock-runtime")
dynamodb = boto3.client("dynamodb")
TABLE = os.environ["TICKETS_TABLE"]
MODEL_ID = os.environ["MODEL_ID"]
MAX_MESSAGE = 1000  # the endpoint is public until sign-in (ch 7); long input costs money
MAX_ROUNDS = 3  # model calls per request: ask, read the tool result, answer
FIRST_NUMBER = 1000  # the first ticket is 1001
COUNTER_KEY = "counter"  # one extra item in the table that counts tickets
TICKET_ID = re.compile(r"^[0-9]{4,9}$")  # keeps "counter" out of reach of get_ticket_status

SYSTEM = [
    {
        "text": "You are an IT helpdesk assistant. To open a ticket you need a short title and "
        "the name of the person asking. If either is missing, ask for it instead of guessing. "
        "To check a ticket, use its number. Never invent a ticket number or a status."
    }
]

TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "create_ticket",
                "description": "Open a new IT ticket and return its number.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "What the person needs."},
                            "requester": {"type": "string", "description": "Who is asking."},
                        },
                        "required": ["title", "requester"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "get_ticket_status",
                "description": "Look up an existing ticket by number and return its status.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "ticket_id": {"type": "string", "description": "For example 1042."}
                        },
                        "required": ["ticket_id"],
                    }
                },
            }
        },
    ]
}


class ToolError(Exception):
    """A problem the model can read and explain to the person, such as a missing detail."""


def reply(status, body):
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


def text_field(args, name, limit):
    value = args.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ToolError(f"Missing detail: {name}. Ask the person for it.")
    return value.strip()[:limit]


def create_ticket(args):
    title = text_field(args, "title", 200)
    requester = text_field(args, "requester", 100)
    # ADD on a number adds to it, and starts from 0 when the item or attribute is not there yet.
    counted = dynamodb.update_item(
        TableName=TABLE,
        Key={"TicketId": {"S": COUNTER_KEY}},
        UpdateExpression="ADD LastNumber :one",
        ExpressionAttributeValues={":one": {"N": "1"}},
        ReturnValues="UPDATED_NEW",
    )
    ticket_id = str(FIRST_NUMBER + int(counted["Attributes"]["LastNumber"]["N"]))
    dynamodb.put_item(
        TableName=TABLE,
        Item={
            "TicketId": {"S": ticket_id},
            "Title": {"S": title},
            "Requester": {"S": requester},
            "Status": {"S": "open"},
        },
        ConditionExpression="attribute_not_exists(TicketId)",
    )
    return {"ticket_id": ticket_id, "status": "open"}


def get_ticket_status(args):
    ticket_id = str(args.get("ticket_id") or "").strip()
    if not TICKET_ID.fullmatch(ticket_id):
        raise ToolError("Missing detail: a ticket number such as 1042. Ask the person for it.")
    found = dynamodb.get_item(
        TableName=TABLE, Key={"TicketId": {"S": ticket_id}}, ConsistentRead=True
    )
    item = found.get("Item")  # no Item in the response means no such ticket
    if not item:
        raise ToolError(f"There is no ticket {ticket_id}.")
    return {
        "ticket_id": ticket_id,
        "title": item["Title"]["S"],
        "status": item["Status"]["S"],
    }


TOOLS = {"create_ticket": create_ticket, "get_ticket_status": get_ticket_status}


def run_tool(tool_use):
    """Run one tool the model asked for. Always returns a toolResult block, never raises."""
    name = tool_use.get("name")
    args = tool_use.get("input")
    result = {"toolUseId": tool_use["toolUseId"]}
    try:
        if name not in TOOLS:
            raise ToolError(f"There is no tool called {name}.")
        output = TOOLS[name](args if isinstance(args, dict) else {})
        result["content"] = [{"json": output}]
    except ToolError as err:
        result["content"] = [{"text": str(err)}]
        result["status"] = "error"
    except Exception:
        logger.exception("tool %s failed", name)
        result["content"] = [{"text": "The ticket system is unavailable right now."}]
        result["status"] = "error"
    return {"toolResult": result}


def words(message):
    return "".join(block.get("text", "") for block in message.get("content", []))


def handler(event, context):
    try:
        text = json.loads(event.get("body") or "{}").get("message")
    except (ValueError, AttributeError):
        text = None
    if not isinstance(text, str) or not text.strip():
        return reply(400, {"error": 'Send JSON like {"message": "..."}'})
    if len(text) > MAX_MESSAGE:
        return reply(400, {"error": f"Keep the message under {MAX_MESSAGE} characters"})

    messages = [{"role": "user", "content": [{"text": text}]}]
    used = []
    for _ in range(MAX_ROUNDS):
        try:
            response = bedrock.converse(
                modelId=MODEL_ID,
                messages=messages,
                system=SYSTEM,
                toolConfig=TOOL_CONFIG,
                inferenceConfig={"maxTokens": 400, "temperature": 0.2},
            )
            message = response["output"]["message"]
            stop_reason = response["stopReason"]
        except Exception:
            logger.exception("model call failed")
            return reply(502, {"error": "The assistant is unavailable. Try again."})
        messages.append(message)
        if stop_reason != "tool_use":
            logger.info("answered after %d tool calls", len(used))
            return reply(200, {"answer": words(message), "tools_used": used})
        results = []
        for block in message.get("content", []):
            if "toolUse" in block:
                used.append(block["toolUse"].get("name"))
                results.append(run_tool(block["toolUse"]))
        if not results:
            break
        messages.append({"role": "user", "content": results})

    logger.error("no final answer after %d model calls", MAX_ROUNDS)
    return reply(502, {"error": "The assistant could not finish. Try again."})
