# Chapter 3 checks

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
aws cloudformation deploy --stack-name helpdesk-dev-ch3 --template-file template.yaml --capabilities CAPABILITY_IAM --parameter-overrides Project=helpdesk Environment=dev
BUCKET=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch3 --query "Stacks[0].Outputs[?OutputKey=='SiteBucketName'].OutputValue" --output text)
SITE=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch3 --query "Stacks[0].Outputs[?OutputKey=='ChatUrl'].OutputValue" --output text)
aws s3 cp app/web/index.html "s3://$BUCKET/index.html" --content-type text/html
curl -s -o /dev/null -w "%{http_code}\n" "$SITE/"
curl -s -X POST "$SITE/ask" -H "content-type: application/json" -d '{"question": "How do I reset my password?"}'
curl -s -o /dev/null -w "%{http_code}\n" "$BUCKET.s3.amazonaws.com/index.html"
aws s3 rm "s3://$BUCKET" --recursive
aws cloudformation delete-stack --stack-name helpdesk-dev-ch3
aws cloudformation wait stack-delete-complete --stack-name helpdesk-dev-ch3
```

The first request prints 200 and the second returns an answer. The third prints 403: the bucket
refuses a request that does not come through CloudFront. After the wait finishes, the stack is gone
and nothing keeps costing money.
