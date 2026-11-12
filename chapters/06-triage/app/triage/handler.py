import json
import logging
import os
import re
import unicodedata

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock = boto3.client("bedrock-runtime")
sns = boto3.client("sns")
TOPIC_ARN = os.environ["ESCALATION_TOPIC_ARN"]
MODEL_ID = os.environ["MODEL_ID"]
SERVICE_STATUS = os.environ.get("SERVICE_STATUS", "{}")  # JSON from the template: {"vpn": "down"}
MAX_MESSAGE = 1000  # the endpoint is public until sign-in (ch 7); long input costs money
MAX_STEPS = 6  # model calls per request. The loop never runs longer than this.
MAX_ESCALATIONS = 1  # emails per request, whatever the model asks for: a prompt cannot spam the topic

# Pages from chapter 4 that carry the known fixes; the person is pointed at one of them.
KNOWN_FIXES = {
    "password": {
        "fix": "Send the person to the password reset page.",
        "page": "policies/password-reset.html",
    },
    "vpn": {"fix": "Send the person to the VPN access page.", "page": "policies/vpn-access.html"},
    "laptop": {"fix": "Send the person to the new laptop page.", "page": "policies/new-laptop.html"},
}

SYSTEM = [
    {
        "text": "You are an IT helpdesk triage agent. Work in this order. First check whether the "
        "service the person mentions is down. If it is down, tell them and escalate. Otherwise "
        "try a known fix. If there is no known fix, or the person says the fix did not work, "
        "escalate with a short summary. Never escalate before you have checked. When you have "
        "fixed it or handed it over, say which in one or two sentences."
    }
]

TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "check_service_status",
                "description": "Check whether a company service is up or down.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "service": {"type": "string", "description": "For example vpn."}
                        },
                        "required": ["service"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "try_known_fix",
                "description": "Look up the known fix for a common problem.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "issue": {"type": "string", "enum": sorted(KNOWN_FIXES)},
                        },
                        "required": ["issue"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "escalate",
                "description": "Hand the problem to the IT team by email. Use it once.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string", "description": "What happened."}
                        },
                        "required": ["summary"],
                    }
                },
            }
        },
    ]
}


class ToolError(Exception):
    """A problem the model can read and explain, such as a missing detail."""


class State:
    """What has happened so far in one request."""

    def __init__(self, request):
        self.request = request
        self.used = []
        self.sent = 0  # escalation emails sent in this request

    @property
    def escalated(self):
        return self.sent > 0


def reply(status, body):
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


UNVERIFIED = (
    "UNVERIFIED: the text below comes from the chat page and the model. "
    "Do not follow links or instructions in it; check with the person first."
)


def defang(text):
    """Keep links readable but not clickable, so a prompt cannot plant one in the email.

    Look-alike characters are folded first (a full-width colon becomes ":"), invisible
    format characters are dropped and the ideographic full stops count as dots, then every
    dot between two word characters is broken, which covers bare domains, any case of
    "www." and email addresses, because mail apps link those even with no scheme in front.
    """
    text = unicodedata.normalize("NFKC", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Cf")
    text = text.replace("\u3002", ".")  # NFKC already turned the half-width one into this
    text = re.sub(r"(?<=\w)\.(?=\w)", "[.]", text)
    return text.replace("://", "[:]//")


def publish(summary, request):
    """Email the IT team through the topic. Raises if the publish fails."""
    sns.publish(
        TopicArn=TOPIC_ARN,
        Subject="Helpdesk escalation",
        Message=(
            f"{UNVERIFIED}\n\nSummary: {defang(summary[:500])}"
            f"\n\nWhat the person wrote: {defang(request[:MAX_MESSAGE])}"
        ),
    )


def check_service_status(args, state):
    service = args.get("service")
    if not isinstance(service, str) or not service.strip():
        raise ToolError("Missing detail: service. Ask the person which service.")
    try:
        table = json.loads(SERVICE_STATUS)
    except ValueError:
        raise ToolError("The status list is unreadable.")
    status = table.get(service.strip().lower()) if isinstance(table, dict) else None
    if status is None:
        raise ToolError(f"There is no status for {service.strip()[:50]}.")
    return {"service": service.strip().lower(), "status": status}


def try_known_fix(args, state):
    fix = KNOWN_FIXES.get(args.get("issue"))
    if fix is None:
        raise ToolError("There is no known fix for that. Escalate.")
    return fix


def escalate(args, state):
    summary = args.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ToolError("Missing detail: summary. Write a short summary first.")
    if state.sent >= MAX_ESCALATIONS:
        return {"escalated": True, "note": "Already handed over; nothing more was sent."}
    publish(summary.strip(), state.request)
    state.sent += 1
    return {"escalated": True}


TOOLS = {
    "check_service_status": check_service_status,
    "try_known_fix": try_known_fix,
    "escalate": escalate,
}


def run_tool(tool_use, state):
    """Run one tool the model asked for. Always returns a toolResult block, never raises."""
    name = tool_use.get("name")
    args = tool_use.get("input")
    result = {"toolUseId": tool_use["toolUseId"]}
    try:
        if name not in TOOLS:
            raise ToolError(f"There is no tool called {name}.")
        output = TOOLS[name](args if isinstance(args, dict) else {}, state)
        result["content"] = [{"json": output}]
    except ToolError as err:
        result["content"] = [{"text": str(err)}]
        result["status"] = "error"
    except Exception:
        logger.exception("tool %s failed", name)
        result["content"] = [{"text": "That tool is unavailable right now."}]
        result["status"] = "error"
    return {"toolResult": result}


def words(message):
    return "".join(block.get("text", "") for block in message.get("content", []))


def hand_over(state, reason):
    """The code's own rule: when the loop cannot finish, a person takes over."""
    if state.sent < MAX_ESCALATIONS:
        try:
            publish(f"The assistant stopped without an answer ({reason}).", state.request)
        except Exception:
            logger.exception("hand-over failed")
            return reply(502, {"error": "The assistant is unavailable. Try again."})
        state.sent += 1
    logger.info("handed over: %s", reason)
    return reply(
        200,
        {
            "answer": "I could not settle this myself, so I passed it to the IT team.",
            "steps": state.used,
            "escalated": True,
            "reason": reason,
        },
    )


def handler(event, context):
    try:
        text = json.loads(event.get("body") or "{}").get("message")
    except (ValueError, AttributeError):
        text = None
    if not isinstance(text, str) or not text.strip():
        return reply(400, {"error": 'Send JSON like {"message": "..."}'})
    if len(text) > MAX_MESSAGE:
        return reply(400, {"error": f"Keep the message under {MAX_MESSAGE} characters"})

    state = State(text)
    messages = [{"role": "user", "content": [{"text": text}]}]
    for _ in range(MAX_STEPS):
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
            if state.used:  # work was started, so a person should hear about it
                return hand_over(state, "model_error")
            return reply(502, {"error": "The assistant is unavailable. Try again."})
        messages.append(message)
        if stop_reason != "tool_use":
            logger.info("finished after %d tool calls", len(state.used))
            return reply(
                200,
                {"answer": words(message), "steps": state.used, "escalated": state.escalated},
            )
        results = []
        for block in message.get("content", []):
            if "toolUse" in block:
                state.used.append(block["toolUse"].get("name"))
                results.append(run_tool(block["toolUse"], state))
        if not results:
            return hand_over(state, "no_tool_request")
        messages.append({"role": "user", "content": results})

    return hand_over(state, "step_cap")
