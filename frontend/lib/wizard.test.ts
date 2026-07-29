import { describe, expect, it } from "vitest";
import { RequestDetail } from "./api";
import {
  WizardState,
  canAdvance,
  initialWizardState,
  toIntakePayload,
  wizardReducer,
} from "./wizard";

const detailStub = { id: 1, status: "draft" } as RequestDetail;

function stateAt(overrides: Partial<WizardState>): WizardState {
  return { ...initialWizardState, ...overrides };
}

// A state that passes every gate up to step 3.
const filled = stateAt({
  kind: "revenue",
  submitterName: "Sam",
  submitterTeam: "Product",
  text: "track refunds",
  businessValue: "finance needs it",
});

describe("initial state", () => {
  it("starts at step 1 and cannot advance", () => {
    expect(initialWizardState.step).toBe(1);
    expect(canAdvance(initialWizardState)).toBe(false);
  });
});

describe("request_kind derivation", () => {
  it("derives new_property_on_existing for existing_event_detail", () => {
    const payload = toIntakePayload(
      stateAt({ kind: "existing_event_detail", existingEvent: "Order Completed" }),
    );
    expect(payload.request_kind).toBe("new_property_on_existing");
    expect(payload.existing_event).toBe("Order Completed");
  });

  it("derives new_event for every other kind", () => {
    for (const kind of ["revenue", "user_action", "user_trait", "unknown"] as const) {
      expect(toIntakePayload(stateAt({ kind })).request_kind).toBe("new_event");
    }
  });
});

describe("canAdvance", () => {
  it("gates step 1 on a chosen kind", () => {
    expect(canAdvance(stateAt({ step: 1 }))).toBe(false);
    expect(canAdvance(stateAt({ step: 1, kind: "unknown" }))).toBe(true);
  });

  it("gates step 2 on submitter name and team", () => {
    expect(canAdvance(stateAt({ step: 2 }))).toBe(false);
    expect(canAdvance(stateAt({ step: 2, submitterName: "Sam" }))).toBe(false);
    expect(canAdvance(stateAt({ step: 2, submitterTeam: "Data" }))).toBe(false);
    expect(
      canAdvance(stateAt({ step: 2, submitterName: "Sam", submitterTeam: "Data" })),
    ).toBe(true);
  });

  it("gates step 3 on text, business value, and an urgency reason when urgent", () => {
    expect(canAdvance(stateAt({ step: 3, text: "t" }))).toBe(false);
    expect(canAdvance(stateAt({ step: 3, businessValue: "b" }))).toBe(false);
    expect(canAdvance(stateAt({ step: 3, text: "t", businessValue: "b" }))).toBe(true);
    expect(
      canAdvance(stateAt({ step: 3, text: "t", businessValue: "b", urgent: true })),
    ).toBe(false);
    expect(
      canAdvance(
        stateAt({
          step: 3,
          text: "t",
          businessValue: "b",
          urgent: true,
          urgencyReason: "launch",
        }),
      ),
    ).toBe(true);
  });

  it("always allows advancing from step 4", () => {
    expect(canAdvance(stateAt({ step: 4 }))).toBe(true);
  });
});

describe("toIntakePayload", () => {
  it("always sends call_type track", () => {
    expect(toIntakePayload(filled).call_type).toBe("track");
    expect(
      toIntakePayload(stateAt({ kind: "existing_event_detail" })).call_type,
    ).toBe("track");
  });

  it("nulls existing_event when the kind is not existing_event_detail", () => {
    const payload = toIntakePayload(
      stateAt({ kind: "revenue", existingEvent: "Order Completed" }),
    );
    expect(payload.existing_event).toBeNull();
  });

  it("nulls urgency_reason when not urgent", () => {
    const payload = toIntakePayload(
      stateAt({ urgent: false, urgencyReason: "stale text" }),
    );
    expect(payload.urgency_reason).toBeNull();
    expect(
      toIntakePayload(stateAt({ urgent: true, urgencyReason: "launch" }))
        .urgency_reason,
    ).toBe("launch");
  });
});

describe("drafting transitions", () => {
  it("DRAFT_SUCCEEDED moves to step 4 with drafting false", () => {
    const drafting = wizardReducer({ ...filled, step: 3 }, { type: "DRAFT_STARTED" });
    expect(drafting.drafting).toBe(true);
    const next = wizardReducer(drafting, {
      type: "DRAFT_SUCCEEDED",
      detail: detailStub,
    });
    expect(next.step).toBe(4);
    expect(next.drafting).toBe(false);
    expect(next.detail).toBe(detailStub);
  });

  it("DRAFT_FAILED stays on step 3 with the error set", () => {
    const drafting = wizardReducer({ ...filled, step: 3 }, { type: "DRAFT_STARTED" });
    const next = wizardReducer(drafting, {
      type: "DRAFT_FAILED",
      error: "rate limit",
    });
    expect(next.step).toBe(3);
    expect(next.drafting).toBe(false);
    expect(next.error).toBe("rate limit");
  });
});

describe("BACK from step 4", () => {
  it("clears the draft so a re-entry re-drafts", () => {
    const atFour = stateAt({ ...filled, step: 4, detail: detailStub });
    const back = wizardReducer(atFour, { type: "BACK" });
    expect(back.step).toBe(3);
    expect(back.detail).toBeNull();
  });
});
