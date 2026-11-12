"""Work out the cost of one ticket from totals you read off the dashboard.

    cost per ticket = (input tokens / per x input price
                       + output tokens / per x output price
                       + other costs) / tickets

No price is written in this file or anywhere in this course. Read the current prices on the
model's pricing page yourself, in the unit that page uses, and pass them in. `--per` is the
number of tokens one price covers (for a price quoted per thousand tokens, 1000). The result is
in whatever currency your prices are in. "Other costs" is anything else you want counted for the
same period, such as the guardrail, the knowledge base and the dashboard: add them up yourself.

Exit code: 0 printed a result, 2 a number was missing or not valid.
"""

import argparse
import math
import sys


def cost_per_ticket(input_tokens, output_tokens, tickets, input_price, output_price, per, other_costs=0):
    """The formula above. Every number must be a finite, non-negative number; tickets and per above zero."""
    values = {
        "input tokens": input_tokens,
        "output tokens": output_tokens,
        "tickets": tickets,
        "input price": input_price,
        "output price": output_price,
        "per": per,
        "other costs": other_costs,
    }
    for name, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be a number that is not negative")
    if tickets <= 0:
        raise ValueError("tickets must be more than zero: there is no cost per ticket without a ticket")
    if per <= 0:
        raise ValueError("per must be more than zero")
    total = input_tokens / per * input_price + output_tokens / per * output_price + other_costs
    return total / tickets


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    for name in ("input-tokens", "output-tokens", "tickets", "input-price", "output-price", "per"):
        parser.add_argument(f"--{name}", type=float, required=True)
    parser.add_argument("--other-costs", type=float, default=0.0)
    args = parser.parse_args(argv)
    try:
        result = cost_per_ticket(
            args.input_tokens, args.output_tokens, args.tickets,
            args.input_price, args.output_price, args.per, args.other_costs,
        )
    except ValueError as err:
        print(f"cannot work it out: {err}", file=sys.stderr)
        return 2
    print(f"cost per ticket = {result:.6f} (in the currency of the prices you entered)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
