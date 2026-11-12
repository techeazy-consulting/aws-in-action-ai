# Chapter 9 checks

Run these from the chapter folder (the top of your repository). The offline checks need no AWS
account, no GitHub account and cost nothing.

## Offline

```bash
pip install pytest cfn-lint boto3 pyyaml
pytest -q
cfn-lint template.yaml deploy-role.yaml
python app/ops/cost.py --input-tokens 2000 --output-tokens 500 --tickets 5 --input-price 1 --output-price 4 --per 1000 --other-costs 3
python app/ops/cost.py --input-tokens 2000 --output-tokens 500 --tickets 0 --input-price 1 --output-price 4 --per 1000; echo "exit $?"
```

Tests must report passed with none skipped. cfn-lint prints nothing when both templates are
clean. The first cost line prints a result for made-up numbers (they are not prices); the second
refuses and prints `exit 2`, because there is no cost per ticket without a ticket. The tests read
the template as data and run the quality check against fakes, so they prove the shape and the
logic, not that a deploy works.

## Live (costs money)

These create real resources in your own AWS account and call the model. The dashboard and the
alarms are billed resources too. Run them only when you are ready to pay, and delete everything
afterwards. Use your own values in place of the placeholders.

```bash
aws cloudformation deploy --stack-name github-bootstrap --template-file deploy-role.yaml --capabilities CAPABILITY_NAMED_IAM --parameter-overrides GitHubSubjectPrefix=<repo-prefix>
# Push to main; the workflow deploys staging, waits for the ingestion job and runs the quality check.
python app/quality/check.py run --function-name helpdesk-staging-ask; echo "exit $?"
aws cloudwatch set-alarm-state --alarm-name helpdesk-staging-errors --state-value ALARM --state-reason "test"
aws cloudwatch describe-alarms --alarm-name-prefix helpdesk-staging- --query "MetricAlarms[].[AlarmName,StateValue]" --output text
for ENV in prod staging; do
  BUCKET=$(aws cloudformation describe-stacks --stack-name "helpdesk-$ENV" --query "Stacks[0].Outputs[?OutputKey=='SiteBucketName'].OutputValue" --output text)
  aws s3 rm "s3://$BUCKET" --recursive
  aws cloudformation delete-stack --stack-name "helpdesk-$ENV"
  aws cloudformation wait stack-delete-complete --stack-name "helpdesk-$ENV"
done
aws cloudformation delete-stack --stack-name github-bootstrap
aws cloudformation wait stack-delete-complete --stack-name github-bootstrap
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE UPDATE_ROLLBACK_COMPLETE ROLLBACK_COMPLETE DELETE_FAILED --query "StackSummaries[?starts_with(StackName, 'helpdesk-') || StackName == 'github-bootstrap'].StackName" --output text
aws cloudwatch describe-alarms --alarm-name-prefix helpdesk- --query "MetricAlarms[].AlarmName" --output text
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/helpdesk- --query "logGroups[].logGroupName" --output text
```

Open Logs Insights on the staging tickets log group and run the first query from the README: the
rows must show `route`, `outcome` and `role` as columns. If they do not, the log format is not
JSON and the metric filters will match nothing. The quality check prints `4 of 4 passed` and `exit 0` once the ingestion job is complete; `exit 1`
means an answer had the wrong shape and the line above it names the question and the problem. The
alarm test sends an email to the address you confirmed in chapter 6. After the deletes, the three
last commands print nothing, and nothing keeps costing money.
