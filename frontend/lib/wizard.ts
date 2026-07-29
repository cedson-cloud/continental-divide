// Pure state machine for the guided intake wizard: no React, no fetch. The page
// component owns the API calls and dispatches DRAFT_* around them, so the POST
// fires between step 3 and step 4 — the requester sees "does this already
// exist?" before they see a drafted event name.

import type { IntakeMeta, RequestDetail } from "./api";

export type DataKind =
  | "revenue"
  | "user_action"
  | "user_trait"
  | "existing_event_detail"
  | "unknown";

export type WizardStep = 1 | 2 | 3 | 4 | 5;

export type WizardState = {
  step: WizardStep;
  kind: DataKind | null;
  existingEvent: string;
  submitterName: string;
  submitterTeam: string;
  side: string;
  neededBy: string;
  destinations: string[];
  text: string;
  businessValue: string;
  urgent: boolean;
  urgencyReason: string;
  drafting: boolean;
  error: string | null;
  detail: RequestDetail | null;
};

type TextField =
  | "existingEvent"
  | "submitterName"
  | "submitterTeam"
  | "side"
  | "neededBy"
  | "text"
  | "businessValue"
  | "urgencyReason";

export type WizardAction =
  | { type: "SELECT_KIND"; kind: DataKind }
  | { type: "SET_FIELD"; field: TextField; value: string }
  | { type: "SET_FIELD"; field: "urgent"; value: boolean }
  | { type: "TOGGLE_DESTINATION"; destination: string }
  | { type: "NEXT" }
  | { type: "BACK" }
  | { type: "DRAFT_STARTED" }
  | { type: "DRAFT_SUCCEEDED"; detail: RequestDetail }
  | { type: "DRAFT_FAILED"; error: string };

export const initialWizardState: WizardState = {
  step: 1,
  kind: null,
  existingEvent: "",
  submitterName: "",
  submitterTeam: "",
  side: "Unsure",
  neededBy: "",
  destinations: [],
  text: "",
  businessValue: "",
  urgent: false,
  urgencyReason: "",
  drafting: false,
  error: null,
  detail: null,
};

export function canAdvance(state: WizardState): boolean {
  switch (state.step) {
    case 1:
      return state.kind !== null;
    case 2:
      return (
        state.submitterName.trim().length > 0 && state.submitterTeam !== ""
      );
    case 3:
      return (
        state.text.trim().length > 0 &&
        state.businessValue.trim().length > 0 &&
        (!state.urgent || state.urgencyReason.trim().length > 0)
      );
    case 4:
      return true;
    default:
      return false;
  }
}

export function wizardReducer(
  state: WizardState,
  action: WizardAction,
): WizardState {
  switch (action.type) {
    case "SELECT_KIND":
      return {
        ...state,
        kind: action.kind,
        existingEvent:
          action.kind === "existing_event_detail" ? state.existingEvent : "",
        side: action.kind === "unknown" ? "Unsure" : state.side,
      };
    case "SET_FIELD":
      return { ...state, [action.field]: action.value };
    case "TOGGLE_DESTINATION":
      return {
        ...state,
        destinations: state.destinations.includes(action.destination)
          ? state.destinations.filter((d) => d !== action.destination)
          : [...state.destinations, action.destination],
      };
    case "NEXT":
      // Leaving step 3 goes through DRAFT_STARTED/DRAFT_SUCCEEDED instead.
      if (state.step === 3 || state.step >= 5 || !canAdvance(state)) {
        return state;
      }
      return { ...state, step: (state.step + 1) as WizardStep };
    case "BACK":
      if (state.step === 1) return state;
      // Leaving step 4 discards the draft: an edited description must never
      // show a stale one. Re-entering step 4 re-drafts.
      if (state.step === 4) {
        return { ...state, step: 3, detail: null, error: null };
      }
      return { ...state, step: (state.step - 1) as WizardStep };
    case "DRAFT_STARTED":
      return { ...state, drafting: true, error: null };
    case "DRAFT_SUCCEEDED":
      return { ...state, drafting: false, detail: action.detail, step: 4 };
    case "DRAFT_FAILED":
      return { ...state, drafting: false, error: action.error };
    default:
      return state;
  }
}

export function toIntakePayload(state: WizardState): IntakeMeta {
  return {
    submitter_name: state.submitterName,
    submitter_team: state.submitterTeam,
    call_type: "track",
    side: state.side,
    business_value: state.businessValue,
    urgent: state.urgent,
    urgency_reason: state.urgent ? state.urgencyReason : null,
    needed_by: state.neededBy || null,
    // Derived, never stored: the answer to "what kind of data?" is the answer
    // to "is this a new event or a property on one we already track?".
    request_kind:
      state.kind === "existing_event_detail"
        ? "new_property_on_existing"
        : "new_event",
    existing_event:
      state.kind === "existing_event_detail" && state.existingEvent
        ? state.existingEvent
        : null,
    destinations: state.destinations,
  };
}
