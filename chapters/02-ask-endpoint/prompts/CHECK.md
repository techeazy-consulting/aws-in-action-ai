# Chapter 2 checks

Run these from the chapter folder. The offline checks need no AWS account and cost nothing.

## Offline

```bash
pip install -r ../../requirements-dev.txt
pytest -q
cfn-lint template.yaml
```

Tests must report passed with none skipped. cfn-lint prints nothing when the template is clean.

## Live (costs money)

These deploy real resources in your own AWS account and call a hosted model. Run them only when
you are ready to pay for a few requests, and delete the stack afterwards.

```bash
aws cloudformation deploy --stack-name helpdesk-dev-ch2 --template-file template.yaml --capabilities CAPABILITY_IAM --parameter-overrides Project=helpdesk Environment=dev
API_URL=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch2 --query "Stacks[0].Outputs[?OutputKey=='AskUrl'].OutputValue" --output text)
curl -s -X POST "$API_URL" -H "content-type: application/json" -d '{"question": "How do I reset my password?"}'
curl -s -X POST "$API_URL" -H "content-type: application/json" -d '{"question": ""}'
aws cloudformation delete-stack --stack-name helpdesk-dev-ch2
aws cloudformation wait stack-delete-complete --stack-name helpdesk-dev-ch2
```

The first request returns an answer. The second returns status 400 with an error message.
After the wait finishes, the stack is gone and nothing keeps costing money.
