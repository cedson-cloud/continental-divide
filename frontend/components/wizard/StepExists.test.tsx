import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ReviewFinding } from "@/lib/api";
import { StepExists } from "./StepExists";

afterEach(cleanup);

function finding(overrides: Partial<ReviewFinding>): ReviewFinding {
  return {
    kind: "duplicate_event",
    existing_event: "Cart Viewed",
    category: "Browsing",
    property_names: [],
    reason: "Same shopper behavior, same moment.",
    confidence: "high",
    ...overrides,
  };
}

function renderStep(findings: ReviewFinding[]) {
  return render(
    <StepExists
      findings={findings}
      busy={false}
      onWithdraw={vi.fn()}
      onSubmit={vi.fn()}
      onNext={vi.fn()}
    />,
  );
}

describe("StepExists", () => {
  it("renders all three doors and no Next on a duplicate_event finding", () => {
    renderStep([finding({})]);

    // Door 1: withdraw in favor of the existing event.
    expect(
      screen.getByRole("button", { name: "Use Cart Viewed instead" }),
    ).toBeInTheDocument();
    // Door 2: pass the question to the approver.
    expect(
      screen.getByRole("button", { name: "I'm not sure — ask the approver" }),
    ).toBeInTheDocument();
    // Door 3: explain why it is not a duplicate and submit.
    expect(
      screen.getByRole("button", { name: "Submit request" }),
    ).toBeInTheDocument();

    expect(screen.queryByRole("button", { name: "Next" })).toBeNull();
  });

  it("renders the nothing-like-this copy and a Next when findings are empty", () => {
    renderStep([]);

    expect(
      screen.getByText("Nothing in the catalog looks like this yet."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeInTheDocument();
  });

  it("renders AgentReview and a Next, without DuplicateResolution, on property_extension-only findings", () => {
    renderStep([
      finding({ kind: "property_extension", reason: "Belongs on Cart Viewed." }),
    ]);

    // AgentReview's heading for this finding kind.
    expect(
      screen.getByText("This may belong on an existing event"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeInTheDocument();

    // None of DuplicateResolution's doors.
    expect(
      screen.queryByRole("button", { name: "Use Cart Viewed instead" }),
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: "I'm not sure — ask the approver" }),
    ).toBeNull();
    expect(screen.queryByRole("button", { name: "Submit request" })).toBeNull();
  });
});
