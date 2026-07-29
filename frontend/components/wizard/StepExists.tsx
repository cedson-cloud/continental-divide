"use client";

import { ReviewFinding, SubmitResolution } from "@/lib/api";
import { AgentReview } from "@/components/AgentReview";
import { DuplicateResolution } from "@/components/DuplicateResolution";

// Step 4: "does this already exist?". With a duplicate_event finding this is
// the LAST step — the three doors (withdraw, ask the approver, note + submit)
// all terminate the wizard, because a step-5 submit without a resolution would
// 422 on DuplicateNoteRequired. No convert button here; convert stays on the
// request detail page.
export function StepExists({
  findings,
  busy,
  onWithdraw,
  onSubmit,
  onNext,
}: {
  findings: ReviewFinding[];
  busy: boolean;
  onWithdraw: (existingEvent: string) => void;
  onSubmit: (resolution: SubmitResolution) => void;
  onNext: () => void;
}) {
  const duplicates = findings.filter(
    (f) => (f.kind ?? "duplicate_event") === "duplicate_event",
  );

  if (duplicates.length > 0) {
    return (
      <div>
        <AgentReview findings={findings} variant="requester" />
        <DuplicateResolution
          findings={duplicates}
          busy={busy}
          onWithdraw={onWithdraw}
          onSubmit={onSubmit}
        />
      </div>
    );
  }

  if (findings.length > 0) {
    return (
      <div>
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
