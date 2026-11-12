# 01 - The tickets table

## Goal

Add a DynamoDB table that holds the tickets, billed per request so an idle table costs nothing.

## Prompt

```text
Extend template.yaml (chapter 4's stack). Change the chapter tag on every resource that supports
tags to session-05 and keep every chapter 4 resource and logical id.

- Add parameters Project (lowercase, default helpdesk) and Environment (dev, test or prod, default
  dev). Name every resource ${Project}-${Environment}-<part>, never from the stack name, keeping
  each existing <part>.
- Make ModelId a dropdown of amazon.nova-lite-v1:0 (the default) and amazon.nova-micro-v1:0, and
  add ModelRoute (auto, direct, us, eu, apac or ca) with the Region-to-route mapping from
  chapter 2. Every role that calls the model allows bedrock:InvokeModel on the chosen route
  only: for direct, the foundation model in this Region; for a profile, the profile in this
  Region plus the foundation model in every Region. Every MODEL_ID is the id the route gives,
  and the knowledge base call's MODEL_ARN is the profile ARN when a profile is used. Add the
  output ModelInUse.
- Tag every resource that supports tags with chapter, project and environment. Use no Retain
  deletion policy.

- TicketsTable (AWS::DynamoDB::Table): billing mode PAY_PER_REQUEST, one string attribute
  TicketId as the partition key, no sort key, no deletion protection, tag chapter: session-05 with project and environment.
- Output TicketsTableName with the table name.
Do not add anything else yet.
```

## Check

```bash
grep -n "AWS::DynamoDB::Table" template.yaml
grep -n "PAY_PER_REQUEST" template.yaml
cfn-lint template.yaml
```
