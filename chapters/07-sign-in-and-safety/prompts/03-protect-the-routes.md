# 03 - The authorizer, the sign-in route and the caller check

## Goal

Put a JWT authorizer in front of the three model routes and make each function read and validate who is calling.

## Prompt

```text
Extend template.yaml and the three model handlers.

- HelpdeskAuthorizer: an AWS::ApiGatewayV2::Authorizer named ${Project}-${Environment}-cognito, of type JWT, identity source the
  Authorization header, audience the app client, issuer this user pool in this region.
- Add AuthorizationType JWT and the authorizer to the /ask, /tickets and /triage routes. Add
  SigninFunction (named ${Project}-${Environment}-signin; log group, role that may only write its own logs, function with CLIENT_ID,
  integration, permission), a POST /signin route with no authorizer, a /signin CloudFront
  behavior, and a tighter route throttle for POST /signin in the stage. Output SigninUrl.
- In each of the three handlers add caller(event): read requestContext.authorizer.jwt.claims; it
  returns None unless token_use is "id", sub looks like a UUID and cognito:groups holds at least
  one of "employee" and "it-staff" (read it as a list, and also as a string such as
  "[employee it-staff]"; drop unknown names; keep an email claim only when email_verified is true or the string "true", it is printable text
  and it is at most 254 characters; the user id is the identity). The handler answers 403 when caller() is None.
- Add SigninFunction: app/signin/handler.py to code-lab.yaml under inline:.
Tests (tests/test_auth.py, tests/test_auth_stack.py): refused with no claims, an access token, a
bad subject and unknown groups, for all three handlers; both group shapes; the template routes.
```

## Check

```bash
cfn-lint template.yaml
pytest -q tests/test_auth.py tests/test_auth_stack.py
grep -n "AuthorizationType: JWT" template.yaml
```
