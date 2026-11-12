# 01 - The user pool and the two groups

## Goal

Create the Cognito user pool, an app client the sign-in function can use, and the employee and it-staff groups.

## Prompt

```text
Extend template.yaml.

- HelpdeskUserPool (AWS::Cognito::UserPool): sign in with the email address, users created by the
  administrator only (AllowAdminCreateUserOnly), password minimum length 12, the chapter tag set
  through UserPoolTags (this resource type names its tags that way).
- The pool auto-verifies email and requires verification before an email change takes effect
  (AutoVerifiedAttributes, UserAttributeUpdateSettings).
- HelpdeskUserPoolClient: ReadAttributes email, email_verified, name; WriteAttributes name only (left
  unset, every standard attribute, email included, is writable); no client secret, explicit flows ALLOW_USER_PASSWORD_AUTH and
  ALLOW_REFRESH_TOKEN_AUTH only, PreventUserExistenceErrors ENABLED.
- EmployeeGroup (GroupName employee) and ITStaffGroup (GroupName it-staff). No IAM role on either:
  these groups carry no AWS permissions, only a name the code reads.
- Outputs UserPoolId and UserPoolClientId.
Name the pool ${Project}-${Environment}-users and the client ${Project}-${Environment}-chat (the
Project and Environment parameters, never the stack name). Tag everything that supports tags with
chapter: session-07, project and environment (replace session-06 everywhere).
```

## Check

```bash
cfn-lint template.yaml
grep -n "AllowAdminCreateUserOnly\|GroupName" template.yaml
```
