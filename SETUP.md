# Setup: do the live steps from the AWS console

This page gets a beginner from "I have an AWS account" to "I deployed a chapter and deleted it
again", using the browser. You do not install anything on your own computer. Every chapter README
has a `## Before you try` table that points back to a numbered section here.

Console paths are written as `Service → page → button`. AWS changes screens from time to time; if a
label differs, look for the closest match and read the page that AWS shows.

**Cost.** The offline tests cost nothing. Deploying creates real resources and each model call is
billed to your account, so finish every chapter by deleting its stack (section 8).

## 1. Sign in with a user that is not the root user

AWS recommends against using the root user for everyday tasks and suggests keeping it for creating
your first user. Sign in as a person-sized user instead.

1. If your organisation gave you a sign-in address for IAM Identity Center, paste it into your
   browser, sign in, and pick the account you were assigned in the AWS access portal.
2. Otherwise, open the AWS sign-in page, choose `IAM user`, enter the account alias or account ID,
   choose `Next`, then enter your user name and password and choose `Sign in`.
3. If you have only the root user, ask whoever manages the account for a user, or create one.
   AWS recommends IAM Identity Center for people and keeps IAM users for specific cases it does not
   suit. The user needs permission to create the resources a chapter's template describes; the
   table below lists them chapter by chapter.

**Do every chapter's steps as an IAM user or an IAM Identity Center user, not as the root user.**
AWS says to create an administrative user for everyday tasks instead of using the root user. In one
run of this course, a chapter 4 Bedrock step done as the root user stopped with a message like this
one (the account number is replaced):

```
AccessDeniedException ... User: arn:aws:iam::<account-id>:root is not authorized to perform: bedrock:StartIngestionJob
```

AWS access-denied messages mostly begin `User:` followed by who was denied, then the action. If you
see one in the console, AWS says to ask your administrator for the missing permission. Check the top
bar of the console: it should show a user name, not only the account.

### What each chapter's stack creates

Each row lists what the chapter adds to the chapter before it, read from that chapter's
`template.yaml`. The user you sign in with, or your administrator, must be allowed to create these
services. Beyond them, AWS says that someone who creates or deletes a stack needs permissions for
CloudFormation and for the services in the template, and that the CloudFormation console also needs
Amazon S3 permissions to upload a template file.

| Chapter | Adds | Services |
|---|---|---|
| 2 | The first answer | Lambda function, API Gateway HTTP API, IAM role, CloudWatch Logs log group |
| 3 | The chat page | Amazon S3 bucket, CloudFront distribution |
| 4 | The knowledge base | Amazon S3 Vectors bucket and index, Amazon Bedrock knowledge base and data source |
| 5 | Tickets | DynamoDB table |
| 6 | Triage | SNS topic and email subscription |
| 7 | Sign-in and safety | Cognito user pool, groups and app client, Bedrock guardrail, API Gateway authorizer |
| 8 | Ship like a team | A second stack, `github-bootstrap`: IAM OIDC provider, permissions boundary and IAM roles that have set names |
| 9 | Run it | CloudWatch alarms, dashboard and metric filters, and the same bootstrap stack again |

## 2. Pick a Region

A Region is a geographic area where your resources live. Resources are specific to the Region they
were created in, so if a stack seems to be missing later, check the Region first.

1. In the console, `top navigation bar → the name of the current Region → the Region you want`.
2. Choose a Region that offers Amazon Bedrock with the model you will use, and, for chapters 4 to 9,
   Amazon S3 Vectors as well (each of those stacks creates an S3 Vectors bucket). US East (N. Virginia), `us-east-1`, is on the S3 Vectors Regions list,
   and Amazon Nova Lite is supported there. Most Regions serve a model only through an inference
   profile, the model id with a geography in front such as `us.` or `apac.`. Calling the plain id
   there fails with "on-demand throughput isn't supported"; waiting does not fix it. The chapter 2
   to 9 templates pick the route for your Region (`ModelRoute`, `auto`).
3. To check another Region: for Bedrock, `Amazon Bedrock → Model catalog`, open the model's page
   and read its Regional availability table; for S3 Vectors, read its Regions list in the S3
   documentation.
4. Use the same Region for every console page in the chapter: CloudFormation, CloudShell, Bedrock
   and S3 all show the Region you have selected.

## 3. Set a budget alert

An alert tells you when spending passes a limit you choose. It warns you; it does not stop spending.

1. `Billing and Cost Management → Budgets → Create budget`.
2. Under `Budget setup`, choose `Use a template (simplified)`.
3. Pick `Monthly cost budget`, which notifies you if you exceed, or are forecast to exceed, the
   amount you set. `Zero spend budget` notifies you once spending goes past the Free Tier limits.
4. Update the template's details and settings with a small amount you are comfortable with.
5. Choose `Create budget`.

## 4. Make sure the model is available to your account

1. `Amazon Bedrock → Model catalog`, then choose the model the chapter uses. Chapter 2's default is
   Amazon Nova Lite; chapters 3 to 9 default to it too. Open it in the playground and send one short message to confirm it answers.
2. For Amazon models there is no separate access request: AWS says that access to many Bedrock
   models is on by default, and that Amazon's models are not sold through AWS Marketplace.
3. In commercial Regions the `Bedrock configurations → Model access` page is not where you ask for
   access; AWS says it applies to AWS GovCloud (US).
4. If you switch the chapter to an Anthropic model, a one-time form comes first. AWS says Anthropic
   asks first-time customers for use case details before the model is invoked, once per account or
   once at the organisation's management account:
   1. `Amazon Bedrock → Model catalog → an Anthropic model → open in the playground`, then
      complete the form. It asks for a description of your intended use and a website address; an
      individual may give a personal portfolio or project page.
   2. If the management account of your organisation has already submitted these details, you can
      use Anthropic models right away.
   3. The agreement can stay pending after you submit. Until AWS emails you that it finished,
      calls can still be refused with `AccessDeniedException`.
5. The user you sign in with may also need AWS Marketplace permissions the first time a
   Marketplace-sold model is used in the account.
6. Chapters 4 to 9 also use an embedding model, which turns the policy pages into numbers the
   knowledge base can search. The model is Amazon Titan Text Embeddings V2. To see it, open
   `Amazon Bedrock → Model catalog` and look for it among the Amazon models; AWS lists it as one of
   the Amazon Titan Embeddings models and says it is optimized for text retrieval. It is an Amazon
   model, so the Marketplace note above does not apply to it. Check that the Region you chose
   (section 2) offers it, in the same way as for the chat model.

## 5. Open CloudShell

CloudShell is a terminal in your browser. The credentials you used to sign in to the console are
available in it, so you do not set up the AWS command line yourself, and the AWS CLI is already
installed. It also has Python 3, `pip`, `git`, `zip`, `unzip` and `make`. AWS makes CloudShell
available at no additional charge; you still pay for the resources you create with it.

1. Choose the Region first (section 2).
2. `Top navigation bar → CloudShell icon`. You can also type `CloudShell` in the search box and
   choose it.
3. Wait for the command prompt. The shell is ready when it appears.
4. Your home directory keeps up to 1 GB of files per Region between sessions. A session you leave
   idle stops by itself; reopen CloudShell and your home directory is still there.

## 6. Put the code in CloudShell

You need the chapter folders in two places: on your own computer (the CloudFormation console uploads
`template.yaml` from there, section 7) and in CloudShell (to run the tests and the commands).

1. Download the code zip from your course page and unzip it on your computer.
2. In CloudShell, `Actions → Upload file → Browse → choose the zip → Upload`. The file lands in your
   home directory.
3. At the prompt, run `unzip` on the file you uploaded. The chapters appear under `chapters/`, each
   with its own `README.md` and `template.yaml`.
4. Or, instead of the upload, use `git clone` with the code link from your course page, because
   `git` is installed in CloudShell.
5. To run the offline checks in CloudShell, open the chapter folder, then follow `## Run the tests`
   in its README.

## 7. Deploy a chapter from the CloudFormation console

1. `CloudFormation → Stacks → Create stack → With new resources (standard)`. Check that the Region in
   the top navigation bar is the one you chose.
2. Under `Prerequisite - Prepare template`, choose `Choose an existing template`. Under
   `Specify template`, choose `Upload a template file → Choose file`, and pick the chapter's
   `template.yaml` from your computer. The file comes from your own computer, so download and
   unzip the code first (section 6). It must be 1 MB or smaller. Choose `Next`.
3. On `Specify stack details`, type the stack name the chapter README gives (for example
   `helpdesk-ch2`). A stack name may contain only letters, digits and hyphens. The `Parameters`
   section is where you give the values the template asks for. Leave the others as they are, and
   fill in these:
   - Chapters 6 to 9: `EscalationEmail`, an address you can read. The chapter README says that
     AWS sends it a message you confirm.
   - The `github-bootstrap` stack in chapters 8 and 9: `GitHubSubjectPrefix`, which the chapter
     README tells you how to build. That stack uses the `deploy-role.yaml` file in the chapter
     folder, not `template.yaml`.

   Choose `Next`.
4. On `Configure stack options`, keep the defaults. Under `Capabilities`, tick
   `I acknowledge that this template may create IAM resources`. The chapter templates create a role,
   which is why CloudFormation asks. The chapter 8 and 9 `github-bootstrap` stack gives its IAM
   resources set names, and AWS says a template with custom names for IAM resources needs the
   named-IAM capability, `CAPABILITY_NAMED_IAM` on the command line. In the console, tick every
   acknowledgement box the `Capabilities` section shows for that stack. Choose `Next`.
5. On `Review and create`, check the details and choose `Submit`.
6. Open the `Events` tab to watch progress until the stack finishes creating.
7. Open the `Outputs` tab. It lists the values the template declares, such as the address to call
   (`AskUrl`) or the chat page address (`ChatUrl`) and the bucket name (`SiteBucketName`). The
   chapter README says which one to use.
8. If creation fails, read the `Events` tab for the reason before you try again.

## 8. Delete a chapter's stack and confirm it is gone

1. If the chapter put files in a bucket, empty it first, because a stack cannot delete a bucket
   that still holds files: `S3 → General purpose buckets → select the bucket named in the Outputs tab → Empty`, type
   the bucket name to confirm, and choose `Empty`. AWS says all objects in a bucket must be deleted
   before the bucket itself can be.
2. `CloudFormation → Stacks → choose the stack → Delete`, and choose `Delete` again when asked. A
   delete cannot be stopped once it has begun.
3. Watch the stack's status in `Events`: it moves to `DELETE_IN_PROGRESS`.
4. Confirm it is gone. AWS hides stacks in `DELETE_COMPLETE` by default, so the stack disappears
   from the `Stacks` list. To see it, use `Filter status → Deleted`.
5. If the status becomes `DELETE_FAILED`, choose the stack and `Retry delete`, then read the
   `Events` tab for the resource that would not delete. Do not leave a failed delete: the resources
   keep costing money.

## 9. Copy a value from the Outputs tab

An **Output** is a value a template hands back once the stack is built, such as a bucket name, a web
address or an id. AWS describes it as a convenient way to capture important details about your
resources. Later steps, and the slides, use these values, so you copy them from here.

1. `CloudFormation → Stacks → choose your stack → Outputs`. Check the Region in the top navigation
   bar first. Output values are available after the stack operation is complete, so wait until the
   stack has finished creating.
2. Find the row by its `Key` (for example `SiteBucketName`) and copy its `Value`.
3. In CloudShell, the same value comes from the stack with one command. Replace `<stack>` with your
   stack name and `<Key>` with the output's key:

   ```
   NAME=$(aws cloudformation describe-stacks --stack-name <stack> --query "Stacks[0].Outputs[?OutputKey=='<Key>'].OutputValue" --output text)
   ```

   `--query` filters the answer on your side, and `OutputValue` is the value that goes with the
   `OutputKey`. Check it with `echo "$NAME"`.
4. A variable you set in CloudShell belongs to that shell session. AWS says data in your home
   directory persists between sessions, and a session also ends after a period without activity,
   so treat the variable as gone when the session ends. Run the line again in the new session.
5. The slides write a name such as `$BUCKET` and say where it comes from. For example,
   `$BUCKET` means: Outputs tab → `SiteBucketName`. A `Values:` line under a code block gives each
   name this way.
