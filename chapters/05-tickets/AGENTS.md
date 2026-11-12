# Context for AI coding tools

This repository holds a hands-on cloud course as one folder per chapter under `chapters/`. Each
chapter is a complete snapshot of the application at the end of that chapter.

## Stack

- Python 3.11 or newer; AWS Lambda functions on the python3.13 runtime; boto3.
- Infrastructure is one CloudFormation template per chapter, `template.yaml`, in YAML.
- Tests use pytest and never need AWS credentials or a network.

## Conventions

- A chapter folder holds `app/`, `tests/`, `prompts/`, `template.yaml` and `README.md`.
- The Lambda code in `template.yaml` is inline (`ZipFile`) and must equal the matching file under
  `app/`, byte for byte. Change both together.
- Tag every taggable resource with the chapter. No `Retain` deletion policy, no account ids and no
  keys in any file; use pseudo parameters such as the account id and region references.
- Keep each change small and run the tests after it.

## What to do when asked

- To build a chapter: follow `prompts/` in order and run each prompt's check before the next.
- To prove a chapter works: run `prompts/CHECK.md`, offline checks first.
- The live checks deploy real resources and cost money. Ask before running them.
- To clean up: delete the stack with `aws cloudformation delete-stack` and wait for it to finish.
