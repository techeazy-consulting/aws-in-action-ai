# Chapter 8 checks

Run these from the chapter folder (the top of your repository). The offline checks need no AWS
account, no GitHub account and cost nothing.

## Offline

```bash
pip install pytest cfn-lint boto3 pyyaml
pytest -q
cfn-lint template.yaml deploy-role.yaml
python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml'))"
```

Tests must report passed with none skipped. cfn-lint prints nothing when both templates are
clean. The tests read the workflow and the templates as data, so they prove the shape (job order,
who can ask for a token, what the roles may do) and not that a deploy works.

## Live (costs money)

These create real resources in your own AWS account and run real workflow jobs. Staging and prod
are two full copies of the helpdesk. Run them only when you are ready to pay for both, and delete
everything afterwards. Use your own values in place of the placeholders.

```bash
aws cloudformation deploy --stack-name github-bootstrap --template-file deploy-role.yaml --capabilities CAPABILITY_NAMED_IAM --parameter-overrides GitHubSubjectPrefix=<repo-prefix>
aws cloudformation describe-stacks --stack-name github-bootstrap --query "Stacks[0].Outputs" --output table
# In the repository settings: environments staging and prod (prod with a required reviewer, both
# limited to the main branch), variables AWS_REGION, DEPLOY_ROLE_ARN, CFN_ROLE_ARN,
# PERMISSIONS_BOUNDARY_ARN, ESCALATION_EMAIL. Check the branch rule on both, then push to main.
for ENV in staging prod; do
  gh api "repos/<owner>/<repo>/environments/$ENV" --jq .deployment_branch_policy
  gh api "repos/<owner>/<repo>/environments/$ENV/deployment-branch-policies" --jq '.branch_policies[].name'
done
aws cloudformation describe-stacks --stack-name helpdesk-staging --query "Stacks[0].StackStatus" --output text
aws cloudformation describe-stacks --stack-name helpdesk-prod --query "Stacks[0].StackStatus" --output text
for ENV in prod staging; do
  BUCKET=$(aws cloudformation describe-stacks --stack-name "helpdesk-$ENV" --query "Stacks[0].Outputs[?OutputKey=='SiteBucketName'].OutputValue" --output text)
  aws s3 rm "s3://$BUCKET" --recursive
  aws cloudformation delete-stack --stack-name "helpdesk-$ENV"
  aws cloudformation wait stack-delete-complete --stack-name "helpdesk-$ENV"
done
aws cloudformation delete-stack --stack-name github-bootstrap
aws cloudformation wait stack-delete-complete --stack-name github-bootstrap
```

The branch check prints custom_branch_policies true and the single name main for each environment;
anything else means a job on another branch could ask for that environment's token. The staging
check prints CREATE_COMPLETE after the first run. The prod check fails with "does not
exist" until you approve the prod deployment in the workflow run, then prints CREATE_COMPLETE.
After the last wait finishes, nothing keeps costing money.
