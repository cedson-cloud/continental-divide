import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import {
  CatalogPlatform,
  CatalogView,
  CatalogViewEvent,
  CatalogViewProperty,
} from "@/lib/api";
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
    evidence: null,
    note: null,
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
    properties_listed: true,
    default_on: {},
    evidence: null,
    note: null,
    sources: [],
    ...overrides,
  };
}

function catalog(
  events: CatalogViewEvent[],
  platform: CatalogPlatform | null = null,
): CatalogView {
  return {
    events,
    platform,
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
                evidence: null,
                note: null,
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
            properties_listed: false,
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

const PLATFORM: CatalogPlatform = {
  name: "segment",
  checked: "2026-10-15",
  libraries: [
    { id: "analytics.js", name: "Analytics.js", surface: "browser", note: null },
    { id: "analytics-swift", name: "Swift", surface: "mobile", note: null },
    {
      id: "analytics-kotlin",
      name: "Kotlin",
      surface: "mobile",
      note: "Its context fields aren't listed yet.",
    },
  ],
  common_fields: [
    {
      path: "context.campaign.source",
      plain_name: "Campaign source (utm_source)",
      group: "Campaign",
      type: null,
      libraries: ["analytics.js"],
      note: "Only on events from a page load whose URL carried it.",
      evidence: "docs",
      sources: ["https://www.twilio.com/docs/segment/connections/spec/common"],
    },
    {
      path: "context.app.version",
      plain_name: "App version",
      group: "App",
      type: null,
      libraries: ["analytics-swift", "analytics-kotlin"],
      note: null,
      evidence: "sdk_code",
      sources: ["https://github.com/segmentio/analytics-swift/blob/main/Context.swift"],
    },
  ],
  reserved_names: [
    {
      name: "Install Attributed",
      records: "an install being attributed to a campaign",
      sent_by: "an attribution provider",
      properties: [
        { name: "provider", type: "string", note: null, evidence: "docs" },
        { name: "action", type: null, note: 'Defaults to "Open".', evidence: "docs" },
      ],
      note: null,
      evidence: "docs",
      sources: ["https://www.twilio.com/docs/segment/connections/spec/mobile"],
    },
  ],
  not_listed_yet: ["context.channel, which Segment's pages place differently."],
};

const OPENED = event({
  name: "Application Opened",
  category: "System events",
  description: "The app being opened",
  source: "system_event",
  sent_as: "Application Opened",
  sent_by: "Segment's mobile libraries",
  properties: [
    prop({ name: "from_background", type: "boolean", source: "system_event", evidence: "docs" }),
    prop({
      name: "version",
      type: null,
      source: "system_event",
      evidence: "sdk_code",
      note: "Kotlin sends it on first launch only.",
    }),
  ],
  default_on: { "analytics-swift": true, "analytics-kotlin": false },
  sources: ["https://www.twilio.com/docs/segment/connections/spec/mobile"],
});

describe("CatalogBrowser, what the platform sends", () => {
  it("shows a system event's properties with how each is known", () => {
    render(<CatalogBrowser catalog={catalog([OPENED], PLATFORM)} />);
    fireEvent.click(screen.getByRole("button", { name: "Application Opened" }));

    const table = screen.getByRole("table", { name: "Application Opened properties" });
    expect(within(table).getByText("Kotlin sends it on first launch only.")).toBeInTheDocument();
    expect(within(table).getByText("not listed yet")).toBeInTheDocument();
    expect(within(table).getByText("From SDK code")).toBeInTheDocument();
    expect(within(table).getAllByText("Segment")).toHaveLength(2);
    expect(
      screen.getByText("On by default in Swift. Off by default in Kotlin."),
    ).toBeInTheDocument();
    expect(screen.getByText(/Sources, checked 15 October 2026/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /twilio\.com\/…\/mobile/ })).toHaveAttribute(
      "target",
      "_blank",
    );
  });

  it("says when the sources give a system event no properties of its own", () => {
    const backgrounded = event({
      name: "Application Backgrounded",
      category: "System events",
      source: "system_event",
      properties: [],
      properties_listed: true,
    });
    render(<CatalogBrowser catalog={catalog([backgrounded], PLATFORM)} />);
    expect(screen.getByText("No properties of its own")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Application Backgrounded" }));
    expect(
      screen.getByText("The sources list no properties of its own for this event."),
    ).toBeInTheDocument();
  });

  it("says how the sources disagree on a disputed event", () => {
    const updated = event({
      ...OPENED,
      name: "Application Updated",
      evidence: "disputed",
      note: "The spec and the code disagree on ordering.",
    });
    render(<CatalogBrowser catalog={catalog([updated], PLATFORM)} />);
    fireEvent.click(screen.getByRole("button", { name: "Application Updated" }));
    expect(screen.getByText("Sources disagree")).toBeInTheDocument();
    expect(screen.getByText(/disagree on ordering/)).toBeInTheDocument();
  });

  it("keeps the common fields collapsed until opened, grouped with their libraries", () => {
    render(<CatalogBrowser catalog={catalog([OPENED], PLATFORM)} />);
    const toggle = screen.getByRole("button", { name: "Sent with every event 2 fields" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("App version")).toBeNull();

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    const app = screen.getByRole("table", { name: "App fields" });
    expect(within(app).getByText("context.app.version")).toBeInTheDocument();
    expect(within(app).getByText("Swift")).toBeInTheDocument();
    expect(within(app).getByText("From SDK code")).toBeInTheDocument();
    expect(screen.getByText(/Its context fields aren't listed yet/)).toBeInTheDocument();
    expect(screen.getByText(/context.channel/)).toBeInTheDocument();
  });

  it("finds a common field by search instead of saying nothing matches", () => {
    render(<CatalogBrowser catalog={catalog([OPENED], PLATFORM)} />);
    fireEvent.change(screen.getByLabelText("Search events"), { target: { value: "utm" } });

    expect(screen.queryByText("No events match")).toBeNull();
    const toggle = screen.getByRole("button", { name: "Sent with every event 1 field" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("context.campaign.source")).toBeInTheDocument();
    expect(screen.queryByText("context.app.version")).toBeNull();
    expect(
      screen.getByText(
        "0 of 1 events shown, plus 1 match among the fields and names the platform sends",
      ),
    ).toBeInTheDocument();
  });

  it("lists reserved names as names to use, not duplicates", () => {
    render(<CatalogBrowser catalog={catalog([OPENED], PLATFORM)} />);
    fireEvent.click(screen.getByRole("button", { name: "Reserved names 1 name" }));
    expect(screen.getByRole("heading", { name: "Install Attributed" })).toBeInTheDocument();
    const props = screen.getByRole("table", { name: "Install Attributed properties" });
    expect(within(props).getByText('Defaults to "Open".')).toBeInTheDocument();
    expect(within(props).getByText("not listed yet")).toBeInTheDocument();
    expect(screen.getByText(/Who sends it: an attribution provider/)).toBeInTheDocument();
    expect(screen.getByText(/isn't a duplicate/)).toBeInTheDocument();
  });

  it("leaves the platform out when showing only the sample plan", () => {
    render(<CatalogBrowser catalog={catalog([event({}), OPENED], PLATFORM)} />);
    fireEvent.click(screen.getByRole("button", { name: /^Sample plan/ }));
    expect(screen.queryByRole("button", { name: /Sent with every event/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Reserved names/ })).toBeNull();
  });
});
