# Chapter 6 checks

Run these from the chapter folder. The offline checks need no AWS account and cost nothing.

## Offline

```bash
pip install -r ../../requirements-dev.txt
pytest -q
cfn-lint template.yaml
```

Tests must report passed with none skipped. cfn-lint prints nothing when the template is clean.

## Live (costs money)

These deploy real resources in your own AWS account, call a generation model several times per
message and send real email to the address you give. Run them only when you are ready to pay for a
few requests, and delete the stack afterwards. Use your own address in place of the placeholder.

```bash
aws cloudformation deploy --stack-name helpdesk-dev-ch6 --template-file template.yaml --capabilities CAPABILITY_IAM --parameter-overrides EscalationEmail=<your-email-address> Project=helpdesk Environment=dev
BUCKET=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch6 --query "Stacks[0].Outputs[?OutputKey=='SiteBucketName'].OutputValue" --output text)
SITE=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch6 --query "Stacks[0].Outputs[?OutputKey=='ChatUrl'].OutputValue" --output text)
TOPIC=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch6 --query "Stacks[0].Outputs[?OutputKey=='EscalationTopicArn'].OutputValue" --output text)
aws sns list-subscriptions-by-topic --topic-arn "$TOPIC"
curl -s -X POST "$SITE/triage" -H "content-type: application/json" -d '{"message": "I forgot my email password."}'
curl -s -X POST "$SITE/triage" -H "content-type: application/json" -d '{"message": "My VPN will not connect."}'
aws s3 rm "s3://$BUCKET" --recursive
aws cloudformation delete-stack --stack-name helpdesk-dev-ch6
aws cloudformation wait stack-delete-complete --stack-name helpdesk-dev-ch6
```

Choose the link in the confirmation email before the curl lines, or no escalation email is
delivered. The first reply has `"escalated": false` and mentions the password reset page. The
second has `"escalated": true` and one email arrives. After the wait finishes, the stack is gone and
nothing keeps costing money.
