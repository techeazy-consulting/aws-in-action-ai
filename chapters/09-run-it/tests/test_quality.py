"""Chapter 9: the after-deploy quality check, with the function and the ingestion job faked."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
from typing import Any

import pytest

CHAPTER = Path(__file__).resolve().parents[1]
SCRIPT = CHAPTER / "app" / "quality" / "check.py"
QUESTIONS = CHAPTER / "app" / "quality" / "questions.json"


def load() -> Any:
    spec = importlib.util.spec_from_file_location("quality_check", SCRIPT)
    assert spec and spec.loader
    module: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def check() -> Any:
    return load()


def reply(answer: Any = "Open the reset page.", sources: Any = None, status: int = 200, **more: Any) -> dict[str, Any]:
    body = {"answer": answer, "sources": [] if sources is None else sources, **more}
    return {"statusCode": status, "body": json.dumps(body)}


def page(name: str, excerpt: str = "Steps for the page.") -> dict[str, str]:
    return {"page": f"policies/{name}.html", "excerpt": excerpt}


class FakeLambda:
    """Plays the ask function: answers by question, or fails as told."""

    def __init__(self, answers: dict[str, Any] | None = None, function_error: bool = False, raises: bool = False) -> None:
        self.answers = answers or {}
        self.function_error = function_error
        self.raises = raises
        self.calls: list[dict[str, Any]] = []

    def invoke(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self.raises:
            raise RuntimeError("AccessDeniedException: secret detail")
        question = json.loads(json.loads(kwargs["Payload"])["body"])["question"]
        payload = self.answers.get(question, reply())
        response: dict[str, Any] = {"Payload": io.BytesIO(json.dumps(payload).encode())}
        if self.function_error:
            response["FunctionError"] = "Unhandled"
        return response


def good_answers(check: Any) -> dict[str, Any]:
    cases = {c["id"]: c for c in check.load_questions()}
    return {
        cases["password-reset"]["question"]: reply(sources=[page("password-reset")]),
        cases["vpn-access"]["question"]: reply(sources=[page("vpn-access")]),
        cases["new-laptop"]["question"]: reply(sources=[page("new-laptop")]),
        cases["off-topic"]["question"]: reply("Ask an IT question.", [], blocked=True),
    }


def test_the_fixed_questions_are_valid_and_cover_the_policy_pages_and_the_guardrail(check: Any) -> None:
    cases = check.load_questions()
    assert len(cases) >= 4
    pages = {c["expect_page"] for c in cases if "expect_page" in c}
    on_disk = {f"policies/{p.name}" for p in (CHAPTER / "app" / "policies").glob("*.html")}
    assert pages == on_disk  # one question per policy page the knowledge base holds
    assert any(c.get("expect_blocked") for c in cases)  # and one the guardrail must refuse


def test_all_good_answers_pass_and_every_call_is_a_signed_in_employee(check: Any) -> None:
    client = FakeLambda(good_answers(check))
    results = check.run_checks(client, "helpdesk-staging-ask", check.load_questions())
    assert all(problems == [] for problems in results.values()) and len(results) == 4
    for call in client.calls:
        assert call["FunctionName"] == "helpdesk-staging-ask" and call["InvocationType"] == "RequestResponse"
        claims = json.loads(call["Payload"])["requestContext"]["authorizer"]["jwt"]["claims"]
        assert claims["token_use"] == "id" and claims["cognito:groups"] == ["employee"]
        assert "email" not in claims  # nothing personal, nothing real


@pytest.mark.parametrize(
    "bad, expected",
    [
        (reply(status=502), "status 502"),
        ({"statusCode": 200, "body": "not json"}, "not JSON"),
        ({"statusCode": 200, "body": "[1]"}, "not an object"),
        (reply(answer="", sources=[page("password-reset")]), "no answer text"),
        (reply(answer=None, sources=[page("password-reset")]), "no answer text"),
        (reply(answer="x" * 4000, sources=[page("password-reset")]), "too long"),
        (reply(sources=[]), "did not cite policies/password-reset.html"),
        (reply(sources=[page("vpn-access")]), "did not cite policies/password-reset.html"),
        (reply(sources="oops"), "sources is not a list"),
        (reply(sources=[{"page": "secrets/payroll.html", "excerpt": "x"}]), "not a policy page"),
        (reply(sources=[{"page": "policies/password-reset.html"}]), "not a policy page"),
        (reply(sources=[page("password-reset")], blocked=True), "was blocked"),
        (reply(answer="The password is hunter2.", sources=[page("password-reset")]), "holds a secret"),
        (reply(sources=[page("password-reset", "key AKIA" + "ABCDEFGHIJKLMNOP")]), "holds a secret"),
    ],
)
def test_a_wrong_answer_shape_fails_with_a_reason(check: Any, bad: dict[str, Any], expected: str) -> None:
    case = {"id": "password-reset", "question": "q", "expect_page": "policies/password-reset.html"}
    problems = check.check_answer(case, bad)
    assert problems and any(expected in p for p in problems), problems


def test_an_off_topic_question_that_is_answered_instead_of_blocked_fails(check: Any) -> None:
    case = {"id": "off-topic", "question": "q", "expect_blocked": True}
    assert any("did not block" in p for p in check.check_answer(case, reply("Buy shares.")))
    assert any("no sources" in p for p in check.check_answer(case, reply("No.", [page("vpn-access")], blocked=True)))
    assert check.check_answer(case, reply("Ask an IT question.", [], blocked=True)) == []


def test_one_bad_answer_fails_only_its_own_question(check: Any) -> None:
    answers = good_answers(check)
    answers["How do I get VPN access?"] = reply(sources=[])
    results = check.run_checks(FakeLambda(answers), "fn", check.load_questions())
    assert [k for k, v in results.items() if v] == ["vpn-access"]


@pytest.mark.parametrize("client", [FakeLambda(function_error=True), FakeLambda(raises=True)])
def test_a_crashed_or_unreachable_function_fails_every_question_without_leaking_details(
    check: Any, client: FakeLambda
) -> None:
    results = check.run_checks(client, "fn", check.load_questions())
    assert all(problems for problems in results.values())
    assert "secret detail" not in json.dumps(results)


def test_main_exit_codes_and_output(check: Any, capsys: pytest.CaptureFixture[str]) -> None:
    ok = check.main(["run", "--function-name", "fn"], lambda service: FakeLambda(good_answers(check)))
    assert ok == 0 and "4 of 4 passed" in capsys.readouterr().out
    bad = check.main(["run", "--function-name", "fn"], lambda service: FakeLambda({}))
    out = capsys.readouterr().out
    assert bad == 1 and "FAIL  password-reset" in out and "0 of 4 passed" in out
    assert "Open the reset page" not in out  # answers are not printed into the CI log


def test_main_returns_2_when_the_check_cannot_run(check: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert check.main(["run", "--function-name", "fn", "--questions", str(tmp_path / "missing.json")], lambda s: FakeLambda()) == 2
    assert "cannot run" in capsys.readouterr().err


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        "{}",
        "[]",
        '[{"id": "a", "question": "q"}]',
        '[{"id": "a", "question": "q", "expect_page": "policies/x.html", "expect_blocked": true}]',
        '[{"id": "a", "question": "q", "expect_page": "elsewhere/x.html"}]',
        '[{"id": "a", "question": "  ", "expect_blocked": true}]',
        '[{"id": "a", "question": "q", "expect_blocked": false}]',
        '[{"id": "a", "question": "q", "expect_blocked": true}, {"id": "a", "question": "r", "expect_blocked": true}]',
    ],
)
def test_a_bad_questions_file_is_refused(check: Any, tmp_path: Path, content: str) -> None:
    path = tmp_path / "q.json"
    path.write_text(content)
    with pytest.raises(check.CheckError):
        check.load_questions(path)


class FakeAgent:
    def __init__(self, *statuses: str, raises: bool = False) -> None:
        self.statuses = list(statuses)
        self.raises = raises
        self.calls = 0

    def get_ingestion_job(self, **kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        if self.raises:
            raise RuntimeError("AccessDenied")
        assert set(kwargs) == {"knowledgeBaseId", "dataSourceId", "ingestionJobId"}
        status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        return {"ingestionJob": {"status": status}}


def test_wait_returns_when_the_job_completes_and_sleeps_between_polls(check: Any) -> None:
    sleeps: list[int] = []
    agent = FakeAgent("STARTING", "IN_PROGRESS", "COMPLETE")
    assert check.wait_for_ingestion(agent, "kb", "ds", "job", sleep=sleeps.append, interval=7) == "COMPLETE"
    assert agent.calls == 3 and sleeps == [7, 7]


@pytest.mark.parametrize("status", ["FAILED", "STOPPING", "STOPPED"])
def test_wait_fails_on_a_job_that_did_not_complete(check: Any, status: str) -> None:
    with pytest.raises(check.CheckError, match=status):
        check.wait_for_ingestion(FakeAgent("IN_PROGRESS", status), "kb", "ds", "job", sleep=lambda s: None)


def test_wait_gives_up_after_a_set_number_of_checks_instead_of_hanging(check: Any) -> None:
    agent = FakeAgent("IN_PROGRESS")
    with pytest.raises(check.CheckError, match="still IN_PROGRESS after 5"):
        check.wait_for_ingestion(agent, "kb", "ds", "job", sleep=lambda s: None, max_polls=5)
    assert agent.calls == 5


def test_wait_reports_an_unreadable_job_by_error_name_only(check: Any) -> None:
    with pytest.raises(check.CheckError) as err:
        check.wait_for_ingestion(FakeAgent("x", raises=True), "kb", "ds", "job", sleep=lambda s: None)
    assert "RuntimeError" in str(err.value) and "AccessDenied" not in str(err.value)


def test_main_wait_exit_codes(check: Any, capsys: pytest.CaptureFixture[str]) -> None:
    args = ["wait", "--knowledge-base-id", "kb", "--data-source-id", "ds", "--job-id", "j"]
    assert check.main(args, lambda service: FakeAgent("COMPLETE")) == 0
    assert check.main(args, lambda service: FakeAgent("FAILED")) == 2
    assert "ingestion COMPLETE" in capsys.readouterr().out


def test_the_script_holds_no_account_id_email_or_link() -> None:
    import re

    text = SCRIPT.read_text(encoding="utf-8") + QUESTIONS.read_text(encoding="utf-8")
    assert not re.search(r"(?<!\d)\d{12}(?!\d)", text) and not re.search(r"@[A-Za-z0-9-]+\.[a-z]{2,}", text)
    assert not re.search(r"https?:[/][/]", text)
