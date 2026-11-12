# 02 - The sign-in function

## Goal

Write the one open function: it trades an email and password for an ID token and keeps the password out of every log and reply.

## Prompt

```text
Create app/signin/handler.py, then tests/test_signin.py with Cognito faked.

- Environment CLIENT_ID. Read "email" and "password" from the JSON body (400 for anything that is
  not two strings, a blank value, an email over 254 characters or a password over 256).
- Call cognito.initiate_auth with AuthFlow USER_PASSWORD_AUTH, the client id and the two values.
- NotAuthorizedException, UserNotFoundException and UserNotConfirmedException all give 401 with
  the same message, so a reply never says whether an account exists. Any other failure is 502 and
  the log holds the error class name only.
- Success returns 200 with only the IdToken and ExpiresIn. A challenge, such as a forced password
  change, or a reply with no token issues nothing (409). The access and refresh tokens are dropped.
- Send cache-control: no-store. Never log, store or return the password.
Tests: a good sign-in, each refusal, an outage, a challenge, bad input, and that the password and
token never appear in the log or the reply.
```

## Check

```bash
pytest -q tests/test_signin.py
grep -n "initiate_auth" app/signin/handler.py
```
