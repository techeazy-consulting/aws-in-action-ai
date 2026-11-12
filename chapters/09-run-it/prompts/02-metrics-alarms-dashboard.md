# 02 - Metrics from the logs, two alarms and a dashboard

## Goal

Turn the log lines into metrics, alarm on errors through the existing topic, and draw a dashboard.

## Prompt

```text
Extend template.yaml (replace session-08 with session-09 everywhere).

- On all four functions set LoggingConfig LogFormat JSON and ApplicationLogLevel INFO.
- Metric filters (one metric per filter), namespace Helpdesk/${Environment}: Errors for every
  function (pattern: event is request and outcome is error); for tickets and triage ModelRequests,
  InputTokens and OutputTokens (pattern: event is request and model_calls above 0, values 1,
  $.input_tokens, $.output_tokens); for tickets TicketsCreated (value $.tickets_created).
- Alarms: ${Project}-${Environment}-errors on Helpdesk/${Environment} Errors, and ${Project}-${Environment}-api-5xx on the API's 5xx
  metric by ApiId. Sum over 300 seconds, threshold 1, missing data not breaching, both
  AlarmActions the existing EscalationTopic. Tag both.
- A dashboard named ${Project}-${Environment}-helpdesk with: a text widget stating the cost-per-ticket formula and
  that no price is written; API Count and 5xx; the Errors metric with the errors alarm line;
  tokens per request as input and output sums divided by ModelRequests; tokens per model call from
  AWS/Bedrock InputTokenCount, OutputTokenCount and Invocations for the id the functions call (the inference profile id when a profile is used, ModelId when the model is called directly); tickets created.
- Outputs DashboardName and ErrorsAlarmName.
Add tests/test_observability_stack.py: JSON logs, the filters and their names, the alarms, the
dashboard body parsed as JSON with every custom metric one a filter writes, and no voice resource.
```

## Check

```bash
cfn-lint template.yaml
pytest -q tests/test_observability_stack.py
grep -n "AlarmActions" template.yaml
```
