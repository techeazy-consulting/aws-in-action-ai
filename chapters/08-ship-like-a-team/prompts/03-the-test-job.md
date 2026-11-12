# 03 - The workflow and its test job

## Goal

Create the workflow file with a job that runs the tests and the template check on every push and pull request.

## Prompt

```text
Create .github/workflows/deploy.yml at the top of the repository.

- Triggers: push to main, pull_request and workflow_dispatch. Default permissions: contents read.
- Job test: check out the code, set up Python 3.13, install pytest, cfn-lint, boto3 and pyyaml,
  run pytest -q, then cfn-lint template.yaml deploy-role.yaml. No environment, no condition.
- Pin every action to a version (checkout, setup-python).
Add tests/test_workflow.py, which reads the workflow as data: where the file sits, the triggers,
the test job's commands, default permissions, that no action is unpinned, no link or account id
appears, and that pull_request_target and workflow_run are absent.
```

## Check

```bash
pytest -q tests/test_workflow.py
python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml'))"
grep -n "pytest" .github/workflows/deploy.yml
```
