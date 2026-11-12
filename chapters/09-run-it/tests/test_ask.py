"""Chapters 4 and 7: the helpdesk's /ask handler, with the knowledge base call faked so nothing touches AWS."""

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
HANDLER = CHAPTER / "app" / "ask" / "handler.py"
# The template sits at the chapter root in the exported repo, and under student/ in the source tree.
TEMPLATES = [CHAPTER / "template.yaml", CHAPTER.parent / "student" / "template.yaml"]


@pytest.fixture
def mod(monkeypatch: pytest.MonkeyPatch) -> Any:
    """The handler module, loaded fresh, with boto3 replaced so nothing touches AWS."""
    monkeypatch.setenv("KNOWLEDGE_BASE_ID", "KB12345678")
    monkeypatch.setenv("MODEL_ARN", "test-model-arn")
    monkeypatch.setenv("GUARDRAIL_ID", "gr1")
    monkeypatch.setenv("GUARDRAIL_VERSION", "1")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    fake_boto3 = types.SimpleNamespace(client=lambda *a, **k: object())
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    spec = importlib.util.spec_from_file_location("ask_handler", HANDLER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reference(uri: str, text: str = "Use the reset link.") -> dict[str, Any]:
    return {"content": {"text": text}, "location": {"type": "S3", "s3Location": {"uri": uri}}}


class FakeAgent:
    """Stands in for the bedrock-agent-runtime client."""

    def __init__(
        self,
        text: str = "Choose Forgot password.",
        citations: list[dict[str, Any]] | None = None,
        fail: bool = False,
    ) -> None:
        self.text, self.citations, self.fail = text, citations or [], fail
        self.calls: list[dict[str, Any]] = []

    def retrieve_and_generate(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("ThrottlingException")
        return {"output": {"text": self.text}, "citations": self.citations, "sessionId": "s1"}


SUB = "11111111-2222-3333-4444-5555555555ab"
OTHER_SUB = "99999999-8888-7777-6666-5555555555cd"


def claims(groups: Any = ("employee",), sub: Any = SUB, **extra: Any) -> dict[str, Any]:
    """The claims the API's JWT authorizer hands the function for a signed-in ID token."""
    return {
        "token_use": "id",
        "sub": sub,
        "email": "priya@example.com",
        "email_verified": "true",  # the gateway hands a boolean claim on as a string
        "cognito:groups": list(groups) if isinstance(groups, (list, tuple)) else groups,
        **extra,
    }


def signed_in(body: Any, groups: Any = ("employee",), sub: Any = SUB, **extra: Any) -> dict[str, Any]:
    context = {"authorizer": {"jwt": {"claims": claims(groups, sub, **extra)}}}
    return {"body": json.dumps(body), "requestContext": context}


def post(question: Any) -> dict[str, Any]:
    return signed_in({"question": question})


def test_happy_path_returns_answer_with_cited_pages_and_sends_the_request(mod: Any) -> None:
    uri = "s3://site-bucket/policies/password-reset.html"
    mod.agent = FakeAgent(
        citations=[{"retrievedReferences": [reference(uri, "Open the sign-in page.")]}]
    )
    out = mod.handler(post("how do I reset my password?"), None)
    assert out["statusCode"] == 200
    body = json.loads(out["body"])
    assert body["answer"] == "Choose Forgot password."
    assert body["sources"] == [{"page": "policies/password-reset.html", "excerpt": "Open the sign-in page."}]
    call = mod.agent.calls[0]
    assert call["input"] == {"text": "how do I reset my password?"}
    config = call["retrieveAndGenerateConfiguration"]
    assert config["type"] == "KNOWLEDGE_BASE"
    assert config["knowledgeBaseConfiguration"]["knowledgeBaseId"] == "KB12345678"
    assert config["knowledgeBaseConfiguration"]["modelArn"] == "test-model-arn"


def test_a_page_cited_twice_is_listed_once_and_other_pages_keep_their_order(mod: Any) -> None:
    refs = [
        reference("s3://b/policies/vpn-access.html"),
        reference("s3://b/policies/new-laptop.html"),
        reference("s3://b/policies/vpn-access.html"),
    ]
    mod.agent = FakeAgent(citations=[{"retrievedReferences": refs[:2]}, {"retrievedReferences": refs[2:]}])
    body = json.loads(mod.handler(post("vpn"), None)["body"])
    assert [s["page"] for s in body["sources"]] == ["policies/vpn-access.html", "policies/new-laptop.html"]


@pytest.mark.parametrize(
    "uri",
    [
        "s3://b/secrets/payroll.html",  # outside the policy folder
        "s3://b/policies/../secrets.html",  # path trick
        "s3://b/policies/notes.txt",  # not a page
        "s3://b/policies/",  # a folder
        "no-scheme/policies/vpn-access.html",
        "",
    ],
)
def test_only_policy_pages_are_passed_to_the_browser(mod: Any, uri: str) -> None:
    mod.agent = FakeAgent(citations=[{"retrievedReferences": [reference(uri)]}])
    body = json.loads(mod.handler(post("anything"), None)["body"])
    assert body["sources"] == []


def test_an_answer_with_no_citations_has_no_sources(mod: Any) -> None:
    mod.agent = FakeAgent(citations=[])
    out = mod.handler(post("what is the weather?"), None)
    assert out["statusCode"] == 200
    assert json.loads(out["body"])["sources"] == []


def test_long_excerpts_are_cut(mod: Any) -> None:
    ref = reference("s3://b/policies/vpn-access.html", "x" * 5000)
    mod.agent = FakeAgent(citations=[{"retrievedReferences": [ref]}])
    body = json.loads(mod.handler(post("vpn"), None)["body"])
    assert len(body["sources"][0]["excerpt"]) == mod.MAX_EXCERPT


@pytest.mark.parametrize("event", [post(""), post("   "), post(None), post(42), {"requestContext": post("")["requestContext"]}, {"body": "x", "requestContext": post("")["requestContext"]}])
def test_missing_or_empty_question_is_400_and_knowledge_base_not_called(mod: Any, event: Any) -> None:
    mod.agent = FakeAgent()
    out = mod.handler(event, None)
    assert out["statusCode"] == 400
    assert "error" in json.loads(out["body"])
    assert mod.agent.calls == []


def test_overlong_question_is_400_and_knowledge_base_not_called(mod: Any) -> None:
    mod.agent = FakeAgent()
    out = mod.handler(post("x" * (mod.MAX_QUESTION + 1)), None)
    assert out["statusCode"] == 400
    assert mod.agent.calls == []
    assert mod.handler(post("x" * mod.MAX_QUESTION), None)["statusCode"] == 200


def test_knowledge_base_error_is_502_with_safe_message(mod: Any) -> None:
    mod.agent = FakeAgent(fail=True)
    out = mod.handler(post("hello"), None)
    assert out["statusCode"] == 502
    assert "Throttling" not in out["body"]


def test_template_throttles_the_public_stage() -> None:
    template = next((p for p in TEMPLATES if p.is_file()), None)
    if template is None:
        pytest.skip("template.yaml is not beside this folder")
    text = template.read_text(encoding="utf-8")
    assert "ThrottlingRateLimit:" in text and "ThrottlingBurstLimit:" in text


# --- chapter 7: sign-in and the guardrail ------------------------------------------------------


def test_the_knowledge_base_call_carries_the_guardrail(mod: Any) -> None:
    mod.agent = FakeAgent()
    mod.handler(post("vpn?"), None)
    generation = mod.agent.calls[0]["retrieveAndGenerateConfiguration"]["knowledgeBaseConfiguration"][
        "generationConfiguration"
    ]
    assert generation["guardrailConfiguration"] == {"guardrailId": "gr1", "guardrailVersion": "1"}
    assert "maxTokens" in str(generation["inferenceConfig"])  # the ch 4 settings are still there


def test_a_blocked_answer_is_shown_with_no_sources(mod: Any) -> None:
    uri = "s3://b/policies/vpn-access.html"
    mod.agent = FakeAgent(text="Ask an IT question.", citations=[{"retrievedReferences": [reference(uri)]}])
    original = mod.agent.retrieve_and_generate
    mod.agent.retrieve_and_generate = lambda **kw: {**original(**kw), "guardrailAction": "INTERVENED"}
    body = json.loads(mod.handler(post("which stock?"), None)["body"])
    assert body == {"answer": "Ask an IT question.", "sources": [], "blocked": True}


def test_an_answer_the_guardrail_left_alone_has_no_blocked_flag(mod: Any) -> None:
    mod.agent = FakeAgent()
    original = mod.agent.retrieve_and_generate
    mod.agent.retrieve_and_generate = lambda **kw: {**original(**kw), "guardrailAction": "NONE"}
    assert "blocked" not in json.loads(mod.handler(post("vpn?"), None)["body"])


@pytest.mark.parametrize("text", ["", None, 5])
def test_an_answer_with_no_usable_text_is_a_502(mod: Any, text: Any) -> None:
    mod.agent = FakeAgent(text=text)
    assert mod.handler(post("vpn?"), None)["statusCode"] == 502


def test_the_guardrail_covers_the_question_and_the_answer_not_the_passages_it_retrieves(mod: Any) -> None:
    # The guardrail is named once, on generation. The passages shown beside the answer come
    # straight from the knowledge base and never pass through it, so a secret that was
    # indexed would be shown. The code cleans the excerpt as a second line; the first line is
    # to keep secrets out of the policy pages (see test_policy_pages_hold_no_secrets).
    key = "AKIA" + "ABCDEFGHIJKLMNOP"
    leaky = reference("s3://b/policies/vpn-access.html", f"Use the shared login. password is hunter2-Xy9, key {key}")
    mod.agent = FakeAgent(citations=[{"retrievedReferences": [leaky]}])
    body = json.loads(mod.handler(post("vpn?"), None)["body"])
    excerpt = body["sources"][0]["excerpt"]
    assert "hunter2-Xy9" not in excerpt and key not in excerpt and "Use the shared login" in excerpt
    assert "apply_guardrail" not in HANDLER.read_text(encoding="utf-8")  # no separate check of passages


# --- chapter 9: one structured log line per request ---------------------------------------------


def lines(caplog: pytest.LogCaptureFixture) -> list[dict[str, Any]]:
    keys = {"event", "route", "outcome", "status", "role", "latency_ms"}
    return [
        {k: v for k, v in r.__dict__.items() if k in keys | {"input_tokens"}}
        for r in caplog.records
        if getattr(r, "event", None) == "request"
    ]


def test_ask_logs_a_summary_line_without_the_question_or_answer(
    mod: Any, caplog: pytest.LogCaptureFixture
) -> None:
    mod.agent = FakeAgent(text="The secret answer text.")
    with caplog.at_level(logging.DEBUG):
        mod.handler(post("a private question about vpn?"), None)
    (line,) = lines(caplog)
    assert line["route"] == "ask" and line["outcome"] == "ok" and line["role"] == "employee"
    assert "input_tokens" not in line  # this call reports no token count; the Bedrock metrics do
    everything = " ".join(f"{r.getMessage()} {sorted((k, str(v)) for k, v in r.__dict__.items())}" for r in caplog.records)
    for private in ("private question", "secret answer", "priya@example.com", SUB):
        assert private not in everything, private


def test_ask_outcomes_blocked_refused_and_error(mod: Any, caplog: pytest.LogCaptureFixture) -> None:
    mod.agent = FakeAgent()
    original = mod.agent.retrieve_and_generate
    with caplog.at_level(logging.INFO):
        mod.agent.retrieve_and_generate = lambda **kw: {**original(**kw), "guardrailAction": "INTERVENED"}
        mod.handler(post("stock?"), None)
        mod.handler({"body": "{}"}, None)
        mod.agent = FakeAgent(fail=True)
        mod.handler(post("vpn?"), None)
    assert [line["outcome"] for line in lines(caplog)] == ["blocked", "refused", "error"]
