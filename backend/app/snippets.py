"""Snippets for engineers: an approved definition as code, one per surface (ADR 0008).

No model writes code. A snippet is rendered from the platform file's call shapes and the
definition, the same every time. Every name is written as a JavaScript string literal,
encoded, never pasted, so what is safe to generate never depends on the naming rule.
Values are empty placeholders of the field's type, each with a comment giving the type
and whether it is required; the write key and ids are placeholders too.
"""

from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel

from .models import EventDefinition, EventProperty
from .platforms import Platform, SnippetSurface, load_platform

USER_ID = "USER_ID"
GROUP_ID = "GROUP_ID"

# The statuses whose definition is settled enough to implement.
SNIPPET_STATUSES = frozenset({"approved", "published"})

# Where the requester said the event fires picks its surface. Unsure, or a request
# that never said, gets every surface the platform has, and each snippet says so.
_SURFACES_FOR_SIDE = {"Client": "browser", "Server": "server"}

_PLACEHOLDERS = {
    "string": '""',
    "number": "0",
    "integer": "0",
    "boolean": "false",
    "array": "[]",
    "object": "{}",
}


class Snippet(BaseModel):
    surface: Literal["browser", "server"]
    label: str
    checked: str
    sources: list[str]
    code: str


def _literal(text: str) -> str:
    # JSON with every non-ASCII character escaped is a valid JavaScript string literal,
    # U+2028 and U+2029 included.
    return json.dumps(text, ensure_ascii=True)


def _fields(fields: list[EventProperty], indent: int) -> list[str]:
    pad = " " * indent
    return [
        f"{pad}{_literal(f.name)}: {_PLACEHOLDERS[f.type.value]}, "
        f"// {f.type.value}, {'required' if f.required else 'optional'}"
        for f in fields
    ]


def _object(fields: list[EventProperty], indent: int) -> str:
    if not fields:
        return "{}"
    return "\n".join(["{", *_fields(fields, indent + 2), " " * indent + "}"])


# Each call shape returns the call and the placeholder ids it carries.


def _positional_call(definition: EventDefinition) -> tuple[str, list[str]]:
    if definition.call_type == "track":
        args = [_literal(definition.name)]
        if definition.properties:
            args.append(_object(definition.properties, 0))
        return f"analytics.track({', '.join(args)});", []
    first = USER_ID if definition.call_type == "identify" else GROUP_ID
    traits = _object(definition.traits, 0)
    return f"analytics.{definition.call_type}({_literal(first)}, {traits});", [first]


def _params_call(definition: EventDefinition) -> tuple[str, list[str]]:
    ids = [USER_ID]
    lines = [f"  userId: {_literal(USER_ID)},"]
    if definition.call_type == "track":
        lines.append(f"  event: {_literal(definition.name)},")
        if definition.properties:
            lines.append(f"  properties: {_object(definition.properties, 2)},")
    else:
        if definition.call_type == "group":
            ids.append(GROUP_ID)
            lines.append(f"  groupId: {_literal(GROUP_ID)},")
        lines.append(f"  traits: {_object(definition.traits, 2)},")
    return "\n".join([f"analytics.{definition.call_type}({{", *lines, "});"]), ids


_CALL_SHAPES = {"positional": _positional_call, "params": _params_call}


def render_snippet(
    definition: EventDefinition,
    surface: SnippetSurface,
    where: Literal["browser", "server"],
    *,
    unsettled: bool = False,
) -> Snippet:
    call, ids = _CALL_SHAPES[surface.style](definition)
    header = [
        f"{surface.name}, {surface.package} {surface.version}",
        f"Call shape checked against the docs on {surface.checked}: {surface.sources[0]}",
        *surface.notes,
    ]
    if unsettled:
        header.append(f"Where this fires isn't settled. This is the {where} call.")
    if definition.call_type == "group":
        header.append(f"Group type: {_literal(definition.name)}")
    if definition.properties or definition.traits:
        header.append("Each value is an empty placeholder of its type: fill it in.")
    if ids:
        header.append(
            f"Replace {' and '.join(ids)} with {'real ids' if len(ids) > 1 else 'a real id'}."
        )
    parts = ["\n".join(f"// {line}" for line in header)]
    if surface.setup:
        parts.append("\n".join(surface.setup))
    parts.append(call)
    return Snippet(
        surface=where,
        label=surface.label,
        checked=surface.checked,
        sources=surface.sources,
        code="\n\n".join(parts) + "\n",
    )


def render_snippets(
    definition: EventDefinition, platform: Platform, side: Optional[str] = None
) -> list[Snippet]:
    """One snippet for each of the platform's surfaces the event fires on."""
    where = {lib.id: lib.surface for lib in platform.libraries}
    wanted = _SURFACES_FOR_SIDE.get(side)
    return [
        render_snippet(definition, s, where[s.library], unsettled=wanted is None)
        for s in platform.snippets
        if wanted is None or where[s.library] == wanted
    ]


def request_snippets(request: dict, platform: Optional[str]) -> list[Snippet]:
    """The snippets for a request, once its definition is approved. None before then,
    and none when the profile names no platform or its file has no call shapes."""
    if (
        platform is None
        or request.get("status") not in SNIPPET_STATUSES
        or not request.get("parsed_definition")
    ):
        return []
    definition = EventDefinition.model_validate(request["parsed_definition"])
    return render_snippets(definition, load_platform(platform), request.get("side"))
