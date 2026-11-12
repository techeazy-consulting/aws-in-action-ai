# 05 - Set up GitHub, run it, roll back, delete

## Goal

Write the setup, first-run, rollback and teardown steps so a learner can do them in order.

## Prompt

```text
Rewrite README.md for chapter 8. Sections: what changed since chapter 7; one template, two
stacks; set it up once; the first run; roll back; run the tests; delete.

- Set up once: copy the chapter into the root of your own repository; find the start of the
  subject claim (the older form repo:OWNER/REPO and the newer form with numeric ids, and the OIDC
  debugger action to print one token); deploy deploy-role.yaml as a stack NOT named helpdesk-*
  with CAPABILITY_NAMED_IAM; create the staging and prod environments, add a required reviewer
  to prod and a main-only branch rule to BOTH, and say why (AWS can test only aud and sub from a
  GitHub token, so the branch cannot be checked in the trust policy); say this needs a public
  repository or a paid plan; add the five repository variables AWS_REGION, DEPLOY_ROLE_ARN,
  CFN_ROLE_ARN, PERMISSIONS_BOUNDARY_ARN, ESCALATION_EMAIL.
- The first run: staging deploys, prod waits for approval; what to do when one action is denied
  (add only that action, never a wildcard).
- Roll back: re-run the earlier run's jobs (same commit) or revert on main and push.
- Delete prod, then staging (empty each bucket first), then the bootstrap stack last.
No link, no account id, no email address, no time estimate in any file.
```

## Check

```bash
grep -n "required reviewer" README.md
grep -n "github-bootstrap" README.md
grep -n "delete-stack" README.md
```
