"""Shared OpenAI Chat Completions helper for planner and classifier.

Both :mod:`aegis_test_generator.planner.llm_planner` and
:mod:`aegis_test_generator.classifier.llm_classifier` need to issue the same
constrained JSON-object chat completion. This module owns the actual API call
so the two domain modules only translate failures into their own exception
hierarchies.

Environment variables
---------------------
``OPENAI_API_KEY``
    Required when ``call_openai`` is invoked without an injected ``client``.
``OPENAI_MODEL``
    Optional override; falls back to the caller-supplied ``default_model``.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai import OpenAI

__all__ = [
    "OpenAICallError",
    "OpenAIConfigError",
    "OpenAIRequestError",
    "call_openai",
]


class OpenAICallError(Exception):
    """Base error for all :func:`call_openai` failures."""


class OpenAIConfigError(OpenAICallError):
    """Missing ``OPENAI_API_KEY`` or ``openai`` package."""


class OpenAIRequestError(OpenAICallError):
    """API call failed or returned empty/invalid content."""


def call_openai(
    messages: list[dict[str, str]],
    *,
    client: "OpenAI | None",
    model: str | None,
    default_model: str,
) -> tuple[str, str]:
    """Issue a JSON-object chat completion and return ``(content, resolved_model)``."""
    resolved_model = model or os.environ.get("OPENAI_MODEL", default_model)

    if client is None:
        if not os.environ.get("OPENAI_API_KEY"):
            raise OpenAIConfigError(
                "OPENAI_API_KEY is required when no client is passed"
            )
        try:
            from openai import OpenAI as OpenAIClient
        except ImportError as exc:
            raise OpenAIConfigError(
                "openai package is required — pip install openai"
            ) from exc
        client = OpenAIClient(api_key=os.environ["OPENAI_API_KEY"])

    try:
        response = client.chat.completions.create(
            model=resolved_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,
        )
    except Exception as exc:
        raise OpenAIRequestError(f"OpenAI request failed: {exc}") from exc

    choice = response.choices[0]
    content = choice.message.content
    if content is None or not str(content).strip():
        raise OpenAIRequestError("OpenAI returned empty message content")
    return str(content), resolved_model
