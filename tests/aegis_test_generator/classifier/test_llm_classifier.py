from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from aegis_test_generator.classifier.llm_classifier import (
    ClassifierError,
    ClassifierResponseError,
    _build_messages,
    classify_transitions,
)


def _fake_response(content: str | None) -> MagicMock:
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


def _client_with(content: str | None) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create.return_value = _fake_response(content)
    return client


def test_classify_transitions_happy_path() -> None:
    payload = {
        "annotations": [
            {"check_id": "a", "applicable": False, "reason": "expected by patch"},
            {"check_id": "b", "applicable": True, "reason": "still relevant"},
        ]
    }
    client = _client_with(json.dumps(payload))
    result = classify_transitions(
        [{"check_id": "a"}, {"check_id": "b"}],
        parsed_input={"patch": {"raw_yaml": "- hosts: all"}},
        client=client,
    )
    assert len(result.annotations) == 2
    assert result.warnings == []
    assert result.annotations[0]["check_id"] == "a"


def test_invalid_json_raises() -> None:
    client = _client_with("not json")
    with pytest.raises(ClassifierResponseError):
        classify_transitions([{"check_id": "a"}], parsed_input={}, client=client)


def test_missing_annotations_raises() -> None:
    client = _client_with(json.dumps({"x": []}))
    with pytest.raises(ClassifierResponseError):
        classify_transitions([{"check_id": "a"}], parsed_input={}, client=client)


def test_row_shape_warnings() -> None:
    payload = {
        "annotations": [
            {"check_id": "a", "applicable": False, "reason": "ok"},
            {"check_id": "", "applicable": False},
            {"check_id": "b", "applicable": "nope"},
        ]
    }
    client = _client_with(json.dumps(payload))
    result = classify_transitions([{"check_id": "a"}], parsed_input={}, client=client)
    assert len(result.annotations) == 1
    assert len(result.warnings) == 2


def test_openai_error_wrapped() -> None:
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("boom")
    with pytest.raises(ClassifierError):
        classify_transitions([{"check_id": "a"}], parsed_input={}, client=client)


def test_build_messages_mentions_role() -> None:
    messages = _build_messages([], parsed_input={})
    assert messages[0]["role"] == "system"
    system_content = messages[0]["content"]
    for token in ("role", "verify", "guard", "verification_failed"):
        assert token in system_content, f"missing token {token!r} in system prompt"

