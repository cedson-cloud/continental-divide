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
