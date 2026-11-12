# 04 - Tests with a fake knowledge base

## Goal

Prove the handler's answers, citations and failures with a fake knowledge base client, so the tests need no AWS account.

## Prompt

```text
Rewrite tests/test_ask.py for the new handler. Load the module from its file path with boto3
replaced by a fake and KNOWLEDGE_BASE_ID and MODEL_ARN set in the test. Replace the module's
`agent` client with a fake whose retrieve_and_generate method records its arguments and returns a
canned response (output text, citations, sessionId) or raises.

Cover:
- a good question returns 200, the answer and the cited page with its excerpt, and the call
  carries the question, type KNOWLEDGE_BASE, the knowledge base id and the model ARN;
- a page cited twice is listed once, in the order first cited;
- a location outside policies/, a path trick, a non-page file, a folder, a URI with no scheme and
  an empty URI are all dropped from sources;
- an answer with no citations returns an empty sources list;
- an excerpt longer than the cap is cut to the cap;
- empty, blank, missing or non-string questions and over-length questions return 400 and the fake
  is never called, while a question exactly at the cap returns 200;
- a failure returns 502 and the body does not contain the error text;
- the template (if present beside the folder) still throttles the public stage.
```

## Check

```bash
pytest -q tests/test_ask.py
```
