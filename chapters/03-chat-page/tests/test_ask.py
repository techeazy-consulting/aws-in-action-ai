"""Chapter 2: the helpdesk's /ask handler, with the model call faked so nothing touches AWS."""

from __future__ import annotations

import importlib.util
import json
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
    monkeypatch.setenv("MODEL_ID", "test-model")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    fake_boto3 = types.SimpleNamespace(client=lambda *a, **k: object())
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    spec = importlib.util.spec_from_file_location("ask_handler", HANDLER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeBedrock:
    def __init__(self, text: str = "Restart the VPN client.", fail: bool = False) -> None:
        self.text, self.fail = text, fail
        self.calls: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("ThrottlingException")
        return {"output": {"message": {"role": "assistant", "content": [{"text": self.text}]}}}


def post(question: Any) -> dict[str, Any]:
    return {"body": json.dumps({"question": question})}


def test_happy_path_returns_answer_and_sends_converse_request(mod: Any) -> None:
    mod.bedrock = FakeBedrock()
    out = mod.handler(post("my laptop won't connect to VPN"), None)
    assert out["statusCode"] == 200
    assert json.loads(out["body"]) == {"answer": "Restart the VPN client."}
    call = mod.bedrock.calls[0]
    assert call["modelId"] == "test-model"
    assert call["messages"][0]["content"][0]["text"] == "my laptop won't connect to VPN"
    assert call["system"][0]["text"]


@pytest.mark.parametrize("event", [post(""), post("   "), post(None), post(42), {}, {"body": "x"}])
def test_missing_or_empty_question_is_400_and_model_not_called(mod: Any, event: Any) -> None:
    mod.bedrock = FakeBedrock()
    out = mod.handler(event, None)
    assert out["statusCode"] == 400
    assert "error" in json.loads(out["body"])
    assert mod.bedrock.calls == []


def test_overlong_question_is_400_and_model_not_called(mod: Any) -> None:
    mod.bedrock = FakeBedrock()
    out = mod.handler(post("x" * (mod.MAX_QUESTION + 1)), None)
    assert out["statusCode"] == 400
    assert mod.bedrock.calls == []
    assert mod.handler(post("x" * mod.MAX_QUESTION), None)["statusCode"] == 200


def test_model_error_is_502_with_safe_message(mod: Any) -> None:
    mod.bedrock = FakeBedrock(fail=True)
    out = mod.handler(post("hello"), None)
    assert out["statusCode"] == 502
    assert "Throttling" not in out["body"]


def test_template_throttles_the_public_stage() -> None:
    template = next((p for p in TEMPLATES if p.is_file()), None)
    if template is None:
        pytest.skip("template.yaml is not beside this folder")
    text = template.read_text(encoding="utf-8")
    assert "ThrottlingRateLimit:" in text and "ThrottlingBurstLimit:" in text
