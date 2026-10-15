"""Snippets for engineers (ADR 0008).

An approved or published request carries its Segment code for each surface it fires
on, the browser, the server, or both when the requester was unsure, rendered from the
definition and the platform file with no model call. Names are
encoded, never pasted: a hostile name still parses, and arrives in the call exactly as
written. Keys and ids are placeholders, each snippet's header records the library version
and the date its call shape was checked, and nothing the library already sends is added.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app.models import EventDefinition
from app.platforms import PlatformError, load_platform
from app.snippets import render_snippets, request_snippets

from .test_catalog_view import _approved_request

CLEAN_EXAMPLE = Path(__file__).parents[1] / "examples" / "clean_cart_cleared.json"
POSTHOG = Path(__file__).parents[2] / "governance" / "templates" / "posthog-snake-case.yaml"
HOSTILE = 'Cart "Cleared"\\\n </script>${x}`); alert(1); //'

TRACK = EventDefinition(
    name="Product Added",
    category="Ecommerce",
    properties=[
        {"name": "product_id", "type": "string", "required": True},
        {"name": "price", "type": "number"},
        {"name": "quantity", "type": "integer"},
        {"name": "in_stock", "type": "boolean"},
        {"name": "products", "type": "array", "items": "product_item"},
        {"name": "coupon", "type": "object"},
    ],
)
IDENTIFY = EventDefinition(call_type="identify", traits=[{"name": "plan", "type": "string"}])
GROUP = EventDefinition(
    call_type="group", name="company", traits=[{"name": "seats", "type": "integer"}]
)


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        if os.environ.get("CI"):
            pytest.fail("CI must have Node to parse-check the snippets")
        pytest.skip("Node is not installed")
    return node


def _by_surface(definition):
    return {s.surface: s for s in render_snippets(definition, load_platform("segment"))}


def _call(code: str) -> str:
    """The snippet's call alone, without its header comments and setup lines."""
    return code.split("\n\n")[-1]


def _run_call(code: str) -> list:
    """Run the call against a stand-in analytics object and return what it was given."""
    script = (
        "const calls = [];\n"
        "const analytics = new Proxy({}, { get: (_, m) => (...a) => calls.push([m, ...a]) });\n"
        f"{_call(code)}\n"
        "console.log(JSON.stringify(calls));\n"
    )
    out = subprocess.run(
        [_node(), "-e", script], capture_output=True, text=True, check=True, timeout=20
    )
    return json.loads(out.stdout)


def _approve_clean_example(client, side="Unsure") -> int:
    request_id = client.post(
        "/requests/raw",
        json={
            "definition": json.loads(CLEAN_EXAMPLE.read_text()),
            "business_value": "measures cart abandonment",
            "side": side,
        },
    ).json()["id"]
    decided = client.post(f"/requests/{request_id}/decision", json={"decision": "approve"})
    assert decided.status_code == 200, decided.text
    return request_id


def test_an_approved_request_carries_browser_then_server_code(client):
    request_id = _approve_clean_example(client, side="Unsure")
    snippets = client.get(f"/requests/{request_id}").json()["snippets"]
    assert [s["surface"] for s in snippets] == ["browser", "server"]
    assert [s["label"] for s in snippets] == ["In the browser", "On your server"]
    browser, server = snippets
    assert "@segment/analytics-next 1.84.3" in browser["code"]
    assert "@segment/analytics-node 3.1.0" in server["code"]
    for snippet in snippets:
        assert snippet["checked"] == "2026-10-15"
        assert snippet["sources"][0].startswith("https://www.twilio.com/docs/segment/")
        assert '"Cart Cleared"' in snippet["code"]


@pytest.mark.parametrize(
    "side, surfaces",
    [("Client", ["browser"]), ("Server", ["server"]), ("Unsure", ["browser", "server"])],
)
def test_where_it_fires_picks_the_surfaces(client, side, surfaces):
    request_id = _approve_clean_example(client, side=side)
    snippets = client.get(f"/requests/{request_id}").json()["snippets"]
    assert [s["surface"] for s in snippets] == surfaces


def test_a_request_that_never_said_where_it_fires_gets_both(storage):
    request_id = _approved_request(storage, "Cart Cleared")
    assert storage.get_request(request_id)["side"] is None
    snippets = request_snippets(storage.get_request(request_id), "segment")
    assert [s.surface for s in snippets] == ["browser", "server"]


def test_a_request_not_yet_approved_carries_no_code(client):
    pending = client.post(
        "/requests/raw",
        json={
            "definition": json.loads(CLEAN_EXAMPLE.read_text()),
            "business_value": "measures cart abandonment",
        },
    ).json()["id"]
    assert client.get(f"/requests/{pending}").json()["snippets"] == []


@pytest.mark.parametrize("status", ["draft", "pending_approval", "rejected", "draft_failed"])
def test_only_a_settled_definition_has_snippets(storage, status):
    request_id = _approved_request(storage, "Cart Cleared", status=status)
    assert request_snippets(storage.get_request(request_id), "segment") == []


def test_a_published_request_keeps_its_snippets(storage):
    request_id = _approved_request(storage, "Cart Cleared", status="published")
    assert len(request_snippets(storage.get_request(request_id), "segment")) == 2


def test_no_platform_means_no_snippets(storage):
    request_id = _approved_request(storage, "Cart Cleared")
    assert request_snippets(storage.get_request(request_id), None) == []


def test_a_profile_on_another_platform_gets_no_segment_code(client, storage, monkeypatch):
    monkeypatch.setattr("app.governance._ACTIVE_PROFILE_PATH", POSTHOG)
    request_id = _approved_request(storage, "cart_cleared")
    assert client.get(f"/requests/{request_id}").json()["snippets"] == []


def test_the_browser_call_is_positional_and_the_server_call_takes_one_object():
    snippets = _by_surface(TRACK)
    assert _run_call(snippets["browser"].code)[0][:2] == ["track", "Product Added"]
    (method, params), = _run_call(snippets["server"].code)
    assert method == "track"
    assert params["userId"] == "USER_ID"
    assert params["event"] == "Product Added"


def test_identify_and_group_follow_each_librarys_shape():
    identify, group = _by_surface(IDENTIFY), _by_surface(GROUP)
    assert _run_call(identify["browser"].code) == [["identify", "USER_ID", {"plan": ""}]]
    assert _run_call(group["browser"].code) == [["group", "GROUP_ID", {"seats": 0}]]
    assert _run_call(identify["server"].code) == [
        ["identify", {"userId": "USER_ID", "traits": {"plan": ""}}]
    ]
    assert _run_call(group["server"].code) == [
        ["group", {"userId": "USER_ID", "groupId": "GROUP_ID", "traits": {"seats": 0}}]
    ]


def test_each_value_is_an_empty_placeholder_of_its_type():
    (_, _, properties), = _run_call(_by_surface(TRACK)["browser"].code)
    assert properties == {
        "product_id": "",
        "price": 0,
        "quantity": 0,
        "in_stock": False,
        "products": [],
        "coupon": {},
    }
    code = _by_surface(TRACK)["browser"].code
    assert '"product_id": "", // string, required' in code
    assert '"price": 0, // number, optional' in code
    # In Python 0 == False, so the boolean is checked in the code itself.
    assert '"in_stock": false, // boolean, optional' in code


def test_an_event_without_properties_sends_just_its_name():
    snippets = _by_surface(EventDefinition(name="Cart Viewed", category="Ecommerce"))
    assert _call(snippets["browser"].code) == 'analytics.track("Cart Viewed");\n'
    assert "placeholder" not in snippets["browser"].code
    assert _run_call(snippets["server"].code) == [
        ["track", {"userId": "USER_ID", "event": "Cart Viewed"}]
    ]


def test_a_hostile_name_is_encoded_and_arrives_exactly_as_written():
    definition = EventDefinition(
        name=HOSTILE,
        category="Ecommerce",
        properties=[{"name": HOSTILE, "type": "string"}],
    )
    snippets = _by_surface(definition)
    assert _run_call(snippets["browser"].code) == [["track", HOSTILE, {HOSTILE: ""}]]
    assert _run_call(snippets["server"].code) == [
        ["track", {"userId": "USER_ID", "event": HOSTILE, "properties": {HOSTILE: ""}}]
    ]


def test_every_snippet_parses_as_javascript(tmp_path):
    node = _node()
    for definition in (TRACK, IDENTIFY, GROUP):
        for snippet in _by_surface(definition).values():
            # The server snippet imports its library, so it parses as a module.
            path = tmp_path / f"{definition.call_type}-{snippet.surface}.mjs"
            path.write_text(snippet.code)
            result = subprocess.run(
                [node, "--check", str(path)], capture_output=True, text=True, timeout=20
            )
            assert result.returncode == 0, result.stderr


def test_keys_are_placeholders_and_nothing_the_library_sends_is_added():
    snippets = _by_surface(TRACK)
    assert 'writeKey: "YOUR_WRITE_KEY"' in snippets["server"].code
    for snippet in snippets.values():
        call = _call(snippet.code)
        for field in ("context", "timestamp", "messageId", "anonymousId", "sentAt"):
            assert field not in call


def test_each_header_records_the_library_version_and_the_date_checked():
    surfaces = {s.label: s for s in load_platform("segment").snippets}
    for snippet in _by_surface(TRACK).values():
        surface = surfaces[snippet.label]
        header = snippet.code.split("\n\n")[0]
        assert all(line.startswith("// ") for line in header.splitlines())
        assert f"{surface.package} {surface.version}" in header
        assert f"checked against the docs on {snippet.checked}" in header
        assert snippet.sources[0] in header


def test_a_snippet_for_an_unsettled_surface_says_so_in_the_code():
    unsure = _by_surface(TRACK)
    settled = "// Where this fires isn't settled. This is the {} call."
    assert settled.format("browser") in unsure["browser"].code
    assert settled.format("server") in unsure["server"].code
    (browser,) = render_snippets(TRACK, load_platform("segment"), "Client")
    assert "settled" not in browser.code


def test_a_group_snippet_names_its_group_type():
    for snippet in _by_surface(GROUP).values():
        assert '// Group type: "company"' in snippet.code


def _platform_with_snippet(tmp_path, **overrides):
    surface = {
        "label": "On your server",
        "name": "Node",
        "library": "server",
        "package": "@segment/analytics-node",
        "version": "3.1.0",
        "style": "params",
        "checked": "2026-10-15",
        "sources": ["https://example.com/docs"],
        **overrides,
    }
    data = {
        "version": 2,
        "name": "test",
        "docs": ["https://example.com/docs"],
        "checked": "2026-10-15",
        "libraries": [
            {"id": "server", "name": "Server", "surface": "server"},
            {"id": "app", "name": "App", "surface": "mobile"},
        ],
        "system_events": [],
        "snippets": [surface],
    }
    (tmp_path / "test.yaml").write_text(json.dumps(data))
    return lambda: load_platform("test", directory=tmp_path)


def test_a_snippet_names_a_library_the_file_lists(tmp_path):
    assert _platform_with_snippet(tmp_path)().snippets[0].name == "Node"
    with pytest.raises(PlatformError, match="unknown library: nowhere"):
        _platform_with_snippet(tmp_path, library="nowhere")()


@pytest.mark.parametrize(
    "field, value",
    [
        ("notes", ["one\nalert(1)"]),
        ("setup", ["import x\u2028alert(1)"]),
        ("name", "Node\nalert(1)"),
        ("version", "3.1.0\ralert(1)"),
        ("sources", ["https://example.com/docs\nalert(1)"]),
    ],
)
def test_nothing_printed_in_a_snippet_can_break_out_of_its_line(tmp_path, field, value):
    with pytest.raises(PlatformError, match="line break"):
        _platform_with_snippet(tmp_path, **{field: value})()


def test_a_snippet_surface_is_its_librarys(tmp_path):
    platform = _platform_with_snippet(tmp_path)()
    (snippet,) = render_snippets(TRACK, platform)
    assert snippet.surface == "server"
    with pytest.raises(PlatformError, match="browser and server libraries only"):
        _platform_with_snippet(tmp_path, library="app")()


def test_a_snippet_must_cite_its_source(tmp_path):
    with pytest.raises(PlatformError):
        _platform_with_snippet(tmp_path, sources=[])()
