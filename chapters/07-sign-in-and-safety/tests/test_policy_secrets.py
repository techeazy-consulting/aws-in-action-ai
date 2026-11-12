"""Chapter 7: keep secrets out of the knowledge base. The guardrail does not read what is retrieved."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

POLICIES = sorted((Path(__file__).resolve().parents[1] / "app" / "policies").glob("*.html"))
SECRET_SHAPES = [
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:password|passwd|pwd|secret|token|api[ _-]?key)\s*(?:is|=|:)\s*\S"),
    re.compile(r"(?<![A-Za-z0-9/+=])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])"),
]


def test_there_are_policy_pages_to_check() -> None:
    assert POLICIES


@pytest.mark.parametrize("path", POLICIES, ids=lambda p: p.name)
def test_policy_pages_hold_no_secrets(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for shape in SECRET_SHAPES:
        assert shape.search(text) is None, f"{path.name} looks like it holds a secret ({shape.pattern})"


def test_the_check_can_fail() -> None:
    assert SECRET_SHAPES[2].search("the shared password is hunter2")
    assert SECRET_SHAPES[0].search("key " + "AKIA" + "ABCDEFGHIJKLMNOP")
