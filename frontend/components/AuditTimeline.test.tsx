import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AuditEntry } from "@/lib/api";
import { AuditTimeline } from "./AuditTimeline";

afterEach(cleanup);

const LOCAL_ACTOR = { email: "dev@example.com", method: "local", verified: false };

function entry(
  id: number,
  step: string,
  detail: Record<string, unknown> | null,
): AuditEntry {
  return { id, request_id: 1, step, detail, created_at: "2026-10-07 09:00:00" };
}

describe("AuditTimeline actor", () => {
  it("names a local actor once per entry, marked unverified, never as raw detail", () => {
    render(
      <AuditTimeline
        entries={[
          entry(1, "submitted", { note: "ready for review", actor: LOCAL_ACTOR }),
          entry(2, "rules_evaluated", { checks: [], flags: [], actor: LOCAL_ACTOR }),
        ]}
      />,
    );

    expect(screen.getAllByText("by dev@example.com · unverified")).toHaveLength(2);
    expect(screen.queryByText("actor")).not.toBeInTheDocument();
    expect(screen.queryByText(/"email"/)).not.toBeInTheDocument();
    expect(screen.getByText("ready for review")).toBeInTheDocument();
  });

  it("names a verified actor with no extra label", () => {
    const verified = { email: "approver@example.com", method: "access", verified: true };
    render(<AuditTimeline entries={[entry(1, "published", { actor: verified })]} />);

    expect(screen.getByText("by approver@example.com")).toBeInTheDocument();
    expect(screen.queryByText(/unverified/)).not.toBeInTheDocument();
  });

  it("says so when an entry predates actors", () => {
    render(
      <AuditTimeline
        entries={[
          entry(1, "intake_received", { raw_intake_text: "clear the cart" }),
          entry(2, "routed", null),
        ]}
      />,
    );

    expect(screen.getAllByText("actor not recorded")).toHaveLength(2);
    expect(screen.getByText("clear the cart")).toBeInTheDocument();
  });
});

describe("AuditTimeline self-approval", () => {
  const DEMO_ACTOR = { email: "anonymous visitor", method: "demo", verified: false };

  it("marks an approval by its own requester, never as raw detail", () => {
    render(
      <AuditTimeline
        entries={[
          entry(1, "decision_received", {
            decision: "approve",
            self_approval: true,
            actor: DEMO_ACTOR,
          }),
        ]}
      />,
    );

    expect(
      screen.getByText("by anonymous visitor · unverified · self-approval"),
    ).toBeInTheDocument();
    expect(screen.queryByText("self_approval")).not.toBeInTheDocument();
  });

  it("adds nothing when someone else requested it, or nobody knows who did", () => {
    render(
      <AuditTimeline
        entries={[
          entry(1, "decision_received", {
            decision: "approve",
            self_approval: false,
            actor: LOCAL_ACTOR,
          }),
          entry(2, "decision_received", {
            decision: "approve",
            self_approval: null,
            actor: LOCAL_ACTOR,
          }),
        ]}
      />,
    );

    expect(screen.getAllByText("by dev@example.com · unverified")).toHaveLength(2);
    expect(screen.queryByText(/self/)).not.toBeInTheDocument();
  });
});

describe("AuditTimeline labels", () => {
  it("says detail keys and values in plain words", () => {
    render(
      <AuditTimeline
        entries={[
          entry(1, "submitted", { decision: "pending_approval", duplicate_unsure: true }),
          entry(2, "rule_disputed", { rule: "event_naming", note: "a product concept" }),
        ]}
      />,
    );

    expect(screen.getByText("Submitted for approval")).toBeInTheDocument();
    expect(screen.getByText("Asked the approver to decide")).toBeInTheDocument();
    expect(screen.getByText("Yes")).toBeInTheDocument();
    expect(screen.getByText("Pending approval")).toBeInTheDocument();
    expect(screen.getByText("Event name")).toBeInTheDocument();
    expect(screen.queryByText(/duplicate_unsure|pending_approval|event_naming/)).not.toBeInTheDocument();
  });

  it("keeps the code font for event names and nothing else", () => {
    render(
      <AuditTimeline
        entries={[entry(1, "withdrawn", { existing_event: "User Signed Up", reason: "same thing" })]}
      />,
    );

    expect(screen.getByText("User Signed Up")).toHaveClass("mono");
    expect(screen.getByText("same thing")).not.toHaveClass("mono");
  });

  it("names rule checks the way the rule-check panel does", () => {
    render(
      <AuditTimeline
        entries={[
          entry(1, "rules_evaluated", {
            checks: [{ rule: "event_naming", passed: false, detail: "word 'in' must be Title Case" }],
            flags: [],
          }),
        ]}
      />,
    );

    expect(screen.getByText("Event name")).toBeInTheDocument();
    expect(screen.getByText("Event name: word 'in' must be Title Case")).toBeInTheDocument();
  });
});

describe("AuditTimeline structured values", () => {
  it("reads findings and per-property reasons as sentences, not JSON", () => {
    render(
      <AuditTimeline
        entries={[
          entry(1, "duplicate_review", {
            findings: [
              { existing_event: "User Signed Up", confidence: "high", reason: "both are signups" },
            ],
          }),
          entry(2, "submitted", { pii_reasons: { email: "joins the email platform" } }),
        ]}
      />,
    );

    expect(
      screen.getByText("User Signed Up (high confidence): both are signups"),
    ).toBeInTheDocument();
    expect(screen.getByText("email: joins the email platform")).toBeInTheDocument();
    expect(screen.queryByText(/[{}]/)).not.toBeInTheDocument();
  });
});
