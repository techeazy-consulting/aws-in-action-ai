# 02 - Tests for the page and the new stack

## Goal

Prove, without a browser or an AWS account, that the page calls the right place and that the new template parts keep the bucket private.

## Prompt

```text
Create tests/test_web.py with pytest tests that only read files. Load the page from
app/web/index.html. Find the template at template.yaml in the chapter folder, or at
../student/template.yaml; skip the template tests if neither exists.

Page tests:
- it posts JSON to the relative path /ask;
- it contains no absolute address (no http or https scheme followed by a colon and two slashes);
- it reads the reply with response.json() and uses none of getReader, ReadableStream,
  EventSource or WebSocket;
- it writes answers with textContent and never innerHTML;
- its textarea maxlength equals MAX_QUESTION in app/ask/handler.py;
- it shows an error when the call fails.

Template tests:
- all four Block Public Access settings are true and there is no website configuration;
- an origin access control with signing behavior always, origin type s3, and a bucket policy that
  trusts the CloudFront service and a source ARN condition;
- both cache behaviors redirect HTTP to HTTPS, /ask has its own path pattern, and the default
  root object is index.html.
```

## Check

```bash
pytest -q tests/test_web.py
```
