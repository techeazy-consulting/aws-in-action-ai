# 03 - A quality check after every deploy

## Goal

Write the script that waits for the ingestion job and asks a fixed list of questions, failing on a wrong answer shape.

## Prompt

```text
Create app/quality/questions.json and app/quality/check.py, with tests/test_quality.py.

- questions.json: one question per policy page the knowledge base holds, each expecting that page
  to be cited, and one off-topic question that must be blocked. Validate the file (unique ids,
  exactly one of expect_page and expect_blocked, pages only under policies/).
- check.py run --function-name NAME: invoke the ask function directly (Lambda Invoke) with the
  claims of a made-up employee (token_use id, a fixed made-up user id, group employee, no email).
  For each question fail on: a status other than 200, a body that is not an object, no answer
  text, an answer that is far too long, sources that are not policy pages with an excerpt, a
  missing expected page, a normal question that was blocked, an off-topic question that was not
  blocked or has sources, and any answer or excerpt that looks like a secret. A crashed or
  unreachable function fails the question without printing the error details.
- check.py wait: poll the ingestion job until COMPLETE; fail on FAILED, STOPPING or STOPPED; give up
  after a fixed number of polls instead of hanging.
- Exit 0 all passed, 1 a check failed, 2 the check could not run. Never print the answers.
Tests use fakes for the function and the job, including a bad shape for each rule.
```

## Check

```bash
pytest -q tests/test_quality.py
python -c "import json; print(len(json.load(open('app/quality/questions.json'))))"
grep -n "def check_answer" app/quality/check.py
```
