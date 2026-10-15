import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { CatalogView, CatalogViewEvent, CatalogViewProperty } from "@/lib/api";
import {
  CatalogBrowser,
  COLLISION_WARNING,
  REVIEW_GAP_NOTICE,
} from "./CatalogBrowser";

afterEach(cleanup);

function prop(overrides: Partial<CatalogViewProperty>): CatalogViewProperty {
  return {
    name: "cart_id",
    type: "string",
    shape: null,
    source: "sample_plan",
    request_id: null,
    also_requested_by: [],
    ...overrides,
  };
}

function event(overrides: Partial<CatalogViewEvent>): CatalogViewEvent {
  return {
    name: "Cart Viewed",
    category: "Core Ordering",
    description: "User viewed their shopping cart",
    properties: [
      prop({}),
      prop({ name: "products", type: "array", shape: "product_item" }),
    ],
    source: "sample_plan",
    request_id: null,
    approved_at: null,
    unresolved_target: false,
    sent_as: null,
    sent_by: null,
    ...overrides,
  };
}

function catalog(events: CatalogViewEvent[]): CatalogView {
  return {
    events,
    shapes: {
      product_item: {
        description: "Shared product shape.",
        properties: [{ name: "product_id", type: "string" }],
      },
    },
    counts: {
      total: events.length,
      from_sample_plan: events.filter((e) => e.source === "sample_plan").length,
      new_events_from_requests: events.filter(
        (e) => e.source === "approved_request" && !e.unresolved_target,
      ).length,
      property_additions_merged: 0,
      unresolved_targets: events.filter((e) => e.unresolved_target).length,
      system_events: events.filter((e) => e.source === "system_event").length,
    },
  };
}

describe("CatalogBrowser", () => {
  it("renders categories with counts and expands an event's properties", () => {
    render(
      <CatalogBrowser
        catalog={catalog([
          event({}),
          event({ name: "Products Searched", category: "Browsing", properties: [] }),
        ])}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Core Ordering 1 event" }),
    ).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: "Browsing 1 event" })).toBeInTheDocument();

    // Properties are hidden until the event is expanded.
    expect(screen.queryByText("cart_id")).toBeNull();
    const toggle = screen.getByRole("button", { name: "Cart Viewed" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("cart_id")).toBeInTheDocument();
    expect(screen.getByText("products")).toBeInTheDocument();
  });

  it("filters on a property name, not just the event name", () => {
    render(
      <CatalogBrowser
        catalog={catalog([
          event({}),
          event({
            name: "Products Searched",
            category: "Browsing",
            description: "User searched for products",
            properties: [prop({ name: "query" })],
          }),
        ])}
      />,
    );

    fireEvent.change(screen.getByLabelText("Search events"), {
      target: { value: "cart_id" },
    });

    expect(screen.getByText("1 of 2 events shown")).toBeInTheDocument();
    // "cart_id" appears in no event name or description — only in properties.
    expect(screen.getByRole("button", { name: /Cart Viewed/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Products Searched/ })).toBeNull();
  });

  it("badges an approved_request entry with a link, and a sample_plan entry without one", () => {
    render(
      <CatalogBrowser
        catalog={catalog([
          event({}),
          event({
            name: "Size Guide Opened",
            category: "Browsing",
            description: "Shopper opened the size guide",
            source: "approved_request",
            request_id: 42,
            approved_at: "2026-07-29 12:00:00",
          }),
        ])}
      />,
    );

    const requested = screen.getByRole("link", { name: "From request #42" });
    expect(requested).toHaveAttribute("href", "/requests/42");

    expect(screen.getByText("Sample plan", { selector: ".catalog-source-tag" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Sample plan" })).toBeNull();
  });

  it("links a merged property to its request while a base property shows none", () => {
    render(
      <CatalogBrowser
        catalog={catalog([
          event({
            properties: [
              prop({}),
              prop({
                name: "gift_note",
                source: "approved_request",
                request_id: 8,
                also_requested_by: [13],
              }),
            ],
          }),
        ])}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Cart Viewed/ }));

    const merged = screen.getByRole("link", { name: "#8" });
    expect(merged).toHaveAttribute("href", "/requests/8");
    // The base property's source cell is the quiet plan marker, never a link.
    expect(within(screen.getByRole("table")).getAllByRole("link")).toHaveLength(1);
    expect(screen.getByText("plan")).toBeInTheDocument();
    expect(screen.getByText(/also requested by #13/)).toBeInTheDocument();
  });

  it("warns on both entries of a new_event name collision", () => {
    render(
      <CatalogBrowser
        catalog={catalog([
          event({}),
          event({
            source: "approved_request",
            request_id: 9,
            approved_at: "2026-07-29 12:00:00",
            properties: [prop({ source: "approved_request", request_id: 9 })],
          }),
        ])}
      />,
    );

    expect(screen.getAllByText(COLLISION_WARNING)).toHaveLength(2);
  });

  it("labels a system event and says what the SDK sends it as", () => {
    render(
      <CatalogBrowser
        catalog={catalog([
          event({
            name: "Page Viewed",
            category: "System events",
            description: "A person seeing a page of the website",
            properties: [],
            source: "system_event",
            sent_as: "a page call",
            sent_by: "analytics.js, by default",
          }),
        ])}
      />,
    );

    expect(screen.getByText("System event", { selector: ".catalog-source-tag" })).toBeInTheDocument();
    expect(
      screen.getByText("Sent automatically as a page call by analytics.js, by default."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Sample plan", { selector: ".catalog-source-tag" })).toBeNull();
    expect(screen.getByRole("button", { name: "System events 1" })).toBeInTheDocument();

    // Never claim a system event carries nothing: the SDK sends properties we don't
    // list yet.
    fireEvent.click(screen.getByRole("button", { name: "Page Viewed" }));
    expect(screen.getByText(/aren't listed here yet/)).toBeInTheDocument();
    expect(screen.queryByText(/carries no properties/)).toBeNull();
    expect(screen.getByText(/1 system event/)).toBeInTheDocument();
  });

  it("always renders the honest notice about what the review compares against", () => {
    render(<CatalogBrowser catalog={catalog([event({})])} />);
    expect(screen.getByText(REVIEW_GAP_NOTICE)).toBeInTheDocument();
  });

  it("shows only what requests touched under From requests, merged properties included", () => {
    render(
      <CatalogBrowser
        catalog={catalog([
          event({}),
          event({
            name: "Checkout Started",
            properties: [prop({ name: "gift_note", source: "approved_request", request_id: 8 })],
          }),
          event({
            name: "Size Guide Opened",
            category: "Browsing",
            source: "approved_request",
            request_id: 42,
            approved_at: "2026-07-29 12:00:00",
          }),
        ])}
      />,
    );

    const fromRequests = screen.getByRole("button", { name: "From requests 2" });
    expect(fromRequests).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(fromRequests);
    expect(fromRequests).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "All 3" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );

    expect(screen.getByRole("button", { name: "Checkout Started" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Size Guide Opened" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cart Viewed" })).toBeNull();
  });

  it("points to a new request when nothing has come from requests yet", () => {
    render(<CatalogBrowser catalog={catalog([event({})])} />);

    expect(
      screen.getByText(/Events you request join this plan once they're approved/),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "From requests 0" }));
    expect(
      screen.getByRole("heading", { name: "Nothing from requests yet" }),
    ).toBeInTheDocument();
    // One way forward, not two: the hint line steps aside for the empty state.
    expect(screen.getAllByRole("link")).toHaveLength(1);
    expect(screen.getByRole("link", { name: "New request" })).toHaveAttribute("href", "/");
  });

  it("counts a request for a property the event already had as from requests", () => {
    render(
      <CatalogBrowser
        catalog={catalog([event({ properties: [prop({ also_requested_by: [6] })] })])}
      />,
    );
    expect(screen.queryByText(/Events you request join this plan/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "From requests 1" }));
    expect(screen.getByRole("button", { name: "Cart Viewed" })).toBeInTheDocument();
  });

  it("keeps a collapsed category collapsed after a search hides and restores it", () => {
    render(
      <CatalogBrowser
        catalog={catalog([
          event({}),
          event({ name: "Products Searched", category: "Browsing", properties: [] }),
        ])}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Core Ordering 1 event" }));
    const search = screen.getByLabelText("Search events");
    fireEvent.change(search, { target: { value: "Searched" } });
    expect(screen.queryByRole("button", { name: /Core Ordering/ })).toBeNull();
    fireEvent.change(search, { target: { value: "" } });
    expect(screen.getByRole("button", { name: "Core Ordering 1 event" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("offers a way back when a search matches nothing", () => {
    render(<CatalogBrowser catalog={catalog([event({})])} />);

    fireEvent.change(screen.getByLabelText("Search events"), {
      target: { value: "no_such_thing" },
    });
    expect(screen.getByRole("heading", { name: "No events match" })).toBeInTheDocument();
    expect(screen.getByText(/Nothing here matches “no_such_thing”/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Show all events" }));
    expect(screen.getByLabelText("Search events")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Cart Viewed" })).toBeInTheDocument();
  });

  it("hides the System events filter when the platform sends none", () => {
    render(<CatalogBrowser catalog={catalog([event({})])} />);
    expect(screen.queryByRole("button", { name: /System events/ })).toBeNull();
  });

  it("collapses a category and says so", () => {
    render(<CatalogBrowser catalog={catalog([event({})])} />);
    const category = screen.getByRole("button", { name: "Core Ordering 1 event" });
    fireEvent.click(category);
    expect(category).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("button", { name: "Cart Viewed" })).toBeNull();
  });
});
