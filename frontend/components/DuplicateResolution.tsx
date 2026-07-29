"use client";

import { useState } from "react";
import { ReviewFinding, SubmitResolution } from "@/lib/api";

// The three doors on a duplicate_event finding: agree and withdraw, pass the
// question to the approver, or say how the existing event won't work and submit.
// Only the third door requires the textarea.
export function DuplicateResolution({
  findings,
  busy,
  onWithdraw,
  onSubmit,
}: {
  findings: ReviewFinding[];
  busy: boolean;
  onWithdraw: (existingEvent: string) => void;
  onSubmit: (resolution: SubmitResolution) => void;
}) {
  const [note, setNote] = useState("");
  const events = Array.from(new Set(findings.map((f) => f.existing_event)));

  return (
    <>
      <div className="row mt-12" style={{ flexWrap: "wrap", gap: 8 }}>
        {events.map((name) => (
          <button
            key={name}
            className="btn"
            onClick={() => onWithdraw(name)}
            disabled={busy}
          >
            Use {name} instead
          </button>
        ))}
        <button
          className="btn"
          onClick={() => onSubmit({ duplicateUnsure: true })}
          disabled={busy}
        >
          I&apos;m not sure — ask the approver
        </button>
      </div>
      <label className="field mt-12">
        <span className="field-label">
          How won&apos;t {events.join(" or ")} work for you?
        </span>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={2}
          disabled={busy}
        />
      </label>
      <div className="row mt-12">
        <button
          className="btn btn-primary"
          onClick={() => onSubmit({ duplicateNote: note })}
          disabled={busy || note.trim().length === 0}
        >
          Submit request
        </button>
      </div>
    </>
  );
}
