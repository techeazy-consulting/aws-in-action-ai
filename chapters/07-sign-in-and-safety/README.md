# Chapter 7: sign-in, roles and a guardrail

Everything from chapter 6 is still here: `/ask`, `/tickets`, `/triage`, the table, the topic and
the chat page. This chapter closes the front door. People sign in, the code reads who they are
and which group they belong to, and every model call goes through a guardrail that masks pasted
passwords and keys and refuses requests that are not about workplace IT.

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

This chapter adds four things to do, in this order (see `## Deploy`):

- **Confirm the escalation email**, as in chapter 6.
- **Upload the chat page and the policy pages, then sync the knowledge base.** Uploading does not
  make a page searchable. Start the sync from Amazon Bedrock → Knowledge base → your knowledge
  base → Data source → Sync, and again after any page changes.
- **Create the people** (see `## Create the people`): nobody can sign themselves up.
- **Sign in** on the chat page at `ChatUrl` as each person and try both roles.

## What changed since chapter 6

- `app/signin/handler.py` - the one open route, `POST /signin`. It trades an email and password
  for an ID token with Cognito and returns that token only. The password is passed on and dropped:
  it is never logged, stored or sent back, and every refusal gets the same message, so a reply
  never says whether an address has an account.
- `app/ask/handler.py`, `app/tickets/handler.py`, `app/triage/handler.py` - each now starts by
  reading the caller from the claims the API has already checked (`caller()`), and refuses with
  403 unless the token is an ID token, the subject looks like a user id and the caller is in a
  known group (`employee` or `it-staff`). Group names are matched exactly; an unknown name counts
  for nothing.
- `app/tickets/handler.py` - a ticket now belongs to the signed-in person (`OwnerId`, taken from
  the token, never from the model). An employee can read only their own tickets; someone else's
  ticket gets the same answer as one that does not exist. IT staff can read any ticket and can
  close one with the new `close_ticket` tool. The tool is offered only to staff, and the code
  checks the group again when it runs, so a prompt cannot add it. It closes a ticket only when one sentence of the staff member's own message says "close" and
  names its number, and never after a ticket title has been shown to the model in the same
  request (ask again in a new message). A title is handed back to the model marked as text
  another person wrote, so a poisoned title that says "close it" cannot get anything closed. `create_ticket` no longer asks
  the model who is asking.
- Every model call carries the guardrail (`guardrailConfig` on Converse, `guardrailConfiguration`
  on the knowledge base call). When the guardrail blocks a request the reply is `blocked: true`
  with the guardrail's own message, and no tool runs and no email is sent.
- A second line of defence in the code (`scrub()`): the guardrail does not read tool call
  arguments, tool results or the passages a knowledge base retrieves, and this code still holds
  the raw text of each request. So pasted passwords and keys are removed from a ticket title, from
  an escalation email and from a cited excerpt before they are saved, sent or shown. Chapter 6's
  link-breaking on the email is unchanged and runs after it.
- `app/web/index.html` - a sign-in form in front of the chat. The token is kept in a page
  variable only, never in storage, and is dropped on sign-out or when it expires.
- `template.yaml` - the chapter 6 stack plus a Cognito user pool (administrator-created users
  only), an app client with no secret, the two groups, a JWT authorizer on the three model
  routes, the sign-in function and route, the guardrail and a published guardrail version.
- `tests/` - the chapter 6 tests, updated to sign in, plus tests for both roles, the claim
  checks, the sign-in function, a masked secret, a blocked topic and the template.
- `prompts/` - one prompt per build step, in order, each with a check. `prompts/CHECK.md` holds
  the checks for the whole chapter.

## What the guardrail does not cover

The guardrail checks the text the person sends and the text the model writes. It does not check
tool call arguments, tool results, or the passages the knowledge base retrieves and shows beside
an answer. A secret that was written into a policy page would be shown. Keep secrets out of the
policy pages (`tests/test_policy_secrets.py` fails if one looks like it holds one), and treat the
code's `scrub()` as a backstop, not a guarantee.

## The model, the Region and the names

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

## Create the people

Users are added by you, with the user pool id from the stack outputs. Nobody can sign themselves
up. Read the password at a prompt so it does not stay in your shell history.

**Console route.** Amazon Cognito → User pools → your pool (its id is the `UserPoolId` output) →
Users → Create user. Choose Don't send an invitation, enter the email address as the username and
choose Create a password. Then open the user from the Users list: edit User attributes to mark the
email address verified, and use Group memberships to add the user to `employee` or `it-staff`.
A password set this way is temporary, and a user with a temporary password cannot sign in until
a permanent one is set. The console has no step we can point to for that, so run the second
command below in CloudShell for each person. The commands below do the same from CloudShell.

```bash
POOL=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch7 --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" --output text)
read -rs PW
aws cognito-idp admin-create-user --user-pool-id "$POOL" --username <employee-email> --user-attributes Name=email,Value=<employee-email> Name=email_verified,Value=true --message-action SUPPRESS
aws cognito-idp admin-set-user-password --user-pool-id "$POOL" --username <employee-email> --password "$PW" --permanent
aws cognito-idp admin-add-user-to-group --user-pool-id "$POOL" --username <employee-email> --group-name employee
```

Repeat with a second address and `--group-name it-staff` for a member of IT staff.

The address is marked verified here by you, the administrator. The code trusts an email address
only when the token says it is verified; the user id is always the identity (tickets and
escalation emails record it), and the email is shown beside it for people to read. The app client
may not write the email attribute, and a changed address must be verified before it takes effect,
so a signed-in person cannot rename themselves into someone else's address.

## Run the tests

```bash
pip install -r ../../requirements-dev.txt
pytest -q
cfn-lint template.yaml
```

## Deploy

The live steps create real resources in your account and cost money: every message calls the
model, usually several times, and the guardrail is billed for each text it checks.

**Console route.** CloudFormation → Stacks → Create stack → With new resources (standard) →
Upload a template file → choose `template.yaml` from your computer → Next. Type the stack name
`helpdesk-dev-ch7` and your address in `EscalationEmail`; leave `Project`, `Environment`, `ModelId`, `ModelRoute` and `ServiceStatus` as they
are. Tick the IAM acknowledgement box, then Submit, and open the Events tab until the stack
finishes creating. Copy `SiteBucketName`, `ChatUrl` and `UserPoolId` from the Outputs tab
(`SETUP.md` section 9). Upload the two files the commands below upload: S3 → Buckets → your bucket
→ Upload → Add file `app/web/index.html`, and under Properties → Add metadata choose the
system-defined key Content-Type with the value `text/html`, then Upload. Upload again with Add
folder `app/policies`, with the same Content-Type. The commands below do the same from CloudShell.

```bash
aws cloudformation deploy --stack-name helpdesk-dev-ch7 --template-file template.yaml --capabilities CAPABILITY_IAM --parameter-overrides EscalationEmail=<your-email-address> Project=helpdesk Environment=dev
BUCKET=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch7 --query "Stacks[0].Outputs[?OutputKey=='SiteBucketName'].OutputValue" --output text)
SITE=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch7 --query "Stacks[0].Outputs[?OutputKey=='ChatUrl'].OutputValue" --output text)
aws s3 cp app/web/index.html "s3://$BUCKET/index.html" --content-type text/html
aws s3 cp app/policies "s3://$BUCKET/policies" --recursive --content-type text/html
```

Create the people (above), and confirm the escalation email as in chapter 6: open the message AWS
sent to your address and choose Confirm subscription (console check: Amazon SNS → Subscriptions →
the row for your address shows Status Confirmed). Then start the knowledge base sync.

**Console route.** Amazon Bedrock → Knowledge base → your knowledge base → Data source → Sync;
a green banner appears when it succeeds. From CloudShell, with `KB` and `DS` from the Outputs tab
(`KnowledgeBaseId`, `DataSourceId`):

```bash
KB=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch7 --query "Stacks[0].Outputs[?OutputKey=='KnowledgeBaseId'].OutputValue" --output text)
DS=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch7 --query "Stacks[0].Outputs[?OutputKey=='DataSourceId'].OutputValue" --output text)
JOB=$(aws bedrock-agent start-ingestion-job --knowledge-base-id "$KB" --data-source-id "$DS" --query "ingestionJob.ingestionJobId" --output text)
aws bedrock-agent get-ingestion-job --knowledge-base-id "$KB" --data-source-id "$DS" --ingestion-job-id "$JOB" --query "ingestionJob.status" --output text
```

Run the last line again until it reads `COMPLETE`.

## Try it

**Console route.** Open the `ChatUrl` address from the Outputs tab. The chat page has a sign-in
form: sign in as each person and try the same requests as below. The commands below do the same
from CloudShell, and the call with no token has no console button.

```bash
TOKEN=$(curl -s -X POST "$SITE/signin" -H "content-type: application/json" -d '{"email": "<employee-email>", "password": "<password>"}' | python3 -c "import sys, json; print(json.load(sys.stdin)['id_token'])")
curl -s -X POST "$SITE/ask" -H "content-type: application/json" -H "authorization: Bearer $TOKEN" -d '{"question": "How do I reset my password?"}'
curl -s -X POST "$SITE/ask" -H "content-type: application/json" -d '{"question": "No token at all"}'
curl -s -X POST "$SITE/tickets" -H "content-type: application/json" -H "authorization: Bearer $TOKEN" -d '{"message": "Please close ticket 1001."}'
curl -s -X POST "$SITE/tickets" -H "content-type: application/json" -H "authorization: Bearer $TOKEN" -d '{"message": "My VPN fails. My password is hunter2-Xy9."}'
curl -s -X POST "$SITE/tickets" -H "content-type: application/json" -H "authorization: Bearer $TOKEN" -d '{"message": "Which stock should I buy?"}'
```

The first call answers with a cited page. The second is refused before any model is called. As an
employee, the third is refused because closing a ticket is staff only; sign in as IT staff and
the same request closes it. The fourth is answered with the password masked, and the ticket never
holds it. The fifth comes back with `"blocked": true`. Messages are at most 1000 characters.

## Delete

**Console route.** S3 → Buckets → select your bucket → Empty (type the bucket name to confirm),
then CloudFormation → Stacks → your stack → Delete. To confirm it is gone, use Filter status →
Deleted on the Stacks page (`SETUP.md` section 8). The commands below do the same from CloudShell.

Empty the bucket first: a stack cannot delete a bucket that still holds files. Deleting the stack
also removes the user pool and the people in it, and every other resource the stack made:
nothing in this template is kept.

```bash
aws s3 rm "s3://$BUCKET" --recursive
aws cloudformation delete-stack --stack-name helpdesk-dev-ch7
aws cloudformation wait stack-delete-complete --stack-name helpdesk-dev-ch7
```
