# 04 - Tickets that belong to someone, and a staff-only tool

## Goal

Make a ticket belong to the signed-in person, let staff read and close any ticket, and keep the close tool away from employees.

## Prompt

```text
Change app/tickets/handler.py. Every tool now receives the caller as a second argument.

- create_ticket takes only "title". The owner is the caller's sub (stored as OwnerId and as Requester) and a
  RequesterEmail is stored only when the email is verified. The model is never asked who is asking, and a name it
  invents is ignored.
- get_ticket_status: an employee reads only a ticket whose OwnerId is their own sub; someone
  else's ticket, and a ticket with no owner, gets exactly the same error as a ticket that does
  not exist. Staff read any ticket and also see the requester.
- close_ticket (new, staff only): takes ticket_id, checked like the others; sets Status to
  "closed" and records the closer's sub, with a condition that the ticket exists (so the counter
  item can never be closed); a failed condition is "There is no ticket N.".
- tool_config(caller) offers close_ticket to staff only, and close_ticket itself refuses anyone
  else, so a prompt cannot add it.
Tests: both roles, own and other people's tickets, a ticket with no owner, a close by staff, a
close attempted by an employee (the table must not be touched), a missing ticket, a database
failure, and ticket ids that are not numbers.
```

## Check

```bash
pytest -q tests/test_tickets.py
grep -n "close_ticket\|OwnerId" app/tickets/handler.py
```
