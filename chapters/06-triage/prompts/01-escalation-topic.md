# 01 - The escalation topic and the email address

## Goal

Add an SNS topic that emails the IT team, with the address passed in as a parameter and never written in a file.

## Prompt

```text
Extend template.yaml (chapter 5's stack). Change the chapter tag on every resource that supports
tags to session-06 and keep every chapter 5 resource and logical id.

- Add parameters Project (lowercase, default helpdesk) and Environment (dev, test or prod, default
  dev). Name every resource ${Project}-${Environment}-<part>, never from the stack name, keeping
  each existing <part>.
- Make ModelId a dropdown of amazon.nova-lite-v1:0 (the default) and amazon.nova-micro-v1:0, and
  add ModelRoute (auto, direct, us, eu, apac or ca) with the Region-to-route mapping from
  chapter 2 (already in chapter 5's stack). Every role that calls the model allows bedrock:InvokeModel on the chosen route
  only: for direct, the foundation model in this Region; for a profile, the profile in this
  Region plus the foundation model in every Region. Every MODEL_ID is the id the route gives,
  and the knowledge base call's MODEL_ARN is the profile ARN when a profile is used. Add the
  output ModelInUse.
- Tag every resource that supports tags with chapter, project and environment. Use no Retain
  deletion policy.

- Parameter EscalationEmail: a string with NO default and an AllowedPattern that accepts only
  something shaped like an email address. Parameter ServiceStatus: a string whose default is a
  small JSON object mapping service names to "up" or "down" (email, vpn, wiki, printing; vpn is
  "down" so the outage case can be tried).
- EscalationTopic (AWS::SNS::Topic), named ${Project}-${Environment}-escalations, tag chapter:
  session-06 with project and environment.
- EscalationSubscription (AWS::SNS::Subscription): the topic, protocol email, endpoint the
  EscalationEmail parameter.
- Outputs: EscalationTopicArn.
Never write a real email address in any file.
```

## Check

```bash
grep -n "AWS::SNS::Topic" template.yaml
grep -n "Protocol: email" template.yaml
cfn-lint template.yaml
```
