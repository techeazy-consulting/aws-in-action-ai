# Chapter 8: ship like a team

Everything from chapter 7 is still here: sign-in, the two groups, the guardrail, `/ask`,
`/tickets`, `/triage`, the table, the topic and the chat page. This chapter changes how the code
reaches AWS. A push to the main branch runs the tests, deploys to a `staging` stack, and then
waits for a person to approve before it deploys the same template to a `prod` stack. No AWS key is
stored anywhere.

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
| Deploy the bootstrap stack | CloudFormation → Stacks → Create stack | `## 7. Deploy a chapter from the CloudFormation console` |
| Copy a value from the Outputs tab | CloudFormation → Stacks → your stack → Outputs | `## 9. Copy a value from the Outputs tab` |
| Delete the stacks | CloudFormation → Stacks → Delete | `## 8. Delete a chapter's stack and confirm it is gone` |

This chapter adds four things to check or do:

- **A Region offering Amazon Bedrock and S3 Vectors.** The template's `ModelRoute` parameter,
  `auto` by default, picks the inference profile your Region needs for the model (see `## The
  model, the Region and the names`), so you are not limited to `us-east-1`.
- **A GitHub repository you own.** It holds this chapter's files at its top. Environments with
  branch rules and required reviewers need a public repository or a paid plan.
- **An email address you can read.** Each stack's `EscalationEmail` receives a confirmation
  message from AWS (see The first run).
- **The IAM boxes.** The bootstrap stack gives its roles set names, so under Capabilities tick
  every acknowledgement box the console shows (`CAPABILITY_NAMED_IAM` on the command line).

## What changed since chapter 7

- `.github/workflows/deploy.yml` - three jobs. `test` installs the tools, runs `pytest` and runs
  `cfn-lint` on both templates, on every push and every pull request. `deploy-staging` needs
  `test`. `deploy-prod` needs `deploy-staging`. Both deploy jobs run only for the main branch,
  never for a pull request, and each names a GitHub environment (`staging`, `prod`). The two
  deploy jobs have the same steps; only the environment name differs.
- `deploy-role.yaml` - a separate, small template you deploy once per account, by hand, before the
  first run. It creates the GitHub identity provider (or uses one your account already has), a
  permissions boundary and two roles. `GitHubDeployRole` can be assumed only by a job that names
  the `staging` or `prod` environment of your repository, and can only run CloudFormation on
  `helpdesk-*` stacks, hand the work to the second role, put the chat page and policy pages in
  the site buckets and start a knowledge base ingestion job. `CloudFormationExecutionRole` can be
  assumed only by CloudFormation. It creates the helpdesk's resources with named actions (no
  service-wide grant), limited by name pattern where we choose the name (functions, tables, topics,
  log groups, the site buckets), by account and Region for what gets an id, and for CloudFront
  distributions, Cognito user pools, guardrails, knowledge bases and vector buckets by a tag: it
  may create one only when the request carries the chapter tag, and change or delete only ones
  that carry it. The one thing that cannot be tagged or tag-tested is a CloudFront origin access
  control, which is limited to this account. It can create or change an IAM role only if
  the role carries the permissions boundary, it cannot attach a managed policy, and it cannot
  change a boundary or either bootstrap role. A workflow therefore cannot use the pipeline to
  mint a role stronger than the helpdesk itself needs.
- `template.yaml` - a `PermissionsBoundaryArn` parameter that every role in the stack carries,
  a `Project` parameter (only `helpdesk`) and an `Environment` parameter (`dev`, `staging` or `prod`)
  that start every resource name, and a site bucket whose name carries them, so the two stacks
  cannot collide and the deploy role can be given access by name pattern. The model is called
  through the Region's inference profile, as in chapter 6 and 7 (`ModelId`, `ModelRoute`).
  Everything else is chapter 7's template. The same file deploys both stacks.
- `tests/test_workflow.py`, `tests/test_deploy_role.py`, `tests/test_environments_stack.py` - they
  read the workflow and both templates as data: the job order, the environments, who can ask for
  the OIDC token, no stored key, no expression written into a shell script, the exact trust
  policy, and that nothing in the roles is wider than stated. Nothing here needs an AWS account or
  GitHub.
- `prompts/` - one prompt per build step, in order, each with a check. `prompts/CHECK.md` holds
  the checks for the whole chapter.

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

The permissions boundary is the ceiling for those roles, so the bootstrap template lets it allow
the model in every Region and the Region's inference profile; without that, a call through a
profile would be refused even though the function's own policy allows it. The chapter tag
conditions in the bootstrap roles also accept the `project` and `environment` tags the template
now sets on every resource. `Project` stays `helpdesk` in this chapter because the bootstrap roles
are scoped to names that start with `helpdesk-`.

## One template, two stacks

Each deploy job runs `aws cloudformation deploy` with `--stack-name helpdesk-$ENVIRONMENT` and
`Environment=$ENVIRONMENT`. With the default `Project=helpdesk` every resource is named
`helpdesk-staging-<part>` or `helpdesk-prod-<part>`. Staging is therefore a real rehearsal for prod: same template, same
commands, a different stack. Two stacks mean two of everything, so delete staging when you are
not testing.

## Set it up once

1. Copy this chapter's files into the root of your own GitHub repository (so `template.yaml`,
   `app/`, `tests/` and `.github/` sit at the top), and push. This step happens on your own
   computer; there is no console route.
2. Find the start of your repository's subject claim. Repositories created before July 15, 2026
   keep the form `repo:OWNER/REPO`; newer ones, and ones that opted in, carry
   numeric ids in the form `repo:OWNER@OWNER-ID/REPO@REPO-ID`. Print one token's subject with the
   OIDC debugger action and use what it shows, up to but not including the part that follows the repository name
   (`:ref:...` or `:environment:...`).
3. Deploy the bootstrap stack, once per account. The stack name does not start with `helpdesk-`,
   so the deploy role cannot touch it.

   In the console: `CloudFormation → Stacks → Create stack → With new resources (standard) →
   Upload a template file → Choose file`, and pick `deploy-role.yaml` from your computer. Name the
   stack `github-bootstrap`, fill in `GitHubSubjectPrefix` (the prefix from step 2), and under
   `Capabilities` tick every acknowledgement box. If the account already has the GitHub provider,
   set `CreateProvider` to `false` and paste its ARN into `ExistingProviderArn`. When the stack is
   complete, open its `Outputs` tab and copy `DeployRoleArn`, `CloudFormationRoleArn` and
   `PermissionsBoundaryArn` (see `SETUP.md` section 9).

   In CloudShell, from this chapter's folder (`PREFIX` is the prefix from step 2):

```bash
PREFIX="repo:OWNER/REPO"
aws cloudformation deploy --stack-name github-bootstrap --template-file deploy-role.yaml --capabilities CAPABILITY_NAMED_IAM --parameter-overrides "GitHubSubjectPrefix=$PREFIX"
aws cloudformation describe-stacks --stack-name github-bootstrap --query "Stacks[0].Outputs" --output table
```

If the account already has the GitHub provider, add `CreateProvider=false ExistingProviderArn=<arn>`.

4. In your repository on GitHub, open `Settings → Environments → New environment` and create the
   two environments `staging` and `prod`. On **both**, under `Deployment branches` choose
   `Selected branches and tags`, choose `Add deployment branch or tag rule`, and add one rule: the
   branch `main` (main branch only). On `prod`, also tick `Required reviewers`, add yourself (or a teammate) and
   choose `Save protection rules`. Environments, branch rules and required reviewers need a public
   repository or a paid plan.
   The branch rule matters because AWS cannot check the branch: from a GitHub token it can test
   only the audience and the subject, and the subject names the environment, not the branch. The
   environment's branch rule is what stops a job on any other branch from getting a token for it.
5. Add five variables (not secrets; none of them is a credential). On GitHub open
   `Settings → Secrets and variables → Actions → Variables → New repository variable` and add
   each one:

   | Variable | The value |
   |---|---|
   | `AWS_REGION` | The Region you deploy to, for example `us-east-1` |
   | `DEPLOY_ROLE_ARN` | Bootstrap stack, Outputs tab → `DeployRoleArn` |
   | `CFN_ROLE_ARN` | Bootstrap stack, Outputs tab → `CloudFormationRoleArn` |
   | `PERMISSIONS_BOUNDARY_ARN` | Bootstrap stack, Outputs tab → `PermissionsBoundaryArn` |
   | `ESCALATION_EMAIL` | Your own address |

## The first run

Push to the main branch. `test` runs, then `deploy-staging` creates the `helpdesk-staging` stack,
publishes the chat page and policy pages and starts an ingestion job. Then `deploy-prod` waits:
open the run (GitHub → Actions → the latest run), click `Review deployments`, tick `prod` and
click `Approve and deploy`. A first run can fail with an access-denied
message naming one action; add only that action to the right role in `deploy-role.yaml`, never a
wildcard, and redeploy the bootstrap stack. If the failure is about creating a role, check that
`PERMISSIONS_BOUNDARY_ARN` is set: a role without the boundary is refused on purpose.

Then, once per stack (`helpdesk-staging` and `helpdesk-prod`):

- **Confirm the escalation email**, as in chapter 6: open the message AWS sent to
  `ESCALATION_EMAIL` and choose its confirmation link.
- **Create the people**, as in chapter 7. In the console, copy `UserPoolId` from the stack's
  `Outputs` tab, then `Amazon Cognito → User pools → your pool → Users → Create a user`, and open
  the user and add it to `employee` (or `it-staff`) under `Group memberships`. The console sets a
  temporary password and the chat page's sign-in does not do a forced password change, so make the
  password permanent in CloudShell (`POOL` is the `UserPoolId`, `EMAIL` the address you gave the
  user):

```bash
read -rs PW
aws cognito-idp admin-set-user-password --user-pool-id "$POOL" --username "$EMAIL" --password "$PW" --permanent
```

The chapter 7 README has the same steps as commands (`Create the people`).

## Roll back

Rollback is a deploy of the previous commit. Either re-run the jobs of the earlier workflow run
(a re-run uses the same commit as the original run), or revert the bad commit on the main branch
and push. Both pass through staging and the prod approval again.

## Run the tests

```bash
pip install pytest cfn-lint boto3 pyyaml
pytest -q
cfn-lint template.yaml deploy-role.yaml
```

## Delete

Delete prod, then staging, then the bootstrap stack last. Empty each site bucket first.

In the console, for `helpdesk-prod` and then `helpdesk-staging`: `S3 → General purpose buckets →
the bucket named in the stack's Outputs tab → Empty`, type the bucket name and choose `Empty`;
then `CloudFormation → Stacks → the stack → Delete`. Last, delete `github-bootstrap` the same way.
The stack leaves the `Stacks` list; `Filter status → Deleted` shows it (`SETUP.md` section 8).

The same in CloudShell:

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

Deleting the bootstrap stack removes the GitHub provider if that stack created it, so do it only
when no other project in the account uses the provider.
