"""Chapter 5: the new template parts -- tickets table, tickets function and its route."""

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


def test_tickets_live_in_an_on_demand_table_keyed_by_ticket_id() -> None:
    text = template_text()
    assert "Type: AWS::DynamoDB::Table" in text
    assert "BillingMode: PAY_PER_REQUEST" in text  # nothing standing to pay for
    assert "AttributeName: TicketId" in text
    assert "DeletionProtectionEnabled" not in text


def test_function_may_only_get_put_and_update_items_in_that_one_table() -> None:
    text = template_text()
    for action in ("dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"):
        assert action in text
    assert "dynamodb:*" not in text and "dynamodb:Scan" not in text and "dynamodb:DeleteItem" not in text
    assert "Resource: !GetAtt TicketsTable.Arn" in text


def test_function_is_wired_to_the_table_and_the_model() -> None:
    text = template_text()
    assert "TICKETS_TABLE: !Ref TicketsTable" in text
    assert "MODEL_ID: !If" in text


def test_tickets_route_is_served_through_the_same_address_and_stays_throttled() -> None:
    text = template_text()
    assert "RouteKey: POST /tickets" in text
    assert "PathPattern: /tickets" in text
    assert "ThrottlingRateLimit:" in text  # the stage default covers the new route too


def test_chapter_5_keeps_the_chapter_4_resources() -> None:
    text = template_text()
    for logical_id in ("AskFunction", "PolicyKnowledgeBase", "SiteDistribution", "SiteBucket"):
        assert f"  {logical_id}:" in text


def test_template_names_resources_from_project_and_environment() -> None:
    text = template_text()
    assert '!Sub "${Project}-${Environment}-ask"' in text
    assert '!Sub "${Project}-${Environment}-api"' in text
    assert '!Sub "${Project}-${Environment}-tickets"' in text
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
