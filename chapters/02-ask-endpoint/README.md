# Chapter 2: the helpdesk's first answer

This is the first code chapter, so everything here is new: a function that sends a question to a
hosted model and returns the answer, and a public endpoint in front of it.

## What is in this folder

- `app/ask/handler.py` - the function. It checks the question, calls the model through the
  Converse API and returns the answer.
- `tests/test_ask.py` - tests with a fake model. They need no AWS account.
- `template.yaml` - the CloudFormation stack: function, log group, a role that may only write its
  logs and call the chosen model, and a throttled HTTP endpoint at `POST /ask`.
- `prompts/` - one prompt per build step, in order, each with a check. `prompts/CHECK.md` holds
  the checks for the whole chapter.

## Before you try

The live steps need a few things set up once. Each row points at a numbered section of `SETUP.md`
at the top of the code lab, which walks through it in the console.

**Do not use the root user.** Sign in as an IAM or IAM Identity Center user. As the root user, a
step can stop with `AccessDeniedException ... :root is not authorized`; the full message and what to
do are in `SETUP.md` section 1.

| What you need | Where in the console | `SETUP.md` section |
| --- | --- | --- |
| A user that is not the root user | The AWS sign-in page, or your IAM Identity Center sign-in address | 1. Sign in with a user that is not the root user |
| A Region with Amazon Bedrock that this template lists (its `RegionRoute` mapping) | Top navigation bar → the Region name | 2. Pick a Region |
| A budget alert | Billing and Cost Management → Budgets → Create budget | 3. Set a budget alert |
| The model available to your account | Amazon Bedrock → Model catalog → the model | 4. Make sure the model is available to your account |
| A terminal in the browser | Top navigation bar → CloudShell icon | 5. Open CloudShell |
| The code in CloudShell | CloudShell → Actions → Upload file | 6. Put the code in CloudShell |
| Deploy and delete from the console | CloudFormation → Stacks | 7. Deploy a chapter from the CloudFormation console; 8. Delete a chapter's stack and confirm it is gone |
| A value from the Outputs tab (`AskUrl`) | CloudFormation → Stacks → your stack → Outputs | 9. Copy a value from the Outputs tab |


## Run the tests

```bash
pip install -r ../../requirements-dev.txt
pytest -q
cfn-lint template.yaml
```

Console route: open CloudShell (`Top navigation bar → CloudShell icon`), upload the code zip with
`Actions → Upload file`, unzip it, open this chapter's folder and run the same commands.

## Deploy

The live steps create real resources in your account and cost money.

Console route: `CloudFormation → Stacks → Create stack → With new resources (standard) → Upload a
template file → Choose file` and pick this folder's `template.yaml` from your computer. Name the
stack `helpdesk-dev-ch2`, leave `Project` as `helpdesk` and `Environment` as `dev`, tick `I acknowledge that this template may create IAM resources`, then
`Submit`. When it finishes, the `Outputs` tab shows `AskUrl`.

```bash
aws cloudformation deploy --stack-name helpdesk-dev-ch2 --template-file template.yaml --capabilities CAPABILITY_IAM --parameter-overrides Project=helpdesk Environment=dev
API_URL=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch2 --query "Stacks[0].Outputs[?OutputKey=='AskUrl'].OutputValue" --output text)
```

## Try it

Console route: copy the `AskUrl` value from `CloudFormation → Stacks → helpdesk-dev-ch2 → Outputs`.
Sending a question has no console route, because the endpoint takes a POST: in CloudShell, run the
command below with that value in place of `$API_URL`.

```bash
curl -s -X POST "$API_URL" -H "content-type: application/json" -d '{"question": "How do I reset my password?"}'
```

To read the function's log, open `CloudWatch → Logs → Log groups → /aws/lambda/helpdesk-dev-ask`,
then the newest log stream (the menu may read `Log Management`). From CloudShell:

```bash
aws logs tail /aws/lambda/helpdesk-dev-ask --since 5m
```

The default model is Amazon Nova Lite. Most Regions serve it only through an inference profile, a
model id with a geography in front such as `apac.amazon.nova-lite-v1:0`; the template's
`ModelRoute` parameter, `auto` by default, picks the right one for your Region, and the stack's
`ModelInUse` output shows which id it chose. To change the model, update the stack and pick
another `ModelId` from the list; editing the function's `MODEL_ID` by hand fails, because the
role only allows the model the stack chose.

`Project` and `Environment` start every resource name (`helpdesk-dev-ask`), so one template
deploys once per environment: give each copy its own stack name and its own `Environment`.

The stage allows a burst of 5 requests and 1 per second,
and a question may be at most 1000 characters, because the endpoint is open to anyone who has the
address until sign-in is added in chapter 7.

## Delete

Console route: `CloudFormation → Stacks → select helpdesk-dev-ch2 → Delete`, then `Delete` again. A
deleted stack leaves the list; `Filter status → Deleted` shows it with the status `DELETE_COMPLETE`.

Deleting the stack removes every resource it made: nothing in this template is kept.

```bash
aws cloudformation delete-stack --stack-name helpdesk-dev-ch2
aws cloudformation wait stack-delete-complete --stack-name helpdesk-dev-ch2
```
