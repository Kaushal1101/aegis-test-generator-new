from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from aegis_test_generator._openai_client import (
    OpenAIConfigError,
    OpenAIRequestError,
    call_openai,
)


_DEFAULT_MODEL = "gpt-default-test"


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


def test_call_openai_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    client = _client_with('{"ok": true}')
    content, resolved = call_openai(
        [{"role": "system", "content": "hi"}],
        client=client,
        model="gpt-explicit",
        default_model=_DEFAULT_MODEL,
    )
    assert content == '{"ok": true}'
    assert resolved == "gpt-explicit"
    client.chat.completions.create.assert_called_once()
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-explicit"
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["temperature"] == 0


def test_call_openai_uses_default_model_when_none_passed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    client = _client_with('{"ok": 1}')
    _, resolved = call_openai(
        [{"role": "system", "content": "hi"}],
        client=client,
        model=None,
        default_model=_DEFAULT_MODEL,
    )
    assert resolved == _DEFAULT_MODEL
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == _DEFAULT_MODEL


def test_call_openai_uses_env_model_over_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    client = _client_with('{"ok": 1}')
    _, resolved = call_openai(
        [{"role": "system", "content": "hi"}],
        client=client,
        model=None,
        default_model=_DEFAULT_MODEL,
    )
    assert resolved == "gpt-test"
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-test"


def test_call_openai_missing_api_key_raises_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(OpenAIConfigError):
        call_openai(
            [{"role": "system", "content": "hi"}],
            client=None,
            model=None,
            default_model=_DEFAULT_MODEL,
        )


def test_call_openai_api_failure_raises_request_error() -> None:
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("boom")
    with pytest.raises(OpenAIRequestError):
        call_openai(
            [{"role": "system", "content": "hi"}],
            client=client,
            model="gpt-test",
            default_model=_DEFAULT_MODEL,
        )


def test_call_openai_empty_content_raises_request_error() -> None:
    client = _client_with(None)
    with pytest.raises(OpenAIRequestError):
        call_openai(
            [{"role": "system", "content": "hi"}],
            client=client,
            model="gpt-test",
            default_model=_DEFAULT_MODEL,
        )
