"""Chapter 8: the main template is one template for two environments."""

from __future__ import annotations

from pathlib import Path

import pytest

CHAPTER = Path(__file__).resolve().parents[1]
TEMPLATES = [CHAPTER / "template.yaml", CHAPTER.parent / "student" / "template.yaml"]


def template_text() -> str:
    template = next((p for p in TEMPLATES if p.is_file()), None)
    if template is None:
        pytest.skip("template.yaml is not beside this folder")
    return template.read_text(encoding="utf-8")


def test_environment_is_a_parameter_with_a_closed_list_of_values() -> None:
    block = template_text().split("  Environment:\n")[1].split("  ModelId:")[0]
    assert "Type: String" in block and "Default: dev" in block
    for value in ("dev", "staging", "prod"):
        assert f"      - {value}\n" in block
    assert "AllowedValues" in block


def test_the_site_bucket_name_carries_the_environment_so_two_stacks_do_not_collide() -> None:
    assert 'BucketName: !Sub "${Project}-${Environment}-site-${AWS::AccountId}-${AWS::Region}"' in template_text()


def test_project_and_environment_name_the_other_resources() -> None:
    # staging and prod are two stacks (helpdesk-staging, helpdesk-prod), so their functions differ
    text = template_text()
    assert 'FunctionName: !Sub "${Project}-${Environment}-ask"' in text
    assert "${AWS::StackName}" not in text


def test_project_stays_helpdesk_because_the_bootstrap_roles_are_scoped_to_that_prefix() -> None:
    block = template_text().split("  Project:\n")[1].split("  Environment:")[0]
    assert "AllowedValues: [helpdesk]" in block


def test_the_workflow_deploy_role_pattern_matches_the_bucket_name() -> None:
    deploy_role = next(
        (p for p in (CHAPTER / "deploy-role.yaml", CHAPTER.parent / "student" / "deploy-role.yaml") if p.is_file()),
        None,
    )
    if deploy_role is None:
        pytest.skip("deploy-role.yaml is not beside this folder")
    assert "helpdesk-*-site-${AWS::AccountId}-${AWS::Region}" in deploy_role.read_text(encoding="utf-8")


def test_chapter_8_keeps_the_chapter_7_resources() -> None:
    text = template_text()
    for logical_id in ("HelpdeskUserPool", "HelpdeskGuardrail", "SigninFunction", "TriageFunction", "SiteBucket"):
        assert f"\n  {logical_id}:\n" in text


def test_every_role_in_the_stack_carries_the_permissions_boundary() -> None:
    text = template_text()
    blocks = text.split("    Type: AWS::IAM::Role\n")[1:]
    assert len(blocks) >= 5
    for block in blocks:
        head = block.split("      AssumeRolePolicyDocument:")[0]
        assert (
            "PermissionsBoundary: !If [HasPermissionsBoundary, !Ref PermissionsBoundaryArn, !Ref AWS::NoValue]" in head
        )


def test_the_boundary_parameter_defaults_to_nothing_but_only_accepts_a_policy_arn() -> None:
    block = template_text().split("  PermissionsBoundaryArn:\n")[1].split("  ModelId:")[0]
    assert 'Default: ""' in block and "policy/" in block and "AllowedPattern" in block
    assert "HasPermissionsBoundary: !Not [!Equals [!Ref PermissionsBoundaryArn, \"\"]]" in template_text()
