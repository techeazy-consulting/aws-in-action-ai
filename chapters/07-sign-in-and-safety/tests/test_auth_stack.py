"""Chapter 7: the new template parts -- user pool, groups, authorizer, sign-in route, guardrail."""

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


def resource(name: str) -> str:
    """The text of one resource: from its header to the next resource (or the Outputs)."""
    text = template_text()
    start = text.index(f"\n  {name}:\n") + 1
    nxt = re.search(r"\n  [A-Za-z0-9]+:\n|\nOutputs:", text[start + 1 :])
    return text[start : start + 1 + nxt.start()] if nxt else text[start:]


def test_people_are_added_by_the_administrator_only() -> None:
    pool = resource("HelpdeskUserPool")
    assert "Type: AWS::Cognito::UserPool" in pool
    assert "AllowAdminCreateUserOnly: true" in pool
    assert "MinimumLength: 12" in pool
    assert "chapter: session-07" in pool


def test_the_app_client_has_no_secret_and_only_the_flows_the_sign_in_function_needs() -> None:
    client = resource("HelpdeskUserPoolClient")
    assert "GenerateSecret: false" in client
    assert "ALLOW_USER_PASSWORD_AUTH" in client and "ALLOW_REFRESH_TOKEN_AUTH" in client
    assert "ALLOW_ADMIN_USER_PASSWORD_AUTH" not in client and "ALLOW_CUSTOM_AUTH" not in client
    assert "PreventUserExistenceErrors: ENABLED" in client


def test_the_two_groups_have_the_exact_names_the_code_looks_for() -> None:
    assert "GroupName: employee" in resource("EmployeeGroup")
    assert "GroupName: it-staff" in resource("ITStaffGroup")
    for group in ("EmployeeGroup", "ITStaffGroup"):
        assert "RoleArn" not in resource(group)  # groups here carry no AWS permissions


def test_the_authorizer_checks_the_app_client_and_this_pool_as_issuer() -> None:
    auth = resource("HelpdeskAuthorizer")
    assert "AuthorizerType: JWT" in auth
    assert "$request.header.Authorization" in auth
    assert "- !Ref HelpdeskUserPoolClient" in auth
    assert "cognito-idp.${AWS::Region}.amazonaws.com/${HelpdeskUserPool}" in auth


@pytest.mark.parametrize("route", ["AskRoute", "TicketsRoute", "TriageRoute"])
def test_the_model_routes_need_a_valid_token(route: str) -> None:
    text = resource(route)
    assert "AuthorizationType: JWT" in text and "AuthorizerId: !Ref HelpdeskAuthorizer" in text


def test_only_the_sign_in_route_is_open_and_it_has_the_tightest_throttle() -> None:
    route = resource("SigninRoute")
    assert "RouteKey: POST /signin" in route and "Authorizer" not in route
    assert "PathPattern: /signin" in template_text()
    stage = resource("DefaultStage")
    assert '"POST /signin":' in stage and "ThrottlingRateLimit" in stage.split('"POST /signin":')[1]
    assert text_count("AuthorizationType: JWT") == 3  # exactly the three model routes


def text_count(needle: str) -> int:
    return template_text().count(needle)


def test_the_sign_in_function_may_only_write_its_own_logs() -> None:
    role = resource("SigninFunctionRole")
    actions = re.findall(r"- (?:logs|bedrock|cognito-idp|dynamodb|sns|s3):[A-Za-z*]+", role)
    assert sorted(actions) == ["- logs:CreateLogStream", "- logs:PutLogEvents"]
    assert "CLIENT_ID: !Ref HelpdeskUserPoolClient" in resource("SigninFunction")


def test_the_guardrail_masks_passwords_and_keys_in_input_and_output_and_blocks_off_topic() -> None:
    g = resource("HelpdeskGuardrail")
    for kind in ("PASSWORD", "AWS_ACCESS_KEY", "AWS_SECRET_KEY"):
        assert f"Type: {kind}" in g
    assert g.count("InputAction: ANONYMIZE") == 4 and g.count("OutputAction: ANONYMIZE") == 4
    assert g.count("InputEnabled: true") >= 5 and g.count("OutputEnabled: true") >= 5
    assert "PRIVATE KEY" in g and "RegexesConfig" in g
    assert "Type: DENY" in g and "InputAction: BLOCK" in g and "OutputAction: BLOCK" in g
    assert "BlockedInputMessaging" in g and "BlockedOutputsMessaging" in g
    assert "chapter" in g and "session-07" in g


def test_the_functions_call_a_published_guardrail_version_not_the_draft() -> None:
    assert "GuardrailIdentifier: !GetAtt HelpdeskGuardrail.GuardrailId" in resource("HelpdeskGuardrailVersion")
    for fn in ("AskFunction", "TicketsFunction", "TriageFunction"):
        body = resource(fn)
        assert "GUARDRAIL_ID: !GetAtt HelpdeskGuardrail.GuardrailId" in body
        assert "GUARDRAIL_VERSION: !GetAtt HelpdeskGuardrailVersion.Version" in body
    assert "DRAFT" not in template_text()


@pytest.mark.parametrize("role", ["AskFunctionRole", "TicketsFunctionRole", "TriageFunctionRole"])
def test_each_model_role_may_apply_that_one_guardrail_and_nothing_wider(role: str) -> None:
    text = resource(role)
    assert "bedrock:ApplyGuardrail" in text
    assert "Resource: !GetAtt HelpdeskGuardrail.GuardrailArn" in text
    assert not re.search(r"bedrock:\*(?!:)", text)  # no wildcard action; the model ARN may use * for Region


def test_no_account_id_key_or_email_address_is_written_in_the_template() -> None:
    text = template_text()
    assert not re.search(r"(?<!\d)\d{12}(?!\d)", text)
    assert not re.search(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b", text)
    assert not re.search(r"[A-Za-z0-9._-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}", text)


def test_chapter_7_keeps_the_chapter_6_resources() -> None:
    text = template_text()
    for logical_id in ("TriageFunction", "EscalationTopic", "TicketsTable", "PolicyKnowledgeBase", "SiteDistribution"):
        assert f"\n  {logical_id}:\n" in text


def test_the_sign_in_notice_is_gone_from_the_stage_comment() -> None:
    assert "Public until sign-in" not in template_text()


def test_the_app_client_can_read_the_email_but_cannot_write_it() -> None:
    client = resource("HelpdeskUserPoolClient")
    read = client.split("ReadAttributes:\n")[1].split("      WriteAttributes:")[0]
    write = client.split("WriteAttributes:\n")[1].split("      ExplicitAuthFlows:")[0]
    assert "- email\n" in read and "- email_verified\n" in read
    assert "email" not in write and "- name" in write  # left unset, every standard attribute is writable


def test_a_changed_email_must_be_verified_before_it_takes_effect() -> None:
    pool = resource("HelpdeskUserPool")
    assert "AutoVerifiedAttributes:\n        - email" in pool
    assert "AttributesRequireVerificationBeforeUpdate:\n          - email" in pool


def test_the_commands_that_create_a_person_mark_the_address_verified() -> None:
    for path in (CHAPTER / "README.md", CHAPTER / "prompts" / "CHECK.md"):
        text = path.read_text(encoding="utf-8")
        if "admin-create-user" in text:
            line = next(l for l in text.splitlines() if "admin-create-user" in l)
            assert "--user-attributes Name=email,Value=" in line and "Name=email_verified,Value=true" in line, path.name


def test_the_chapter_7_resources_are_named_from_project_and_environment() -> None:
    text = template_text()
    for part in ("users", "chat", "cognito", "signin", "guardrail"):
        assert f'!Sub "${{Project}}-${{Environment}}-{part}"' in text
    assert '!Sub "/aws/lambda/${Project}-${Environment}-signin"' in text


def test_the_chapter_7_resources_carry_the_project_and_environment_tags() -> None:
    for logical_id in ("HelpdeskUserPool", "SigninFunction", "HelpdeskGuardrail"):
        text = resource(logical_id)
        assert "project: !Ref Project" in text or "Key: project" in text
        assert "environment: !Ref Environment" in text or "Key: environment" in text
