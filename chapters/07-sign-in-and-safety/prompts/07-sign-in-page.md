# 07 - The chat page signs in first

## Goal

Put a sign-in form in front of the chat and keep the token in memory only.

## Prompt

```text
Edit app/web/index.html. Keep everything on one address: no absolute address in the page.
- A sign-in form (email, password with type password, autocomplete hints) that POSTs JSON to
  /signin. Clear the password field as soon as it is sent. Show errors in a role=alert paragraph
  with textContent, never as markup.
- On success keep id_token in a variable named token (never localStorage, sessionStorage, cookies
  or IndexedDB), hide the form and show the chat, which is hidden until then.
- /ask is sent with an authorization header "Bearer " plus the token. A 401 clears the token and
  the chat and shows the form again with a message. A Sign out button does the same.
Tests (tests/test_web.py): the sign-in call, the bearer header, the password field, the token kept
in memory only, the chat hidden until sign-in.
```

## Check

```bash
pytest -q tests/test_web.py
grep -n "signin\|Bearer" app/web/index.html
```
