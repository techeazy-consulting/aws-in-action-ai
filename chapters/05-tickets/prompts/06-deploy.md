# 06 - Deploy, open a ticket, look it up, delete

## Goal

Deploy the stack, open a ticket and look it up through the model, then delete everything.

## Prompt

```text
Update the README sections Deploy, Try it and Delete for chapter 5 with AWS CLI and curl commands.

- Deploy the stack helpdesk-dev-ch5 from template.yaml with the IAM capability, the parameters
  Project=helpdesk and Environment=dev, and read the outputs
  SiteBucketName and ChatUrl into BUCKET and SITE. Copy app/web/index.html and app/policies to
  the bucket as in chapter 4, and run the knowledge base sync only if you want /ask to answer.
- Try it: POST to $SITE/tickets a message that opens a ticket, then a message that asks for its
  status, then a message that leaves out the name of the person. Say what each should do.
- Show how to read the tickets table with the aws dynamodb scan command, and say that this scan
  is for looking around in a small demo table, not for the function.
- Delete: empty the bucket first, then delete the stack and wait until it is gone.
Remind me that the live steps cost money and that I must delete the stack when I am done.
```

## Check

```bash
grep -n "/tickets" README.md
grep -n "delete-stack" README.md
# Costs money: needs an AWS account and the stack deployed.
curl -s -X POST "$SITE/tickets" -H "content-type: application/json" -d '{"message": "Please request Figma access for me. My name is Priya."}'
```
