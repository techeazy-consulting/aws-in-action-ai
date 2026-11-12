# 05 - The tickets function and its address

## Goal

Deploy the handler as its own function behind POST /tickets, reachable through the same CloudFront address.

## Prompt

```text
Extend template.yaml.

- TicketsFunctionLogGroup (short log retention, as the others) and TicketsFunctionRole. The role may write its own log
  group, call bedrock:InvokeModel on the model route chosen by ModelId and ModelRoute (as in the ask role), and
  dynamodb:GetItem, PutItem and UpdateItem on TicketsTable only. Nothing broader.
- TicketsFunction: python3.13, handler index.handler, timeout 30, memory 256, environment
  TICKETS_TABLE (the table) and MODEL_ID (the id the route gives), the log group above, and the
  code of app/tickets/handler.py inline as ZipFile, byte for byte.
- An API integration, a route "POST /tickets" on the existing HTTP API, and a Lambda permission
  that lets only that route invoke the function. Keep the existing stage throttle.
- A CloudFront cache behavior for path /tickets, copied from the /ask one: the API origin, HTTPS
  only, all methods, caching disabled, the same origin request policy.
- Output TicketsUrl. Add TicketsFunction: app/tickets/handler.py under inline: in code-lab.yaml.
Name it ${Project}-${Environment}-tickets and tag everything that supports tags with chapter:
session-05, project and environment.

Then create tests/test_tickets_stack.py, which only reads the template (skip if it is not beside
the folder): the table, its billing mode and key; the function may only get, put and update items
in that table; the environment variables; the /tickets route and CloudFront path; and that the
chapter 4 resources are still there.
```

## Check

```bash
cfn-lint template.yaml
pytest -q tests/test_tickets_stack.py
grep -n "POST /tickets" template.yaml
```
