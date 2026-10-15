import { describe, expect, it } from "vitest";
import type { CatalogView, CatalogViewEvent } from "./api";
import {
  catalogSummary,
  matchesSearch,
  matchesSource,
  propertyCount,
  touchedByRequest,
} from "./catalog";

const counts = (overrides: Partial<CatalogView["counts"]>): CatalogView["counts"] => ({
  total: 28,
  from_sample_plan: 28,
  new_events_from_requests: 0,
  property_additions_merged: 0,
  unresolved_targets: 0,
  system_events: 0,
  ...overrides,
});

function event(overrides: Partial<CatalogViewEvent>): CatalogViewEvent {
  return {
    name: "Cart Viewed",
    category: "Core Ordering",
    description: "User viewed their shopping cart",
    properties: [],
    source: "sample_plan",
    request_id: null,
    approved_at: null,
    unresolved_target: false,
    sent_as: null,
    sent_by: null,
    ...overrides,
  };
}

describe("catalogSummary", () => {
  it("names only the sources that contribute", () => {
    expect(catalogSummary(counts({}))).toBe("28 events: 28 from the sample plan.");
  });

  it("lists every non-empty source, joined in plain English", () => {
    expect(
      catalogSummary(
        counts({
          total: 31,
          system_events: 1,
          new_events_from_requests: 2,
          property_additions_merged: 1,
        }),
      ),
    ).toBe(
      "31 events: 28 from the sample plan, 1 system event, 2 approved as new events " +
        "and 1 property request merged in.",
    );
  });

  it("names a single new event in the singular", () => {
    expect(catalogSummary(counts({ total: 29, new_events_from_requests: 1 }))).toBe(
      "29 events: 28 from the sample plan and 1 approved as a new event.",
    );
  });

  it("calls out a property request with nowhere to attach", () => {
    expect(catalogSummary(counts({ total: 29, unresolved_targets: 1 }))).toBe(
      "29 events: 28 from the sample plan and 1 with no target event.",
    );
  });
});

describe("propertyCount", () => {
  it("says so when an event has no properties", () => {
    expect(propertyCount(0, 0)).toBe("No properties");
  });

  it("uses the singular for one", () => {
    expect(propertyCount(1, 0)).toBe("1 property");
  });

  it("names how many arrived by request", () => {
    expect(propertyCount(11, 1)).toBe("11 properties, 1 added by request");
  });
});

describe("matchesSearch", () => {
  const cart = event({
    properties: [
      {
        name: "coupon_id",
        type: "string",
        shape: null,
        source: "sample_plan",
        request_id: null,
        also_requested_by: [],
      },
    ],
  });

  it("matches a property name, ignoring case and surrounding space", () => {
    expect(matchesSearch(cart, "  COUPON ")).toBe(true);
  });

  it("matches the description as well as the name", () => {
    expect(matchesSearch(cart, "shopping cart")).toBe(true);
    expect(matchesSearch(cart, "wishlist")).toBe(false);
  });

  it("matches everything when the search is blank", () => {
    expect(matchesSearch(cart, "   ")).toBe(true);
  });
});

describe("touchedByRequest", () => {
  it("is true for a request-created event and false for an untouched one", () => {
    expect(touchedByRequest(event({ source: "approved_request", request_id: 3 }))).toBe(
      true,
    );
    expect(touchedByRequest(event({}))).toBe(false);
  });

  it("is true when a request asked for a property the event already had", () => {
    const asked = event({
      properties: [
        {
          name: "cart_id",
          type: "string",
          shape: null,
          source: "sample_plan",
          request_id: null,
          also_requested_by: [6],
        },
      ],
    });
    expect(touchedByRequest(asked)).toBe(true);
  });
});

describe("matchesSource", () => {
  const merged = event({
    properties: [
      {
        name: "gift_note",
        type: "string",
        shape: null,
        source: "approved_request",
        request_id: 8,
        also_requested_by: [],
      },
    ],
  });

  it("puts a sample-plan event with a requested property under both sources", () => {
    expect(matchesSource(merged, "requests")).toBe(true);
    expect(matchesSource(merged, "sample_plan")).toBe(true);
  });

  it("keeps an untouched sample-plan event out of From requests", () => {
    expect(matchesSource(event({}), "requests")).toBe(false);
    expect(matchesSource(event({}), "all")).toBe(true);
  });

  it("matches system events by their source", () => {
    expect(matchesSource(event({ source: "system_event" }), "system_event")).toBe(true);
    expect(matchesSource(event({}), "system_event")).toBe(false);
  });
});
