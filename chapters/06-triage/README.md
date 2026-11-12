# Chapter 6: a triage agent that checks, fixes and escalates

Everything from chapter 5 is still here: `/ask`, `/tickets`, the table and the chat page. This
chapter adds a third endpoint, `/triage`, where the model works through a problem in steps. It
checks whether a service is down, tries a known fix, and if neither settles it, emails the IT team.

The loop is written by hand. Each round the function asks the model what to do next with the
Converse API, runs the tool the model asks for, and sends the result back, until the model gives
an answer. No managed agent service is used, and no new service beyond an SNS topic.

## Before you try

The offline checks below need no AWS account. The live steps need the setup in this table. Console
routes here are written `Service → page → button`; the full numbered steps are in `SETUP.md` at the
top of the course repository. The setup and the live steps can be done from the console plus
CloudShell.

| What you need | Where in the console | `SETUP.md` section |
|---|---|---|
| A user that is not the root user (as the root user a Bedrock step stops with `AccessDeniedException ... :root is not authorized`) | The top bar shows a user name, not just the account | `## 1. Sign in with a user that is not the root user` |
| A Region offering Amazon Bedrock and S3 Vectors | Region menu in the top bar | `## 2. Pick a Region` |
| A budget alert | Billing and Cost Management → Budgets | `## 3. Set a budget alert` |
| The models available to your account: Amazon Nova Lite (it supports tool use) and Amazon Titan Text Embeddings V2 | Amazon Bedrock → Model catalog | `## 4. Make sure the model is available to your account` |
| A terminal | CloudShell icon in the top bar | `## 5. Open CloudShell` |
| The code on your computer and in CloudShell | CloudShell → Actions → Upload file | `## 6. Put the code in CloudShell` |
| An email address you can read | Not a console page: you type it into the `EscalationEmail` box | `## 7. Deploy a chapter from the CloudFormation console` |
| Deploy the stack | CloudFormation → Stacks → Create stack | `## 7. Deploy a chapter from the CloudFormation console` |
| Copy a value from the Outputs tab | CloudFormation → Stacks → your stack → Outputs | `## 9. Copy a value from the Outputs tab` |
| Delete the stack | CloudFormation → Stacks → Delete | `## 8. Delete a chapter's stack and confirm it is gone` |

This chapter adds three things to do:

- **Give an address you can read.** `EscalationEmail` has no default. AWS sends a message to it
  after the stack is created, and you confirm it (see `## Confirm the email`).
- **Upload the chat page and the policy pages** (see `## Deploy`). The `/triage` route works
  without them; the chat page and `/ask` need them.
- **Sync the knowledge base when you want `/ask` to answer.** Uploading does not make a page searchable. Start
  the sync from Amazon Bedrock → Knowledge base → your knowledge base → Data source → Sync, as in
  chapter 4. `/triage` does not need it.

## Public until sign-in

`/triage` has no sign-in. Anyone who has the address can run it, each message is billed to your
account, and a message can cause an email to your inbox. Sign-in arrives in chapter 7. Until then:
keep the stage throttle in the template, do not put real names or real problems in a test
message, and delete the stack as soon as you have finished testing. The code limits what one
request can do: a request makes at most 6 model calls, sends at most 1 escalation email whatever
the model asks for, can only publish to the one topic named in the environment, and chooses
nothing in the email but a short summary. The email opens with an UNVERIFIED line, and every
link, bare domain or address in the chat text or the summary arrives broken (`evil[.]example`,
`https[:]//`), look-alike characters included, so a message cannot plant a clickable link that
seems to come from the helpdesk.

## What changed since chapter 5

- `app/triage/handler.py` - the new function with three tools:
  `check_service_status` reads a status list that the template sets (the `ServiceStatus`
  parameter, JSON such as `{"vpn": "down"}`); `try_known_fix` points to one of the chapter 4
  policy pages; `escalate` publishes to an SNS topic that emails the IT team.
- **Step cap.** The loop makes at most `MAX_STEPS` model calls.
- **Hand-over rule, in code.** If the loop ends without an answer, the model stops asking for
  tools without asking for any, or the model call fails after work started, the code itself
  sends one escalation email and returns `escalated: true` with a `reason`. If that email also
  fails, the reply is an error, not a promise that someone was told.
- `tests/test_triage.py` and `tests/test_triage_stack.py` - an easy case (fixed with no email),
  a hard case (escalated), the step cap, and the limits above. The model and the topic are
  faked, so no test needs an AWS account. The chapter 5 tests are unchanged and pass, except that
  `tests/test_web.py` now counts one redirect rule per path instead of a fixed number.
- `template.yaml` - the chapter 5 stack plus the escalation topic, an email subscription, the
  triage function (allowed to publish to that one topic) and a `POST /triage` route with its
  CloudFront path.
- `prompts/` - one prompt per build step, in order, each with a check. `prompts/CHECK.md` holds
  the checks for the whole chapter.

## The email address

The address that receives escalations is the `EscalationEmail` parameter. It has no default and no
address is written in any file; you pass your own when you deploy. An email subscription does not
deliver anything until its owner confirms it: AWS sends a confirmation message, and you must choose
its link. Until then the subscription shows `PendingConfirmation` in place of its ARN, and
escalation emails are not delivered.

## Models

The functions call the model in the `ModelId` parameter (Amazon Nova Lite by default, which lists
client-side tool calling as supported; the list also offers Nova Micro). Keep to the list: a model
without tool use with the Converse API fails the request.

Most Regions serve the model only through an inference profile, a model id with a geography in
front such as `apac.amazon.nova-lite-v1:0`; the template's `ModelRoute` parameter, `auto` by
default, picks the right one for your Region, and the stack's `ModelInUse` output shows which id
it chose. The `/ask` function sends the matching profile ARN to the knowledge base, so one
setting reaches the functions that call the model. To change the model, update the stack and
pick another `ModelId` from the list; editing a function's `MODEL_ID` or `MODEL_ARN` by hand
fails, because the role only allows the model the stack chose.

`Project` and `Environment` start every resource name (`helpdesk-dev-ask`), so one template
deploys once per environment: give each copy its own stack name and its own `Environment`.

## Run the tests

```bash
pip install -r ../../requirements-dev.txt
pytest -q
cfn-lint template.yaml
```

## Deploy

The live steps create real resources in your account and cost money: every message calls the
model, usually several times.

**Console route.** CloudFormation → Stacks → Create stack → With new resources (standard) →
Upload a template file → choose `template.yaml` from your computer → Next. Type the stack name
`helpdesk-dev-ch6` and your address in `EscalationEmail`; leave the other boxes as they are. Tick
the IAM acknowledgement box, then Submit, and open the Events tab until the stack finishes
creating. Copy `SiteBucketName`, `ChatUrl` and `EscalationTopicArn` from the stack's Outputs tab
(`SETUP.md` section 9). Then upload the two files the commands below upload: S3 → Buckets → your
bucket → Upload → Add file `app/web/index.html`, and under Properties → Add metadata choose the
system-defined key Content-Type with the value `text/html`, then Upload. Upload again with Add
folder `app/policies`, with the same Content-Type. The commands below do the same from CloudShell.

```bash
aws cloudformation deploy --stack-name helpdesk-dev-ch6 --template-file template.yaml --capabilities CAPABILITY_IAM --parameter-overrides EscalationEmail=<your-email-address> Project=helpdesk Environment=dev
BUCKET=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch6 --query "Stacks[0].Outputs[?OutputKey=='SiteBucketName'].OutputValue" --output text)
SITE=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch6 --query "Stacks[0].Outputs[?OutputKey=='ChatUrl'].OutputValue" --output text)
TOPIC=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch6 --query "Stacks[0].Outputs[?OutputKey=='EscalationTopicArn'].OutputValue" --output text)
aws s3 cp app/web/index.html "s3://$BUCKET/index.html" --content-type text/html
aws s3 cp app/policies "s3://$BUCKET/policies" --recursive --content-type text/html
```

## Confirm the email

Open the message AWS sent to your address and choose the confirmation link. Then check.

**Console route.** Amazon SNS → Subscriptions → the row for your address: its Status shows
Confirmed once you have chosen the link. In CloudShell:

```bash
aws sns list-subscriptions-by-topic --topic-arn "$TOPIC"
```

A confirmed subscription lists a full ARN; an unconfirmed one lists `PendingConfirmation`.

## Try it

**Console route.** A POST call has no console button, so send the two messages from
CloudShell with the commands below.

```bash
curl -s -X POST "$SITE/triage" -H "content-type: application/json" -d '{"message": "I forgot my email password."}'
curl -s -X POST "$SITE/triage" -H "content-type: application/json" -d '{"message": "My VPN will not connect."}'
```

The first should check that email is up, point to the password reset page and report
`"escalated": false`; no email arrives. The second finds the VPN marked down in the status list,
escalates, reports `"escalated": true`, and one email arrives. To see a hand-over by the step cap,
read the function logs after a message the model cannot settle. To move the outage, change the
`ServiceStatus` parameter and update the stack. A message may be at most 1000 characters.

## Delete

**Console route.** S3 → Buckets → select your bucket → Empty (type the bucket name to confirm),
then CloudFormation → Stacks → your stack → Delete. To confirm it is gone, use Filter status →
Deleted on the Stacks page (`SETUP.md` section 8). The commands below do the same from CloudShell.

Empty the bucket first: a stack cannot delete a bucket that still holds files. Deleting the stack
removes the functions, the table, the topic and its subscription, and the knowledge base. Deleting
the stack removes every resource it made: nothing in this template is kept.

```bash
aws s3 rm "s3://$BUCKET" --recursive
aws cloudformation delete-stack --stack-name helpdesk-dev-ch6
aws cloudformation wait stack-delete-complete --stack-name helpdesk-dev-ch6
```
