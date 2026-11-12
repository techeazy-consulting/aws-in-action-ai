# 03 - Run the tool the model asks for

## Goal

Write the two tools and the handler that sends the tool result back to the model, handling a failing tool and a missing detail without crashing.

## Prompt

```text
Finish app/tickets/handler.py.

- A ToolError exception for problems the model can explain to the person.
- create_ticket(args): title and requester must be non-blank strings (cut to 200 and 100
  characters), otherwise raise ToolError "Missing detail: <name>. Ask the person for it." Count
  tickets with one UpdateItem on the item whose TicketId is "counter": UpdateExpression
  "ADD LastNumber :one", ReturnValues UPDATED_NEW. The ticket id is 1000 plus that number, as a
  string, so the first ticket is 1001. Save the ticket with PutItem (TicketId, Title, Requester,
  Status "open") and ConditionExpression attribute_not_exists(TicketId). Return the id and status.
- get_ticket_status(args): the id must match ^[0-9]{4,9}$ (so the counter item can never be read),
  otherwise ToolError. Use GetItem with ConsistentRead. No Item in the response means ToolError
  "There is no ticket <id>." Return id, title and status.
- run_tool(tool_use) returns {"toolResult": {...}} and never raises: a ToolError becomes a text
  content block with status "error"; any other exception is logged and becomes a text block
  "The ticket system is unavailable right now." with status "error"; success is a json content
  block. Keep the toolUseId of the request. An unknown tool name is a ToolError.
- handler(event, context): read "message" from the JSON body (400 if missing, not a string, blank
  or over 1000 characters). Call bedrock.converse with modelId, messages, system, toolConfig and
  inferenceConfig (maxTokens 400, temperature 0.2). If stopReason is "tool_use", append the model's
  message, run every toolUse block, append ONE user message holding all the toolResult blocks,
  and call again. Stop after 3 model calls and return 502. If stopReason is anything else, return
  200 {"answer": <the text>, "tools_used": [<names>]}. If the model call fails, log it and return
  502 with a safe message.
```

## Check

```bash
python -c "import ast, pathlib; ast.parse(pathlib.Path('app/tickets/handler.py').read_text())"
grep -n "toolResult" app/tickets/handler.py
grep -n "attribute_not_exists" app/tickets/handler.py
grep -n "tool_use" app/tickets/handler.py
```
