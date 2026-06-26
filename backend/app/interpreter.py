"""Natural-language intake: a server-side model call drafts a candidate event
definition from plain text.

The model only drafts. The Pydantic schema, the deterministic rules, and the human
approver still govern: this module faithfully captures what the user asked for and
hands it on for judgment. The Anthropic key is read from the environment server-side
and never returned to a caller.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

import anthropic

from .config import get_settings
from .rules import known_categories

_SYSTEM_PROMPT = """You turn a plain-language request for a new analytics tracking event into a single structured event definition.

Return ONLY a JSON object. No prose, no explanation, no markdown code fences.

The object has these fields:
- "name": the event name in Object Action, Title Case — each word capitalized, ending in a past-tense action verb (for example "Cart Cleared", "Coupon Applied", "Product Added to Wishlist", where lowercase connectors like "to" and "from" are allowed).
- "category": one of the valid categories listed below.
- "description": one short sentence describing when the event fires.
- "properties": a list of objects, each {{"name": a snake_case string, "type": one of "string" | "number" | "integer" | "boolean" | "array" | "object", "required": a boolean}}.

Valid categories: {categories}.

Capture faithfully exactly what the user asked for. Record the properties they describe, using the names they imply. If the user explicitly states a specific event name or property name, use it verbatim even if it does not match the conventions above. Do not drop, rename, or alter anything to make it pass a rule — separate downstream checks handle validation."""


class InterpreterError(Exception):
    """Raised when the model service itself fails (API error, timeout, connection)."""

    def __init__(self, model: str, message: str) -> None:
        self.model = model
        super().__init__(message)


@dataclass
class Interpretation:
    model: str
    proposed_definition: Optional[dict]
    raw_response: str
    parse_error: Optional[str]


def _strip_fences(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def interpret(raw_intake_text: str) -> Interpretation:
    """Draft a candidate definition from raw text. Returns the parsed draft, or a
    parse error if the model output was not a JSON object. Raises InterpreterError if
    the model service is unreachable."""
    settings = get_settings()
    model = settings.anthropic_model
    system = _SYSTEM_PROMPT.format(categories=", ".join(sorted(known_categories())))

    api_key = settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise InterpreterError(model, "no ANTHROPIC_API_KEY configured")

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            temperature=0,
            system=system,
            messages=[{"role": "user", "content": raw_intake_text}],
        )
    except anthropic.AnthropicError as exc:
        raise InterpreterError(model, f"model request failed ({type(exc).__name__})") from exc

    text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    cleaned = _strip_fences(text)

    try:
        proposed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        return Interpretation(model, None, text, f"model output was not valid JSON: {exc.msg}")

    if not isinstance(proposed, dict):
        return Interpretation(model, None, text, "model output was not a JSON object")

    return Interpretation(model, proposed, text, None)
