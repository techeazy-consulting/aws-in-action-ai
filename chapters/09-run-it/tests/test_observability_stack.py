"""Chapter 9: JSON logs, log-derived metrics, two alarms and a dashboard, read from the template."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

CHAPTER = Path(__file__).resolve().parents[1]
TEMPLATES = [CHAPTER / "template.yaml", CHAPTER.parent / "student" / "template.yaml"]
FUNCTIONS = ("AskFunction", "TicketsFunction", "TriageFunction", "SigninFunction")
GROUPS = {
    "Ask": "AskFunctionLogGroup",
    "Tickets": "TicketsFunctionLogGroup",
    "Triage": "TriageFunctionLogGroup",
    "Signin": "SigninFunctionLogGroup",
}


def template_text() -> str:
    template = next((p for p in TEMPLATES if p.is_file()), None)
    if template is None:
        pytest.skip("template.yaml is not beside this folder")
    return template.read_text(encoding="utf-8")


def resource(name: str) -> str:
    text = template_text()
    start = text.index(f"\n  {name}:\n") + 1
    nxt = re.search(r"\n  [A-Za-z0-9]+:\n|\nOutputs:", text[start + 1 :])
    return text[start : start + 1 + nxt.start()] if nxt else text[start:]


def filters() -> dict[str, str]:
    return {m.group(1): resource(m.group(1)) for m in re.finditer(r"\n  (\w+Filter):\n", template_text())}


@pytest.mark.parametrize("function", FUNCTIONS)
def test_every_function_writes_json_logs_with_the_level_set_in_the_template(function: str) -> None:
    logging = resource(function).split("      LoggingConfig:\n")[1].split("      Code:")[0]
    assert "LogFormat: JSON" in logging and "ApplicationLogLevel: INFO" in logging


def test_the_handlers_do_not_set_the_log_level_themselves() -> None:
    for route in ("ask", "tickets", "triage", "signin"):
        assert "setLevel" not in (CHAPTER / "app" / route / "handler.py").read_text(encoding="utf-8")


def test_there_is_one_error_filter_per_function_and_token_filters_for_the_two_model_routes() -> None:
    found = filters()
    assert {f"{r}ErrorsFilter" for r in GROUPS} <= set(found)
    for route in ("Tickets", "Triage"):
        for kind in ("ModelRequests", "InputTokens", "OutputTokens"):
            assert f"{route}{kind}Filter" in found
    assert "TicketsCreatedFilter" in found
    assert len(found) == 11
    assert "AskInputTokensFilter" not in found  # the ask call reports no token count


def test_each_filter_reads_the_structured_summary_line_of_its_own_log_group() -> None:
    for name, body in filters().items():
        route = re.match(r"(Ask|Tickets|Triage|Signin)", name)
        assert route and f"LogGroupName: !Ref {GROUPS[route.group(1)]}" in body, name
        assert "$.event = \"request\"" in body, name  # the summary line, not any other log line
        assert 'MetricNamespace: !Sub "Helpdesk/${Environment}"' in body, name


def test_the_error_filters_match_the_outcome_the_handlers_log() -> None:
    for route in GROUPS:
        assert '$.outcome = "error"' in filters()[f"{route}ErrorsFilter"]
    outcomes = {"error"}
    for route in ("ask", "tickets", "triage", "signin"):
        assert 'return "error"' in (CHAPTER / "app" / route / "handler.py").read_text(encoding="utf-8")
    assert outcomes == {"error"}


def test_token_filters_take_their_value_from_the_field_the_handlers_log() -> None:
    assert 'MetricValue: "$.input_tokens"' in filters()["TicketsInputTokensFilter"]
    assert 'MetricValue: "$.output_tokens"' in filters()["TriageOutputTokensFilter"]
    assert 'MetricValue: "$.tickets_created"' in filters()["TicketsCreatedFilter"]
    for route in ("tickets", "triage"):
        source = (CHAPTER / "app" / route / "handler.py").read_text(encoding="utf-8")
        assert "input_tokens=stats.input_tokens" in source and "output_tokens=stats.output_tokens" in source
    assert 'fields["tickets_created"]' in (CHAPTER / "app" / "tickets" / "handler.py").read_text(encoding="utf-8")


@pytest.mark.parametrize("alarm", ["ErrorsAlarm", "ApiServerErrorsAlarm"])
def test_both_alarms_email_through_the_existing_escalation_topic(alarm: str) -> None:
    body = resource(alarm)
    assert "AlarmActions:\n        - !Ref EscalationTopic" in body
    assert "TreatMissingData: notBreaching" in body  # a quiet hour is not an error
    assert "Statistic: Sum" in body and "ComparisonOperator: GreaterThanOrEqualToThreshold" in body
    assert "chapter" in body and "session-09" in body


def test_the_error_alarm_watches_the_metric_the_filters_write() -> None:
    body = resource("ErrorsAlarm")
    assert "MetricName: Errors" in body and 'Namespace: !Sub "Helpdesk/${Environment}"' in body
    api = resource("ApiServerErrorsAlarm")
    assert "Namespace: AWS/ApiGateway" in api and "MetricName: 5xx" in api and "Value: !Ref HelpdeskApi" in api


def dashboard() -> dict:
    body = resource("HelpdeskDashboard").split("DashboardBody: !Sub\n        - |\n")[1].split("        # The Bedrock runtime")[0]
    text = "\n".join(line[10:] for line in body.splitlines())
    substituted = (
        text.replace("${AWS::Region}", "us-east-1")
        .replace("${Environment}", "staging")
        .replace("${HelpdeskApi}", "abc123")
        .replace("${ModelInUseId}", "us.model-id")
        .replace("${ErrorsAlarm.Arn}", "alarm-arn")
    )
    assert "${" not in substituted, "a placeholder was left in the dashboard body"
    return json.loads(substituted)


def test_the_dashboard_body_is_valid_json_with_widgets_inside_the_24_column_grid() -> None:
    widgets = dashboard()["widgets"]
    assert len(widgets) >= 6
    for widget in widgets:
        assert widget["type"] in {"metric", "text"}
        assert widget["x"] + widget["width"] <= 24 and widget["height"] > 0


def test_every_custom_metric_on_the_dashboard_is_one_a_filter_writes() -> None:
    written = set(re.findall(r"MetricName: (\w+)", "".join(filters().values())))
    used = set()
    for widget in dashboard()["widgets"]:
        for metric in widget["properties"].get("metrics", []):
            if metric and isinstance(metric[0], str) and metric[0].startswith("Helpdesk/"):
                used.add(metric[1])
    assert used and used <= written, used - written


def test_tokens_per_request_is_a_ratio_of_two_logged_sums_and_per_call_comes_from_the_bedrock_metrics() -> None:
    widgets = {w["properties"]["title"]: w["properties"] for w in dashboard()["widgets"] if w["type"] == "metric"}
    per_request = next(p for t, p in widgets.items() if t.startswith("Tokens per request"))
    assert {m[0]["expression"] for m in per_request["metrics"] if isinstance(m[0], dict)} == {"tin / treq", "tout / treq"}
    per_call = next(p for t, p in widgets.items() if "Bedrock runtime metrics" in t)
    names = [m[1] for m in per_call["metrics"] if isinstance(m[0], str)]
    assert names == ["InputTokenCount", "OutputTokenCount", "Invocations"]
    assert all(m[0] == "AWS/Bedrock" and m[2] == "ModelId" for m in per_call["metrics"] if isinstance(m[0], str))
    # filed under the id the function calls, which is the inference profile id when one is used
    assert all(m[3] == "us.model-id" for m in per_call["metrics"] if isinstance(m[0], str))


def test_the_error_widget_shows_the_alarm_line() -> None:
    widget = next(w for w in dashboard()["widgets"] if w["properties"].get("annotations"))
    assert widget["properties"]["annotations"] == {"alarms": ["alarm-arn"]}


def test_the_dashboard_states_a_formula_and_no_price() -> None:
    text = json.dumps(dashboard())
    assert "Cost per ticket" in text and "none is written here" in text
    assert not re.search(r"\$\s?\d|\bUSD\b|per million|per 1,?000", text)


def test_the_voice_teaser_is_slides_only_so_no_voice_resource_or_code_exists() -> None:
    text = template_text().lower()
    for word in ("sonic", "voice", "polly", "transcribe", "speech"):
        assert word not in text, word
    for path in (CHAPTER / "app").rglob("*"):
        if path.is_file() and path.suffix in {".py", ".html", ".json"}:
            body = path.read_text(encoding="utf-8").lower()
            assert "sonic" not in body and "voice" not in body, path.name


def test_chapter_9_keeps_the_chapter_8_resources() -> None:
    text = template_text()
    for logical_id in ("EscalationTopic", "HelpdeskUserPool", "HelpdeskGuardrail", "SiteBucket", "TriageFunction"):
        assert f"\n  {logical_id}:\n" in text


def test_the_stack_outputs_name_the_dashboard_and_the_alarm_to_test() -> None:
    text = template_text()
    assert "  DashboardName:\n" in text and "  ErrorsAlarmName:\n" in text


def test_nothing_is_retained_and_no_deletion_protection_is_set() -> None:
    text = template_text()
    assert "DeletionPolicy: Retain" not in text and "DeletionProtection" not in text
