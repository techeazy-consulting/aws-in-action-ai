"""Chapter 7: the sign-in function, with Cognito faked. The password is never kept or shown."""

from __future__ import annotations

import importlib.util
import json
import logging
import sys
import types
from pathlib import Path
from typing import Any

import pytest

CHAPTER = Path(__file__).resolve().parents[1]
HANDLER = CHAPTER / "app" / "signin" / "handler.py"
PASSWORD = "correct-horse-battery-9"


class CognitoError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(f"{code}: the details mentioned {PASSWORD}")  # a message that would leak
        self.response = {"Error": {"Code": code}}


class FakeCognito:
    def __init__(self, result: Any = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def initiate_auth(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def mod(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("CLIENT_ID", "client123")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setitem(sys.modules, "boto3", types.SimpleNamespace(client=lambda *a, **k: object()))
    spec = importlib.util.spec_from_file_location("signin_h", HANDLER)
    assert spec and spec.loader
    module: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def post(**body: Any) -> dict[str, Any]:
    return {"body": json.dumps(body)}


GOOD = {"AuthenticationResult": {"IdToken": "id.tok.en", "AccessToken": "acc", "RefreshToken": "ref", "ExpiresIn": 3600}}


def test_a_good_sign_in_returns_the_id_token_and_nothing_else(mod: Any) -> None:
    mod.cognito = FakeCognito(GOOD)
    out = mod.handler(post(email=" priya@example.com ", password=PASSWORD), None)
    assert out["statusCode"] == 200
    assert json.loads(out["body"]) == {"id_token": "id.tok.en", "expires_in": 3600}
    assert "acc" not in out["body"] and "ref" not in out["body"]  # access and refresh tokens stay here
    assert out["headers"]["cache-control"] == "no-store"
    (call,) = mod.cognito.calls
    assert call["AuthFlow"] == "USER_PASSWORD_AUTH" and call["ClientId"] == "client123"
    assert call["AuthParameters"] == {"USERNAME": "priya@example.com", "PASSWORD": PASSWORD}


@pytest.mark.parametrize("code", ["NotAuthorizedException", "UserNotFoundException", "UserNotConfirmedException"])
def test_every_refusal_gets_one_message_that_does_not_say_whether_the_account_exists(
    mod: Any, code: str
) -> None:
    mod.cognito = FakeCognito(error=CognitoError(code))
    out = mod.handler(post(email="a@example.com", password=PASSWORD), None)
    assert out["statusCode"] == 401
    assert json.loads(out["body"]) == {"error": "Wrong email or password."}
    assert PASSWORD not in out["body"]


def test_a_cognito_outage_is_502_and_the_log_holds_no_password(
    mod: Any, caplog: pytest.LogCaptureFixture
) -> None:
    mod.cognito = FakeCognito(error=CognitoError("InternalErrorException"))
    with caplog.at_level(logging.DEBUG):
        out = mod.handler(post(email="a@example.com", password=PASSWORD), None)
    assert out["statusCode"] == 502
    assert PASSWORD not in out["body"]
    assert PASSWORD not in caplog.text and "a@example.com" not in caplog.text


def test_a_good_sign_in_logs_no_password_either(mod: Any, caplog: pytest.LogCaptureFixture) -> None:
    mod.cognito = FakeCognito(GOOD)
    with caplog.at_level(logging.DEBUG):
        mod.handler(post(email="a@example.com", password=PASSWORD), None)
    assert PASSWORD not in caplog.text and "id.tok.en" not in caplog.text


def test_a_challenge_is_not_a_sign_in(mod: Any) -> None:
    mod.cognito = FakeCognito({"ChallengeName": "NEW_PASSWORD_REQUIRED", "Session": "s"})
    out = mod.handler(post(email="a@example.com", password=PASSWORD), None)
    assert out["statusCode"] == 409
    assert "Session" not in out["body"] and "id_token" not in out["body"]


@pytest.mark.parametrize("response", [None, {}, {"AuthenticationResult": {}}, {"AuthenticationResult": {"IdToken": 5}}, "x"])
def test_a_reply_with_no_usable_token_issues_nothing(mod: Any, response: Any) -> None:
    mod.cognito = FakeCognito(response)
    out = mod.handler(post(email="a@example.com", password=PASSWORD), None)
    assert out["statusCode"] == 409 and "id_token" not in out["body"]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"email": "a@example.com"},
        {"password": PASSWORD},
        {"email": 5, "password": PASSWORD},
        {"email": "a@example.com", "password": ["x"]},
        {"email": "   ", "password": PASSWORD},
        {"email": "a@example.com", "password": ""},
        {"email": "a" * 255, "password": PASSWORD},
        {"email": "a@example.com", "password": "p" * 257},
    ],
)
def test_bad_input_is_400_and_cognito_is_not_called(mod: Any, body: dict[str, Any]) -> None:
    mod.cognito = FakeCognito(GOOD)
    out = mod.handler({"body": json.dumps(body)}, None)
    assert out["statusCode"] == 400
    assert mod.cognito.calls == []


@pytest.mark.parametrize("event", [{}, {"body": None}, {"body": "not json"}, {"body": "[1]"}, {"body": '"x"'}])
def test_a_body_that_is_not_an_object_is_400(mod: Any, event: dict[str, Any]) -> None:
    mod.cognito = FakeCognito(GOOD)
    assert mod.handler(event, None)["statusCode"] == 400
    assert mod.cognito.calls == []


def test_signin_logs_a_summary_line_with_the_outcome_and_no_credentials(
    mod: Any, caplog: pytest.LogCaptureFixture
) -> None:
    mod.cognito = FakeCognito(GOOD)
    with caplog.at_level(logging.DEBUG):
        mod.handler(post(email="a@example.com", password=PASSWORD), None)
        mod.cognito = FakeCognito(error=CognitoError("NotAuthorizedException"))
        mod.handler(post(email="a@example.com", password=PASSWORD), None)
        mod.cognito = FakeCognito(error=CognitoError("InternalErrorException"))
        mod.handler(post(email="a@example.com", password=PASSWORD), None)
    summary = [r for r in caplog.records if getattr(r, "event", None) == "request"]
    assert [r.outcome for r in summary] == ["ok", "refused", "error"]  # type: ignore[attr-defined]
    assert {r.route for r in summary} == {"signin"}  # type: ignore[attr-defined]
    everything = " ".join(f"{r.getMessage()} {sorted((k, str(v)) for k, v in r.__dict__.items())}" for r in caplog.records)
    assert PASSWORD not in everything and "a@example.com" not in everything and "id.tok.en" not in everything
