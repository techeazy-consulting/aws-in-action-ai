# 06 - Teardown that lists every stack

## Goal

Write the README so a learner reads the logs, tests the alarm, and deletes every stack, the bootstrap one last, then proves the account is clean.

## Prompt

```text
Rewrite README.md for chapter 9. Sections: what changed since chapter 8; read the logs (two Logs
Insights queries); tokens per request (the logs for tickets and triage; the Bedrock runtime
metrics count model calls by model, and do not claim they include the knowledge base answers); cost per ticket (the formula, the command, no price); the
dashboard and the alarms (test with set-alarm-state); the quality check (what it proves and what
it does not); the voice teaser (slides only, nothing here); run the tests; tear it all down.
- Tear down: prod, then staging (empty each site bucket first), then the github-bootstrap stack
  last. Then three commands that must print nothing: list-stacks with a status filter for stacks
  named helpdesk- or github-bootstrap, describe-alarms with the helpdesk- prefix, and
  describe-log-groups with the /aws/lambda/helpdesk- prefix.
- Say what stays outside AWS (GitHub environments, variables, the code) and that the bootstrap
  stack may hold the account's only GitHub provider.
No link, no account id, no email address, no time estimate in any file.
```

## Check

```bash
grep -n "github-bootstrap" README.md
grep -n "list-stacks" README.md
grep -n "describe-alarms" README.md
```
