# Helpdesk code lab

The complete code for each hands-on chapter of the course. Every chapter folder is a full snapshot,
so you can start at any chapter without the ones before it.

## Three ways to use it

- **Watch.** The slides show short excerpts and name the file they come from. Follow along.
- **Copy and run.** Open a chapter folder, read its `README.md`, then run the tests, deploy,
  try it and delete the stack.
- **Build with an AI tool.** Open the chapter's `prompts/` folder, paste each prompt into your
  coding tool in order, and run that prompt's check before moving on. `prompts/CHECK.md` proves
  the whole chapter.

## Before you start

- Python 3.11 or newer, and `pip install -r requirements-dev.txt` for the offline checks.
- For the live steps only: an AWS account of your own, the AWS CLI signed in to it, and access to
  the model the chapter uses switched on in your account.

## Cost warning and teardown

The tests and `cfn-lint` run offline and cost nothing. Deploying creates real resources and every
model call is billed to your account. The endpoints are public until sign-in is added in a later
chapter, so they are throttled; do not leave them running. When you finish a chapter, delete its
stack and confirm the delete completed. Each chapter README gives the exact commands.
