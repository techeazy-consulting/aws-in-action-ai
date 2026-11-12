# 06 - Deploy, confirm the email, try the cases, delete

## Goal

Deploy the stack with your own email address, confirm the subscription, try the easy case, the outage case and the hand-over, then delete everything.

## Prompt

```text
Update the README sections Deploy, Confirm the email, Try it and Delete for chapter 6 with AWS CLI
and curl commands.

- Deploy the stack helpdesk-dev-ch6 from template.yaml with the IAM capability and parameter
  overrides Project=helpdesk, Environment=dev and EscalationEmail=<your-email-address> (a placeholder, never a real address in the
  file). Read the outputs SiteBucketName and ChatUrl into BUCKET and SITE.
- Confirm the email: AWS sends a confirmation message to that address; the subscription gets no
  escalations until its link is chosen. Show how to list the topic's subscriptions and tell
  "pending confirmation" from a confirmed one.
- Try it: POST to $SITE/triage (1) a password problem with email up, which should end in the
  password reset page and no email; (2) a VPN problem, where the status says down, which should
  escalate and send one email; (3) say how to see the step cap by reading the function logs.
- Say plainly that the endpoint is public until sign-in in chapter 7, throttled, and to be
  deleted after testing.
- Delete: empty the bucket first, then delete the stack and wait until it is gone.
Remind me that the live steps cost money.
```

## Check

```bash
grep -n "/triage" README.md
grep -n "list-subscriptions-by-topic" README.md
grep -n "delete-stack" README.md
# Costs money: needs an AWS account, the stack deployed and the subscription confirmed.
curl -s -X POST "$SITE/triage" -H "content-type: application/json" -d '{"message": "My VPN will not connect."}'
```
