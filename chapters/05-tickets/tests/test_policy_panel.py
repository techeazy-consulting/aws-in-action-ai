"""Chapter 4: the policy pages and the panel that shows the cited page beside the answer."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

CHAPTER = Path(__file__).resolve().parents[1]
PAGE = CHAPTER / "app" / "web" / "index.html"
POLICIES = sorted((CHAPTER / "app" / "policies").glob("*.html"))


def test_there_are_policy_pages_to_cite() -> None:
    assert len(POLICIES) >= 3


@pytest.mark.parametrize("path", POLICIES, ids=lambda p: p.name)
def test_each_policy_page_is_a_small_titled_page_with_no_links(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert "<title>" in text and "<h1>" in text
    assert re.search(r"https?:[/][/]", text, re.IGNORECASE) is None
    assert "<script" not in text.lower()
    assert re.fullmatch(r"[a-z0-9-]+\.html", path.name)  # matches what the handler accepts


def test_page_shows_the_cited_page_in_a_locked_frame_beside_the_chat() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert '<iframe id="page"' in page
    assert 'sandbox=""' in page  # a policy page can run no script and submit no form
    assert 'frame.src = "/" + source.page' in page  # same address as the chat, no other host


def test_page_only_frames_pages_from_the_policy_folder() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert "policies\\/[A-Za-z0-9._-]+\\.html" in page
    assert "if (!PAGE.test(source.page)) return;" in page


def test_page_lists_the_sources_and_shows_the_first_one() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert "addSources(data.sources)" in page
    assert "show(sources[0])" in page
    assert "Array.isArray(sources)" in page  # an answer with no sources must not break the page
