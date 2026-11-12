"""Chapter 8: the GitHub Actions workflow. Read as data; nothing here runs a workflow."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

CHAPTER = Path(__file__).resolve().parents[1]
WORKFLOW = CHAPTER / ".github" / "workflows" / "deploy.yml"
DEPLOY_JOBS = {"deploy-staging": "staging", "deploy-prod": "prod"}


def workflow() -> dict[str, Any]:
    loaded = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    if True in loaded:  # YAML reads the bare key "on" as the boolean True
        loaded["on"] = loaded.pop(True)
    return loaded


def jobs() -> dict[str, Any]:
    return workflow()["jobs"]


def runs(job: dict[str, Any]) -> list[str]:
    return [step["run"] for step in job["steps"] if "run" in step]


def run_named(job: dict[str, Any], name: str) -> str:
    """The script of the step with this name (steps are found by name, not by position)."""
    return next(step["run"] for step in job["steps"] if step.get("name") == name)


def test_the_workflow_sits_where_github_reads_workflows() -> None:
    assert WORKFLOW.parent.parts[-2:] == (".github", "workflows")
    assert set(workflow()["on"]) == {"push", "pull_request", "workflow_dispatch"}
    assert workflow()["on"]["push"] == {"branches": ["main"]}


def test_tests_and_template_checks_run_first_and_on_pull_requests() -> None:
    test = jobs()["test"]
    assert "environment" not in test and "if" not in test  # every event, no approval
    commands = " ".join(runs(test))
    assert "pytest" in commands and "cfn-lint template.yaml" in commands
    assert "deploy-role.yaml" in commands  # the bootstrap template is checked too


def test_staging_waits_for_the_tests_and_prod_waits_for_staging() -> None:
    assert jobs()["deploy-staging"]["needs"] == "test"
    assert jobs()["deploy-prod"]["needs"] == "deploy-staging"


@pytest.mark.parametrize("job, environment", DEPLOY_JOBS.items())
def test_each_deploy_job_names_its_github_environment(job: str, environment: str) -> None:
    # The environment is where a person's approval (a required reviewer) is set, and it is
    # also the name the AWS trust policy matches. Prod's rule is set in GitHub, not in this file.
    assert jobs()[job]["environment"] == environment
    assert jobs()[job]["env"]["ENVIRONMENT"] == environment


@pytest.mark.parametrize("job", DEPLOY_JOBS)
def test_deploys_only_from_main_and_never_from_a_pull_request(job: str) -> None:
    condition = jobs()[job]["if"]
    assert "github.ref == 'refs/heads/main'" in condition
    assert "github.event_name != 'pull_request'" in condition


def test_the_default_token_is_read_only_and_only_deploy_jobs_may_ask_for_the_oidc_token() -> None:
    assert workflow()["permissions"] == {"contents": "read"}
    assert "permissions" not in jobs()["test"]  # so the test job, which runs pull requests, has none
    for job in DEPLOY_JOBS:
        assert jobs()[job]["permissions"] == {"contents": "read", "id-token": "write"}


@pytest.mark.parametrize("job", DEPLOY_JOBS)
def test_aws_access_comes_from_a_role_through_oidc_not_from_a_stored_key(job: str) -> None:
    step = next(s for s in jobs()[job]["steps"] if "configure-aws-credentials" in s.get("uses", ""))
    assert set(step["with"]) == {"role-to-assume", "aws-region"}
    assert step["with"]["role-to-assume"] == "${{ vars.DEPLOY_ROLE_ARN }}"  # a variable, not a secret
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "aws-access-key-id" not in text.lower() and "secret-access-key" not in text.lower()
    assert "secrets." not in text and "AWS_ACCESS_KEY" not in text


def test_no_expression_is_written_into_a_shell_script() -> None:
    # Values go through env: and are quoted in the script, so none can inject a command.
    for name, job in jobs().items():
        for command in runs(job):
            assert "${{" not in command, f"{name}: an expression inside run:"


def test_every_dangerous_trigger_is_absent() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request_target" not in text and "workflow_run" not in text


def test_the_two_stacks_differ_only_by_their_environment_value() -> None:
    staging, prod = jobs()["deploy-staging"], jobs()["deploy-prod"]
    assert runs(staging) == runs(prod)  # one set of commands, so staging is a real rehearsal
    assert staging["steps"] == prod["steps"]
    command = run_named(staging, "Deploy the stack")
    assert '--stack-name "helpdesk-$ENVIRONMENT"' in command
    assert '"Environment=$ENVIRONMENT"' in command
    assert "--template-file template.yaml" in command


@pytest.mark.parametrize("job", DEPLOY_JOBS)
def test_the_deploy_hands_the_work_to_the_cloudformation_role_and_the_email_is_not_in_the_file(job: str) -> None:
    command = run_named(jobs()[job], "Deploy the stack")
    assert '--role-arn "$CFN_ROLE_ARN"' in command
    assert "--capabilities CAPABILITY_IAM" in command
    assert jobs()[job]["env"]["CFN_ROLE_ARN"] == "${{ vars.CFN_ROLE_ARN }}"
    assert jobs()[job]["env"]["ESCALATION_EMAIL"] == "${{ vars.ESCALATION_EMAIL }}"
    assert not re.search(r"[A-Za-z0-9._-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}", WORKFLOW.read_text())


def test_deploys_of_one_environment_do_not_overlap() -> None:
    assert jobs()["deploy-staging"]["concurrency"] == "deploy-staging"
    assert jobs()["deploy-prod"]["concurrency"] == "deploy-prod"


@pytest.mark.parametrize("job", DEPLOY_JOBS)
def test_the_pages_are_published_to_the_stack_output_bucket_and_ingested(job: str) -> None:
    command = run_named(jobs()[job], "Publish the chat page and the policy pages")
    assert "SiteBucketName" in command and "app/web/index.html" in command
    assert "app/policies" in command and "start-ingestion-job" in command
    assert "KnowledgeBaseId" in command and "DataSourceId" in command


def test_every_action_is_pinned_to_a_version() -> None:
    for job in jobs().values():
        for step in job["steps"]:
            if "uses" in step:
                assert re.fullmatch(r"[\w.-]+/[\w.-]+@(v\d+(\.\d+){0,2}|[0-9a-f]{40})", step["uses"]), step["uses"]


def test_the_workflow_names_no_link_or_account_id() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert not re.search(r"https?:[/][/]", text, re.IGNORECASE)
    assert not re.search(r"(?<!\d)\d{12}(?!\d)", text)


@pytest.mark.parametrize("job", DEPLOY_JOBS)
def test_the_permissions_boundary_is_passed_to_every_deploy(job: str) -> None:
    assert jobs()[job]["env"]["PERMISSIONS_BOUNDARY_ARN"] == "${{ vars.PERMISSIONS_BOUNDARY_ARN }}"
    assert '"PermissionsBoundaryArn=$PERMISSIONS_BOUNDARY_ARN"' in run_named(jobs()[job], "Deploy the stack")


def test_the_readme_names_the_branch_rule_on_both_environments_and_every_variable_the_workflow_reads() -> None:
    readme = (CHAPTER / "README.md").read_text(encoding="utf-8")
    assert "On **both**" in readme and "main branch only" in readme
    for variable in sorted(set(re.findall(r"vars\.([A-Z_]+)", WORKFLOW.read_text(encoding="utf-8")))):
        assert f"`{variable}`" in readme, f"README does not name the variable {variable}"


# --- chapter 9: the quality check after each deploy ----------------------------------------------


def step_names(job: str) -> list[str]:
    return [step.get("name", step.get("uses", "")) for step in jobs()[job]["steps"]]


@pytest.mark.parametrize("job", DEPLOY_JOBS)
def test_after_each_deploy_the_pages_are_published_the_ingestion_awaited_and_the_questions_asked(job: str) -> None:
    names = step_names(job)
    order = ["Deploy the stack", "Publish the chat page and the policy pages", "Quality check"]
    assert [n for n in names if n in order] == order
    publish = run_named(jobs()[job], "Publish the chat page and the policy pages")
    assert "--query ingestionJob.ingestionJobId" in publish
    assert 'python app/quality/check.py wait' in publish and '--job-id "$JOB"' in publish
    # the questions are asked of the ask function of the stack this job just deployed
    assert run_named(jobs()[job], "Quality check") == 'python app/quality/check.py run --function-name "helpdesk-$ENVIRONMENT-ask"'


@pytest.mark.parametrize("job", DEPLOY_JOBS)
def test_the_check_has_python_and_boto3_before_it_runs(job: str) -> None:
    steps = jobs()[job]["steps"]
    uses = [s.get("uses", "") for s in steps]
    assert any(u.startswith("actions/setup-python@") for u in uses)
    install = next(i for i, s in enumerate(steps) if s.get("run") == "pip install boto3")
    check = next(i for i, s in enumerate(steps) if s.get("name") == "Quality check")
    assert install < check


def test_a_failed_staging_check_stops_the_prod_job_because_prod_needs_staging() -> None:
    assert jobs()["deploy-prod"]["needs"] == "deploy-staging"
    steps = jobs()["deploy-staging"]["steps"]
    assert "continue-on-error" not in json.dumps(steps) and not any("if" in s for s in steps)


def test_the_check_scripts_the_workflow_calls_exist() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    for path in sorted(set(re.findall(r"python (app/[\w/]+\.py)", text))):
        assert (CHAPTER / path).is_file(), path
