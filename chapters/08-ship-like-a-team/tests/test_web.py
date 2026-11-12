"""Chapter 3: the chat page and the stack that serves it. Nothing here touches AWS."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

CHAPTER = Path(__file__).resolve().parents[1]
PAGE = CHAPTER / "app" / "web" / "index.html"
# The template sits at the chapter root in the exported repo, and under student/ in the source tree.
TEMPLATES = [CHAPTER / "template.yaml", CHAPTER.parent / "student" / "template.yaml"]


def template_text() -> str:
    template = next((p for p in TEMPLATES if p.is_file()), None)
    if template is None:
        pytest.skip("template.yaml is not beside this folder")
    return template.read_text(encoding="utf-8")


def test_page_posts_the_question_to_the_same_origin() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert 'fetch("/ask"' in page
    assert 'method: "POST"' in page
    assert "JSON.stringify({ question })" in page


def test_page_names_no_other_address() -> None:
    # Same origin means no absolute address in the page, so no cross-origin rules are needed.
    page = PAGE.read_text(encoding="utf-8")
    assert re.search(r"https?:[/][/]", page, re.IGNORECASE) is None


def test_page_shows_the_whole_reply_not_a_stream() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert "await response.json()" in page
    for streaming in ("getReader", "ReadableStream", "EventSource", "WebSocket"):
        assert streaming not in page


def test_page_writes_answers_as_text_not_markup() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert "textContent" in page
    assert "innerHTML" not in page


def test_page_question_box_matches_the_server_cap() -> None:
    page = PAGE.read_text(encoding="utf-8")
    declared = re.search(r"MAX_QUESTION = (\d+)", (CHAPTER / "app/ask/handler.py").read_text())
    assert declared is not None
    assert f'maxlength="{declared.group(1)}"' in page


def test_page_shows_an_error_when_the_call_fails() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert "catch (error)" in page
    assert 'add("err"' in page


def test_template_keeps_the_bucket_private() -> None:
    text = template_text()
    for setting in ("BlockPublicAcls", "BlockPublicPolicy", "IgnorePublicAcls", "RestrictPublicBuckets"):
        assert f"{setting}: true" in text
    assert "WebsiteConfiguration" not in text  # a website endpoint cannot use origin access control


def test_template_signs_requests_to_the_bucket_with_origin_access_control() -> None:
    text = template_text()
    assert "AWS::CloudFront::OriginAccessControl" in text
    assert "SigningBehavior: always" in text
    assert "OriginAccessControlOriginType: s3" in text
    assert "cloudfront.amazonaws.com" in text  # the bucket policy trusts the service, not the world
    assert "AWS:SourceArn" in text  # ... and only this distribution


def test_template_serves_https_and_routes_ask_to_the_api() -> None:
    text = template_text()
    # the default behavior plus one behavior per API path (each later chapter adds its own)
    assert text.count("ViewerProtocolPolicy: redirect-to-https") == 1 + text.count("PathPattern:")
    assert "PathPattern: /ask" in text
    assert "DefaultRootObject: index.html" in text


# --- chapter 7: sign-in ------------------------------------------------------------------------


def test_page_signs_in_through_its_own_address_and_sends_the_token_as_a_bearer_header() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert 'fetch("/signin"' in page
    assert 'authorization: "Bearer " + token' in page
    assert "JSON.stringify({ email, password })" in page


def test_the_password_field_hides_what_is_typed_and_is_cleared_once_sent() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert 'id="password" type="password"' in page
    assert 'passwordBox.value = ""' in page
    assert page.index('passwordBox.value = ""') < page.index('fetch("/signin"')


def test_the_token_is_kept_in_memory_only() -> None:
    page = PAGE.read_text(encoding="utf-8")
    for store in ("localStorage", "sessionStorage", "document.cookie", "indexedDB"):
        assert store not in page
    assert "let token = null" in page


def test_signing_out_or_an_expired_token_clears_the_chat_and_returns_to_the_form() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert "response.status === 401" in page
    assert "log.replaceChildren()" in page and "token = null" in page


def test_the_chat_is_hidden_until_sign_in() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert '<section id="chat" hidden>' in page


def test_template_names_resources_from_project_and_environment() -> None:
    text = template_text()
    assert '!Sub "${Project}-${Environment}-ask"' in text
    assert '!Sub "${Project}-${Environment}-api"' in text
    assert '!Sub "${Project}-${Environment}-site"' in text
    assert "${AWS::StackName}" not in text


def test_template_lets_the_role_call_an_inference_profile() -> None:
    # Most Regions serve the model only through an inference profile (geo prefix + model id);
    # the role must allow the profile and the model in every Region the profile routes to.
    text = template_text()
    assert ":inference-profile/${Id}" in text
    assert "bedrock:*::foundation-model/${ModelId}" in text
    assert "ap-south-1: {Route: apac}" in text


def test_template_keeps_nothing_after_delete() -> None:
    # DataDeletionPolicy (the data source's DELETE) is a different setting.
    text = template_text().replace("DataDeletionPolicy", "")
    assert "DeletionPolicy" not in text and "UpdateReplacePolicy" not in text
