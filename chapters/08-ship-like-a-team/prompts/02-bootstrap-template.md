# 02 - The once-per-account deploy role

## Goal

Write a small separate template that lets a GitHub workflow deploy with no stored key.

## Prompt

```text
Create deploy-role.yaml (a second template, deployed by hand once per account, not part of the
helpdesk stack).

- Parameters: GitHubSubjectPrefix (no default; allowed pattern repo:OWNER/REPO or
  repo:OWNER@ID/REPO@ID, no wildcard), CreateProvider (true or false) and ExistingProviderArn.
- GitHubOidcProvider (only when CreateProvider is true): the GitHub token address as Url, and
  sts.amazonaws.com as the only client id.
- HelpdeskPermissionsBoundary (a managed policy): the ceiling for every role a helpdesk stack
  creates, with exactly the actions the stack's own roles use and no wildcard action.
- CloudFormationExecutionRole: only CloudFormation can assume it. It may create the helpdesk's
  resources, with named actions only (no service-wide grant such as lambda:*): Lambda functions,
  DynamoDB tables, SNS topics, log groups and the site buckets limited to helpdesk-* names; API
  Gateway limited to HTTP APIs and tags in this Region; Bedrock guardrails and knowledge bases,
  vector buckets, CloudFront distributions and Cognito user pools created only when the request
  carries the chapter tag (aws:RequestTag/chapter) and changed or deleted only when the resource
  carries it (aws:ResourceTag/chapter); CloudFront origin access controls limited to this account
  (they cannot be tagged). For IAM it may create or change a role named helpdesk-*
  ONLY with the boundary attached (the iam:PermissionsBoundary condition), read, tag and delete
  those roles, and pass them only to Lambda and Bedrock. It has no attach-policy action and
  nothing that touches a boundary. Its own name and the deploy role's name must NOT start with helpdesk-.
- GitHubDeployRole: trusts the provider through sts:AssumeRoleWithWebIdentity with a StringEquals
  condition on aud (sts.amazonaws.com) and on sub (the prefix plus :environment:staging, and the
  same with :environment:prod). It may run CloudFormation change set actions on helpdesk-* stacks
  (no delete), read a template summary, pass only the CloudFormation role and only to
  cloudformation.amazonaws.com, put pages in the site buckets, and start an ingestion job.
- Outputs DeployRoleArn, CloudFormationRoleArn and PermissionsBoundaryArn. Tag every resource that
  takes tags chapter: session-08. The tag-key conditions on every create and tag call allow the
  keys chapter, project and environment (and aws:cloudformation:*), because the main template tags
  every resource with all three. The permissions boundary allows bedrock:InvokeModel on the
  foundation model in every Region and on inference profiles in this Region and account, because
  the functions reach the model through a profile.
Add tests/test_deploy_role.py that reads the file as data and checks every line above.
```

## Check

```bash
cfn-lint deploy-role.yaml
pytest -q tests/test_deploy_role.py
grep -n "AssumeRoleWithWebIdentity" deploy-role.yaml
```
