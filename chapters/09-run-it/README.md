# Chapter 9: run it

Everything from chapter 8 is still here: sign-in, the guardrail, the workflow, staging and prod,
the bootstrap template. This chapter lets you see the helpdesk while it runs, hear about it when
it breaks, check it after every deploy, and delete all of it cleanly.

## Before you try

The offline checks below need no AWS account. The live steps need the setup in this table. Console
routes here are written `Service → page → button`; the full numbered steps are in `SETUP.md` at
the top of the course repository. The setup and the live steps can be done from the console plus
CloudShell. Sign in as an IAM or IAM Identity Center user, not as the root user: as the root user,
a Bedrock step can stop with `AccessDeniedException ... :root is not authorized`.

| What you need | Where in the console | `SETUP.md` section |
|---|---|---|
| A user that is not the root user | Sign in with an administrative or IAM user, not the root user | `## 1. Sign in with a user that is not the root user` |
| A Region offering Amazon Bedrock and S3 Vectors | Region menu in the top bar | `## 2. Pick a Region` |
| A budget alert | Billing and Cost Management → Budgets | `## 3. Set a budget alert` |
| Amazon Nova Lite (it supports tool use) and Amazon Titan Text Embeddings V2 | Amazon Bedrock → Model catalog | `## 4. Make sure the model is available to your account` |
| A terminal | CloudShell icon in the top bar | `## 5. Open CloudShell` |
| The code in CloudShell and on your computer | CloudShell → Actions → Upload file | `## 6. Put the code in CloudShell` |
| The bootstrap stack, redeployed | CloudFormation → Stacks → Update | `## 7. Deploy a chapter from the CloudFormation console` |
| Copy a value from the Outputs tab | CloudFormation → Stacks → your stack → Outputs | `## 9. Copy a value from the Outputs tab` |
| Delete the stacks | CloudFormation → Stacks → Delete | `## 8. Delete a chapter's stack and confirm it is gone` |

This chapter adds four things to check or do:

- **A Region offering Amazon Bedrock and S3 Vectors.** The template's `ModelRoute` parameter,
  `auto` by default, picks the inference profile your Region needs for the model (see `## The
  model, the Region and the names`), so you are not limited to `us-east-1`.
- **Chapter 8 first.** The repository, its two environments, the five variables and the confirmed
  escalation email must exist (see Set it up).
- **The bootstrap redeploy.** It gained permissions for alarms, the dashboard and metric filters;
  redeploy it before the first push.
- **Some traffic.** Send a few messages through a stack's chat page before you read its logs.

## What changed since chapter 8

- `app/*/handler.py` - every function now writes **one JSON summary line per request**: the route,
  how it ended (`ok`, `blocked`, `refused`, `bad_request` or `error`), the caller's role (never a
  name, email or user id), the time it took and, for `/tickets` and `/triage`, the model calls,
  the input and output tokens the model reported and the tickets created. The line never holds
  what anyone wrote or what the model answered. A request that fails in a way nobody planned for
  is logged as an error and answered with a safe 500.
- `template.yaml` - the functions log in JSON format at INFO level (set here, not in the code);
  eleven log metric filters turn the summary lines into metrics under `Helpdesk/<environment>`;
  two alarms (`<project>-<environment>-errors` on those metrics and `<project>-<environment>-api-5xx` on the API's server errors)
  email through the escalation topic that already exists; one CloudWatch dashboard shows
  requests, errors, tokens per request and tickets created.
- `app/quality/check.py` and `app/quality/questions.json` - a fixed list of helpdesk questions
  asked of the deployed `/ask` function after each deploy. It fails when an answer has the wrong
  shape: no answer text, no cited policy page, the wrong page, a normal question blocked, an
  off-topic question answered instead of blocked, or something that looks like a secret.
- `.github/workflows/deploy.yml` - after each deploy the workflow waits for the knowledge base
  ingestion job and then runs the quality check, so a bad staging deploy stops before the prod
  approval.
- `app/ops/cost.py` - the cost-per-ticket formula. It contains no price.
- `deploy-role.yaml` - the permissions the new pieces need, on top of chapter 8's tag- and
  name-limited roles (alarms, dashboards, metric filters,
  watching an ingestion job, invoking the ask function). Deploy it again before the first run.
- `tests/` - the chapter 8 tests plus tests for the log lines, the metric filters, the alarms,
  the dashboard, the quality check, the formula and the new permissions.

## The model, the Region and the names

The functions call the model in the `ModelId` parameter (Amazon Nova Lite by default, which lists
client-side tool calling as supported; the list also offers Nova Micro). Keep to the list: a model
without tool use with the Converse API fails the request.

Most Regions serve the model only through an inference profile, a model id with a geography in
front such as `apac.amazon.nova-lite-v1:0`; the template's `ModelRoute` parameter, `auto` by
default, picks the right one for your Region, and the stack's `ModelInUse` output shows which id
it chose. The `/ask` function sends the matching profile ARN to the knowledge base, so one
setting reaches the functions that call the model. The dashboard's Bedrock widget reads the
metrics filed under that same id. To change the model, update the stack and pick another `ModelId`
from the list; editing a function's `MODEL_ID` or `MODEL_ARN` by hand fails, because the role only
allows the model the stack chose.

The bootstrap template's permissions boundary allows the model in every Region and the Region's
inference profile, and its tag-key conditions accept the `project` and `environment` tags the
template sets on every resource next to `chapter`; redeploy the bootstrap stack if you built it
from an earlier version. `Project` stays `helpdesk` because the bootstrap roles are scoped to names
that start with `helpdesk-`; with `Environment` it starts every resource name, such as
`helpdesk-staging-ask` and the alarm `helpdesk-staging-errors`.

## Set it up

This is chapter 8's setup plus one redeploy. If you start here, do chapter 8's setup first; if you
finished chapter 8, redeploy the bootstrap template, because it now carries more permissions.

1. Copy this chapter's files into the root of your own GitHub repository and push. This step
   happens on your own computer; there is no console route.
2. Deploy `deploy-role.yaml` as a stack named `github-bootstrap` (not `helpdesk-` anything) with
   `CAPABILITY_NAMED_IAM` and your `GitHubSubjectPrefix`; redeploy it if it already exists.
   In the console: for a new stack, `CloudFormation → Stacks → Create stack → With new resources
   (standard) → Upload a template file`; for an existing one, `CloudFormation → Stacks → github-bootstrap
   → Update → Replace existing template → Upload a template file → Choose file`, pick this chapter's
   `deploy-role.yaml`, keep the parameter values CloudFormation fills in, and tick every
   acknowledgement box under `Capabilities`. In CloudShell, from this chapter's folder (`PREFIX`
   is your subject prefix from chapter 8):

```bash
PREFIX="repo:OWNER/REPO"
aws cloudformation deploy --stack-name github-bootstrap --template-file deploy-role.yaml --capabilities CAPABILITY_NAMED_IAM --parameter-overrides "GitHubSubjectPrefix=$PREFIX"
```

3. Create the environments `staging` and `prod`: on GitHub, `Settings → Environments → New
   environment`. On **both**, set the deployment branches to the main branch only (under
   `Deployment branches` choose `Selected branches and tags`, then `Add deployment branch or tag
   rule`); on `prod`, also tick `Required reviewers` and add one. AWS cannot check the branch from a
   GitHub token, so this rule is what keeps other branches out. Environments, branch rules and
   required reviewers need a public repository or a paid plan.
4. Add five repository variables (none is a credential): `AWS_REGION`, `DEPLOY_ROLE_ARN`,
   `CFN_ROLE_ARN`, `PERMISSIONS_BOUNDARY_ARN` and `ESCALATION_EMAIL`. On GitHub:
   `Settings → Secrets and variables → Actions → Variables → New repository variable`. The three
   addresses come from the bootstrap stack's `Outputs` tab: `DeployRoleArn`,
   `CloudFormationRoleArn` and `PermissionsBoundaryArn`.
5. Push to the main branch. Staging deploys and is checked; prod waits for your approval:
   `GitHub → Actions → the latest run → Review deployments → tick prod → Approve and deploy`.
   Confirm the escalation email as in chapter 6 (the AWS message to `ESCALATION_EMAIL`; its link
   confirms the subscription) and create the people as in chapter 7.

## Read the logs

A log group holds lines only after requests, so send a few messages through the chat page first.
In the CloudWatch console choose `Logs`, then `Logs Insights`; in `Select log group(s)` choose the
log groups of one stack (for example `/aws/lambda/helpdesk-staging-tickets` and
`/aws/lambda/helpdesk-staging-triage`) and run:

```
fields @timestamp, route, outcome, role, latency_ms, input_tokens, output_tokens
| filter event = "request"
| sort @timestamp desc
| limit 20
```

Because the lines are JSON, each field is a column you can filter and add up. To total a day:

```
filter event = "request" and model_calls > 0
| stats sum(input_tokens) as input_tokens, sum(output_tokens) as output_tokens, sum(tickets_created) as tickets by bin(1d)
```

## Tokens per request

There are two sources and they answer different questions.

- **The logs** hold the token counts the model reported for each request on `/tickets` and
  `/triage`. The dashboard divides the logged input and output tokens by the logged number of
  model requests, so you see tokens per request for those two routes.
- **The Bedrock runtime metrics** (`InputTokenCount`, `OutputTokenCount`, `Invocations`, by model)
  count the calls made to the model through the Converse family of operations, for the whole
  account and not per request. The dashboard shows tokens per model call from them. The knowledge
  base answers behind `/ask` report no token count to this code, so `/ask` appears in neither
  per-request number; do not assume the model metrics include it.

## Cost per ticket

```
cost per ticket = (input tokens / per x input price + output tokens / per x output price + other costs) / tickets
```

Read the current prices for your model on the Bedrock pricing page, in the unit that page uses.
Nothing in this course states a price. Take the token and ticket totals from Logs Insights (above)
for the period, add up any other costs you want counted (the guardrail, the knowledge base, the
dashboard) and run:

```bash
python app/ops/cost.py --input-tokens <n> --output-tokens <n> --tickets <n> --input-price <p> --output-price <p> --per <tokens-one-price-covers> --other-costs <c>
```

The command refuses to run without every price and without at least one ticket.

## The dashboard and the alarms

Open the dashboard named in the stack output `DashboardName` (`CloudWatch → Dashboards`, then
that name). The error widget draws the alarm
line. Both alarms send to the escalation topic, so the address you confirmed in chapter 6 receives
them. Test the path without breaking anything:

```bash
aws cloudwatch set-alarm-state --alarm-name helpdesk-staging-errors --state-value ALARM --state-reason "test"
```

An email arrives; the alarm returns to its real state by itself, often within seconds. If no
email arrives, check that the subscription is confirmed (chapter 6).

## The quality check

The workflow runs it after each deploy. To run it by hand with your own credentials, in CloudShell
(there is no console route for this step). `KB` and `DS` are the `KnowledgeBaseId` and
`DataSourceId` values from the `helpdesk-staging` stack's `Outputs` tab; the first command starts
an ingestion job and gives its id:

```bash
JOB=$(aws bedrock-agent start-ingestion-job --knowledge-base-id "$KB" --data-source-id "$DS" --query ingestionJob.ingestionJobId --output text)
python3 app/quality/check.py wait --knowledge-base-id "$KB" --data-source-id "$DS" --job-id "$JOB"
python3 app/quality/check.py run --function-name helpdesk-staging-ask
```

It invokes the ask function directly with the claims of a made-up employee, so it needs no
password and stores no secret. That proves the function, the knowledge base, the model and the
guardrail work together after a deploy. It does not test sign-in or the API's token check; the
unit tests and the live steps in chapter 7 cover those. An exit code of 1 means an answer had the
wrong shape; 2 means the check could not run. Add a question by adding an entry to
`questions.json` that expects a cited policy page or a block.

## The voice teaser

The short voice demo in the slides has no code and no resource in this template. The advanced
voice sessions are sold separately.

## Run the tests

```bash
pip install pytest cfn-lint boto3 pyyaml
pytest -q
cfn-lint template.yaml deploy-role.yaml
```

## Tear it all down

Three stacks, and nothing else in AWS: prod, staging and the bootstrap stack last, because the
workflow's roles live in it. Empty each site bucket first.

In the console, for `helpdesk-prod`, then `helpdesk-staging`: `S3 → General purpose buckets → the
bucket named in the stack's Outputs tab → Empty`; then `CloudFormation → Stacks → the stack →
Delete`. Last, delete `github-bootstrap` the same way. `Filter status → Deleted` shows the stacks
gone (`SETUP.md` section 8). The same in CloudShell:

```bash
for ENV in prod staging; do
  BUCKET=$(aws cloudformation describe-stacks --stack-name "helpdesk-$ENV" --query "Stacks[0].Outputs[?OutputKey=='SiteBucketName'].OutputValue" --output text)
  aws s3 rm "s3://$BUCKET" --recursive
  aws cloudformation delete-stack --stack-name "helpdesk-$ENV"
  aws cloudformation wait stack-delete-complete --stack-name "helpdesk-$ENV"
done
aws cloudformation delete-stack --stack-name github-bootstrap
aws cloudformation wait stack-delete-complete --stack-name github-bootstrap
```

Confirm the account is clean, in the same Region you deployed to. Each command should print
nothing:

```bash
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE UPDATE_ROLLBACK_COMPLETE ROLLBACK_COMPLETE DELETE_FAILED --query "StackSummaries[?starts_with(StackName, 'helpdesk-') || StackName == 'github-bootstrap'].StackName" --output text
aws cloudwatch describe-alarms --alarm-name-prefix helpdesk- --query "MetricAlarms[].AlarmName" --output text
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/helpdesk- --query "logGroups[].logGroupName" --output text
```

A stack listed as `DELETE_FAILED` names the resource that blocked it; fix that one and delete
again. What stays outside AWS: the GitHub environments, the repository variables and the code
itself. Remove those in your repository settings if you no longer want them. Deleting the
bootstrap stack removes the GitHub provider if that stack created it, so do it only when no other
project in the account uses the provider.
