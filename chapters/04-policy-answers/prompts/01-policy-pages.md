# 01 - The IT policy pages

## Goal

Write the small set of policy pages that the helpdesk will answer from and cite.

## Prompt

```text
Create three short HTML pages in app/policies/: password-reset.html, vpn-access.html and
new-laptop.html. Each is a complete page with a <title> and one <h1>, headings for its sections
and short lists of steps or rules, written for a generic company's IT team. Rules:

- file names use only lowercase letters, digits and hyphens;
- no scripts, no links, no company or product names;
- no time estimates anywhere.
```

## Check

```bash
ls app/policies
grep -c "<h1>" app/policies/*.html
```
