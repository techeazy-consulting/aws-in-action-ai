"""Chapter 5: the /tickets handler, with the model and the table faked so nothing touches AWS."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

CHAPTER = Path(__file__).resolve().parents[1]
HANDLER = CHAPTER / "app" / "tickets" / "handler.py"


@pytest.fixture
def mod(monkeypatch: pytest.MonkeyPatch) -> Any:
    """The handler module, loaded fresh, with boto3 replaced so nothing touches AWS."""
    monkeypatch.setenv("TICKETS_TABLE", "tickets-table")
    monkeypatch.setenv("MODEL_ID", "test-model")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    fake_boto3 = types.SimpleNamespace(client=lambda *a, **k: object())
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    spec = importlib.util.spec_from_file_location("tickets_handler", HANDLER)
    assert spec and spec.loader
    module: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeTable:
    """Stands in for the dynamodb client: one counter item plus the tickets."""

    def __init__(self, fail: bool = False) -> None:
        self.items: dict[str, dict[str, Any]] = {}
        self.counter = 0
        self.fail = fail
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def update_item(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("update_item", kwargs))
        if self.fail:
            raise RuntimeError("ProvisionedThroughputExceededException")
        self.counter += int(kwargs["ExpressionAttributeValues"][":one"]["N"])
        return {"Attributes": {"LastNumber": {"N": str(self.counter)}}}

    def put_item(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("put_item", kwargs))
        if self.fail:
            raise RuntimeError("ProvisionedThroughputExceededException")
        self.items[kwargs["Item"]["TicketId"]["S"]] = kwargs["Item"]
        return {}

    def get_item(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("get_item", kwargs))
        if self.fail:
            raise RuntimeError("ProvisionedThroughputExceededException")
        item = self.items.get(kwargs["Key"]["TicketId"]["S"])
        return {"Item": item} if item else {}


class FakeModel:
    """Stands in for the bedrock-runtime client: plays back one scripted response per call."""

    def __init__(self, *responses: dict[str, Any], fail: bool = False) -> None:
        self.responses = list(responses)
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(json.loads(json.dumps(kwargs)))  # a copy: messages grow after the call
        if self.fail:
            raise RuntimeError("ThrottlingException")
        return self.responses.pop(0)


def says(text: str) -> dict[str, Any]:
    message = {"role": "assistant", "content": [{"text": text}]}
    return {"output": {"message": message}, "stopReason": "end_turn"}


def asks(name: str, tool_input: Any, tool_use_id: str = "tooluse_1") -> dict[str, Any]:
    block = {"toolUse": {"toolUseId": tool_use_id, "name": name, "input": tool_input}}
    return {"output": {"message": {"role": "assistant", "content": [block]}}, "stopReason": "tool_use"}


def post(message: Any) -> dict[str, Any]:
    return {"body": json.dumps({"message": message})}


def tool_result(call: dict[str, Any]) -> dict[str, Any]:
    """The toolResult block the handler sent back in the last user message of a model call."""
    return call["messages"][-1]["content"][0]["toolResult"]


def test_the_request_offers_both_tools_with_json_schemas(mod: Any) -> None:
    mod.bedrock, mod.dynamodb = FakeModel(says("Hello.")), FakeTable()
    mod.handler(post("hi"), None)
    config = mod.bedrock.calls[0]["toolConfig"]
    names = [t["toolSpec"]["name"] for t in config["tools"]]
    assert names == ["create_ticket", "get_ticket_status"]
    for tool in config["tools"]:
        schema = tool["toolSpec"]["inputSchema"]["json"]
        assert schema["type"] == "object" and schema["required"]
    assert mod.bedrock.calls[0]["modelId"] == "test-model"


def test_a_request_that_needs_no_tool_is_answered_directly(mod: Any) -> None:
    mod.bedrock, mod.dynamodb = FakeModel(says("Hello, how can I help?")), FakeTable()
    out = mod.handler(post("hi"), None)
    assert out["statusCode"] == 200
    assert json.loads(out["body"]) == {"answer": "Hello, how can I help?", "tools_used": []}
    assert mod.dynamodb.calls == []


def test_create_ticket_round_trip_gives_a_readable_id_and_returns_the_result_to_the_model(
    mod: Any,
) -> None:
    mod.dynamodb = FakeTable()
    mod.bedrock = FakeModel(
        asks("create_ticket", {"title": "Figma access", "requester": "Priya"}),
        says("Done. Your ticket is 1001."),
    )
    out = mod.handler(post("Please request Figma access for me, I am Priya"), None)
    assert out["statusCode"] == 200
    body = json.loads(out["body"])
    assert body == {"answer": "Done. Your ticket is 1001.", "tools_used": ["create_ticket"]}
    # the table holds the ticket under the readable id
    assert mod.dynamodb.items["1001"]["Title"] == {"S": "Figma access"}
    assert mod.dynamodb.items["1001"]["Status"] == {"S": "open"}
    # the second model call carries the tool's result, matched to the request by its id
    second = mod.bedrock.calls[1]
    assistant, user = second["messages"][-2], second["messages"][-1]
    assert "toolUse" in assistant["content"][0] and user["role"] == "user"
    result = tool_result(second)
    assert result["toolUseId"] == "tooluse_1"
    assert result["content"] == [{"json": {"ticket_id": "1001", "status": "open"}}]
    assert "status" not in result  # success carries no error status


def test_ticket_numbers_count_up_from_1001(mod: Any) -> None:
    mod.dynamodb = FakeTable()
    args = {"title": "VPN", "requester": "Sam"}
    mod.bedrock = FakeModel(asks("create_ticket", args), says("ok"), asks("create_ticket", args), says("ok"))
    mod.handler(post("one"), None)
    mod.handler(post("two"), None)
    assert sorted(mod.dynamodb.items) == ["1001", "1002"]
    puts = [kw for name, kw in mod.dynamodb.calls if name == "put_item"]
    assert all(kw["ConditionExpression"] == "attribute_not_exists(TicketId)" for kw in puts)


def test_get_ticket_status_reads_the_ticket_and_returns_it_to_the_model(mod: Any) -> None:
    mod.dynamodb = FakeTable()
    mod.dynamodb.items["1042"] = {
        "TicketId": {"S": "1042"},
        "Title": {"S": "New laptop"},
        "Status": {"S": "open"},
    }
    mod.bedrock = FakeModel(asks("get_ticket_status", {"ticket_id": "1042"}), says("It is open."))
    out = mod.handler(post("status of 1042?"), None)
    assert json.loads(out["body"])["tools_used"] == ["get_ticket_status"]
    result = tool_result(mod.bedrock.calls[1])
    assert result["content"] == [
        {"json": {"ticket_id": "1042", "title": "New laptop", "status": "open"}}
    ]


def test_an_unknown_ticket_is_reported_to_the_model_as_an_error_not_a_crash(mod: Any) -> None:
    mod.dynamodb = FakeTable()
    mod.bedrock = FakeModel(asks("get_ticket_status", {"ticket_id": "9999"}), says("No such ticket."))
    out = mod.handler(post("status of 9999?"), None)
    assert out["statusCode"] == 200
    result = tool_result(mod.bedrock.calls[1])
    assert result["status"] == "error"
    assert "9999" in result["content"][0]["text"]


@pytest.mark.parametrize("bad_id", ["counter", "", "abc", "10 42", "../1042"])
def test_only_ticket_numbers_can_be_looked_up_never_the_counter_item(mod: Any, bad_id: str) -> None:
    mod.dynamodb = FakeTable()
    mod.bedrock = FakeModel(asks("get_ticket_status", {"ticket_id": bad_id}), says("Which ticket?"))
    mod.handler(post("status?"), None)
    assert tool_result(mod.bedrock.calls[1])["status"] == "error"
    assert mod.dynamodb.calls == []  # the table was never touched


@pytest.mark.parametrize(
    "bad_id",
    ["1042; DROP", "1042 ", "١٠٤٢", "12", "1" * 10, "-1042", "1042.0", "0x1042", "10\n42", "1042/../x"],
)
def test_ticket_ids_are_digits_only_and_bounded(mod: Any, bad_id: str) -> None:
    # ("1042 " with a trailing space is trimmed by the handler, so it is the one valid case here)
    mod.dynamodb = FakeTable()
    mod.dynamodb.items["1042"] = {"TicketId": {"S": "1042"}, "Title": {"S": "t"}, "Status": {"S": "open"}}
    mod.bedrock = FakeModel(asks("get_ticket_status", {"ticket_id": bad_id}), says("ok"))
    mod.handler(post("status?"), None)
    result = tool_result(mod.bedrock.calls[1])
    if bad_id.strip() == "1042":
        assert "status" not in result
    else:
        assert result["status"] == "error"
        assert mod.dynamodb.calls == []


def test_model_input_can_never_pick_the_table_or_the_key(mod: Any) -> None:
    mod.dynamodb = FakeTable()
    mod.dynamodb.items["1042"] = {"TicketId": {"S": "1042"}, "Title": {"S": "t"}, "Status": {"S": "open"}}
    sneaky = {"ticket_id": "1042", "TableName": "other-table", "Key": {"TicketId": {"S": "counter"}}}
    mod.bedrock = FakeModel(asks("get_ticket_status", sneaky), says("ok"))
    mod.handler(post("status?"), None)
    (name, call), = mod.dynamodb.calls
    assert name == "get_item"
    assert call["TableName"] == "tickets-table"  # from the environment, not from the model
    assert call["Key"] == {"TicketId": {"S": "1042"}}


def test_status_lookup_returns_only_what_a_requester_needs(mod: Any) -> None:
    mod.dynamodb = FakeTable()
    mod.dynamodb.items["1042"] = {
        "TicketId": {"S": "1042"},
        "Title": {"S": "New laptop"},
        "Requester": {"S": "Priya"},
        "Status": {"S": "open"},
        "InternalNote": {"S": "do not share"},
    }
    mod.bedrock = FakeModel(asks("get_ticket_status", {"ticket_id": "1042"}), says("Open."))
    mod.handler(post("status of 1042?"), None)
    sent = json.dumps(tool_result(mod.bedrock.calls[1]))
    assert "Priya" not in sent and "do not share" not in sent
    assert set(tool_result(mod.bedrock.calls[1])["content"][0]["json"]) == {"ticket_id", "title", "status"}


@pytest.mark.parametrize(
    "args, missing",
    [
        ({"title": "Figma access"}, "requester"),
        ({"requester": "Priya"}, "title"),
        ({"title": "   ", "requester": "Priya"}, "title"),
        ({}, "title"),
    ],
)
def test_a_request_missing_a_detail_creates_nothing_and_tells_the_model_what_to_ask(
    mod: Any, args: dict[str, Any], missing: str
) -> None:
    mod.dynamodb = FakeTable()
    mod.bedrock = FakeModel(asks("create_ticket", args), says("Who is asking?"))
    out = mod.handler(post("I need access"), None)
    assert out["statusCode"] == 200
    result = tool_result(mod.bedrock.calls[1])
    assert result["status"] == "error"
    assert missing in result["content"][0]["text"]
    assert mod.dynamodb.items == {} and mod.dynamodb.counter == 0


def test_tool_input_that_is_not_an_object_is_handled(mod: Any) -> None:
    mod.dynamodb = FakeTable()
    mod.bedrock = FakeModel(asks("create_ticket", "oops"), says("What do you need?"))
    assert mod.handler(post("help"), None)["statusCode"] == 200
    assert tool_result(mod.bedrock.calls[1])["status"] == "error"


def test_a_failing_tool_is_an_error_result_with_a_safe_message_and_the_request_still_answers(
    mod: Any,
) -> None:
    mod.dynamodb = FakeTable(fail=True)
    mod.bedrock = FakeModel(
        asks("create_ticket", {"title": "Figma", "requester": "Priya"}),
        says("Sorry, the ticket system is down. Please try again."),
    )
    out = mod.handler(post("open a ticket for Figma, I am Priya"), None)
    assert out["statusCode"] == 200
    result = tool_result(mod.bedrock.calls[1])
    assert result["status"] == "error"
    assert "ProvisionedThroughput" not in json.dumps(result)  # the raw error stays in the logs


def test_an_unknown_tool_name_is_an_error_result(mod: Any) -> None:
    mod.dynamodb = FakeTable()
    mod.bedrock = FakeModel(asks("delete_everything", {}), says("I cannot do that."))
    assert mod.handler(post("do it"), None)["statusCode"] == 200
    assert tool_result(mod.bedrock.calls[1])["status"] == "error"


def test_two_tool_requests_in_one_turn_both_get_a_result(mod: Any) -> None:
    mod.dynamodb = FakeTable()
    blocks = [
        {"toolUse": {"toolUseId": "a", "name": "get_ticket_status", "input": {"ticket_id": "1001"}}},
        {"toolUse": {"toolUseId": "b", "name": "get_ticket_status", "input": {"ticket_id": "1002"}}},
    ]
    both = {"output": {"message": {"role": "assistant", "content": blocks}}, "stopReason": "tool_use"}
    mod.bedrock = FakeModel(both, says("Neither exists."))
    mod.handler(post("check 1001 and 1002"), None)
    sent = mod.bedrock.calls[1]["messages"][-1]["content"]
    assert [b["toolResult"]["toolUseId"] for b in sent] == ["a", "b"]


def test_a_model_that_keeps_asking_for_tools_stops_at_the_round_limit(mod: Any) -> None:
    mod.dynamodb = FakeTable()
    mod.bedrock = FakeModel(*[asks("get_ticket_status", {"ticket_id": "1001"}) for _ in range(10)])
    out = mod.handler(post("loop forever"), None)
    assert out["statusCode"] == 502
    assert len(mod.bedrock.calls) == mod.MAX_ROUNDS


def test_a_tool_use_stop_with_no_tool_request_is_a_502_not_a_hang(mod: Any) -> None:
    empty = {"output": {"message": {"role": "assistant", "content": [{"text": "hm"}]}}, "stopReason": "tool_use"}
    mod.dynamodb, mod.bedrock = FakeTable(), FakeModel(empty)
    assert mod.handler(post("hi"), None)["statusCode"] == 502


@pytest.mark.parametrize("event", [post(""), post("   "), post(None), post(42), {}, {"body": "x"}])
def test_missing_or_empty_message_is_400_and_the_model_not_called(mod: Any, event: Any) -> None:
    mod.bedrock, mod.dynamodb = FakeModel(), FakeTable()
    out = mod.handler(event, None)
    assert out["statusCode"] == 400
    assert mod.bedrock.calls == []


def test_overlong_message_is_400(mod: Any) -> None:
    mod.bedrock, mod.dynamodb = FakeModel(says("ok")), FakeTable()
    assert mod.handler(post("x" * (mod.MAX_MESSAGE + 1)), None)["statusCode"] == 400
    assert mod.handler(post("x" * mod.MAX_MESSAGE), None)["statusCode"] == 200


def test_model_error_is_502_with_safe_message(mod: Any) -> None:
    mod.bedrock, mod.dynamodb = FakeModel(fail=True), FakeTable()
    out = mod.handler(post("hello"), None)
    assert out["statusCode"] == 502
    assert "Throttling" not in out["body"]
