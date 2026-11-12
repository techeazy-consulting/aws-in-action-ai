# 01 - The handler

## Goal

Write the function that takes a question, asks the hosted model and returns the answer.

## Prompt

```text
Create app/ask/handler.py, a Python AWS Lambda handler named `handler` for POST /ask.

- Read the model id from the MODEL_ID environment variable.
- The request body is JSON like {"question": "..."}. If the body is missing, not JSON, or the
  question is not a non-empty string, return status 400 with {"error": "..."}.
- Reject a question longer than 1000 characters with status 400. The endpoint is public until
  sign-in arrives in chapter 7, and long input costs money.
- Call the Amazon Bedrock Converse API through boto3 ("bedrock-runtime"): one system prompt that
  makes it an IT helpdesk assistant that answers in at most five short steps and says so when it
  is not sure, the question as the user message, maxTokens 400, temperature 0.2.
- Return status 200 with {"answer": "<text>"}. If the model call fails, log it and return 502
  with a safe message that does not repeat the error.
- Responses carry the content-type header application/json.
- Use only the standard library and boto3.
```

## Check

```bash
python -c "import ast, pathlib; ast.parse(pathlib.Path('app/ask/handler.py').read_text())"
grep -n "MAX_QUESTION" app/ask/handler.py
```
