# 05 - The triage function and its address

## Goal

Deploy the loop as its own function behind POST /triage, reachable through the same CloudFront address, allowed to publish to the escalation topic and nothing else.

## Prompt

```text
Extend template.yaml.

- TriageFunctionLogGroup (short log retention, as the others) and TriageFunctionRole. The role
  may write its own log group, call bedrock:InvokeModel on the model route chosen by
  ModelId and ModelRoute (as in the ask role), and sns:Publish on EscalationTopic only. Nothing broader.
- TriageFunction: python3.13, handler index.handler, timeout 30, memory 256, environment
  ESCALATION_TOPIC_ARN (the topic), MODEL_ID (the id the route gives) and SERVICE_STATUS (the parameter), the log
  group above, and the code of app/triage/handler.py inline as ZipFile, byte for byte.
- An API integration, a route "POST /triage" on the existing HTTP API, and a Lambda permission
  that lets only that route invoke the function. Keep the stage throttle.
- A CloudFront cache behavior for path /triage, copied from the /ask one.
- Output TriageUrl. Add TriageFunction: app/triage/handler.py under inline: in code-lab.yaml.
Name it ${Project}-${Environment}-triage and tag everything that supports tags with chapter:
session-06, project and environment.

Then create tests/test_triage_stack.py, which only reads the template (skip if it is not beside
the folder): the topic and the email subscription; the address is a parameter with no default and
no email address appears anywhere in the file; the function may only publish to the topic; the
environment variables; the status list default is JSON; the /triage route and CloudFront path;
and that the chapter 5 resources are still there.
```

## Check

```bash
cfn-lint template.yaml
pytest -q tests/test_triage_stack.py
grep -n "POST /triage" template.yaml
```
