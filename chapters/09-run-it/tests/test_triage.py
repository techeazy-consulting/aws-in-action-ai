"""Chapters 6 and 7: the triage loop, with the model and the topic faked so nothing touches AWS."""

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
HANDLER = CHAPTER / "app" / "triage" / "handler.py"
STATUS = json.dumps({"email": "up", "vpn": "down", "wiki": "up"})


@pytest.fixture
def mod(monkeypatch: pytest.MonkeyPatch) -> Any:
    """The handler module, loaded fresh, with boto3 replaced so nothing touches AWS."""
    monkeypatch.setenv("ESCALATION_TOPIC_ARN", "topic-arn")
    monkeypatch.setenv("MODEL_ID", "test-model")
    monkeypatch.setenv("GUARDRAIL_ID", "gr1")
    monkeypatch.setenv("GUARDRAIL_VERSION", "1")
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


def post(message: Any, **who: Any) -> dict[str, Any]:
    return signed_in({"message": message}, **who)


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
    assert "UNVERIFIED" in message and message.startswith("Signed in as")
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


@pytest.mark.parametrize("event", [post(""), post("   "), post(None), post(42), {"requestContext": post("")["requestContext"]}, {"body": "x", "requestContext": post("")["requestContext"]}])
def test_missing_or_empty_message_is_400_and_nothing_is_called(mod: Any, event: Any) -> None:
    mod.bedrock = FakeModel(says("x"))
    assert mod.handler(event, None)["statusCode"] == 400
    assert mod.bedrock.calls == [] and mod.sns.published == []


def test_overlong_message_is_400(mod: Any) -> None:
    mod.bedrock = FakeModel(says("ok"))
    assert mod.handler(post("x" * (mod.MAX_MESSAGE + 1)), None)["statusCode"] == 400
    assert mod.handler(post("x" * mod.MAX_MESSAGE), None)["statusCode"] == 200


# --- chapter 7: sign-in, the guardrail and the email --------------------------------------------


def guardrail_stop(text: str = "Ask an IT question.") -> dict[str, Any]:
    message = {"role": "assistant", "content": [{"text": text}]}
    return {"output": {"message": message}, "stopReason": "guardrail_intervened"}


def test_both_roles_may_triage(mod: Any) -> None:
    for groups in (("employee",), ("it-staff",)):
        mod.bedrock = FakeModel(says("Fine."))
        assert mod.handler(post("hi", groups=groups), None)["statusCode"] == 200


def test_every_model_call_goes_through_the_guardrail(mod: Any) -> None:
    mod.bedrock = FakeModel(asks("check_service_status", {"service": "vpn"}), says("VPN is down."))
    mod.handler(post("vpn?"), None)
    assert len(mod.bedrock.calls) == 2
    for call in mod.bedrock.calls:
        assert call["guardrailConfig"] == {"guardrailIdentifier": "gr1", "guardrailVersion": "1"}


def test_a_blocked_request_is_answered_with_the_guardrails_message_and_nothing_is_emailed(mod: Any) -> None:
    mod.bedrock = FakeModel(guardrail_stop("Ask an IT question."))
    out = mod.handler(post("which stock should I buy?"), None)
    assert out["statusCode"] == 200
    assert body(out) == {"answer": "Ask an IT question.", "steps": [], "escalated": False, "blocked": True}
    assert mod.sns.published == []  # a refused topic is not an outage


@pytest.mark.parametrize("reply", [{}, {"content": []}, None, "oops", {"content": [{"text": "x" * 900}]}])
def test_the_guardrails_message_is_checked_before_it_is_shown(mod: Any, reply: Any) -> None:
    mod.bedrock = FakeModel({"output": {"message": reply}, "stopReason": "guardrail_intervened"})
    answer = body(mod.handler(post("anything"), None))["answer"]
    assert isinstance(answer, str) and 0 < len(answer) <= 500


def test_a_block_after_a_tool_has_run_keeps_the_steps_and_does_not_escalate(mod: Any) -> None:
    mod.bedrock = FakeModel(asks("check_service_status", {"service": "vpn"}), guardrail_stop())
    result = body(mod.handler(post("vpn?"), None))
    assert result["blocked"] is True and result["steps"] == ["check_service_status"]
    assert mod.sns.published == []


def test_the_email_names_who_is_signed_in_from_the_token_and_breaks_the_address(mod: Any) -> None:
    mod.bedrock = FakeModel(asks("escalate", {"summary": "VPN down"}), says("Done."))
    mod.handler(post("vpn", **{"email": "priya@example.com"}), None)
    message = mod.sns.published[0]["Message"]
    assert message.startswith(
        f"Signed in as (from the sign-in token): user {SUB}, verified email priya@example[.]com"
    )
    assert "priya@example.com" not in message


def test_the_email_says_so_when_the_token_has_no_email(mod: Any) -> None:
    mod.bedrock = FakeModel(asks("escalate", {"summary": "VPN down"}), says("Done."))
    mod.handler(post("vpn", email=None), None)
    assert f"user {SUB}, no verified email" in mod.sns.published[0]["Message"]


def test_a_password_pasted_into_the_chat_does_not_reach_the_email_even_though_the_code_holds_it(
    mod: Any,
) -> None:
    # The guardrail masks the text the model sees. This function still holds the raw request,
    # and the model may copy a secret into its summary, so both are scrubbed before the email.
    key = "AKIA" + "ABCDEFGHIJKLMNOP"
    mod.bedrock = FakeModel(
        asks("escalate", {"summary": f"VPN down. user says password is hunter2-Xy9 and key {key}"}),
        says("Done."),
    )
    mod.handler(post(f"VPN fails. my password is hunter2-Xy9 and key {key}"), None)
    message = mod.sns.published[0]["Message"]
    assert "hunter2-Xy9" not in message and key not in message
    assert "VPN fails" in message and "[removed" in message


def test_the_email_keeps_the_ch6_link_breaking_after_the_scrub(mod: Any) -> None:
    mod.bedrock = FakeModel(asks("escalate", {"summary": "see evil.example/reset"}), says("Done."))
    mod.handler(post("help at WWW.EVIL.EXAMPLE"), None)
    message = mod.sns.published[0]["Message"]
    assert "evil.example" not in message.lower() and "evil[.]example" in message.lower()
    assert "UNVERIFIED" in message


def test_the_hand_over_email_also_names_the_caller(mod: Any) -> None:
    mod.bedrock = FakeModel(asks("check_service_status", {"service": "vpn"}), fail_after=1)
    mod.handler(post("vpn"), None)
    assert f"user {SUB}, verified email priya@example[.]com" in mod.sns.published[0]["Message"]


# --- chapter 9: one structured log line per request ---------------------------------------------

FIELDS = {"event", "route", "outcome", "status", "role", "latency_ms", "model_calls",
          "input_tokens", "output_tokens"}


def request_lines(caplog: pytest.LogCaptureFixture) -> list[dict[str, Any]]:
    return [
        {k: v for k, v in r.__dict__.items() if k in FIELDS}
        for r in caplog.records
        if getattr(r, "event", None) == "request"
    ]


def test_a_triage_request_logs_its_steps_tokens_and_outcome(mod: Any, caplog: pytest.LogCaptureFixture) -> None:
    first = {**asks("check_service_status", {"service": "vpn"}), "usage": {"inputTokens": 100, "outputTokens": 10}}
    last = {**says("VPN is down."), "usage": {"inputTokens": 160, "outputTokens": 25}}
    mod.bedrock = FakeModel(first, last)
    with caplog.at_level(logging.INFO):
        mod.handler(post("vpn?"), None)
    (line,) = request_lines(caplog)
    assert line["route"] == "triage" and line["outcome"] == "ok" and line["model_calls"] == 2
    assert line["input_tokens"] == 260 and line["output_tokens"] == 35 and line["role"] == "employee"


def test_the_triage_log_holds_no_message_summary_or_email(mod: Any, caplog: pytest.LogCaptureFixture) -> None:
    mod.bedrock = FakeModel(asks("escalate", {"summary": "VPN down for secret-summary-text"}), says("Done."))
    with caplog.at_level(logging.DEBUG):
        mod.handler(post("vpn broken, message-body-text"), None)
    everything = " ".join(f"{r.getMessage()} {sorted((k, str(v)) for k, v in r.__dict__.items())}" for r in caplog.records)
    for private in ("secret-summary-text", "message-body-text", "priya@example.com", SUB):
        assert private not in everything, private


def test_a_blocked_triage_request_and_a_step_cap_hand_over_are_told_apart(
    mod: Any, caplog: pytest.LogCaptureFixture
) -> None:
    mod.bedrock = FakeModel(guardrail_stop())
    with caplog.at_level(logging.INFO):
        mod.handler(post("which stock?"), None)
        mod.bedrock = FakeModel(asks("check_service_status", {"service": "vpn"}))
        mod.handler(post("loop forever"), None)
    assert [line["outcome"] for line in request_lines(caplog)] == ["blocked", "ok"]


def test_an_unexpected_exception_in_triage_is_an_error_line_and_a_safe_500(
    mod: Any, caplog: pytest.LogCaptureFixture
) -> None:
    mod.bedrock = FakeModel(says("x"))
    mod.words = lambda message: 1 / 0
    with caplog.at_level(logging.INFO):
        out = mod.handler(post("hi"), None)
    assert out["statusCode"] == 500 and request_lines(caplog)[0]["outcome"] == "error"


@pytest.mark.parametrize("verified", [False, "false", None, "yes", 1, ""])
def test_an_unverified_email_never_reaches_the_escalation_email(mod: Any, verified: Any) -> None:
    mod.bedrock = FakeModel(asks("escalate", {"summary": "VPN down"}), says("Done."))
    mod.handler(post("vpn", email_verified=verified), None)
    message = mod.sns.published[0]["Message"]
    assert "example" not in message and "priya" not in message
    assert f"Signed in as (from the sign-in token): user {SUB}, no verified email" in message
