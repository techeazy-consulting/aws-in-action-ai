# 01 - The chat page

## Goal

Write one HTML file that lets an employee type a question and read the whole answer.

## Prompt

```text
Create app/web/index.html, a single self-contained page (HTML, a small style block and a small
script, no libraries, no build step) for the IT helpdesk chat.

- A list that shows the conversation, a form with a textarea (maxlength 1000, matching the server
  cap in app/ask/handler.py) and a Send button.
- On submit, show the question, clear the box, disable the button, and POST {"question": "..."} as
  JSON to the relative path /ask. Never write a full address: the page and the endpoint share one
  address, so no cross-origin rules are needed.
- Wait for the whole reply with response.json(), then show data.answer. Do not stream.
- If the response is not ok, show data.error. If the call itself fails, show a short message.
  Always enable the button again afterwards.
- Add answers to the page with textContent, never innerHTML, because the answer is not trusted.
```

## Check

```bash
grep -n 'fetch("/ask"' app/web/index.html
grep -c "innerHTML" app/web/index.html
```
