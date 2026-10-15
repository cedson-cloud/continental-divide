import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Dispute, GovernanceProfileInfo } from "@/lib/api";
import { GovernanceProfile } from "./GovernanceProfile";

afterEach(cleanup);

function profile(overrides: Partial<GovernanceProfileInfo> = {}): GovernanceProfileInfo {
  return {
    name: "segment-ecommerce",
    source: "https://www.twilio.com/docs/segment/protocols/tracking-plan/best-practices",
    event_naming: {
      convention: "title_case_object_action",
      connectors: [],
      particles: [],
      irregular_past: [],
    },
    property_naming: { convention: "snake_case" },
    pii: { mode: "flag", blocklist: ["email", "phone"] },
    categories: { values: ["Core Ordering"], source: "sample_plan" },
    destinations: ["warehouse", "product_analytics"],
    examples: [
      { name: "Cart Cleared", passes: true, reason: null },
      { name: "add_to_cart", passes: false, reason: "not Object Action in Title Case" },
    ],
    ...overrides,
  };
}

const dispute: Dispute = {
  request_id: 12,
  event_name: "Newsletter Signed Up",
  request_status: "rejected",
  rule: "event_naming",
  note: "Our marketing team uses this name everywhere.",
  profile: "segment-ecommerce",
  profile_digest: "a1b2c3",
  created_at: "2026-10-15 10:00:00",
};

describe("GovernanceProfile", () => {
  it("says each convention in plain English, with the profile's identifier beside it", () => {
    render(<GovernanceProfile profile={profile()} disputes={[]} />);

    expect(screen.getByText("Title Case Object Action")).toBeInTheDocument();
    expect(screen.getByText("Cart Cleared", { selector: ".gov-rule .mono" })).toBeInTheDocument();
    expect(
      screen.getByText("event_naming.convention: title_case_object_action"),
    ).toBeInTheDocument();
    expect(screen.getByText("property_naming.convention: snake_case")).toBeInTheDocument();
  });

  it("describes personal data as flagged and gated on a reason, never rejected", () => {
    render(<GovernanceProfile profile={profile()} disputes={[]} />);
    expect(screen.getByText("Flagged, never rejected.")).toBeInTheDocument();
    expect(screen.getByText(/the requester writes a reason for each one/)).toBeInTheDocument();
    expect(screen.getByText("email")).toBeInTheDocument();
  });

  it("marks each example as passing or failing for a screen reader", () => {
    render(<GovernanceProfile profile={profile()} disputes={[]} />);
    expect(screen.getByRole("img", { name: "passes" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "fails" })).toBeInTheDocument();
    expect(screen.getByText(/not Object Action in Title Case/)).toBeInTheDocument();
  });

  it("labels destinations the way the setup wizard does", () => {
    render(<GovernanceProfile profile={profile()} disputes={[]} />);
    expect(screen.getByText("Product analytics")).toBeInTheDocument();
    expect(
      screen.getByText("destinations: [warehouse, product_analytics]"),
    ).toBeInTheDocument();
  });

  it("names a disputed rule in plain English and links its request", () => {
    render(<GovernanceProfile profile={profile()} disputes={[dispute]} />);
    expect(screen.getByText("Event name")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Request #12" })).toHaveAttribute(
      "href",
      "/requests/12",
    );
    expect(screen.getByText("Rejected")).toBeInTheDocument();
  });

  it("says so when nobody has disputed a rule", () => {
    render(<GovernanceProfile profile={profile()} disputes={[]} />);
    expect(screen.getByText("No disputes on record.")).toBeInTheDocument();
  });

  it("shows where the convention comes from by its site, not its full address", () => {
    render(<GovernanceProfile profile={profile()} disputes={[]} />);
    expect(screen.getByRole("link", { name: "twilio.com (opens in a new tab)" })).toHaveAttribute(
      "href",
      "https://www.twilio.com/docs/segment/protocols/tracking-plan/best-practices",
    );
  });
});
