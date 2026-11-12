# Chapter 4: answers from the IT policy pages

Everything from chapter 3 is still here: the private bucket, the CloudFront address that serves
the chat page and routes `/ask` to the API, and the throttled endpoint. This chapter changes where
the answers come from. Instead of the model's general knowledge, `/ask` now looks the question up
in the company's IT policy pages and answers from what it finds, naming the pages it used.

## Before you try

The offline checks below need no AWS account. The live steps need the setup in this table. Console
routes here are written `Service → page → button`; the full numbered steps are in `SETUP.md` at
the top of the course repository. The setup and the live steps can be done from the console plus
CloudShell.

| What you need | Where in the console | `SETUP.md` section |
|---|---|---|
| A user that is not the root user | Sign in with an administrative or IAM user, not the root user | `## 1. Sign in with a user that is not the root user` |
| A Region offering Amazon Bedrock and S3 Vectors | Region menu in the top bar | `## 2. Pick a Region` |
| A budget alert | Billing and Cost Management → Budgets | `## 3. Set a budget alert` |
| The models available to your account | Amazon Bedrock → Model catalog | `## 4. Make sure the model is available to your account` |
| A terminal | CloudShell icon in the top bar | `## 5. Open CloudShell` |
| The code in CloudShell | CloudShell → Actions → Upload file | `## 6. Put the code in CloudShell` |
| Deploy the stack | CloudFormation → Stacks → Create stack | `## 7. Deploy a chapter from the CloudFormation console` |
| Delete the stack | CloudFormation → Stacks → Delete | `## 8. Delete a chapter's stack and confirm it is gone` |

**Not the root user.** Do the live steps as an IAM or IAM Identity Center user. In one run of this
course, the sync step done as the root user stopped with `AccessDeniedException ... :root is not
authorized to perform: bedrock:StartIngestionJob`. `SETUP.md` section 1 explains how to sign in as
a user, and lists the services this chapter's stack needs permission for.

**Values from the Outputs tab.** Later steps use `BUCKET`, `SITE`, `KB` and `DS`. In the console you
copy each one from `CloudFormation → Stacks → your stack → Outputs` (`SiteBucketName`, `ChatUrl`,
`KnowledgeBaseId`, `DataSourceId`); in CloudShell the commands below read them for you. See `SETUP.md`
section 9.

This chapter adds four things to check or do:

- **A Region with both services.** The knowledge base stores its vectors in S3 Vectors, so pick a
  Region where Amazon Bedrock and S3 Vectors are both offered. Check the Region against the list
  of S3 Vectors Regions in the AWS documentation before you deploy.
- **The embedding model.** Ingesting the pages uses Amazon Titan Text Embeddings V2. Open Amazon
  Bedrock → Model catalog, find it, and confirm it is offered in your Region and works in your
  account. The answer model (`ModelId`, Amazon Nova Lite by default) needs the same check.
- **Uploading the pages.** Put the chat page and the policy pages in the bucket from the S3
  console: S3 → Buckets → your bucket (its name is in the stack's Outputs tab) → Upload → Add file
  or Add folder → Upload.
- **Syncing.** Uploading does not make a page searchable. Start the sync from Amazon Bedrock →
  Knowledge base → your knowledge base → Data source → Sync, and again after any page changes.

If a model is refused with an access error, some models need extra account-level access that
activation alone does not give; try another model id as the `ModelId` parameter.

## What changed since chapter 3

- `app/policies/` - three short IT policy pages (password reset, VPN access, new laptop). Replace
  them with your own pages and run the sync step again.
- `app/ask/handler.py` - the function now makes one retrieve-and-generate call to a knowledge base
  instead of a plain model call. It returns `{"answer": "...", "sources": [{"page": "...",
  "excerpt": "..."}]}`. Only pages from the `policies/` folder are ever returned as sources.
- `app/web/index.html` - the chat page lists the sources under each answer and shows the first
  cited page beside the chat. Choose another source to switch pages.
- `tests/test_ask.py` - rewritten for the new handler, with the knowledge base call faked.
  `tests/test_policy_panel.py` and `tests/test_knowledge_base.py` cover the policy pages, the
  page panel and the new template parts. Chapter 3's `tests/test_web.py` is unchanged and still
  passes. No test needs an AWS account.
- `template.yaml` - the chapter 3 stack plus a vector bucket and index, a knowledge base that
  reads the `policies/` folder of the site bucket, its service role, and permission for the
  function to query it. The policy pages live in the same private bucket as the chat page, so
  CloudFront can serve the cited page from the same address.
- `prompts/` - one prompt per build step, in order, each with a check. `prompts/CHECK.md` holds
  the checks for the whole chapter.

## The vector store

The knowledge base stores its vectors in Amazon S3 Vectors. It has no instance to size, and its
price list shows no standing charge: you pay for the storage and the queries you use, so with a
few small pages the standing cost is close to nothing. It is best suited to infrequent queries, which fits a helpdesk
demo. Use a Region where Amazon Bedrock and S3 Vectors are both offered.

The retrieve-and-generate call uses the model in the `ModelId` parameter (Amazon Nova Lite by
default). If your Region or account cannot use it for knowledge base answers, pass another model
id that can.

Most Regions serve that model only through an inference profile, a model id with a geography in
front such as `apac.amazon.nova-lite-v1:0`. The template's `ModelRoute` parameter, `auto` by
default, picks the right one for your Region, and the stack's `ModelInUse` output shows which id
it chose. The function gives the knowledge base call the profile's full address (its ARN) when
the route is a profile, and the model's address when it is not. A profile may send the call to
another Region in its geography, so the data can leave your Region. To change the model, update the
stack and pick another `ModelId` from the list; editing the function's `MODEL_ARN` by hand fails,
because the role only allows the model the stack chose. The embedding model is not part of this
route: it stays `amazon.titan-embed-text-v2:0` in your own Region.

`Project` and `Environment` start every resource name (`helpdesk-dev-ask`,
`helpdesk-dev-policies`), so one template deploys once per environment: give each copy its own
stack name and its own `Environment`.

## Run the tests

```bash
pip install -r ../../requirements-dev.txt
pytest -q
cfn-lint template.yaml
```

## Deploy

The live steps create real resources in your account and cost money. Ingesting the pages calls an
embedding model, and every question calls a generation model.

```bash
aws cloudformation deploy --stack-name helpdesk-dev-ch4 --template-file template.yaml --capabilities CAPABILITY_IAM --parameter-overrides Project=helpdesk Environment=dev
BUCKET=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch4 --query "Stacks[0].Outputs[?OutputKey=='SiteBucketName'].OutputValue" --output text)
SITE=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch4 --query "Stacks[0].Outputs[?OutputKey=='ChatUrl'].OutputValue" --output text)
KB=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch4 --query "Stacks[0].Outputs[?OutputKey=='KnowledgeBaseId'].OutputValue" --output text)
DS=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch4 --query "Stacks[0].Outputs[?OutputKey=='DataSourceId'].OutputValue" --output text)
aws s3 cp app/web/index.html "s3://$BUCKET/index.html" --content-type text/html
aws s3 cp app/policies "s3://$BUCKET/policies" --recursive --content-type text/html
```

**Console route.**

1. CloudFormation → Stacks → Create stack → With new resources (standard) → Upload a template
   file, and choose `template.yaml`. Name the stack `helpdesk-dev-ch4`, leave `Project` as `helpdesk` and
   `Environment` as `dev` on the stack details page, tick the box that says the template may create IAM resources, and
   choose Submit.
2. When the stack is complete, open its Outputs tab and note `SiteBucketName`, `ChatUrl`,
   `KnowledgeBaseId` and `DataSourceId`.
3. S3 → Buckets → the `SiteBucketName` bucket → Upload → Add file, choose `app/web/index.html`.
   Under Properties → Add metadata, choose System defined, `Content-Type`, and `text/html`. Upload.
4. In the same bucket, Upload → Add folder, choose `app/policies` (the keys then start with
   `policies/`), set the same `Content-Type` metadata, and upload.

## Sync the pages into the knowledge base

Uploading a page does not make it searchable. Start an ingestion job, and run it again whenever a
page is added, changed or removed.

Before you sync, check that two things are true. The stack is deployed and complete, so its Outputs
tab shows `KnowledgeBaseId` and `DataSourceId`. And the chat page and the policy pages are uploaded,
with the pages under `policies/` in the bucket: the data source in this template reads that folder. Run the
commands as a user that is not the root user (`SETUP.md` section 1). `KB` and `DS` are set in the
Deploy block above; in a new CloudShell session, read them again with the two `describe-stacks`
lines there.

```bash
JOB=$(aws bedrock-agent start-ingestion-job --knowledge-base-id "$KB" --data-source-id "$DS" --query "ingestionJob.ingestionJobId" --output text)
aws bedrock-agent get-ingestion-job --knowledge-base-id "$KB" --data-source-id "$DS" --ingestion-job-id "$JOB" --query "ingestionJob.status" --output text
```

Repeat the second command until it prints `COMPLETE`. Even then, a short wait may be needed before
new vectors are returned.

**Console route.** Amazon Bedrock → Knowledge base → your knowledge base → Data source section → Sync.
A green banner appears when the sync succeeds, and the data
source's Sync history lists each run (View warnings shows why a run failed).

## Try it

Open the address in `$SITE`, ask "How do I reset my password?", and check that the password reset
page appears beside the answer. From a terminal:

```bash
curl -s -X POST "$SITE/ask" -H "content-type: application/json" -d '{"question": "How do I reset my password?"}'
```

The reply holds the answer and a `sources` list. A question the pages cannot answer comes back
with no sources. A question may be at most 1000 characters. The API is still open to anyone who
has its address until sign-in is added in chapter 7, so the stage throttle stays.

## Delete

Empty the bucket first: a stack cannot delete a bucket that still holds files. Once the bucket is
empty, deleting the stack removes every resource it made, including the knowledge base, its
vectors, the vector index and the vector bucket: nothing in this template is kept.

```bash
aws s3 rm "s3://$BUCKET" --recursive
aws cloudformation delete-stack --stack-name helpdesk-dev-ch4
aws cloudformation wait stack-delete-complete --stack-name helpdesk-dev-ch4
```

**Console route.**

1. S3 → General purpose buckets → select the site bucket → Empty, type the bucket name, and choose
   Empty. Emptying cannot be undone.
2. CloudFormation → Stacks → select `helpdesk-dev-ch4` → Delete → confirm Delete.
3. Wait for the status to leave `DELETE_IN_PROGRESS`. Deleted stacks are hidden from the list by
   default; set the Filter status to Deleted to see it.
