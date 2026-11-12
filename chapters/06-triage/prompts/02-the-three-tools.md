# 02 - The three tools

## Goal

Describe and write the three tools the agent can use: check a service, try a known fix, escalate.

## Prompt

```text
Create app/triage/handler.py with the tools only, no loop yet. Standard library and boto3.

- Clients: "bedrock-runtime" named `bedrock` and "sns" named `sns`. Read ESCALATION_TOPIC_ARN and
  MODEL_ID from the environment, and SERVICE_STATUS (JSON text) with a default of "{}".
- A SYSTEM prompt: check the service first; if it is down say so and escalate; otherwise try a
  known fix; if there is none or it did not work, escalate with a short summary; never escalate
  before checking; finish by saying in one or two sentences whether it is fixed or handed over.
- A TOOL_CONFIG for the Converse API with three toolSpec tools, each with an object schema:
  check_service_status (service, required), try_known_fix (issue, one of password, vpn, laptop),
  escalate (summary, required).
- A ToolError exception and a State class holding the request text, the list of tool names used
  and how many escalation emails were sent.
- check_service_status reads the SERVICE_STATUS JSON; an unknown service or unreadable JSON is a
  ToolError. try_known_fix returns the page to send the person to (the chapter 4 policy pages:
  policies/password-reset.html, policies/vpn-access.html, policies/new-laptop.html); anything else
  is a ToolError "There is no known fix for that. Escalate."
- escalate publishes to the topic with sns.publish: TopicArn from the environment, Subject
  "Helpdesk escalation", Message holding the summary (cut to 500 characters) and the person's
  request (cut to 1000). The model chooses nothing but the summary.
- run_tool(tool_use, state) always returns a {"toolResult": {...}} block and never raises: a
  ToolError is a text block with status "error"; any other exception is logged and becomes a
  generic text block with status "error"; success is a json block.
```

## Check

```bash
python -c "import ast, pathlib; ast.parse(pathlib.Path('app/triage/handler.py').read_text())"
grep -n "check_service_status\|try_known_fix\|escalate" app/triage/handler.py
grep -n "sns.publish" app/triage/handler.py
```
