"""Chapter 5: the new template parts -- tickets table, tickets function and its route."""

from __future__ import annotations

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
