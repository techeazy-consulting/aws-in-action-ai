# 02 - Tests that need no cloud

## Goal

Prove the handler's behaviour with a fake model, so the tests run without an AWS account.

## Prompt

```text
Create tests/test_ask.py with pytest tests for app/ask/handler.py. Load the module from its file
path with boto3 replaced by a fake, and set MODEL_ID in the test, so nothing reaches AWS and no
credentials are needed. Replace the module's `bedrock` client with a fake whose `converse` method
records its arguments and returns a canned answer, or raises to simulate a failure.

Cover:
- a good question returns 200 with the answer, and the Converse call carries the model id, the
  system prompt and the user's text;
- an empty, blank, missing or non-string question returns 400 and the model is never called;
- a question over the length cap returns 400 and the model is never called, while one exactly at
  the cap returns 200;
- a model failure returns 502 and the body does not contain the error text.
```

## Check

```bash
pytest -q
```
