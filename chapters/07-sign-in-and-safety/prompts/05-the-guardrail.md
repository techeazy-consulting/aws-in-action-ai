# 05 - The guardrail on every model call

## Goal

Create a guardrail that masks passwords and keys and denies off-topic requests, publish a version, and send every model call through it.

## Prompt

```text
Extend template.yaml and the three handlers.

- HelpdeskGuardrail (AWS::Bedrock::Guardrail): blocked-message texts for input and output; the
  sensitive information policy masks (ANONYMIZE) PASSWORD, AWS_ACCESS_KEY and AWS_SECRET_KEY plus
  a regex for the first line of a private key, each enabled on both input and output; the topic
  policy has one DENY topic for requests that are not about workplace IT, with three example
  phrases, set to BLOCK on input and output. Named ${Project}-${Environment}-guardrail; tagged
  with chapter, project and environment.
- HelpdeskGuardrailVersion publishes a version; the functions use it, never DRAFT.
- Each of the three roles keeps its bedrock:InvokeModel permission on the model route chosen by
  ModelId and ModelRoute (chapter 6) and may also bedrock:ApplyGuardrail on that one guardrail's ARN. Each function
  gets GUARDRAIL_ID and GUARDRAIL_VERSION and fails to start without them.
- Tickets and triage pass guardrailConfig (identifier and version) on every Converse call. When
  stopReason is "guardrail_intervened", return 200 with the guardrail's message (checked to be
  text and cut to 500 characters) and "blocked": true; run no tool and send no email.
- Ask passes guardrailConfiguration inside generationConfiguration; when the response says
  guardrailAction is INTERVENED, return the text with sources [] and "blocked": true.
Tests: the guardrail on every call, a masked secret (a fake model that masks only when a guardrail
is named), a blocked topic, a malformed blocked reply, and the template.
```

## Check

```bash
cfn-lint template.yaml
pytest -q tests/test_tickets.py tests/test_triage.py tests/test_ask.py tests/test_auth_stack.py
grep -n "guardrailConfig" app/tickets/handler.py app/triage/handler.py
```
