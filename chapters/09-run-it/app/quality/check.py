"""Run after each deploy: a fixed list of helpdesk questions against the deployed /ask function.

Two commands:
  wait  - wait for the knowledge base ingestion job to finish (a new page is not searchable before).
  run   - ask every question in questions.json and fail on a wrong answer shape.

The check calls the ask function directly (Lambda Invoke) with the claims of a made-up employee,
so it needs no password and no stored secret; the invoking role needs permission to invoke that
one function. It therefore proves the function, the knowledge base, the model and the guardrail
work together after a deploy. It does not exercise sign-in or the API's token check: those have
their own tests.

Exit code: 0 every check passed, 1 a check failed, 2 the check could not run.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

QUESTIONS = Path(__file__).with_name("questions.json")
PAGE_KEY = re.compile(r"^policies/[A-Za-z0-9._-]+\.html$")
MAX_ANSWER = 3000  # an answer longer than this is not the short reply the page is built for
# The caller the check pretends to be: an ID token's claims for a made-up employee.
CLAIMS = {
    "token_use": "id",
    "sub": "00000000-0000-4000-8000-0000000000aa",
    "cognito:groups": ["employee"],
}
# The same shapes the functions scrub: a model answer or an excerpt must never carry one.
SECRET_SHAPES = (
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:password|passwd|pwd|secret|token|api[ _-]?key)\s*(?:is|=|:)\s*\S"),
)
DONE = {"COMPLETE"}
FAILED = {"FAILED", "STOPPING", "STOPPED"}


class CheckError(Exception):
    """The check could not run (a bad file, a failed call, a job that never finished)."""


def load_questions(path=QUESTIONS):
    try:
        cases = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise CheckError(f"cannot read the questions: {err}") from err
    if not isinstance(cases, list) or not cases:
        raise CheckError("the questions file must hold a non-empty list")
    seen = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or case["id"] in seen:
            raise CheckError("every question needs its own string id")
        seen.add(case["id"])
        question = case.get("question")
        if not isinstance(question, str) or not question.strip():
            raise CheckError(f"{case['id']}: the question must be text")
        page, blocked = case.get("expect_page"), case.get("expect_blocked")
        if (page is None) == (blocked is None):
            raise CheckError(f"{case['id']}: give exactly one of expect_page and expect_blocked")
        if page is not None and not (isinstance(page, str) and PAGE_KEY.match(page)):
            raise CheckError(f"{case['id']}: expect_page must be a policies/ page")
        if blocked is not None and blocked is not True:
            raise CheckError(f"{case['id']}: expect_blocked must be true")
    return cases


def build_event(question):
    """The event API Gateway would hand the function for a signed-in employee."""
    return {
        "body": json.dumps({"question": question}),
        "requestContext": {"authorizer": {"jwt": {"claims": dict(CLAIMS)}}},
    }


def invoke(client, function_name, event):
    """Invoke the function and return its reply (statusCode, body). Raises CheckError."""
    try:
        response = client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(event).encode("utf-8"),
        )
        if response.get("FunctionError"):
            raise CheckError("the function crashed")
        reply = json.loads(response["Payload"].read())
    except CheckError:
        raise
    except Exception as err:
        raise CheckError(f"could not invoke the function: {type(err).__name__}") from err
    if not isinstance(reply, dict):
        raise CheckError("the function did not return an object")
    return reply


def check_answer(case, reply):
    """Every way this reply has the wrong shape, as short sentences. Empty means it passed."""
    problems = []
    if reply.get("statusCode") != 200:
        return [f"status {reply.get('statusCode')}, expected 200"]
    try:
        body = json.loads(reply.get("body") or "")
    except ValueError:
        return ["the body is not JSON"]
    if not isinstance(body, dict):
        return ["the body is not an object"]
    answer = body.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        problems.append("no answer text")
    elif len(answer) > MAX_ANSWER:
        problems.append("the answer is far too long")
    sources = body.get("sources")
    if not isinstance(sources, list):
        problems.append("sources is not a list")
        sources = []
    pages = []
    for source in sources:
        page = source.get("page") if isinstance(source, dict) else None
        excerpt = source.get("excerpt") if isinstance(source, dict) else None
        if not (isinstance(page, str) and PAGE_KEY.match(page) and isinstance(excerpt, str)):
            problems.append("a source is not a policy page with an excerpt")
        else:
            pages.append(page)
    if case.get("expect_blocked"):
        if body.get("blocked") is not True:
            problems.append("the guardrail did not block this off-topic question")
        if sources:
            problems.append("a blocked answer must show no sources")
    else:
        if body.get("blocked") is True:
            problems.append("a normal question was blocked")
        if case["expect_page"] not in pages:
            problems.append(f"did not cite {case['expect_page']}")
    text = " ".join([answer if isinstance(answer, str) else ""] + [s.get("excerpt", "") for s in sources if isinstance(s, dict) and isinstance(s.get("excerpt"), str)])
    if any(shape.search(text) for shape in SECRET_SHAPES):
        problems.append("the answer or an excerpt looks like it holds a secret")
    return problems


def run_checks(client, function_name, cases):
    """Ask every question. Returns {id: [problems]} with an empty list for each pass."""
    results = {}
    for case in cases:
        try:
            reply = invoke(client, function_name, build_event(case["question"]))
            results[case["id"]] = check_answer(case, reply)
        except CheckError as err:
            results[case["id"]] = [str(err)]
    return results


def wait_for_ingestion(client, knowledge_base_id, data_source_id, job_id, sleep=time.sleep, interval=10, max_polls=60):
    """Poll the ingestion job until it is COMPLETE. Raises CheckError on failure or timeout."""
    status = "STARTING"
    for _ in range(max_polls):
        try:
            job = client.get_ingestion_job(
                knowledgeBaseId=knowledge_base_id, dataSourceId=data_source_id, ingestionJobId=job_id
            )["ingestionJob"]
            status = job["status"]
        except Exception as err:
            raise CheckError(f"could not read the ingestion job: {type(err).__name__}") from err
        if status in DONE:
            return status
        if status in FAILED:
            raise CheckError(f"the ingestion job ended as {status}")
        sleep(interval)
    raise CheckError(f"the ingestion job was still {status} after {max_polls} checks")


def main(argv=None, client_factory=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="ask the fixed questions")
    run.add_argument("--function-name", required=True)
    run.add_argument("--questions", default=str(QUESTIONS))
    wait = commands.add_parser("wait", help="wait for an ingestion job")
    wait.add_argument("--knowledge-base-id", required=True)
    wait.add_argument("--data-source-id", required=True)
    wait.add_argument("--job-id", required=True)
    args = parser.parse_args(argv)
    try:
        if client_factory is None:
            import boto3

            client_factory = boto3.client
        if args.command == "wait":
            client = client_factory("bedrock-agent")
            status = wait_for_ingestion(client, args.knowledge_base_id, args.data_source_id, args.job_id)
            print(f"ingestion {status}")
            return 0
        results = run_checks(client_factory("lambda"), args.function_name, load_questions(args.questions))
    except CheckError as err:
        print(f"cannot run: {err}", file=sys.stderr)
        return 2
    failed = 0
    for case_id, problems in results.items():
        print(f"{'FAIL' if problems else 'PASS'}  {case_id}" + "".join(f"\n      - {p}" for p in problems))
        failed += bool(problems)
    print(f"{len(results) - failed} of {len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
