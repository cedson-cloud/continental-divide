import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RequestDetail, ReviewFinding, RuleCheck } from "@/lib/api";
import { DecisionCard } from "./DecisionCard";

afterEach(cleanup);

const FINDING: ReviewFinding = {
  kind: "duplicate_event",
  existing_event: "User Signed Up",
  category: "Account",
  property_names: [],
  reason: "Both fire when someone signs up.",
  confidence: "high",
};

function detail(overrides: Partial<RequestDetail> = {}): RequestDetail {
  return {
    id: 27,
    raw_intake_text: "track newsletter signups",
    parsed_definition: null,
    category: null,
    status: "pending_approval",
    pii_flagged: false,
    pii_details: null,
    duplicate_candidates: [],
    submitter_name: null,
    submitter_team: null,
    call_type: null,
    side: null,
    business_value: null,
    urgent: false,
    urgency_reason: null,
    needed_by: null,
    request_kind: null,
    existing_event: null,
    destinations: null,
    published_artifact: null,
    created_at: "2026-10-07 09:00:00",
    updated_at: "2026-10-07 09:00:00",
    audit_log: [],
    name_suggestions: [],
    pii_hits: {},
    pii_reasons: {},
    would_be_self_approval: false,
    snippets: [],
    ...overrides,
  };
}

const GATED = detail({
  pii_flagged: true,
  pii_details: "email -> email",
  pii_hits: { email: "email" },
  pii_reasons: { email: "Joins signups to the email platform." },
  duplicate_candidates: [FINDING],
});

const CLEAN_CHECKS: RuleCheck[] = [
  {
    rule: "duplicate",
    passed: true,
    detail: "'Newsletter Signed Up' is not already in the tracking plan",
  },
  { rule: "near_duplicate", passed: true, detail: "no near duplicate in the tracking plan" },
];

const NEAR_DUPLICATE: RuleCheck[] = [
  {
    rule: "duplicate",
    passed: true,
    detail: "'order completed' is not already in the tracking plan",
  },
  {
    rule: "near_duplicate",
    passed: false,
    detail: "'order completed' is the same name as 'Order Completed' written differently",
  },
];

const EXACT_DUPLICATE: RuleCheck[] = [
  {
    rule: "duplicate",
    passed: false,
    detail: "'Order Completed' already exists in the tracking plan",
  },
  {
    rule: "near_duplicate",
    passed: true,
    detail: "not checked: an exact match already answers the question",
  },
];

function renderCard(
  d: RequestDetail,
  onDecide = vi.fn().mockResolvedValue(true),
  checks: RuleCheck[] = CLEAN_CHECKS,
) {
  render(
    <DecisionCard
      detail={d}
      checks={checks}
      deciding={false}
      error={null}
      onDecide={onDecide}
    />,
  );
  return onDecide;
}

const approve = () => screen.getByRole("button", { name: /Approve & publish/ });
const reject = () => screen.getByRole("button", { name: "Reject" });

describe("DecisionCard gating", () => {
  it("holds Approve until personal data and duplicates are both acknowledged", () => {
    renderCard(GATED);

    expect(screen.getByText("Acknowledge 2 items to approve.")).toBeInTheDocument();
    expect(approve()).toBeDisabled();
    expect(reject()).toBeEnabled();

    fireEvent.click(screen.getByRole("checkbox", { name: /Personal data reviewed/ }));
    expect(screen.getByText("Acknowledge 1 item to approve.")).toBeInTheDocument();
    expect(approve()).toBeDisabled();

    fireEvent.click(
      screen.getByRole("checkbox", { name: /This event is not User Signed Up/ }),
    );
    expect(approve()).toBeEnabled();
  });

  it("shows the requester's reason for each flagged property beside the acknowledgment", () => {
    renderCard(GATED);
    expect(screen.getByText("Joins signups to the email platform.")).toBeInTheDocument();
  });

  it("asks for nothing when there is nothing to acknowledge", () => {
    renderCard(detail());
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByText(/Acknowledge/)).not.toBeInTheDocument();
    expect(approve()).toBeEnabled();
  });

  it("sends the name, note and both acknowledgments with the decision", async () => {
    const onDecide = renderCard(GATED);
    fireEvent.change(screen.getByRole("textbox", { name: "Your name (optional)" }), {
      target: { value: "Ana" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Note (optional)" }), {
      target: { value: "Looks right" },
    });
    fireEvent.click(screen.getByRole("checkbox", { name: /Personal data reviewed/ }));
    fireEvent.click(
      screen.getByRole("checkbox", { name: /This event is not User Signed Up/ }),
    );
    fireEvent.click(approve());

    await waitFor(() => expect(onDecide).toHaveBeenCalledTimes(1));
    expect(onDecide).toHaveBeenCalledWith("approve", {
      note: "Looks right",
      approver_name: "Ana",
      pii_acknowledged: true,
      findings_acknowledged: true,
    });
  });

  it("keeps the acknowledgments when the decision did not land", async () => {
    const onDecide = renderCard(GATED, vi.fn().mockResolvedValue(false));
    fireEvent.click(screen.getByRole("checkbox", { name: /Personal data reviewed/ }));
    fireEvent.click(reject());

    await waitFor(() => expect(onDecide).toHaveBeenCalled());
    expect(screen.getByRole("checkbox", { name: /Personal data reviewed/ })).toBeChecked();
  });

  // A raw-path request has no agent findings, so the engine is the only thing that
  // fired. The server still refuses Approve without the acknowledgment.
  it("gates Approve on an engine-only near duplicate until it is acknowledged", async () => {
    const onDecide = renderCard(detail(), undefined, NEAR_DUPLICATE);

    expect(screen.getByText("Acknowledge 1 item to approve.")).toBeInTheDocument();
    expect(approve()).toBeDisabled();

    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /same name as 'Order Completed' written differently/,
      }),
    );
    expect(approve()).toBeEnabled();
    fireEvent.click(approve());

    await waitFor(() => expect(onDecide).toHaveBeenCalledTimes(1));
    expect(onDecide).toHaveBeenCalledWith(
      "approve",
      expect.objectContaining({ findings_acknowledged: true }),
    );
  });

  it("gates Approve on an engine-only exact duplicate", () => {
    renderCard(detail(), undefined, EXACT_DUPLICATE);
    expect(
      screen.getByRole("checkbox", { name: /Duplicate name reviewed/ }),
    ).toBeInTheDocument();
    expect(approve()).toBeDisabled();
  });

  it("asks once when the engine and the duplicate review both fired", () => {
    renderCard(detail({ duplicate_candidates: [FINDING] }), undefined, NEAR_DUPLICATE);

    expect(screen.getAllByRole("checkbox")).toHaveLength(1);
    const box = screen.getByRole("checkbox", {
      name: /written differently.*This event is not User Signed Up/,
    });
    fireEvent.click(box);
    expect(approve()).toBeEnabled();
  });
});

describe("DecisionCard self-approval notice", () => {
  it("tells the approver before they approve that it will be a self-approval", () => {
    renderCard({ ...GATED, would_be_self_approval: true });

    const note = /made or submitted this request, so approving it will be recorded as a self-approval/;
    expect(screen.getByText(note)).toBeInTheDocument();
    expect(approve()).toHaveAccessibleDescription(
      expect.stringMatching(/Acknowledge 2 items to approve\. .*self-approval/),
    );
  });

  it("says nothing when the approver is someone else, or the requester is unknown", () => {
    renderCard(detail({ would_be_self_approval: false }));
    expect(screen.queryByText(/self-approval/)).not.toBeInTheDocument();
    cleanup();
    renderCard(detail({ would_be_self_approval: null }));
    expect(screen.queryByText(/self-approval/)).not.toBeInTheDocument();
    expect(approve()).not.toHaveAttribute("aria-describedby");
  });
});
