"""Chapter 6: the new template parts -- escalation topic, email subscription, triage function."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

CHAPTER = Path(__file__).resolve().parents[1]
# The template sits at the chapter root in the exported repo, and under student/ in the source tree.
TEMPLATES = [CHAPTER / "template.yaml", CHAPTER.parent / "student" / "template.yaml"]


def template_text() -> str:
    template = next((p for p in TEMPLATES if p.is_file()), None)
    if template is None:
        pytest.skip("template.yaml is not beside this folder")
    return template.read_text(encoding="utf-8")


def test_escalations_go_to_an_sns_topic_with_an_email_subscription() -> None:
    text = template_text()
    assert "Type: AWS::SNS::Topic" in text
    assert "Type: AWS::SNS::Subscription" in text
    assert "Protocol: email" in text
    assert "Endpoint: !Ref EscalationEmail" in text


def test_the_email_address_is_a_parameter_with_no_default_and_none_is_written_in_the_file() -> None:
    text = template_text()
    parameter = text.split("  EscalationEmail:")[1].split("  ServiceStatus:")[0]
    assert "Type: String" in parameter and "Default:" not in parameter
    assert "AllowedPattern" in parameter
    assert not re.search(r"[A-Za-z0-9._-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}", text)


def test_function_may_only_publish_to_the_escalation_topic() -> None:
    text = template_text()
    assert "sns:Publish" in text
    assert "Resource: !Ref EscalationTopic" in text
    assert "sns:*" not in text and "sns:Subscribe" not in text


def test_function_is_wired_to_the_topic_the_model_and_the_status_list() -> None:
    text = template_text()
    assert "ESCALATION_TOPIC_ARN: !Ref EscalationTopic" in text
    assert "MODEL_ID: !If" in text
    assert "SERVICE_STATUS: !Ref ServiceStatus" in text


def test_the_status_list_is_json_the_check_can_read() -> None:
    import json

    text = template_text()
    line = next(l for l in text.splitlines() if l.strip().startswith("Default: '{"))
    status = json.loads(line.split("Default: ", 1)[1].strip().strip("'"))
    assert status and set(status.values()) <= {"up", "down"}


def test_triage_route_is_served_through_the_same_address_and_stays_throttled() -> None:
    text = template_text()
    assert "RouteKey: POST /triage" in text
    assert "PathPattern: /triage" in text
    assert "ThrottlingRateLimit:" in text


def test_chapter_6_keeps_the_chapter_5_resources() -> None:
    text = template_text()
    for logical_id in ("AskFunction", "TicketsFunction", "TicketsTable", "SiteDistribution"):
        assert f"  {logical_id}:" in text


def test_template_names_resources_from_project_and_environment() -> None:
    text = template_text()
    assert '!Sub "${Project}-${Environment}-ask"' in text
    assert '!Sub "${Project}-${Environment}-api"' in text
    assert '!Sub "${Project}-${Environment}-tickets"' in text
    assert '!Sub "${Project}-${Environment}-triage"' in text
    assert '!Sub "${Project}-${Environment}-escalations"' in text
    assert '!Sub "${Project}-${Environment}-site"' in text
    assert '!Sub "${Project}-${Environment}-policies"' in text
    assert '!Sub "${Project}-${Environment}-policy-pages"' in text
    assert "${AWS::StackName}" not in text


def test_template_lets_the_role_call_an_inference_profile() -> None:
    # Most Regions serve the model only through an inference profile (geo prefix + model id);
    # the role must allow the profile and the model in every Region the profile routes to.
    text = template_text()
    assert ":inference-profile/${Id}" in text
    assert "bedrock:*::foundation-model/${ModelId}" in text
    assert "ap-south-1: {Route: apac}" in text


def test_template_keeps_nothing_after_delete() -> None:
    # The data source's DataDeletionPolicy only empties the vectors; no resource may carry
    # DeletionPolicy or UpdateReplacePolicy, so deleting the stack removes everything.
    text = template_text()
    assert not re.search(r"^\s*(DeletionPolicy|UpdateReplacePolicy):", text, re.MULTILINE)


def test_ask_function_can_send_an_inference_profile_arn_to_the_knowledge_base() -> None:
    text = template_text()
    start = text.index("MODEL_ARN: !If")
    arn = text[start : start + 700]
    assert ":inference-profile/" in arn
    assert "::foundation-model/${ModelId}" in arn
