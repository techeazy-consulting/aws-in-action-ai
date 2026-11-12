# 04 - Deploy to staging, then to prod after approval

## Goal

Add the two deploy jobs: staging after the tests, prod after staging and a person's approval, with no stored key.

## Prompt

```text
Extend .github/workflows/deploy.yml with deploy-staging (needs test) and deploy-prod (needs
deploy-staging).

- Both: run only for the main branch and never for a pull request; environment staging or prod;
  a concurrency group of their own name; permissions contents read and id-token write on the job
  only; env ENVIRONMENT (staging or prod) plus AWS_REGION, CFN_ROLE_ARN, PERMISSIONS_BOUNDARY_ARN and ESCALATION_EMAIL from
  repository variables (vars context, never secrets).
- Steps: check out; aws-actions/configure-aws-credentials with role-to-assume from the variable
  DEPLOY_ROLE_ARN and aws-region; deploy with aws cloudformation deploy (stack helpdesk-$ENVIRONMENT,
  template.yaml, --capabilities CAPABILITY_IAM, --role-arn "$CFN_ROLE_ARN", --no-fail-on-empty-changeset,
  --parameter-overrides Environment, EscalationEmail and PermissionsBoundaryArn); then read SiteBucketName, KnowledgeBaseId
  and DataSourceId from the stack outputs, copy app/web/index.html and app/policies to the bucket
  and start an ingestion job.
- No expression may appear inside a run: script; values go through env and are quoted.
- The steps of the two jobs must be identical, so staging rehearses prod.
Extend tests/test_workflow.py for all of this: job order, environments, main only, permissions,
the role through OIDC with no key and no secret, no expression in a script, identical steps,
the role handed to CloudFormation, the pages published, and that no email address is in the file.
```

## Check

```bash
pytest -q tests/test_workflow.py
grep -n "environment:" .github/workflows/deploy.yml
grep -n "id-token" .github/workflows/deploy.yml
```
