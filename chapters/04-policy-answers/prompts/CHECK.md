# Chapter 4 checks

Run these from the chapter folder. The offline checks need no AWS account and cost nothing.

## Offline

```bash
pip install -r ../../requirements-dev.txt
pytest -q
cfn-lint template.yaml
```

Tests must report passed with none skipped. cfn-lint prints nothing when the template is clean.

## Live (costs money)

These deploy real resources in your own AWS account, call an embedding model to ingest the pages
and call a generation model for each question. Run them only when you are ready to pay for a few
requests, and delete the stack afterwards.

```bash
aws cloudformation deploy --stack-name helpdesk-dev-ch4 --template-file template.yaml --capabilities CAPABILITY_IAM --parameter-overrides Project=helpdesk Environment=dev
BUCKET=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch4 --query "Stacks[0].Outputs[?OutputKey=='SiteBucketName'].OutputValue" --output text)
SITE=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch4 --query "Stacks[0].Outputs[?OutputKey=='ChatUrl'].OutputValue" --output text)
KB=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch4 --query "Stacks[0].Outputs[?OutputKey=='KnowledgeBaseId'].OutputValue" --output text)
DS=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch4 --query "Stacks[0].Outputs[?OutputKey=='DataSourceId'].OutputValue" --output text)
aws s3 cp app/web/index.html "s3://$BUCKET/index.html" --content-type text/html
aws s3 cp app/policies "s3://$BUCKET/policies" --recursive --content-type text/html
JOB=$(aws bedrock-agent start-ingestion-job --knowledge-base-id "$KB" --data-source-id "$DS" --query "ingestionJob.ingestionJobId" --output text)
aws bedrock-agent get-ingestion-job --knowledge-base-id "$KB" --data-source-id "$DS" --ingestion-job-id "$JOB" --query "ingestionJob.status" --output text
curl -s -X POST "$SITE/ask" -H "content-type: application/json" -d '{"question": "How do I reset my password?"}'
curl -s -o /dev/null -w "%{http_code}\n" "$SITE/policies/password-reset.html"
aws s3 rm "s3://$BUCKET" --recursive
aws cloudformation delete-stack --stack-name helpdesk-dev-ch4
aws cloudformation wait stack-delete-complete --stack-name helpdesk-dev-ch4
```

Run the status command until it prints COMPLETE, then ask. The answer names the password reset page
in its `sources` list, and the page request prints 200. After the wait finishes, the stack is gone
and nothing keeps costing money.
