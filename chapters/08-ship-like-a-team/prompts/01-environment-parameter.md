# 01 - One template, an Environment parameter

## Goal

Make the template deployable twice, as staging and as prod, without the two stacks colliding.

## Prompt

```text
Edit template.yaml (replace session-07 with session-08 everywhere, including the tags).

- Add the parameter Environment: String, default dev, allowed values dev, staging and prod, and
  the parameter Project (the only allowed value is helpdesk, because the bootstrap roles are scoped
  to helpdesk-* names). Every resource name already follows ${Project}-${Environment}-<part>.
- Tag every taggable resource with project and environment as well as chapter.
- Give SiteBucket the BucketName ${Project}-${Environment}-site-${AWS::AccountId}-${AWS::Region},
  so each environment has its own bucket and a role can be given access by that name pattern.
- Add the parameter PermissionsBoundaryArn (default empty, accepts only a policy ARN) and a
  condition HasPermissionsBoundary; every AWS::IAM::Role gets PermissionsBoundary set from it
  (or no value when it is empty).
- Add the output EnvironmentName. Everything else stays as in chapter 7.
Add tests/test_environments_stack.py, which only reads the template: the parameter and its closed
list of values, the bucket name, the Project and Environment naming the functions, and that the chapter 7
resources are still there. Update tests/test_auth_stack.py for the new chapter tag.
```

## Check

```bash
cfn-lint template.yaml
pytest -q tests/test_environments_stack.py tests/test_auth_stack.py
grep -n "BucketName" template.yaml
```
