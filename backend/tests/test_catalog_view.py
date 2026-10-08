"""The data dictionary endpoint, and the guard that keeps it away from the prompt.

GET /catalog composes the bundled sample plan with approved requests at read time,
through its own response models. A new_event request is its own entry, collisions
included; a new_property_on_existing request merges into its target with
attribution instead. The last test here is the reason those models exist:
``catalog_entries()`` is rendered verbatim into the duplicate-review system
prompt, so this suite pins its output exactly. Widening the review's view of the
catalog must be a deliberate decision, never a side effect of dictionary work.
"""

from app.catalog import catalog_entries
from app.rules import _PLAN_PATH


def _approved_request(
    storage,
    name,
    *,
    category="Browsing",
    description="",
    properties=None,
    status="approved",
    request_kind="new_event",
    existing_event=None,
):
    request_id = storage.create_request(
        raw_intake_text=f"track {name}",
        parsed_definition={
            "name": name,
            "category": category,
            "description": description,
            "properties": properties or [],
        },
        category=category,
        status=status,
        request_kind=request_kind,
        existing_event=existing_event,
    )
    storage.add_audit_entry(
        request_id,
        "decision_received",
        {"decision": "approve", "approver": "Dana", "note": None},
    )
    return request_id


def _event(body, name, source="sample_plan"):
    return next(
        e for e in body["events"] if e["name"] == name and e["source"] == source
    )


def test_composes_both_sources_and_counts_add_up(client, storage):
    _approved_request(storage, "Size Guide Opened")
    _approved_request(storage, "Store Locator Used", status="published")

    body = client.get("/catalog").json()
    counts = body["counts"]
    assert counts["from_sample_plan"] == 28
    assert counts["new_events_from_requests"] == 2
    # The active profile names Segment, whose system events join the dictionary.
    assert counts["system_events"] == 8
    assert counts["total"] == (
        counts["from_sample_plan"]
        + counts["system_events"]
        + counts["new_events_from_requests"]
    )
    assert counts["total"] == len(body["events"])
    assert {e["source"] for e in body["events"]} == {
        "sample_plan",
        "system_event",
        "approved_request",
    }


def test_an_approved_request_carries_its_source_id_and_approval_time(client, storage):
    request_id = _approved_request(
        storage,
        "Size Guide Opened",
        description="Shopper opened the size guide",
        properties=[{"name": "product_id", "type": "string"}],
    )

    body = client.get("/catalog").json()
    entry = _event(body, "Size Guide Opened", source="approved_request")
    assert entry["request_id"] == request_id
    assert entry["approved_at"] is not None
    assert entry["description"] == "Shopper opened the size guide"
    assert entry["unresolved_target"] is False
    assert entry["properties"] == [
        {
            "name": "product_id",
            "type": "string",
            "shape": None,
            "source": "approved_request",
            "request_id": request_id,
            "also_requested_by": [],
        }
    ]


def test_statuses_short_of_approval_never_appear(client, storage):
    for status in ("draft", "pending_approval", "rejected", "withdrawn", "superseded"):
        _approved_request(storage, f"Never Shown {status}", status=status)

    counts = client.get("/catalog").json()["counts"]
    assert counts["new_events_from_requests"] == 0
    assert counts["property_additions_merged"] == 0
    assert counts["unresolved_targets"] == 0


def test_a_new_event_name_collision_returns_both_entries(client, storage):
    request_id = _approved_request(
        storage, "Cart Viewed", category="Core Ordering", request_kind="new_event"
    )

    body = client.get("/catalog").json()
    collisions = [e for e in body["events"] if e["name"] == "Cart Viewed"]
    assert len(collisions) == 2
    assert {e["source"] for e in collisions} == {"sample_plan", "approved_request"}
    assert next(
        e for e in collisions if e["source"] == "approved_request"
    )["request_id"] == request_id


def test_a_property_addition_merges_instead_of_colliding(client, storage):
    request_id = _approved_request(
        storage,
        "Cart Viewed",
        category="Core Ordering",
        properties=[{"name": "gift_note", "type": "string"}],
        request_kind="new_property_on_existing",
        existing_event="Cart Viewed",
    )

    body = client.get("/catalog").json()
    entries = [e for e in body["events"] if e["name"] == "Cart Viewed"]
    assert len(entries) == 1
    assert entries[0]["source"] == "sample_plan"

    merged = next(p for p in entries[0]["properties"] if p["name"] == "gift_note")
    assert merged["source"] == "approved_request"
    assert merged["request_id"] == request_id
    for prop in entries[0]["properties"]:
        if prop["name"] != "gift_note":
            assert prop["source"] == "sample_plan"
            assert prop["request_id"] is None

    counts = body["counts"]
    assert counts["property_additions_merged"] == 1
    assert counts["new_events_from_requests"] == 0


def test_merged_properties_follow_the_base_in_request_id_order(client, storage):
    first = _approved_request(
        storage,
        "Cart Viewed",
        properties=[{"name": "gift_note", "type": "string"}],
        request_kind="new_property_on_existing",
        existing_event="Cart Viewed",
    )
    second = _approved_request(
        storage,
        "Cart Viewed",
        properties=[{"name": "gift_wrapping_chosen", "type": "boolean"}],
        request_kind="new_property_on_existing",
        existing_event="Cart Viewed",
    )

    body = client.get("/catalog").json()
    names = [p["name"] for p in _event(body, "Cart Viewed")["properties"]]
    # The sample plan's own properties first, then the additions by request id.
    assert names == ["cart_id", "products", "gift_note", "gift_wrapping_chosen"]
    assert first < second


def test_a_redundant_property_is_not_duplicated(client, storage):
    request_id = _approved_request(
        storage,
        "Cart Viewed",
        properties=[{"name": "cart_id", "type": "string"}],
        request_kind="new_property_on_existing",
        existing_event="Cart Viewed",
    )

    body = client.get("/catalog").json()
    entry = _event(body, "Cart Viewed")
    cart_id_rows = [p for p in entry["properties"] if p["name"] == "cart_id"]
    assert len(cart_id_rows) == 1
    assert cart_id_rows[0]["source"] == "sample_plan"
    assert cart_id_rows[0]["also_requested_by"] == [request_id]
    assert body["counts"]["property_additions_merged"] == 1


def test_an_addition_targeting_an_unknown_event_is_surfaced_unresolved(client, storage):
    request_id = _approved_request(
        storage,
        "Gift Registry Created",
        properties=[{"name": "registry_id", "type": "string"}],
        request_kind="new_property_on_existing",
        existing_event="Gift Registry Created",
    )

    body = client.get("/catalog").json()
    entry = _event(body, "Gift Registry Created", source="approved_request")
    assert entry["unresolved_target"] is True
    assert entry["request_id"] == request_id
    counts = body["counts"]
    assert counts["unresolved_targets"] == 1
    assert counts["property_additions_merged"] == 0
    assert counts["new_events_from_requests"] == 0


def test_counts_across_every_branch(client, storage):
    _approved_request(storage, "Size Guide Opened")  # new event, no collision
    _approved_request(storage, "Cart Viewed")  # new event, collision
    _approved_request(  # b1: normal merge
        storage,
        "Cart Viewed",
        properties=[{"name": "gift_note", "type": "string"}],
        request_kind="new_property_on_existing",
        existing_event="Cart Viewed",
    )
    _approved_request(  # b2: redundant property
        storage,
        "Products Searched",
        properties=[{"name": "query", "type": "string"}],
        request_kind="new_property_on_existing",
        existing_event="Products Searched",
    )
    _approved_request(  # b3: unknown target
        storage,
        "Gift Registry Created",
        properties=[{"name": "registry_id", "type": "string"}],
        request_kind="new_property_on_existing",
        existing_event="Gift Registry Created",
    )

    counts = client.get("/catalog").json()["counts"]
    assert counts == {
        "total": 28 + 8 + 2 + 1,
        "from_sample_plan": 28,
        "new_events_from_requests": 2,
        "property_additions_merged": 2,
        "unresolved_targets": 1,
        "system_events": 8,
    }


def test_product_item_is_a_shape_reference_returned_once(client, storage):
    body = client.get("/catalog").json()

    cart_viewed = _event(body, "Cart Viewed")
    products = next(p for p in cart_viewed["properties"] if p["name"] == "products")
    assert products["type"] == "array"
    assert products["shape"] == "product_item"

    shape = body["shapes"]["product_item"]
    assert shape["description"]
    assert {"name": "product_id", "type": "string"} in shape["properties"]

    # The shape is never inlined: every event property is exactly the view model.
    for event in body["events"]:
        for prop in event["properties"]:
            assert set(prop) == {
                "name",
                "type",
                "shape",
                "source",
                "request_id",
                "also_requested_by",
            }


def test_the_endpoint_performs_no_writes(client, storage):
    before = _PLAN_PATH.stat().st_mtime_ns
    assert client.get("/catalog").status_code == 200
    assert _PLAN_PATH.stat().st_mtime_ns == before


# What the duplicate-review prompt is built from, pinned exactly. If this test
# fails, something changed the review's view of the catalog — which changes the
# rendered system prompt, and there is no live eval tier to catch that yet.
_PROMPT_CATALOG = {
    ("Cart Shared", "Sharing", "Shared the cart with one or more friends", ("share_via", "share_message", "recipient", "cart_id", "products")),
    ("Cart Viewed", "Core Ordering", "User viewed their shopping cart", ("cart_id", "products")),
    ("Checkout Started", "Core Ordering", "User initiated the order process (a transaction is created)", ("order_id", "affiliation", "value", "revenue", "shipping", "tax", "discount", "coupon", "currency", "products")),
    ("Checkout Step Completed", "Core Ordering", "User completed a checkout step", ("checkout_id", "step", "shipping_method", "payment_method")),
    ("Checkout Step Viewed", "Core Ordering", "User viewed a checkout step", ("checkout_id", "step", "shipping_method", "payment_method")),
    ("Coupon Applied", "Coupons", "Coupon was applied on a user's shopping cart or order", ("order_id", "cart_id", "coupon_id", "coupon_name", "discount")),
    ("Coupon Denied", "Coupons", "Coupon was denied from a user's shopping cart or order", ("order_id", "cart_id", "coupon_id", "reason")),
    ("Coupon Entered", "Coupons", "User entered a coupon on a shopping cart or order", ("order_id", "cart_id", "coupon_id")),
    ("Coupon Removed", "Coupons", "User removed a coupon from a cart or order", ("order_id", "cart_id", "coupon_id", "coupon_name")),
    ("Order Cancelled", "Core Ordering", "User cancelled the order", ("order_id", "total", "currency", "products")),
    ("Order Completed", "Core Ordering", "User completed the order", ("checkout_id", "order_id", "affiliation", "total", "revenue", "shipping", "tax", "discount", "coupon", "currency", "products")),
    ("Order Refunded", "Core Ordering", "User refunded the order", ("order_id", "total", "currency", "products")),
    ("Order Updated", "Core Ordering", "User updated the order", ("order_id", "affiliation", "value", "revenue", "shipping", "tax", "discount", "coupon", "currency", "products")),
    ("Payment Info Entered", "Core Ordering", "User added payment information", ("checkout_id", "order_id", "step", "shipping_method", "payment_method")),
    ("Product Added", "Core Ordering", "User added a product to their shopping cart", ("cart_id", "product_id", "sku", "category", "name", "brand", "variant", "price", "quantity", "coupon", "position", "url", "image_url")),
    ("Product Added to Wishlist", "Wishlisting", "User added a product to the wish list", ("wishlist_id", "wishlist_name", "product_id", "sku", "category", "name", "brand", "variant", "price", "quantity", "coupon", "position", "url", "image_url")),
    ("Product Clicked", "Core Ordering", "User clicked on a product", ("product_id", "sku", "category", "name", "brand", "variant", "price", "quantity", "coupon", "position", "url", "image_url")),
    ("Product List Filtered", "Browsing", "User filtered a product list or category", ("list_id", "category", "filters", "sorts", "products")),
    ("Product List Viewed", "Browsing", "User viewed a product list or category", ("list_id", "category", "products")),
    ("Product Removed", "Core Ordering", "User removed a product from their shopping cart", ("cart_id", "product_id", "sku", "category", "name", "brand", "variant", "price", "quantity", "coupon", "position", "url", "image_url")),
    ("Product Removed from Wishlist", "Wishlisting", "User removed a product from the wish list", ("wishlist_id", "wishlist_name", "product_id", "sku", "category", "name", "brand", "variant", "price", "quantity", "coupon", "position", "url", "image_url")),
    ("Product Reviewed", "Reviewing", "User reviewed a product", ("product_id", "review_id", "review_body", "rating")),
    ("Product Shared", "Sharing", "Shared a product with one or more friends", ("share_via", "share_message", "recipient", "product_id", "sku", "category", "name", "brand", "variant", "price", "url", "image_url")),
    ("Product Viewed", "Core Ordering", "User viewed product details", ("product_id", "sku", "category", "name", "brand", "variant", "price", "quantity", "coupon", "currency", "url", "image_url")),
    ("Products Searched", "Browsing", "User searched for products", ("query",)),
    ("Promotion Clicked", "Promotions", "User clicked on promotion", ("promotion_id", "creative", "name", "position")),
    ("Promotion Viewed", "Promotions", "User viewed promotion", ("promotion_id", "creative", "name", "position")),
    ("Wishlist Product Added to Cart", "Wishlisting", "User added a wishlist product to the cart", ("wishlist_id", "wishlist_name", "cart_id", "product_id", "sku", "category", "name", "brand", "variant", "price", "quantity", "coupon", "position", "url", "image_url")),
}


def test_catalog_entries_is_unchanged_because_it_feeds_the_prompt():
    entries = catalog_entries()
    assert len(entries) == 28
    assert {
        (e.name, e.category, e.description, tuple(e.property_names)) for e in entries
    } == _PROMPT_CATALOG
