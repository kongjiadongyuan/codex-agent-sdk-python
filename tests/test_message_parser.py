"""Tests for Codex message parsing heuristics."""

from codex_agent_sdk._internal.message_parser import (
    default_final_event_predicate,
    parse_message,
)
from codex_agent_sdk.types import CodexEvent, CodexMessage


def test_parse_message_basic_role_content():
    event = {"role": "assistant", "content": "Hello"}
    msg = parse_message(event)
    assert isinstance(msg, CodexMessage)
    assert msg.kind == "item"
    assert msg.role == "assistant"
    assert msg.text == "Hello"


def test_parse_message_tool_event():
    event = {
        "type": "tool_call",
        "tool": {"name": "shell", "input": {"command": "ls"}},
    }
    msg = parse_message(event)
    assert isinstance(msg, CodexMessage)
    assert msg.kind == "tool"
    assert msg.tool_name == "shell"
    assert msg.tool_input == {"command": "ls"}


def test_parse_message_error_event():
    event = {"type": "error", "error": "boom"}
    msg = parse_message(event)
    assert isinstance(msg, CodexMessage)
    assert msg.kind == "error"
    assert msg.error == "boom"


def test_parse_message_delta_event():
    event = {"type": "response.output_text.delta", "delta": "hi"}
    msg = parse_message(event)
    assert isinstance(msg, CodexMessage)
    assert msg.kind == "item"
    assert msg.text == "hi"


def test_parse_message_result_event():
    event = {"type": "result", "status": "completed"}
    msg = parse_message(event)
    assert isinstance(msg, CodexEvent)
    assert msg.kind == "turn"
    assert msg.status == "completed"


def test_parse_message_item_completed_agent_message():
    event = {
        "type": "item.completed",
        "item": {"id": "item_1", "type": "agent_message", "text": "Hello"},
    }
    msg = parse_message(event)
    assert isinstance(msg, CodexMessage)
    assert msg.kind == "item"
    assert msg.role == "assistant"
    assert msg.text == "Hello"


def test_parse_message_turn_completed_is_final():
    event = {"type": "turn.completed", "status": "completed"}
    msg = parse_message(event)
    assert isinstance(msg, CodexEvent)
    assert msg.kind == "turn"


def test_parse_message_item_started_command_execution():
    event = {
        "type": "item.started",
        "item": {
            "id": "item_1",
            "type": "command_execution",
            "command": "/bin/zsh -lc ls",
            "status": "in_progress",
        },
    }
    msg = parse_message(event)
    assert isinstance(msg, CodexMessage)
    assert msg.kind == "tool"
    assert msg.tool_name == "command_execution"
    assert msg.tool_input == {"command": "/bin/zsh -lc ls"}


def test_parse_message_raw_event_fallback():
    event = {"foo": "bar"}
    msg = parse_message(event)
    assert isinstance(msg, CodexEvent)
    assert msg.kind == "raw"


def test_default_final_predicate():
    event = {"type": "turn.completed", "status": "completed"}
    msg = parse_message(event)
    assert default_final_event_predicate(msg) is True
