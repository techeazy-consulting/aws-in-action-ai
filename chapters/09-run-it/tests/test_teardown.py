"""Chapter 9: the teardown names every stack, in an order that works, and proves the account is clean."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

CHAPTER = Path(__file__).resolve().parents[1]
README = CHAPTER / "README.md"
CHECK = CHAPTER / "prompts" / "CHECK.md"
WORKFLOW = CHAPTER / ".github" / "workflows" / "deploy.yml"


def teardown_block(text: str) -> str:
    return text.split("## Tear it all down")[1].split("Confirm the account is clean")[0] if "## Tear it all down" in text else text


@pytest.mark.parametrize("path", [README, CHECK])
def test_prod_then_staging_then_the_bootstrap_stack_last(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    loop = text.index("for ENV in prod staging")
    boot = text.index("delete-stack --stack-name github-bootstrap")
    assert loop < boot
    assert 'delete-stack --stack-name "helpdesk-$ENV"' in text[loop:boot]
    assert 'wait stack-delete-complete --stack-name "helpdesk-$ENV"' in text[loop:boot]


@pytest.mark.parametrize("path", [README, CHECK])
def test_each_site_bucket_is_emptied_before_its_stack_is_deleted(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    loop = text[text.index("for ENV in prod staging"):]
    assert loop.index("--recursive") < loop.index('delete-stack --stack-name "helpdesk-$ENV"')


def test_every_stack_the_workflow_creates_is_in_the_teardown() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert '--stack-name "helpdesk-$ENVIRONMENT"' in workflow
    environments = set(re.findall(r"^\s+ENVIRONMENT: (\w+)$", workflow, re.MULTILINE))
    assert environments == {"staging", "prod"}
    text = README.read_text(encoding="utf-8")
    assert "for ENV in prod staging" in text and "github-bootstrap" in text


@pytest.mark.parametrize("path", [README, CHECK])
def test_three_commands_prove_the_account_is_clean(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert "aws cloudformation list-stacks --stack-status-filter" in text and "DELETE_FAILED" in text
    assert "starts_with(StackName, 'helpdesk-') || StackName == 'github-bootstrap'" in text
    assert "aws cloudwatch describe-alarms --alarm-name-prefix helpdesk-" in text
    assert "aws logs describe-log-groups --log-group-name-prefix /aws/lambda/helpdesk-" in text


def test_the_readme_says_what_stays_outside_aws_and_warns_about_the_shared_provider() -> None:
    text = " ".join(README.read_text(encoding="utf-8").split())
    assert "What stays outside AWS" in text and "GitHub environments" in text
    assert "only when no other project in the account uses the provider" in text


def test_the_readme_states_a_formula_and_no_price() -> None:
    text = " ".join(README.read_text(encoding="utf-8").split())
    assert "cost per ticket = (input tokens / per x input price" in text
    assert "Nothing in this course states a price" in text
    assert not re.search(r"\$\s?\d|\bUSD\b", text)
