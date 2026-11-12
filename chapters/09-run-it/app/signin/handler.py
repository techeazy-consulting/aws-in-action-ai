import json
import logging
import os
import time

import boto3

logger = logging.getLogger()  # the level is set in the template (ApplicationLogLevel), not here
ROUTE = "signin"

cognito = boto3.client("cognito-idp")
CLIENT_ID = os.environ["CLIENT_ID"]
MAX_EMAIL = 254
MAX_PASSWORD = 256
# Cognito's answers that mean "those details did not work". All of them get one message, so the
# reply never says whether an email address has an account.
REFUSED = {"NotAuthorizedException", "UserNotFoundException", "UserNotConfirmedException"}


def reply(status, body):
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json", "cache-control": "no-store"},
        "body": json.dumps(body),
    }


def handle(event, context, stats):
    # The password is read, passed on and dropped. It is never logged, stored or sent back.
    try:
        body = json.loads(event.get("body") or "{}")
        email, password = body.get("email"), body.get("password")
    except (ValueError, AttributeError):
        email = password = None
    if not isinstance(email, str) or not isinstance(password, str):
        return reply(400, {"error": 'Send JSON like {"email": "...", "password": "..."}'})
    email = email.strip()
    if not email or not password or len(email) > MAX_EMAIL or len(password) > MAX_PASSWORD:
        return reply(400, {"error": "Enter your email and password."})

    try:
        response = cognito.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            ClientId=CLIENT_ID,
            AuthParameters={"USERNAME": email, "PASSWORD": password},
        )
    except Exception as err:
        code = getattr(err, "response", {}).get("Error", {}).get("Code")
        if code in REFUSED:
            return reply(401, {"error": "Wrong email or password."})
        logger.error("sign-in call failed: %s", type(err).__name__)  # the name only, never details
        return reply(502, {"error": "Sign-in is unavailable. Try again."})

    result = response.get("AuthenticationResult") if isinstance(response, dict) else None
    token = result.get("IdToken") if isinstance(result, dict) else None
    if not isinstance(token, str) or not token:
        # A challenge, such as a forced password change, is not a sign-in. Nothing is issued.
        challenge = response.get("ChallengeName") if isinstance(response, dict) else None
        logger.info("sign-in needs a step this page does not do: %s", challenge)
        return reply(409, {"error": "Your account needs a password change. Ask IT."})
    expires = result.get("ExpiresIn")
    # Only the ID token goes to the page. The access and refresh tokens stay here and are dropped.
    return reply(
        200, {"id_token": token, "expires_in": expires if isinstance(expires, int) else None}
    )


class Stats:
    """What one request used, for the single summary log line. It never holds anyone's words."""

    def __init__(self):
        self.role = "none"  # employee, staff or none (not signed in)
        self.model_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.tickets_created = 0



def outcome_of(response):
    """One word for how the request ended, for the dashboard and the alarm."""
    status = response.get("statusCode", 500) if isinstance(response, dict) else 500
    if status >= 500:
        return "error"
    if status in (401, 403, 409):
        return "refused"
    if status != 200:
        return "bad_request"
    try:
        body = json.loads(response.get("body") or "{}")
    except ValueError:
        return "error"
    return "blocked" if isinstance(body, dict) and body.get("blocked") else "ok"


def log_request(response, stats, started):
    """One JSON log line per request: how it ended, who (a role, never a name), how long, how many tokens."""
    fields = {
        "event": "request",
        "route": ROUTE,
        "outcome": outcome_of(response),
        "status": response.get("statusCode") if isinstance(response, dict) else None,
        "role": stats.role,
        "latency_ms": int((time.monotonic() - started) * 1000),
    }
    logger.info("request", extra=fields)


def handler(event, context):
    started = time.monotonic()
    stats = Stats()
    try:
        response = handle(event, context, stats)
    except Exception:
        logger.exception("unhandled error")
        response = reply(500, {"error": "Something went wrong. Try again."})
    log_request(response, stats, started)
    return response
