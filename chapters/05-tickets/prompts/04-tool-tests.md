# 04 - Prove it offline

## Goal

Test the whole tool round trip with a fake model and a fake table, including a failing tool and a request with a missing detail.

## Prompt

```text
Create tests/test_tickets.py. Load app/tickets/handler.py fresh in a fixture with boto3 replaced
by a stub and TICKETS_TABLE and MODEL_ID set. Then replace `bedrock` and `dynamodb` on the module
with fakes: a FakeTable (update_item counts, put_item stores, get_item returns the item or an
empty dict, and a fail switch that raises) and a FakeModel that plays back scripted responses
and records each call. No test may touch AWS.

Cover: both tools are offered with object schemas; a reply that needs no tool; create_ticket round
trip (ticket 1001 saved, the second model call carries a toolResult with the same toolUseId and
no error status); ids count up; get_ticket_status round trip; an unknown ticket and the id
"counter" give an error result and the counter item is never read; each missing detail gives an
error result and creates nothing; a failing table gives an error result with a safe message and
the request still answers 200; an unknown tool name; two tool requests in one turn both get a
result; a model that always asks for a tool stops at the round limit with 502; 400 for a bad
message; 502 when the model call fails.
```

## Check

```bash
pytest -q tests/test_tickets.py
pytest -q
```
