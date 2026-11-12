# 06 - Secrets the guardrail does not read

## Goal

Remove pasted secrets from the places the guardrail never looks: tool arguments, escalation emails and cited excerpts.

## Prompt

```text
Add scrub(text) to the ask, tickets and triage handlers: normalise the text (NFKC), then replace a
private key block, an access key id (AKIA or ASIA plus 16 capitals or digits), a word such as
password, secret, token or api key followed by is, = or : and a value, and any 40 character run of
letters, digits and / + = that mixes capitals, lower case and digits, each with a marker.
- tickets: scrub the title before it is saved.
- triage: scrub the model's summary and the person's request before they go in the email, then
  break links as before; start the email with the signed-in address from the token (also broken
  so it is not a link), or say there is none.
- ask: scrub each excerpt before it is returned.
Add tests/test_policy_secrets.py, which fails when a policy page looks like it holds a secret.
Tests: each pattern, ordinary text left alone, and one test per handler showing the secret is gone.
```

## Check

```bash
pytest -q tests/test_tickets.py tests/test_triage.py tests/test_ask.py tests/test_policy_secrets.py
grep -n "def scrub" app/ask/handler.py app/tickets/handler.py app/triage/handler.py
```
