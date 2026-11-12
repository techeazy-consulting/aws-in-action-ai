"""Chapter 7: who is calling. The claims are read, checked again and never trusted blindly."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

CHAPTER = Path(__file__).resolve().parents[1]
SUB = "11111111-2222-3333-4444-5555555555ab"
ENV = {
    "ask": {"KNOWLEDGE_BASE_ID": "KB1", "MODEL_ARN": "model-arn"},
    "tickets": {"TICKETS_TABLE": "tickets-table", "MODEL_ID": "m"},
    "triage": {"ESCALATION_TOPIC_ARN": "topic", "MODEL_ID": "m", "SERVICE_STATUS": "{}"},
}
BODY = {"ask": {"question": "hi"}, "tickets": {"message": "hi"}, "triage": {"message": "hi"}}


class Untouchable:
    """Any call on it fails the test: nothing may reach AWS when the caller is refused."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"{name} was called for a caller who is not allowed in")


def load(monkeypatch: pytest.MonkeyPatch, name: str) -> Any:
    for key, value in {**ENV[name], "GUARDRAIL_ID": "gr1", "GUARDRAIL_VERSION": "1"}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setitem(sys.modules, "boto3", types.SimpleNamespace(client=lambda *a, **k: Untouchable()))
    spec = importlib.util.spec_from_file_location(f"{name}_h", CHAPTER / "app" / name / "handler.py")
    assert spec and spec.loader
    module: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def event(name: str, claims: Any) -> dict[str, Any]:
    context = {"authorizer": {"jwt": {"claims": claims}}}
    return {"body": json.dumps(BODY[name]), "requestContext": context}


def good(**over: Any) -> dict[str, Any]:
    return {
        "token_use": "id",
        "sub": SUB,
        "email": "a@example.com",
        "email_verified": "true",
        "cognito:groups": ["employee"],
        **over,
    }


@pytest.fixture(params=["ask", "tickets", "triage"])
def name(request: pytest.FixtureRequest) -> str:
    return str(request.param)


def refused(monkeypatch: pytest.MonkeyPatch, name: str, ev: dict[str, Any]) -> None:
    mod = load(monkeypatch, name)
    out = mod.handler(ev, None)  # Untouchable clients: reaching one fails the test
    assert out["statusCode"] == 403
    assert "error" in json.loads(out["body"])


def test_a_request_with_no_claims_is_refused(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    refused(monkeypatch, name, {"body": json.dumps(BODY[name])})
    refused(monkeypatch, name, {"body": json.dumps(BODY[name]), "requestContext": {}})
    refused(monkeypatch, name, event(name, None))
    refused(monkeypatch, name, event(name, "claims-as-text"))


@pytest.mark.parametrize(
    "over",
    [
        {"token_use": "access"},  # an access token is not an ID token
        {"token_use": None},
        {"sub": None},
        {"sub": "not-a-uuid"},
        {"sub": SUB + "extra"},
        {"sub": 42},
        {"cognito:groups": None},
        {"cognito:groups": []},
        {"cognito:groups": ["admins"]},  # a group the helpdesk does not know
        {"cognito:groups": "admins"},
        {"cognito:groups": [42, None, {"employee": True}]},
        {"cognito:groups": 7},
        {"cognito:groups": ["EMPLOYEE", "It-Staff"]},  # names are exact
    ],
)
def test_claims_that_do_not_check_out_are_refused(
    monkeypatch: pytest.MonkeyPatch, name: str, over: dict[str, Any]
) -> None:
    refused(monkeypatch, name, event(name, good(**over)))


def test_a_missing_token_use_claim_is_refused(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    claims = good()
    del claims["token_use"]
    refused(monkeypatch, name, event(name, claims))


@pytest.mark.parametrize(
    "groups, staff",
    [
        (["employee"], False),
        (["it-staff"], True),
        (["employee", "it-staff"], True),
        ("[employee it-staff]", True),  # some gateways pass a list claim on as one string
        ("[employee]", False),
        ("employee,it-staff", True),
        (["employee", "admins", 42], False),  # unknown names are dropped, not trusted
    ],
)
def test_known_groups_are_read_in_both_shapes(
    monkeypatch: pytest.MonkeyPatch, groups: Any, staff: bool
) -> None:
    mod = load(monkeypatch, "tickets")
    who = mod.caller(event("tickets", good(**{"cognito:groups": groups})))
    assert who is not None and who["staff"] is staff and who["sub"] == SUB
    assert who["groups"] <= {"employee", "it-staff"}


@pytest.mark.parametrize("email", [None, 42, "x" * 300, "a\nb@example.com", "a\x00b@example.com"])
def test_an_odd_email_claim_is_dropped_not_trusted(monkeypatch: pytest.MonkeyPatch, email: Any) -> None:
    mod = load(monkeypatch, "tickets")
    who = mod.caller(event("tickets", good(email=email)))
    assert who is not None and who["email"] == ""


def test_the_functions_do_not_start_without_a_guardrail(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    load(monkeypatch, name)  # fine with both variables set
    monkeypatch.delenv("GUARDRAIL_ID")
    spec = importlib.util.spec_from_file_location("x", CHAPTER / "app" / name / "handler.py")
    assert spec and spec.loader
    with pytest.raises(KeyError):
        spec.loader.exec_module(importlib.util.module_from_spec(spec))


@pytest.mark.parametrize("verified", [True, "true", "TRUE"])
def test_a_verified_email_is_kept(monkeypatch: pytest.MonkeyPatch, name: str, verified: Any) -> None:
    mod = load(monkeypatch, name)
    assert mod.caller(event(name, good(email_verified=verified)))["email"] == "a@example.com"


@pytest.mark.parametrize("verified", [False, "false", "False", None, "yes", 1, 0, "", [], {}, "true "])
def test_an_unverified_or_oddly_verified_email_is_dropped(monkeypatch: pytest.MonkeyPatch, name: str, verified: Any) -> None:
    mod = load(monkeypatch, name)
    assert mod.caller(event(name, good(email_verified=verified)))["email"] == ""


def test_a_token_with_no_email_verified_claim_at_all_has_no_email(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    claims = good()
    del claims["email_verified"]
    mod = load(monkeypatch, name)
    who = mod.caller(event(name, claims))
    assert who is not None and who["email"] == "" and who["sub"] == SUB  # the id is still the identity
