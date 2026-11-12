# 03 - The stack: function, role and logs

## Goal

Describe the function, its log group and a role that may only write its logs and call the chosen model.

## Prompt

```text
Create template.yaml, an AWS CloudFormation template (YAML) for the helpdesk.

- Parameters Project (lowercase, default helpdesk) and Environment (dev, test or prod, default dev).
  Name every resource ${Project}-${Environment}-<part>, never from the stack name.
- Parameter ModelId, a dropdown of amazon.nova-lite-v1:0 (the default) and amazon.nova-micro-v1:0.
- Parameter ModelRoute: auto (the default), direct, us, eu, apac or ca. Most Regions serve a model
  only through an inference profile, the model id with a geography in front. Add a mapping from
  Region to route (from the Nova Lite page's Regional availability table) that auto uses.
- A log group for the function with RetentionInDays set to 7.
- An IAM role the Lambda service can assume, with one inline policy allowing only
  logs:CreateLogStream and logs:PutLogEvents on that log group, and bedrock:InvokeModel on the
  chosen model only: for direct, the foundation model in this Region; for a profile, the profile
  in this Region plus the foundation model in every Region (the profile may route to any of
  them). Build ARNs from pseudo parameters; write no account id.
- A Lambda function on python3.13, handler index.handler, 30 second timeout, 256 MB, with MODEL_ID
  set to the id the route gives (the model id, or the profile id), using that log group. Put the code of app/ask/handler.py inline in the
  Code ZipFile property, byte for byte.
- Tag every resource that supports tags with chapter: session-02, project and environment. Add an output ModelInUse. Use no Retain deletion policy.
```

## Check

```bash
cfn-lint template.yaml
```
