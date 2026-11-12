# 08 - Deploy, create the people, try both roles, delete

## Goal

Deploy the stack, create an employee and a staff member, try the allowed and refused cases, then delete everything.

## Prompt

```text
Update the README sections Create the people, Deploy, Try it and Delete for chapter 7 with AWS CLI
and curl commands.

- Deploy the stack helpdesk-dev-ch7 from template.yaml with the IAM capability,
  EscalationEmail=<your-email-address> (a placeholder, never a real address in the file),
  Project=helpdesk and Environment=dev.
- Create people with admin-create-user (message suppressed, with --user-attributes marking the email address verified), admin-set-user-password (permanent)
  and admin-add-user-to-group, reading the password at a prompt with read -rs so it stays out of
  the shell history. One employee and one member of IT staff.
- Try it: sign in at /signin for a token; ask a question with it; call /ask with no token (refused);
  as an employee ask to close a ticket (refused) and as staff close it; paste a fake password in a
  message (masked, never saved); ask which stock to buy (blocked).
- Delete: empty the bucket first, then delete the stack and wait until it is gone.
Remind me that the live steps cost money.
```

## Check

```bash
grep -n "admin-add-user-to-group" README.md
grep -n "delete-stack" README.md
# Costs money: needs an AWS account and the stack deployed.
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$SITE/ask" -H "content-type: application/json" -d '{"question": "hi"}'
```
