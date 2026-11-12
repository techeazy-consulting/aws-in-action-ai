# 05 - Deploy, ask, delete

## Goal

Deploy the stack to your own account, ask one question, then delete the stack.

## Prompt

```text
Give me the commands to deploy template.yaml as a stack named helpdesk-dev-ch2 with the AWS CLI
(capabilities for IAM, parameters Project=helpdesk and Environment=dev, no hard-coded account id), read the AskUrl output into a shell variable
API_URL, send one POST with a JSON question, and then delete the stack and wait until it is gone.
Put them in the README under Deploy, Try it and Delete. Remind me that the live steps cost money
and that I must delete the stack when I am done.
```

## Check

```bash
grep -n "cloudformation deploy" README.md
grep -n "cloudformation delete-stack" README.md
# Costs money: needs an AWS account and the stack deployed.
curl -s -X POST "$API_URL" -H "content-type: application/json" -d '{"question": "How do I reset my password?"}'
```
