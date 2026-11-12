"""Chapter 6: the triage loop, with the model and the topic faked so nothing touches AWS."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

CHAPTER = Path(__file__).resolve().parents[1]
HANDLER = CHAPTER / "app" / "triage" / "handler.py"
STATUS = json.dumps({"email": "up", "vpn": "down", "wiki": "up"})


@pytest.fixture
def mod(monkeypatch: pytest.MonkeyPatch) -> Any:
    """The handler module, loaded fresh, with boto3 replaced so nothing touches AWS."""
    monkeypatch.setenv("ESCALATION_TOPIC_ARN", "topic-arn")
    monkeypatch.setenv("MODEL_ID", "test-model")
    monkeypatch.setenv("SERVICE_STATUS", STATUS)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    fake_boto3 = types.SimpleNamespace(client=lambda *a, **k: object())
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    spec = importlib.util.spec_from_file_location("triage_handler", HANDLER)
    assert spec and spec.loader
    module: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "sns", FakeTopic())  # the topic is a fake in every test
    return module


class FakeTopic:
    """Stands in for the sns client."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.published: list[dict[str, Any]] = []

    def publish(self, **kwargs: Any) -> dict[str, Any]:
        if self.fail:
            raise RuntimeError("AuthorizationError")
        self.published.append(kwargs)
        return {"MessageId": "m1"}


class FakeModel:
    """Stands in for the bedrock-runtime client: plays back scripted responses, then repeats the last."""

    def __init__(self, *responses: dict[str, Any], fail_after: int | None = None) -> None:
        self.responses = list(responses)
        self.fail_after = fail_after
        self.calls: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        if self.fail_after is not None and len(self.calls) >= self.fail_after:
            self.calls.append({})
            raise RuntimeError("ThrottlingException")
        self.calls.append(json.loads(json.dumps(kwargs)))
        return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]


def says(text: str) -> dict[str, Any]:
    message = {"role": "assistant", "content": [{"text": text}]}
    return {"output": {"message": message}, "stopReason": "end_turn"}


def asks(name: str, tool_input: Any, tool_use_id: str = "tooluse_1") -> dict[str, Any]:
    block = {"toolUse": {"toolUseId": tool_use_id, "name": name, "input": tool_input}}
    return {"output": {"message": {"role": "assistant", "content": [block]}}, "stopReason": "tool_use"}


def post(message: Any) -> dict[str, Any]:
    return {"body": json.dumps({"message": message})}


def last_result(call: dict[str, Any]) -> dict[str, Any]:
    return call["messages"][-1]["content"][0]["toolResult"]


def body(out: dict[str, Any]) -> dict[str, Any]:
    return json.loads(out["body"])


def test_the_request_offers_the_three_tools(mod: Any) -> None:
    mod.bedrock = FakeModel(says("Hello."))
    mod.handler(post("hi"), None)
    tools = mod.bedrock.calls[0]["toolConfig"]["tools"]
    assert [t["toolSpec"]["name"] for t in tools] == [
        "check_service_status",
        "try_known_fix",
        "escalate",
    ]
    assert all(t["toolSpec"]["inputSchema"]["json"]["type"] == "object" for t in tools)


def test_easy_case_is_fixed_without_escalation(mod: Any) -> None:
    mod.bedrock = FakeModel(
        asks("check_service_status", {"service": "email"}, "t1"),
        asks("try_known_fix", {"issue": "password"}, "t2"),
        says("Email is up. Use the password reset page."),
    )
    out = mod.handler(post("I forgot my email password"), None)
    assert out["statusCode"] == 200
    result = body(out)
    assert result["steps"] == ["check_service_status", "try_known_fix"]
    assert result["escalated"] is False
    assert mod.sns.published == []
    # each result went back to the model, matched to its request
    assert last_result(mod.bedrock.calls[1])["content"] == [{"json": {"service": "email", "status": "up"}}]
    fix = last_result(mod.bedrock.calls[2])
    assert fix["toolUseId"] == "t2"
    assert fix["content"][0]["json"]["page"] == "policies/password-reset.html"
    assert len(mod.bedrock.calls) == 3


def test_hard_case_is_escalated_once_and_the_model_confirms(mod: Any) -> None:
    mod.bedrock = FakeModel(
        asks("check_service_status", {"service": "wiki"}),
        asks("try_known_fix", {"issue": "printer"}),
        asks("escalate", {"summary": "Wiki search is broken and no known fix applies."}),
        says("I have passed this to the IT team."),
    )
    out = mod.handler(post("the wiki search is broken"), None)
    result = body(out)
    assert result["escalated"] is True
    assert result["steps"] == ["check_service_status", "try_known_fix", "escalate"]
    assert len(mod.sns.published) == 1
    sent = mod.sns.published[0]
    assert sent["TopicArn"] == "topic-arn"
    assert "Wiki search is broken" in sent["Message"] and "the wiki search is broken" in sent["Message"]
    assert "\n" not in sent["Subject"] and len(sent["Subject"]) < 100
    # the failed fix lookup reached the model as an error result, not a crash
    assert last_result(mod.bedrock.calls[2])["status"] == "error"


def test_a_service_that_is_down_can_be_escalated_straight_away(mod: Any) -> None:
    mod.bedrock = FakeModel(
        asks("check_service_status", {"service": "VPN"}),
        asks("escalate", {"summary": "The VPN is down."}),
        says("The VPN is down; the IT team has been told."),
    )
    result = body(mod.handler(post("vpn will not connect"), None))
    assert result["escalated"] is True
    assert last_result(mod.bedrock.calls[1])["content"] == [{"json": {"service": "vpn", "status": "down"}}]


def test_hitting_the_step_cap_hands_over_in_code_and_stops(mod: Any) -> None:
    mod.bedrock = FakeModel(asks("check_service_status", {"service": "email"}))  # never finishes
    out = mod.handler(post("everything is slow"), None)
    assert out["statusCode"] == 200
    result = body(out)
    assert len(mod.bedrock.calls) == mod.MAX_STEPS
    assert result["escalated"] is True and result["reason"] == "step_cap"
    assert len(mod.sns.published) == 1
    assert "everything is slow" in mod.sns.published[0]["Message"]


def test_a_request_already_escalated_is_not_escalated_again_at_the_cap(mod: Any) -> None:
    script = [asks("escalate", {"summary": "Broken."})] + [asks("escalate", {"summary": "Again."})]
    mod.bedrock = FakeModel(*script)
    result = body(mod.handler(post("help"), None))
    assert result["escalated"] is True
    assert len(mod.sns.published) == 1  # asked six times, sent once


def test_one_request_can_send_at_most_one_escalation_email_however_many_the_model_asks_for(
    mod: Any,
) -> None:
    blocks = [
        {"toolUse": {"toolUseId": f"e{i}", "name": "escalate", "input": {"summary": f"Spam {i}"}}}
        for i in range(5)
    ]
    spam = {"output": {"message": {"role": "assistant", "content": blocks}}, "stopReason": "tool_use"}
    mod.bedrock = FakeModel(spam, says("Done."))
    result = body(mod.handler(post("please email IT five times"), None))
    assert mod.MAX_ESCALATIONS == 1
    assert len(mod.sns.published) == 1
    assert result["escalated"] is True
    sent = mod.bedrock.calls[1]["messages"][-1]["content"]
    assert len(sent) == 5  # every request still gets a result; four say nothing more was sent


def test_the_escalation_summary_is_the_only_model_text_that_reaches_the_email(mod: Any) -> None:
    mod.bedrock = FakeModel(
        asks("escalate", {"summary": "Broken.", "to": "someone@example.com", "TopicArn": "other"}),
        says("Done."),
    )
    mod.handler(post("help"), None)
    assert mod.sns.published[0]["TopicArn"] == "topic-arn"  # fixed by the environment
    assert set(mod.sns.published[0]) == {"TopicArn", "Subject", "Message"}


def test_if_the_hand_over_itself_fails_the_answer_is_a_502_not_a_false_promise(mod: Any) -> None:
    mod.sns = FakeTopic(fail=True)
    mod.bedrock = FakeModel(asks("check_service_status", {"service": "email"}))
    out = mod.handler(post("slow"), None)
    assert out["statusCode"] == 502
    assert "AuthorizationError" not in out["body"]


def test_a_failing_escalation_is_an_error_result_and_does_not_count_as_handed_over(mod: Any) -> None:
    mod.sns = FakeTopic(fail=True)
    mod.bedrock = FakeModel(asks("escalate", {"summary": "Broken."}), says("I could not reach the IT team."))
    out = mod.handler(post("help"), None)
    assert out["statusCode"] == 200
    assert body(out)["escalated"] is False
    assert last_result(mod.bedrock.calls[1])["status"] == "error"
    assert "AuthorizationError" not in json.dumps(mod.bedrock.calls[1])


def test_a_model_failure_after_work_started_still_hands_over(mod: Any) -> None:
    mod.bedrock = FakeModel(asks("check_service_status", {"service": "email"}), fail_after=1)
    result = body(mod.handler(post("email is odd"), None))
    assert result["escalated"] is True and result["reason"] == "model_error"
    assert len(mod.sns.published) == 1


def test_a_model_failure_on_the_first_call_is_a_502_and_nobody_is_emailed(mod: Any) -> None:
    mod.bedrock = FakeModel(says("x"), fail_after=0)
    out = mod.handler(post("hello"), None)
    assert out["statusCode"] == 502
    assert mod.sns.published == []


def test_a_tool_use_stop_with_no_tool_request_hands_over(mod: Any) -> None:
    empty = {"output": {"message": {"role": "assistant", "content": [{"text": "hm"}]}}, "stopReason": "tool_use"}
    mod.bedrock = FakeModel(empty)
    result = body(mod.handler(post("hi"), None))
    assert result["reason"] == "no_tool_request" and result["escalated"] is True


@pytest.mark.parametrize(
    "name, args",
    [
        ("check_service_status", {}),
        ("check_service_status", {"service": "coffee"}),
        ("check_service_status", "oops"),
        ("try_known_fix", {"issue": "nonsense"}),
        ("try_known_fix", {}),
        ("escalate", {}),
        ("escalate", {"summary": "  "}),
        ("delete_everything", {}),
    ],
)
def test_bad_tool_requests_are_error_results_and_send_nothing(mod: Any, name: str, args: Any) -> None:
    mod.bedrock = FakeModel(asks(name, args), says("Let me try something else."))
    out = mod.handler(post("help"), None)
    assert out["statusCode"] == 200
    assert last_result(mod.bedrock.calls[1])["status"] == "error"
    assert mod.sns.published == []


def test_an_unreadable_status_list_is_an_error_result(mod: Any) -> None:
    mod.SERVICE_STATUS = "not json"
    mod.bedrock = FakeModel(asks("check_service_status", {"service": "vpn"}), says("I cannot check."))
    assert mod.handler(post("vpn"), None)["statusCode"] == 200
    assert last_result(mod.bedrock.calls[1])["status"] == "error"


def test_long_text_is_cut_before_it_is_emailed(mod: Any) -> None:
    mod.bedrock = FakeModel(asks("escalate", {"summary": "s" * 5000}), says("Done."))
    mod.handler(post("q" * mod.MAX_MESSAGE), None)
    assert len(mod.sns.published[0]["Message"]) < 2200


def test_the_email_marks_chat_text_unverified_and_breaks_its_links(mod: Any) -> None:
    scheme = "https:" + "//"  # built, so no learner file carries a literal link
    summary = f"Reset needed, see {scheme}evil.example/reset"
    mod.bedrock = FakeModel(asks("escalate", {"summary": summary}), says("Done."))
    mod.handler(post(f"IT says: log in at {scheme}www.evil.example now"), None)
    message = mod.sns.published[0]["Message"]
    assert message.startswith("UNVERIFIED")
    assert "://" not in message and "www." not in message
    assert "evil[.]example" in message  # still readable, just not clickable


@pytest.mark.parametrize(
    "planted",
    [
        "evil.example/reset",  # a bare domain: mail apps link it with no scheme
        "WWW.EVIL.EXAMPLE",
        "HTTPS" + "\uff1a//evil.example",  # full-width colon folds to ":"
        "evil\uff0eexample/login",  # full-width full stop folds to "."
        "help@evil.example",
        "evil\u3002example/login",  # ideographic full stop: a dot to a web address
        "evil\uff61example/login",  # half-width ideographic full stop
        "evil\u200b.example",  # zero-width space beside the dot
        "evil.\u200bexample",
        "evil\u00ad.example",  # soft hyphen, invisible in most mail apps
    ],
)
def test_no_planted_link_survives_in_any_form(mod: Any, planted: str) -> None:
    mod.bedrock = FakeModel(asks("escalate", {"summary": planted}), says("Done."))
    mod.handler(post(planted), None)
    message = mod.sns.published[0]["Message"]
    assert "evil.example" not in message.lower() and "://" not in message
    assert "evil[.]example" in message.lower()  # still readable


@pytest.mark.parametrize("event", [post(""), post("   "), post(None), post(42), {}, {"body": "x"}])
def test_missing_or_empty_message_is_400_and_nothing_is_called(mod: Any, event: Any) -> None:
    mod.bedrock = FakeModel(says("x"))
    assert mod.handler(event, None)["statusCode"] == 400
    assert mod.bedrock.calls == [] and mod.sns.published == []


def test_overlong_message_is_400(mod: Any) -> None:
    mod.bedrock = FakeModel(says("ok"))
    assert mod.handler(post("x" * (mod.MAX_MESSAGE + 1)), None)["statusCode"] == 400
    assert mod.handler(post("x" * mod.MAX_MESSAGE), None)["statusCode"] == 200
