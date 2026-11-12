# 03 - Retrieve and generate, with citations

## Goal

Change the function so it asks the knowledge base and returns the answer together with the policy pages it came from.

## Prompt

```text
Change app/ask/handler.py. Keep the request checks (JSON body, non-empty string question, the
1000 character cap) and the 502 behaviour exactly as they are.

- Read KNOWLEDGE_BASE_ID and MODEL_ARN from the environment. Create a boto3 client for
  "bedrock-agent-runtime" named `agent`.
- Replace the model call with one agent.retrieve_and_generate call: input text is the question;
  retrieveAndGenerateConfiguration type KNOWLEDGE_BASE with the knowledge base id, the model ARN
  and generationConfiguration inferenceConfig textInferenceConfig maxTokens 400, temperature 0.2.
- The answer is response["output"]["text"].
- Build `sources` from response["citations"][*]["retrievedReferences"]: take the S3 location URI of
  each reference, keep the part after the bucket name, and keep it only if it matches
  ^policies/[A-Za-z0-9._-]+\.html$. List each page once, in the order first cited, with the first 300
  characters of the cited text as "excerpt".
- Return 200 with {"answer": "...", "sources": [{"page": "...", "excerpt": "..."}]}. If the call
  fails, log it and return 502 with the same safe message as before.
- Use only the standard library and boto3.
```

## Check

```bash
python -c "import ast, pathlib; ast.parse(pathlib.Path('app/ask/handler.py').read_text())"
grep -n "retrieve_and_generate\|PAGE_KEY" app/ask/handler.py
```
