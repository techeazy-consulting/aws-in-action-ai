# Chapter 5: tickets through tool use

Everything from chapter 4 is still here: the private bucket, the CloudFront address, the policy
pages and the knowledge base behind `/ask`. This chapter adds a second endpoint, `/tickets`, where
the model can open a ticket or look one up. The model does not touch the table. It asks, your
function runs the tool, and the result goes back to the model, which writes the reply.

## Before you try

The offline checks below need no AWS account. The live steps need the setup in this table. Console
routes here are written `Service → page → button`; the full numbered steps are in `SETUP.md` at
the top of the course repository. The setup and the live steps can be done from the console plus
CloudShell, except sending the messages, which needs `curl` in CloudShell because a POST has no
console route.

| What you need | Where in the console | `SETUP.md` section |
|---|---|---|
| A user that is not the root user | Sign in with an administrative or IAM user, not the root user | `## 1. Sign in with a user that is not the root user` |
| A Region offering Amazon Bedrock and S3 Vectors | Region menu in the top bar | `## 2. Pick a Region` |
| A budget alert | Billing and Cost Management → Budgets | `## 3. Set a budget alert` |
| The models available to your account | Amazon Bedrock → Model catalog | `## 4. Make sure the model is available to your account` |
| A terminal | CloudShell icon in the top bar | `## 5. Open CloudShell` |
| The code in CloudShell | CloudShell → Actions → Upload file | `## 6. Put the code in CloudShell` |
| Deploy the stack | CloudFormation → Stacks → Create stack | `## 7. Deploy a chapter from the CloudFormation console` |
| Copy a value from the Outputs tab | CloudFormation → Stacks → your stack → Outputs | `## 9. Copy a value from the Outputs tab` |
| Delete the stack | CloudFormation → Stacks → Delete | `## 8. Delete a chapter's stack and confirm it is gone` |

**Not the root user.** Do the live steps as an IAM or IAM Identity Center user. A Bedrock step done
as the root user can stop with `AccessDeniedException ... :root is not authorized to perform ...`.
`SETUP.md` section 1 explains how to sign in as a user and lists the services each chapter's stack
needs permission for.

This chapter adds three things to check:

- **A Region with both services.** The stack still holds chapter 4's knowledge base, which stores
  its vectors in S3 Vectors and embeds the pages with Amazon Titan Text Embeddings V2. Pick a Region
  where Amazon Bedrock and S3 Vectors are both offered, and check that the embedding model is
  shown in Amazon Bedrock → Model catalog.
- **A model with tool use.** Amazon Nova Lite (the default) and Amazon Nova Micro list client-side
  tool calling as supported; see Models below. Check the one you use in Amazon Bedrock → Model
  catalog.
- **Made-up test messages.** The `/tickets` address has no sign-in until chapter 7, so type no real
  names or problems.

## Public until sign-in

`/tickets` has no sign-in. Anyone who has the address can open tickets and look up any ticket
number, and each message is billed to your account. Sign-in arrives in chapter 7. Until then:
keep the stage throttle in the template, do not put real names or real problems in a test
message, and delete the stack as soon as you have finished testing. The function protects what
it can: a ticket number must be 4 to 9 digits, the table and key are fixed in code and never
chosen by the model, and a status lookup returns only the number, title and status (never who
asked).

## What changed since chapter 4

- `app/tickets/handler.py` - the new function. It sends two tool descriptions to the model with
  the Converse API (`toolConfig`). When the model stops with `tool_use`, the function runs each
  requested tool and sends the results back in one user message, then asks the model again.
  The reply is `{"answer": "...", "tools_used": ["create_ticket"]}`.
- `create_ticket` needs a title and the name of the person asking. `get_ticket_status` needs a
  ticket number. A missing detail, an unknown ticket and a table failure all go back to the model
  as an error result, so it can ask the person or apologise. None of them crash the request.
- Ticket numbers are readable: 1001, 1002, and so on. A counter item in the same table hands them
  out. The counter adds without a guard against repeats, so a retried call could skip a number.
  That is fine for a demo and is not fine for money; the ticket itself is saved with a guard so
  one number can never be written twice.
- A request stops after three model calls and returns an error, so a model that keeps asking for
  tools cannot run up the bill.
- `tests/test_tickets.py` and `tests/test_tickets_stack.py` - the new tests. The model and the
  table are faked, so no test needs an AWS account. The chapter 4 tests still pass;
  `tests/test_web.py` now counts one redirect rule per path instead of a fixed number, so a new
  path does not break it.
- `template.yaml` - the chapter 4 stack plus a DynamoDB table billed per request, the tickets
  function with permission to get, put and update items in that one table, the `POST /tickets`
  route and a CloudFront path for it. The chat page is unchanged; use `curl` for tickets.
- `prompts/` - one prompt per build step, in order, each with a check. `prompts/CHECK.md` holds
  the checks for the whole chapter.

## Models

The functions call the model in the `ModelId` parameter (Amazon Nova Lite by default, which lists
client-side tool calling as supported; the list also offers Nova Micro). A model without tool use
with the Converse API fails the request, so keep to the list. The `status` field on an error
result is only supported by some model families, so check yours before relying on it.

Most Regions serve the model only through an inference profile, a model id with a geography in
front such as `apac.amazon.nova-lite-v1:0`; the template's `ModelRoute` parameter, `auto` by
default, picks the right one for your Region, and the stack's `ModelInUse` output shows which id
it chose. The `/ask` function sends the matching profile ARN to the knowledge base, so one
setting reaches the functions that call the model. To change the model, update the stack and
pick another `ModelId` from the list; editing a function's `MODEL_ID` or `MODEL_ARN` by hand
fails, because the role only allows the model the stack chose.

`Project` and `Environment` start every resource name (`helpdesk-dev-ask`), so one template
deploys once per environment: give each copy its own stack name and its own `Environment`.

## Run the tests

```bash
pip install -r ../../requirements-dev.txt
pytest -q
cfn-lint template.yaml
```

## Deploy

The live steps create real resources in your account and cost money: every message calls the
model, usually twice.

```bash
aws cloudformation deploy --stack-name helpdesk-dev-ch5 --template-file template.yaml --capabilities CAPABILITY_IAM --parameter-overrides Project=helpdesk Environment=dev
BUCKET=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch5 --query "Stacks[0].Outputs[?OutputKey=='SiteBucketName'].OutputValue" --output text)
SITE=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch5 --query "Stacks[0].Outputs[?OutputKey=='ChatUrl'].OutputValue" --output text)
TICKETS=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch5 --query "Stacks[0].Outputs[?OutputKey=='TicketsUrl'].OutputValue" --output text)
TABLE=$(aws cloudformation describe-stacks --stack-name helpdesk-dev-ch5 --query "Stacks[0].Outputs[?OutputKey=='TicketsTableName'].OutputValue" --output text)
aws s3 cp app/web/index.html "s3://$BUCKET/index.html" --content-type text/html
aws s3 cp app/policies "s3://$BUCKET/policies" --recursive --content-type text/html
```

The last two lines put the chat page and the policy pages in the bucket. The tickets route needs
neither: they matter when you also want the chat page or `/ask` to work. Chapter 4's knowledge
base sync is only needed if you also want `/ask` to answer from the pages.

**Console route.**

1. CloudFormation → Stacks → Create stack → With new resources (standard) → Upload a template
   file, and choose `template.yaml`. Name the stack `helpdesk-dev-ch5`, leave `Project` as
   `helpdesk` and `Environment` as `dev` on the stack details page, tick the box that says the
   template may create IAM resources, and choose Submit.
2. When the stack is complete, open its Outputs tab and note `TicketsUrl`, `TicketsTableName` and
   `SiteBucketName`.
3. If you want the chat page or `/ask` to work: S3 → Buckets → the `SiteBucketName` bucket → Upload →
   Add file (`app/web/index.html`) or Add folder (`app/policies`), as in chapter 4.

## Try it

Sending a message is a POST to an address, which the console cannot do, so use `curl` in CloudShell.

```bash
curl -s -X POST "$TICKETS" -H "content-type: application/json" -d '{"message": "Please request Figma access for me. My name is Priya."}'
curl -s -X POST "$TICKETS" -H "content-type: application/json" -d '{"message": "What is the status of ticket 1001?"}'
curl -s -X POST "$TICKETS" -H "content-type: application/json" -d '{"message": "I need a new monitor."}'
```

The first reply gives a ticket number, and `tools_used` lists `create_ticket`. The second reports the
ticket as open. The third leaves out who is asking, so the model should ask for a name instead of
opening a ticket. A message may be at most 1000 characters. The API is still open to anyone who has
its address until sign-in is added in chapter 7, so the stage throttle stays.

To look around the demo table, use the console or CloudShell. Console route: DynamoDB → Tables →
your table (the `TicketsTableName` output) → Explore table items. The ticket and the `counter` item
are listed under Items returned. From CloudShell:

```bash
aws dynamodb scan --table-name "$TABLE"
```

## Delete

Empty the bucket first: a stack cannot delete a bucket that still holds files. Deleting the stack
removes the table and its tickets, the knowledge base and its vectors. Deleting the stack removes
every resource it made: nothing in this template is kept.

```bash
aws s3 rm "s3://$BUCKET" --recursive
aws cloudformation delete-stack --stack-name helpdesk-dev-ch5
aws cloudformation wait stack-delete-complete --stack-name helpdesk-dev-ch5
```

**Console route.**

1. S3 → General purpose buckets → select the site bucket → Empty, type the bucket name, and choose
   Empty. Emptying cannot be undone.
2. CloudFormation → Stacks → select `helpdesk-dev-ch5` → Delete → confirm Delete.
3. Wait for the status to leave `DELETE_IN_PROGRESS`. Deleted stacks are hidden from the list by
   default; set the Filter status to Deleted to see it.
