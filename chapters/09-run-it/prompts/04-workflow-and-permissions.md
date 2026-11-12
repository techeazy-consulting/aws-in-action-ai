# 04 - Run the check in the workflow

## Goal

Run the ingestion wait and the quality check after each deploy, and give the deploy role exactly the new permissions it needs.

## Prompt

```text
Edit .github/workflows/deploy.yml and deploy-role.yaml (replace session-08 with session-09).

- In both deploy jobs: set up Python and install boto3 before the credentials step. In the publish
  step capture the ingestion job id (--query ingestionJob.ingestionJobId --output text) and run
  python app/quality/check.py wait with the knowledge base id, data source id and job id. Add a
  final step named Quality check that runs
  python app/quality/check.py run --function-name "helpdesk-$ENVIRONMENT-ask".
  The steps stay identical in the two jobs; prod still needs staging, so a failed check stops prod.
- deploy-role.yaml, deploy role: lambda:InvokeFunction on function:helpdesk-*-ask only, and
  bedrock:GetIngestionJob beside StartIngestionJob.
- deploy-role.yaml, CloudFormation role: alarm actions on alarm:helpdesk-*, dashboard actions on
  dashboard/helpdesk-*, PutMetricFilter and DeleteMetricFilter on the helpdesk log groups, and the
  two describe actions that take no resource.
Extend tests/test_workflow.py and tests/test_deploy_role.py: the step order, the exact check
command, Python and boto3 before the check, and the scoped permissions.
```

## Check

```bash
cfn-lint deploy-role.yaml
pytest -q tests/test_workflow.py tests/test_deploy_role.py
grep -n "quality" .github/workflows/deploy.yml
```
