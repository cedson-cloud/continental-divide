"""Names use plain characters only, and a name that breaks that is told which
character, never given an unrelated reason it cannot act on.

Property values may hold any character; these rules apply to names alone.
"""

import json
from pathlib import Path

import pytest

from app.rules import event_name_error, property_name_error
from app.vet import vet_plan

CLEAN_EXAMPLE = Path(__file__).parents[1] / "examples" / "clean_cart_cleared.json"


@pytest.mark.parametrize(
    "name, found",
    [
        ("Order-Completed", "'-'"),
        ("Order/Completed", "'/'"),
        ("Order.Completed", "'.'"),
        ("Order $ Refunded", "'$'"),
        ("Order Completed!", "'!'"),
        ("Order Completéd", "'é'"),
        ("Order Completed 🎉", "'🎉'"),
    ],
)
def test_a_title_case_name_is_told_which_character_is_not_allowed(name, found):
    assert event_name_error(name, convention="title_case_object_action") == (
        "Title Case names may only use letters A–Z, numbers and spaces "
        f"(found {found})"
    )


@pytest.mark.parametrize(
    "name, found",
    [
        ("order-completed", "'-'"),
        ("order_$_refunded", "'$'"),
        ("order.completed", "'.'"),
        ("order_completéd", "'é'"),
        ("order completed", "a space"),
        ("order-completed!", "'-', '!'"),
    ],
)
def test_a_snake_case_name_is_told_which_character_is_not_allowed(name, found):
    assert event_name_error(name, convention="snake_case_object_action") == (
        "snake_case names may only use lowercase letters a–z, numbers and "
        f"underscores (found {found})"
    )


@pytest.mark.parametrize(
    "name, found",
    [
        ("cart-id", "'-'"),
        ("cart$id", "'$'"),
        ("cart.id", "'.'"),
        ("cart_ïd", "'ï'"),
        ("$current_url", "'$'"),
        ("cart id", "a space"),
    ],
)
def test_a_property_name_is_told_which_character_is_not_allowed(name, found):
    assert property_name_error(name) == (
        f"property '{name}' must be snake_case: lowercase letters a–z, numbers "
        f"and underscores only (found {found})"
    )


def test_names_with_plain_characters_keep_their_existing_reasons():
    assert "underscores" in event_name_error("Add_To Cart")
    assert "Title Case" in event_name_error("Order completed")
    snake = event_name_error("Order_Completed", convention="snake_case_object_action")
    assert snake == "name must be lowercase snake_case (object_action)"
    assert property_name_error("cartId") == "property 'cartId' must be snake_case"


def test_a_requester_sees_which_character_broke_the_name(client):
    definition = json.loads(CLEAN_EXAMPLE.read_text())
    definition["name"] = "Cart-Cleared"
    definition["properties"] = [{"name": "cart-id", "type": "string", "required": True}]

    response = client.post(
        "/requests/raw",
        json={"definition": definition, "business_value": "measures cart abandonment"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    checks = {c["rule"]: c for c in body["checks"]}
    assert checks["event_naming"]["detail"] == (
        "Title Case names may only use letters A–Z, numbers and spaces (found '-')"
    )
    assert checks["property_naming"]["detail"] == (
        "property 'cart-id' must be snake_case: lowercase letters a–z, numbers "
        "and underscores only (found '-')"
    )


def test_the_vetter_gives_each_bad_property_its_own_reason():
    event = {
        "name": "Cart Cleared",
        "category": "Growth",
        "properties": [
            {"name": "cart-id", "type": "string"},
            {"name": "cartId", "type": "string"},
        ],
    }
    report = vet_plan({"source": "acme", "events": [event]})["events"][0]
    detail = next(c for c in report["checks"] if c["rule"] == "property_naming")["detail"]
    assert detail == (
        "property 'cart-id' must be snake_case: lowercase letters a–z, numbers "
        "and underscores only (found '-'); property 'cartId' must be snake_case"
    )
