"use client";

import { ReviewFinding, RuleCheck, SubmitResolution } from "@/lib/api";
import { AgentReview } from "@/components/AgentReview";
import { DuplicateResolution } from "@/components/DuplicateResolution";
import { EngineDuplicates } from "@/components/EngineDuplicates";
import { gatingDuplicateFindings, submissionNeedsAnswer } from "@/lib/gating";

// Step 4: "does this already exist?". When something requires an answer this is
// the LAST step — the three doors (withdraw, ask the approver, note + submit)
// all terminate the wizard, because a step-5 submit without a resolution would
// 422 on DuplicateNoteRequired. No convert button here; convert stays on the
// request detail page.
//
// Two things require an answer: a high-confidence duplicate_event finding, and the
// engine's near-duplicate rule. Findings below high confidence, and the engine's
// exact match, are shown and cost the requester nothing — the exact match is the
// approver's to acknowledge, because there is nothing to argue.
export function StepExists({
  findings,
  checks,
  flags,
  busy,
  onWithdraw,
  onSubmit,
  onNext,
}: {
  findings: ReviewFinding[];
  checks: RuleCheck[];
  flags: string[];
  busy: boolean;
  onWithdraw: (existingEvent: string) => void;
  onSubmit: (resolution: SubmitResolution) => void;
  onNext: () => void;
}) {
  const engine = <EngineDuplicates checks={checks} flags={flags} />;

  if (submissionNeedsAnswer(findings, checks)) {
    return (
      <div>
        {engine}
        <AgentReview findings={findings} variant="requester" />
        <DuplicateResolution
          findings={gatingDuplicateFindings(findings)}
          busy={busy}
          onWithdraw={onWithdraw}
          onSubmit={onSubmit}
        />
      </div>
    );
  }

  if (findings.length > 0 || flags.length > 0) {
    return (
      <div>
        {engine}
        <AgentReview findings={findings} variant="requester" />
        <div className="row mt-16">
          <button className="btn btn-primary" onClick={onNext} disabled={busy}>
            Next
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <p style={{ marginTop: 0 }}>
        Nothing in the catalog looks like this yet.
      </p>
      <div className="row mt-16">
        <button className="btn btn-primary" onClick={onNext} disabled={busy}>
          Next
        </button>
      </div>
    </div>
  );
}
