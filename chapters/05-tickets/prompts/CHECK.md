# Chapter 5 checks

Run these from the chapter folder. The offline checks need no AWS account and cost nothing.

## Offline

```bash
pip install -r ../../requirements-dev.txt
pytest -q
cfn-lint template.yaml
```

Tests must report passed with none skipped. cfn-lint prints nothing when the template is clean.

## Live (costs money)

These deploy real resources in your own AWS account and call a generation model for each message,
usually twice. Run them only when you are ready to pay for a few requests, and delete the stack
afterwards.

```bash
aws cloudformation deploy --stack-name helpdesk-dev-ch5 --template-file template.yaml --capabilities CAPABILITY_IAM --parameter-overrides Project=helpdesk Environment=dev
BUCKET=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch5 --query "Stacks[0].Outputs[?OutputKey=='SiteBucketName'].OutputValue" --output text)
SITE=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch5 --query "Stacks[0].Outputs[?OutputKey=='ChatUrl'].OutputValue" --output text)
curl -s -X POST "$SITE/tickets" -H "content-type: application/json" -d '{"message": "Please request Figma access for me. My name is Priya."}'
curl -s -X POST "$SITE/tickets" -H "content-type: application/json" -d '{"message": "What is the status of ticket 1001?"}'
curl -s -X POST "$SITE/tickets" -H "content-type: application/json" -d '{"message": "I need a new monitor."}'
aws s3 rm "s3://$BUCKET" --recursive
aws cloudformation delete-stack --stack-name helpdesk-dev-ch5
aws cloudformation wait stack-delete-complete --stack-name helpdesk-dev-ch5
```

The first reply names ticket 1001 and `tools_used` lists `create_ticket`. The second says it is
open. The third asks who is asking and opens nothing. After the wait finishes, the stack is gone
and nothing keeps costing money.
