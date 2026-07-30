"use client";

import { useState } from "react";
import { RuleCheck } from "@/lib/api";
import { RuleChecks, decidingFailures } from "@/components/RuleChecks";

// The one component every rejection renders — wizard step 4, the single-screen
// outcome, and the request detail page all share it, so the doors cannot exist on one
// screen and not another. Before this, a rule rejection was a dead end: the trail
// stopped at rules_evaluated -> routed with nothing for the requester to do and no way
// to disagree.
//
// Two doors, and they are different in kind. The rename takes a name the engine itself
// vouches for — the candidates are derived and re-validated server-side, so this
// component only ever displays them. The dispute changes nothing at all; it files the
// disagreement for the data team. It renders whether or not a compliant name exists,
// because "the tool has no suggestion" is exactly when a requester most needs to say
// the rule is wrong.
export function RejectedRecourse({
  checks,
  flags,
  suggestions,
  busy,
  onRename,
  onDispute,
  error,
}: {
  checks: RuleCheck[];
  flags: string[];
  suggestions: string[];
  busy: boolean;
  onRename: (name: string) => void;
  onDispute: (rule: string, note: string) => void;
  error?: string | null;
}) {
  const [note, setNote] = useState("");
  const [showDispute, setShowDispute] = useState(false);
  const failures = decidingFailures(checks);
  const disputableRule = failures[0]?.rule ?? null;

  return (
    <div>
      <p style={{ marginTop: 0 }}>
        The rules rejected this draft before it reached anyone.
      </p>

      <RuleChecks checks={checks} flags={flags} />

      {suggestions.length > 0 && (
        <div className="mt-16">
          <div className="panel-title" style={{ marginBottom: 6 }}>
            {suggestions.length === 1
              ? `${suggestions[0]} follows your team's convention — use that instead?`
              : "These names follow your team's convention — use one instead?"}
          </div>
          <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
            Everything else about the request is kept. It goes back through the same
            rules under the new name.
          </p>
          <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
            {suggestions.map((name) => (
              <button
                key={name}
                className="btn btn-primary"
                onClick={() => onRename(name)}
                disabled={busy}
              >
                Use {name}
              </button>
            ))}
          </div>
        </div>
      )}

      {disputableRule && (
        <div className="mt-16">
          {!showDispute ? (
            <button
              className="link-button"
              onClick={() => setShowDispute(true)}
              disabled={busy}
            >
              This rule looks wrong for us
            </button>
          ) : (
            <>
              <label className="field">
                <span className="field-label">
                  Why does {disputableRule} look wrong for your team? *
                </span>
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={3}
                  placeholder="e.g. “Back in Stock” is a product concept here, not a verb phrase"
                  disabled={busy}
                />
              </label>
              <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
                This changes nothing on its own — the request stays rejected and the
                rules stay as they are. It records your disagreement, with the profile
                version it applies to, for the data team to review.
              </p>
              <div className="row">
                <button
                  className="btn"
                  onClick={() => onDispute(disputableRule, note)}
                  disabled={busy || note.trim().length === 0}
                >
                  Send to the data team
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {error && <div className="msg msg-error mt-16">{error}</div>}
    </div>
  );
}
