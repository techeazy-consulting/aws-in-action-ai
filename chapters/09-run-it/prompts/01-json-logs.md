# 01 - One JSON log line per request

## Goal

Make every function log one structured summary line per request that holds numbers and words about the request, never what anyone wrote.

## Prompt

```text
Change the four handlers (ask, tickets, triage, signin).

- Rename handler to handle(event, context, stats) and write a new handler that times the call,
  runs handle, turns any exception into a logged error and a safe 500, and logs the summary.
- The summary is logger.info("request", extra={...}) with event "request", route, outcome (ok,
  blocked, refused, bad_request or error, from the status code and the blocked flag), status, role
  (employee, staff or none), latency_ms. For tickets and triage also model_calls, input_tokens and
  output_tokens read from the usage the model reports (ignore a count that is missing, negative,
  not a whole number or a boolean); for tickets also tickets_created.
- Never log the message, the answer, a ticket title, an email address, a user id or a password.
- Remove logger.setLevel from the code; the level is set in the template.
Tests in each handler's test file: the fields and values, the token sums, the outcomes, an
unexpected exception, odd usage values, and that none of the private values appears in any log
record.
```

## Check

```bash
pytest -q tests/test_tickets.py tests/test_triage.py tests/test_ask.py tests/test_signin.py
grep -n "def log_request" app/*/handler.py
```
