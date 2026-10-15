import { describe, expect, it } from "vitest";
import type { CatalogView, CatalogViewEvent, CommonField, PlatformLibrary } from "./api";
import {
  catalogSummary,
  defaultsSentence,
  groupFields,
  librariesLabel,
  matchesField,
  matchesSearch,
  matchesSource,
  propertyCount,
  propertySummary,
  sharedSources,
  touchedByRequest,
} from "./catalog";
import { formatChecked, sourceLabel } from "./format";

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
    properties_listed: true,
    default_on: {},
    evidence: null,
    note: null,
    sources: [],
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
  it("says none are listed, not that none exist", () => {
    expect(propertyCount(0, 0)).toBe("No properties listed");
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
        evidence: null,
        note: null,
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
          evidence: null,
          note: null,
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
        evidence: null,
        note: null,
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

const LIBRARIES: PlatformLibrary[] = [
  { id: "analytics.js", name: "Analytics.js", surface: "browser", note: null },
  { id: "analytics-swift", name: "Swift", surface: "mobile", note: null },
  { id: "analytics-kotlin", name: "Kotlin", surface: "mobile", note: null },
  { id: "analytics-react-native", name: "React Native", surface: "mobile", note: null },
];

function field(overrides: Partial<CommonField>): CommonField {
  return {
    path: "context.campaign.source",
    plain_name: "Campaign source (utm_source)",
    group: "Campaign",
    type: null,
    libraries: ["analytics.js"],
    note: null,
    evidence: "docs",
    sources: ["https://www.twilio.com/docs/segment/connections/spec/common"],
    ...overrides,
  };
}

describe("defaultsSentence", () => {
  it("says which libraries send it by default and which need it turned on", () => {
    expect(
      defaultsSentence(
        { "analytics-swift": true, "analytics-kotlin": false, "analytics-react-native": false },
        LIBRARIES,
      ),
    ).toBe("On by default in Swift. Off by default in Kotlin and React Native.");
  });

  it("says when no library's default is listed, rather than nothing", () => {
    expect(defaultsSentence({}, LIBRARIES)).toBe(
      "Which libraries send it by default isn't listed yet.",
    );
  });
});

describe("librariesLabel", () => {
  it("names each library", () => {
    expect(librariesLabel(["analytics-swift", "analytics-kotlin"], LIBRARIES)).toEqual([
      "Swift",
      "Kotlin",
    ]);
  });

  it("says every library when all of them send it", () => {
    expect(librariesLabel(LIBRARIES.map((l) => l.id), LIBRARIES)).toEqual([
      "Every library",
    ]);
  });
});

describe("sourceLabel", () => {
  it("names the site and the page", () => {
    expect(sourceLabel("https://www.twilio.com/docs/segment/connections/spec/mobile")).toBe(
      "twilio.com/…/mobile",
    );
    expect(sourceLabel("https://github.com/PostHog/posthog-js")).toBe(
      "github.com/…/posthog-js",
    );
  });
});

describe("formatChecked", () => {
  it("writes the date out without shifting it by time zone", () => {
    expect(formatChecked("2026-10-15")).toBe("15 October 2026");
  });
});

describe("matchesField", () => {
  it("finds a field by its plain name or its key", () => {
    expect(matchesField(field({}), "utm")).toBe(true);
    expect(matchesField(field({}), "context.campaign")).toBe(true);
    expect(matchesField(field({}), "coupon")).toBe(false);
  });
});

describe("groupFields", () => {
  it("keeps the file's order within and across groups", () => {
    const groups = groupFields([
      field({ path: "a", group: "Page" }),
      field({ path: "b", group: "Campaign" }),
      field({ path: "c", group: "Page" }),
    ]);
    expect(groups.map(([group, fields]) => [group, fields.map((f) => f.path)])).toEqual([
      ["Page", ["a", "c"]],
      ["Campaign", ["b"]],
    ]);
  });
});

describe("propertySummary", () => {
  it("says a system event's properties aren't listed yet rather than none", () => {
    const unlisted = event({ source: "system_event", properties_listed: false });
    expect(propertySummary(unlisted, 0)).toBe("Properties not listed yet");
  });

  it("says a system event carries none of its own when its sources say so", () => {
    expect(propertySummary(event({ source: "system_event" }), 0)).toBe(
      "No properties of its own",
    );
  });

  it("counts like any other event otherwise", () => {
    expect(propertySummary(event({}), 0)).toBe(propertyCount(0, 0));
  });
});

describe("sharedSources", () => {
  it("returns the list when every row cites the same sources", () => {
    expect(sharedSources([["a", "b"], ["a", "b"]])).toEqual(["a", "b"]);
  });

  it("returns null when any row differs, or there is only one row", () => {
    expect(sharedSources([["a"], ["a", "b"]])).toBeNull();
    expect(sharedSources([["a"]])).toBeNull();
  });
});
