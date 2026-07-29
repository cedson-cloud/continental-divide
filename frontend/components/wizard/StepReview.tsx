"use client";

import { EventDefinition, RequestDetail, RuleCheck } from "@/lib/api";
import { WizardState } from "@/lib/wizard";
import { ProposedDefinition } from "@/components/AuditTimeline";
import { RuleChecks } from "@/components/RuleChecks";

const KIND_LABELS: Record<string, string> = {
  revenue: "money or revenue",
  user_action: "something a user did",
  user_trait: "something about a user",
  existing_event_detail: "detail on something we already track",
  unknown: "not sure yet",
};

// Step 5: the drafted request, read back in plain English, with the rule
// checks that ran on it. Submit sends it to the approval queue.
export function StepReview({
  detail,
  state,
  busy,
  onSubmit,
}: {
  detail: RequestDetail;
  state: WizardState;
  busy: boolean;
  onSubmit: () => void;
}) {
  const log = detail.audit_log;
  const modelEntry = log.find((e) => e.step === "model_interpreted");
  const rulesEntry = log.find((e) => e.step === "rules_evaluated");
  const proposed = (modelEntry?.detail?.proposed_definition ??
    null) as Partial<EventDefinition> | null;
  const checks = (rulesEntry?.detail?.checks as RuleCheck[]) || [];
  const flags = (rulesEntry?.detail?.flags as string[]) || [];

  return (
    <div>
      {proposed && (
        <div className="proposal">
          <div className="proposal-label">Model proposed</div>
          <ProposedDefinition definition={proposed} />
        </div>
      )}

      {checks.length > 0 && (
        <div className="mt-16">
          <RuleChecks checks={checks} flags={flags} />
        </div>
      )}

      <div className="mt-16">
        <div className="panel-title">Your request, read back</div>
        <p style={{ marginTop: 0, fontSize: 14 }}>
          {state.submitterName} ({state.submitterTeam}) is asking to track{" "}
          {KIND_LABELS[state.kind ?? "unknown"]}: “{state.text.trim()}”. Why it
          matters: {state.businessValue.trim()}.
        </p>
        <p className="muted" style={{ fontSize: 13.5 }}>
          Call type: track. Side: {state.side}.
          {state.kind === "existing_event_detail" && state.existingEvent
            ? ` Adds to the existing event ${state.existingEvent}.`
            : ""}
          {state.neededBy ? ` Needed by ${state.neededBy}.` : ""}
          {state.urgent ? ` Urgent: ${state.urgencyReason.trim()}.` : ""}
          {state.destinations.length > 0
            ? ` Destinations: ${state.destinations.join(", ")}.`
            : ""}
        </p>
      </div>

      <div className="row mt-16">
        <button className="btn btn-primary" onClick={onSubmit} disabled={busy}>
          {busy ? "Submitting…" : "Submit request"}
        </button>
      </div>
    </div>
  );
}
