# 02 - Describe the two tools to the model

## Goal

Write the tool descriptions the model reads, so it knows when to ask for a ticket to be created or looked up.

## Prompt

```text
Create app/tickets/handler.py with only the first part, no handler function yet.

- Standard library and boto3 only. Create two boto3 clients, "bedrock-runtime" named `bedrock` and
  "dynamodb" named `dynamodb`. Read TICKETS_TABLE and MODEL_ID from the environment.
- A SYSTEM list with one text block: the model is an IT helpdesk assistant; to open a ticket it
  needs a short title and the name of the person asking; if either is missing it must ask instead
  of guessing; it never invents a ticket number or a status.
- A TOOL_CONFIG dict for the Converse API: a "tools" list with two "toolSpec" entries, each with a
  name, a description and an "inputSchema" holding a "json" object schema.
  create_ticket takes title and requester, both strings, both required.
  get_ticket_status takes ticket_id, a string, required.
```

## Check

```bash
python -c "import ast, pathlib; ast.parse(pathlib.Path('app/tickets/handler.py').read_text())"
grep -n "toolSpec" app/tickets/handler.py
grep -n "inputSchema" app/tickets/handler.py
```
