"""Chapter 8: the GitHub Actions workflow. Read as data; nothing here runs a workflow."""

from __future__ import annotations

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
    command = runs(staging)[0]
    assert '--stack-name "helpdesk-$ENVIRONMENT"' in command
    assert '"Environment=$ENVIRONMENT"' in command
    assert "--template-file template.yaml" in command


@pytest.mark.parametrize("job", DEPLOY_JOBS)
def test_the_deploy_hands_the_work_to_the_cloudformation_role_and_the_email_is_not_in_the_file(job: str) -> None:
    command = runs(jobs()[job])[0]
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
    command = runs(jobs()[job])[1]
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
    assert '"PermissionsBoundaryArn=$PERMISSIONS_BOUNDARY_ARN"' in runs(jobs()[job])[0]


def test_the_readme_names_the_branch_rule_on_both_environments_and_every_variable_the_workflow_reads() -> None:
    readme = (CHAPTER / "README.md").read_text(encoding="utf-8")
    assert "On **both**" in readme and "main branch only" in readme
    for variable in sorted(set(re.findall(r"vars\.([A-Z_]+)", WORKFLOW.read_text(encoding="utf-8")))):
        assert f"`{variable}`" in readme, f"README does not name the variable {variable}"
