# Chapter 7 checks

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
message, bill the guardrail for each text it checks and send real email to the address you give.
Run them only when you are ready to pay for a few requests, and delete the stack afterwards. Use
your own addresses in place of the placeholders and read the password at a prompt.

```bash
aws cloudformation deploy --stack-name helpdesk-dev-ch7 --template-file template.yaml --capabilities CAPABILITY_IAM --parameter-overrides EscalationEmail=<your-email-address> Project=helpdesk Environment=dev
POOL=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch7 --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" --output text)
SITE=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch7 --query "Stacks[0].Outputs[?OutputKey=='ChatUrl'].OutputValue" --output text)
BUCKET=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch7 --query "Stacks[0].Outputs[?OutputKey=='SiteBucketName'].OutputValue" --output text)
read -rs PW
aws cognito-idp admin-create-user --user-pool-id "$POOL" --username <employee-email> --user-attributes Name=email,Value=<employee-email> Name=email_verified,Value=true --message-action SUPPRESS
aws cognito-idp admin-set-user-password --user-pool-id "$POOL" --username <employee-email> --password "$PW" --permanent
aws cognito-idp admin-add-user-to-group --user-pool-id "$POOL" --username <employee-email> --group-name employee
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$SITE/ask" -H "content-type: application/json" -d '{"question": "hi"}'
aws s3 rm "s3://$BUCKET" --recursive
aws cloudformation delete-stack --stack-name helpdesk-dev-ch7
aws cloudformation wait stack-delete-complete --stack-name helpdesk-dev-ch7
```

The curl line with no token prints 401, because the API refuses it before any function runs. Sign
in through `/signin` for the token and try the calls in the README. After the wait finishes, the
stack is gone and nothing keeps costing money.
