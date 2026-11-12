# 04 - Prove the three cases offline

## Goal

Test an easy case, a hard case and the step cap with a fake model and a fake topic, plus the limits on what one request can send.

## Prompt

```text
Create tests/test_triage.py. Load app/triage/handler.py fresh in a fixture with boto3 replaced by
a stub and ESCALATION_TOPIC_ARN, MODEL_ID and SERVICE_STATUS set; use monkeypatch to put a fake
sns client on the module. Replace `bedrock` on the module with a FakeModel that plays back
scripted responses (and repeats the last one) and records every call. No test may touch AWS.

Cover: the three tools are offered; the EASY case (check the service, try a known fix, answer;
nothing is emailed; each result goes back with its toolUseId); the HARD case (check, no known fix,
escalate, answer; exactly one email whose Message holds the summary and the person's text and
whose Subject has no line break); a service that is down escalated straight away; the STEP CAP (a
model that never finishes: exactly MAX_STEPS model calls, then one email sent by the code and
reason step_cap); no second email when the model already escalated; five escalate requests in one
turn send one email; the model cannot change the topic or add recipients; a failing hand-over
email is a 502; a failing escalate tool is an error result and is not counted as handed over; a
model failure after work started hands over, and on the first call is a 502 with no email; every
bad tool request (missing detail, unknown service, unknown fix, unknown tool) is an error result
that sends nothing; long text is cut before it is emailed; 400 for a bad message.
```

## Check

```bash
pytest -q tests/test_triage.py
pytest -q
```
