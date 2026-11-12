# 05 - Deploy, upload the page, ask, delete

## Goal

Deploy the stack, upload the page to the private bucket, ask one question in the browser, then delete everything.

## Prompt

```text
Update the README sections Deploy, Try it and Delete for chapter 3 with AWS CLI commands.

- Deploy the stack helpdesk-dev-ch3 from template.yaml with the IAM capability and the parameters
  Project=helpdesk and Environment=dev, read the outputs
  SiteBucketName and ChatUrl into BUCKET and SITE, and copy app/web/index.html to the bucket as
  index.html with content type text/html.
- Try it: open the ChatUrl address, ask a question, and show the same request with curl to
  $SITE/ask.
- Delete: empty the bucket first (a stack cannot delete a bucket that holds files), then delete the
  stack and wait until it is gone.
Remind me that the live steps cost money and that I must delete the stack when I am done.
```

## Check

```bash
grep -n "cloudformation deploy" README.md
grep -n "s3 cp" README.md
grep -n "delete-stack" README.md
# Costs money: needs an AWS account and the stack deployed.
curl -s -X POST "$SITE/ask" -H "content-type: application/json" -d '{"question": "How do I reset my password?"}'
```
