# 05 - The cost-per-ticket formula

## Goal

Write the small command that works out a ticket's cost from totals you read off the dashboard, with no price in it.

## Prompt

```text
Create app/ops/cost.py and tests/test_cost.py.

cost per ticket = (input tokens / per x input price + output tokens / per x output price + other
costs) / tickets.
- cost_per_ticket(...) validates every number: finite, not negative, not a boolean; tickets and
  per must be above zero. Raise ValueError with a plain sentence otherwise.
- The command takes --input-tokens, --output-tokens, --tickets, --input-price, --output-price and
  --per, all required, and --other-costs (default 0). It must never default a price. Print the
  result in the currency of the prices entered; exit 2 for a bad number.
- No price, currency sign or price unit appears in the file. The tests use made-up round numbers.
```

## Check

```bash
pytest -q tests/test_cost.py
python app/ops/cost.py --input-tokens 2000 --output-tokens 500 --tickets 5 --input-price 1 --output-price 4 --per 1000
python app/ops/cost.py --input-tokens 1 --output-tokens 1 --tickets 0 --input-price 1 --output-price 1 --per 1000; echo "exit $?"
```
