# Chapter 3: the employee chat page

Everything from chapter 2 is still here, unchanged: the function, its tests and the throttled
`POST /ask` endpoint. This chapter adds a chat page that employees open in a browser.

## What changed since chapter 2

- `app/web/index.html` - the chat page: one file, no build step. It posts the question to `/ask`
  on its own address and shows the whole reply when it arrives. There is no streaming; the reply
  comes back in one piece.
- `tests/test_web.py` - tests for the page and for the new parts of the template. No AWS account
  needed.
- `template.yaml` - the chapter 2 stack plus a private S3 bucket for the page, an origin access
  control so only CloudFront can read it, a bucket policy that names this one distribution, and a
  CloudFront distribution. The distribution serves the page from the bucket and sends `/ask` to the
  API. Viewers who ask for plain HTTP are redirected to HTTPS.
- `prompts/` - one prompt per build step, in order, each with a check. `prompts/CHECK.md` holds
  the checks for the whole chapter.

## Why the page and the API share one address

The browser sees a single site. CloudFront answers `/` from the bucket and forwards `/ask` to the
API, so the page calls `/ask` without a full address and no cross-origin rules are needed.

The API behind CloudFront still has its own address from chapter 2, and it is still open to anyone
who finds it until sign-in is added in chapter 7. The stage throttle stays in place for that reason.

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
| A value from the Outputs tab (`SiteBucketName`, `ChatUrl`) | CloudFormation → Stacks → your stack → Outputs | 9. Copy a value from the Outputs tab |
| The page in the bucket | S3 → General purpose buckets → the bucket named by `SiteBucketName` in the stack's Outputs tab → Upload | Deploy below |


## Run the tests

```bash
pip install -r ../../requirements-dev.txt
pytest -q
cfn-lint template.yaml
```

Console route: open CloudShell (`Top navigation bar → CloudShell icon`), upload the code zip with
`Actions → Upload file`, unzip it, open this chapter's folder and run the same commands.

## Deploy

The live steps create real resources in your account and cost money. A new distribution needs a
while to finish deploying; the deploy command returns when the stack is ready.

Console route: `CloudFormation → Stacks → Create stack → With new resources (standard) → Upload a
template file → Choose file` and pick this folder's `template.yaml` from your computer. Name the
stack `helpdesk-dev-ch3`, leave `Project` as `helpdesk` and `Environment` as `dev`, tick `I acknowledge that this template may create IAM resources`, then
`Submit`. When it finishes, the `Outputs` tab shows `SiteBucketName` and `ChatUrl`. To put the page
in the bucket from the console: `S3 → General purpose buckets → the bucket → Upload → Add file`,
choose `app/web/index.html` from your computer, then `Open`. The object name is the file name, so
it is stored as `index.html`. To match the command's content type, open `Properties → Add metadata`,
set `Type` to `System defined`, `Key` to `Content-Type` and the value to `text/html`. Then choose
`Upload`. Do this before opening `ChatUrl`.

```bash
aws cloudformation deploy --stack-name helpdesk-dev-ch3 --template-file template.yaml --capabilities CAPABILITY_IAM --parameter-overrides Project=helpdesk Environment=dev
BUCKET=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch3 --query "Stacks[0].Outputs[?OutputKey=='SiteBucketName'].OutputValue" --output text)
SITE=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch3 --query "Stacks[0].Outputs[?OutputKey=='ChatUrl'].OutputValue" --output text)
aws s3 cp app/web/index.html "s3://$BUCKET/index.html" --content-type text/html
```

## Try it

Open the address in `$SITE` in a browser and ask a question. From the console, the same address is
the `ChatUrl` value in `CloudFormation → Stacks → helpdesk-dev-ch3 → Outputs`. From a terminal, the same address
serves the page, and `/ask` on it returns an answer.

```bash
echo "$SITE"
curl -s -o /dev/null -w "%{http_code}\n" "$SITE/"
curl -s -X POST "$SITE/ask" -H "content-type: application/json" -d '{"question": "How do I reset my password?"}'
```

The default model is Amazon Nova Lite. Most Regions serve it only through an inference profile, a
model id with a geography in front such as `apac.amazon.nova-lite-v1:0`; the template's
`ModelRoute` parameter, `auto` by default, picks the right one for your Region, and the stack's
`ModelInUse` output shows which id it chose. To change the model, update the stack and pick
another `ModelId` from the list; editing the function's `MODEL_ID` by hand fails, because the
role only allows the model the stack chose.

`Project` and `Environment` start every resource name (`helpdesk-dev-ask`), so one template
deploys once per environment: give each copy its own stack name and its own `Environment`.

A question may be at most 1000 characters.

## Delete

Empty the bucket first: a stack cannot delete a bucket that still holds files.

Console route: `S3 → General purpose buckets → select the bucket → Empty`, type the bucket name to
confirm, and choose `Empty`. Then `CloudFormation → Stacks → select helpdesk-dev-ch3 → Delete`, and
`Delete` again. A deleted stack leaves the list; `Filter status → Deleted` shows it with the status
`DELETE_COMPLETE`.

Once the bucket is empty, deleting the stack removes every resource it made: nothing in this
template is kept.

```bash
aws s3 rm "s3://$BUCKET" --recursive
aws cloudformation delete-stack --stack-name helpdesk-dev-ch3
aws cloudformation wait stack-delete-complete --stack-name helpdesk-dev-ch3
```
