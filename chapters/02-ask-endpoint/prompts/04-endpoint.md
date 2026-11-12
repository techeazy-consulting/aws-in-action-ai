# 04 - The public endpoint, throttled

## Goal

Put an HTTP API in front of the function and cap its request rate, because anyone with the address can call it.

## Prompt

```text
Extend template.yaml with a public HTTP endpoint.

- An API Gateway HTTP API (AWS::ApiGatewayV2::Api, protocol HTTP).
- An AWS_PROXY integration to the function with payload format 2.0, and a route POST /ask to it.
- The $default stage with auto deploy, and default route settings that limit requests to a burst
  of 5 and a steady rate of 1 per second, so a leaked address cannot run up a bill. Add a comment
  saying the endpoint stays open until sign-in is added in chapter 7.
- A Lambda permission letting API Gateway invoke the function, scoped to this API's POST /ask
  route (use the account id pseudo parameter, never a number).
- An output AskUrl with the full address of the /ask route.
```

## Check

```bash
cfn-lint template.yaml
grep -n "ThrottlingRateLimit\|ThrottlingBurstLimit" template.yaml
pytest -q
```
