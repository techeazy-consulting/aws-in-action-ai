# 05 - The cited page beside the answer

## Goal

Show the policy page an answer came from next to the chat, so the employee can check the source.

## Prompt

```text
Change app/web/index.html. Keep everything it does today: the relative POST to /ask, reading the
whole reply with response.json(), textContent only (never innerHTML), the error messages and the
1000 character limit.

- Put the chat and a second panel side by side (they stack on a narrow screen). The panel is
  hidden until there is a source.
- After a good answer, read data.sources. If it is a non-empty array, add a "Sources:" line with
  one button per page, and show the first page straight away. Tolerate a missing or empty list.
- Showing a page: set the panel title and the excerpt as text, and set the src of an iframe with
  the empty sandbox attribute to "/" + source.page. Never set it unless the page matches
  ^policies/[A-Za-z0-9._-]+\.html$.
- Create tests/test_policy_panel.py that reads the files and checks the policy pages (titled, no
  links, no scripts, file names the handler accepts), the locked frame, the same-address src, the
  pattern check and the tolerant sources handling.
```

## Check

```bash
pytest -q
```
