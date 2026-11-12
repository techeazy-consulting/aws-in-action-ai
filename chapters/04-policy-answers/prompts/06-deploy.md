# 06 - Deploy, sync, ask, delete

## Goal

Deploy the stack, upload and sync the policy pages, ask a question and see the cited page, then delete everything.

## Prompt

```text
Update the README sections Deploy, Sync the pages into the knowledge base, Try it and Delete for
chapter 4 with AWS CLI commands.

- Deploy the stack helpdesk-dev-ch4 from template.yaml with the IAM capability and the parameters
  Project=helpdesk and Environment=dev, read the outputs
  SiteBucketName, ChatUrl, KnowledgeBaseId and DataSourceId into BUCKET, SITE, KB and DS, copy
  app/web/index.html to the bucket, and copy app/policies to the policies/ folder with content type
  text/html.
- Sync: start an ingestion job with the bedrock-agent service for KB and DS, keep its job id, and
  poll the job status until it is COMPLETE. Say the sync must be run again after any page change.
- Try it: open the ChatUrl address, ask how to reset a password, and check that the password reset
  page appears beside the answer; show the same request with curl to $SITE/ask.
- Delete: empty the bucket first, then delete the stack and wait until it is gone.
Remind me that the live steps cost money and that I must delete the stack when I am done.
```

## Check

```bash
grep -n "start-ingestion-job" README.md
grep -n "get-ingestion-job" README.md
grep -n "delete-stack" README.md
# Costs money: needs an AWS account and the stack deployed and synced.
curl -s -X POST "$SITE/ask" -H "content-type: application/json" -d '{"question": "How do I reset my password?"}'
```
