"""Chapter 9: the cost-per-ticket formula. No price is written anywhere; these numbers are made up."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any

import pytest

CHAPTER = Path(__file__).resolve().parents[1]
SCRIPT = CHAPTER / "app" / "ops" / "cost.py"


def load() -> Any:
    spec = importlib.util.spec_from_file_location("ops_cost", SCRIPT)
    assert spec and spec.loader
    module: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def cost() -> Any:
    return load()


def test_the_formula_with_made_up_round_numbers(cost: Any) -> None:
    # 2000 in at 1 per 1000, 500 out at 4 per 1000, plus 3 other, over 5 tickets
    assert cost.cost_per_ticket(2000, 500, 5, 1, 4, 1000, 3) == pytest.approx((2 + 2 + 3) / 5)


def test_other_costs_default_to_nothing(cost: Any) -> None:
    assert cost.cost_per_ticket(1000, 1000, 1, 2, 2, 1000) == pytest.approx(4)


def test_more_tickets_means_a_lower_cost_per_ticket(cost: Any) -> None:
    assert cost.cost_per_ticket(1000, 1000, 4, 2, 2, 1000) < cost.cost_per_ticket(1000, 1000, 2, 2, 2, 1000)


@pytest.mark.parametrize(
    "args",
    [
        (1000, 1000, 0, 1, 1, 1000),  # no tickets: no cost per ticket
        (1000, 1000, 1, 1, 1, 0),  # a price per zero tokens
        (-1, 0, 1, 1, 1, 1000),
        (0, 0, 1, -1, 1, 1000),
        (0, 0, 1, 1, float("nan"), 1000),
        (0, 0, 1, 1, float("inf"), 1000),
        (True, 0, 1, 1, 1, 1000),
        ("100", 0, 1, 1, 1, 1000),
        (None, 0, 1, 1, 1, 1000),
    ],
)
def test_a_missing_or_impossible_number_is_refused(cost: Any, args: tuple[Any, ...]) -> None:
    with pytest.raises(ValueError):
        cost.cost_per_ticket(*args)


def test_the_command_needs_every_number_and_never_assumes_a_price(cost: Any, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cost.main(["--input-tokens", "1000", "--output-tokens", "100", "--tickets", "2"])
    assert exit_info.value.code == 2  # the prices and per are required
    assert "--input-price" in capsys.readouterr().err


def test_the_command_prints_a_result_and_returns_2_for_a_bad_number(cost: Any, capsys: pytest.CaptureFixture[str]) -> None:
    good = ["--input-tokens", "2000", "--output-tokens", "500", "--tickets", "5",
            "--input-price", "1", "--output-price", "4", "--per", "1000", "--other-costs", "3"]
    assert cost.main(good) == 0 and "cost per ticket = 1.400000" in capsys.readouterr().out
    assert cost.main(["--input-tokens", "1", "--output-tokens", "1", "--tickets", "0",
                      "--input-price", "1", "--output-price", "1", "--per", "1000"]) == 2
    assert "tickets must be more than zero" in capsys.readouterr().err


def test_no_price_default_is_written_in_the_script() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert not re.search(r"(input|output)[-_]price[^\n]*default", text)
    assert not re.search(r"\$\s?\d|\bUSD\b|per million|per 1,?000", text)
