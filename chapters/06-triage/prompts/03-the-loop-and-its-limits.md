# 03 - The loop, the step cap and the hand-over rule

## Goal

Write the loop that keeps asking the model what to do next, with a hard step cap and a rule in code that hands over to a person when the loop cannot finish.

## Prompt

```text
Finish app/triage/handler.py. This loop is written by hand with the Converse API; it uses no
managed agent service.

- Constants MAX_MESSAGE 1000, MAX_STEPS 6 (model calls per request) and MAX_ESCALATIONS 1
  (emails per request, whatever the model asks for).
- escalate must send nothing more once MAX_ESCALATIONS emails have been sent in this request; it
  answers that the problem was already handed over.
- handler(event, context): read "message" from the JSON body (400 if missing, not a string, blank
  or too long). Loop at most MAX_STEPS times: call bedrock.converse with modelId, messages,
  system, toolConfig and inferenceConfig (maxTokens 400, temperature 0.2); append the model's
  message; if stopReason is not "tool_use", return 200 with {"answer", "steps" (tool names in
  order), "escalated" (true if an email was sent)}; otherwise run every toolUse block and append
  ONE user message holding all the toolResult blocks.
- hand_over(state, reason): when the loop ends without an answer, or the model call fails after
  work started, or the model stops for tools without asking for one, the CODE sends one escalation
  email (unless one was already sent) and returns 200 {"answer": "I could not settle this myself,
  so I passed it to the IT team.", "steps", "escalated": true, "reason"}. Reasons: step_cap,
  model_error, no_tool_request. If that email itself fails, return 502 with a safe message,
  never a false promise.
- A model failure on the very first call is a 502 and sends nothing.
```

## Check

```bash
python -c "import ast, pathlib; ast.parse(pathlib.Path('app/triage/handler.py').read_text())"
grep -n "MAX_STEPS\|MAX_ESCALATIONS" app/triage/handler.py
grep -n "def hand_over" app/triage/handler.py
```
