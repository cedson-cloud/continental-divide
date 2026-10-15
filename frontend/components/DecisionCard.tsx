"use client";

import { Fragment, useState } from "react";
import { DecisionOptions, RequestDetail, ReviewFinding, RuleCheck } from "@/lib/api";
import { engineDuplicateCheck } from "@/lib/gating";

const KIND_PHRASES: Record<string, string> = {
  duplicate_event: "possible duplicates",
  property_extension: "possible property extensions",
  property_already_exists: "possibly existing properties",
};

function findingsText(findings: ReviewFinding[]): { title: string; detail: string } {
  const kinds = Array.from(
    new Set(findings.map((f) => f.kind ?? "duplicate_event")),
  );
  if (kinds.length === 1 && kinds[0] === "duplicate_event") {
    const names = Array.from(new Set(findings.map((f) => f.existing_event)));
    return {
      title: "Possible duplicates reviewed",
      detail: `This event is not ${names.join(", ")}.`,
    };
  }
  const phrases = kinds.map((k) => KIND_PHRASES[k] ?? k).join(", ");
  return {
    title: "Duplicate review findings reviewed",
    detail: `${phrases.charAt(0).toUpperCase()}${phrases.slice(1)}.`,
  };
}

// The engine's check sentence is shown as written, so the approver acknowledges the
// same words the rule checks panel shows. One checkbox covers both sources, because
// the server takes one acknowledgment for every duplicate tier.
function acknowledgeText(
  findings: ReviewFinding[],
  engineCheck: RuleCheck | undefined,
): { title: string; detail: string } | null {
  const text = findings.length > 0 ? findingsText(findings) : null;
  if (!engineCheck) return text;
  const engine = `${engineCheck.detail}.`;
  return text
    ? { ...text, detail: `${engine} ${text.detail}` }
    : { title: "Duplicate name reviewed", detail: engine };
}

// The approver's side of the page. Approve is gated on the same acknowledgments the
// server requires; Reject never is. onDecide resolves true when the decision landed.
export function DecisionCard({
  detail,
  checks,
  deciding,
  error,
  onDecide,
}: {
  detail: RequestDetail;
  checks: RuleCheck[];
  deciding: boolean;
  error: string | null;
  onDecide: (decision: "approve" | "reject", body: DecisionOptions) => Promise<boolean>;
}) {
  const [note, setNote] = useState("");
  const [approverName, setApproverName] = useState("");
  const [piiAcknowledged, setPiiAcknowledged] = useState(false);
  const [findingsAcknowledged, setFindingsAcknowledged] = useState(false);

  const findings = detail.duplicate_candidates;
  const needsPii = detail.pii_flagged;
  const ack = acknowledgeText(findings, engineDuplicateCheck(checks));
  const needsFindings = ack !== null;
  const required = Number(needsPii) + Number(needsFindings);
  const remaining =
    Number(needsPii && !piiAcknowledged) + Number(needsFindings && !findingsAcknowledged);
  const selfApproval = detail.would_be_self_approval === true;
  const approveDescribedBy =
    [required > 0 && "decision-remaining", selfApproval && "decision-self"]
      .filter(Boolean)
      .join(" ") || undefined;

  async function decide(decision: "approve" | "reject") {
    const landed = await onDecide(decision, {
      note,
      approver_name: approverName,
      pii_acknowledged: piiAcknowledged,
      findings_acknowledged: findingsAcknowledged,
    });
    if (landed) {
      setNote("");
      setPiiAcknowledged(false);
      setFindingsAcknowledged(false);
    }
  }

  return (
    <section className="rail-card" aria-labelledby="decision-title">
      <span className="role-hint">You&apos;re the approver</span>
      <h2 id="decision-title" className="rail-title">
        Your decision
      </h2>
      {required > 0 && (
        <p id="decision-remaining" className="rail-lede" aria-live="polite">
          {remaining === 0
            ? "Everything is acknowledged. Ready to approve."
            : `Acknowledge ${remaining} ${remaining === 1 ? "item" : "items"} to approve.`}
        </p>
      )}

      {needsPii && (
        <div className="ack">
          <label className="ack-check">
            <input
              type="checkbox"
              checked={piiAcknowledged}
              onChange={(e) => setPiiAcknowledged(e.target.checked)}
              disabled={deciding}
            />
            <span>
              <span className="ack-title">Personal data reviewed</span>
              {detail.pii_details && (
                <span className="ack-detail">{detail.pii_details}</span>
              )}
            </span>
          </label>
          {Object.keys(detail.pii_hits).length > 0 && (
            <dl className="ack-reasons">
              {Object.entries(detail.pii_hits).map(([name, entry]) => (
                <Fragment key={name}>
                  <dt>
                    <span className="mono">{name}</span> (matched {entry})
                  </dt>
                  <dd>
                    {detail.pii_reasons[name] ||
                      "No reason recorded: submitted before reasons were required."}
                  </dd>
                </Fragment>
              ))}
            </dl>
          )}
        </div>
      )}

      {ack && (
        <div className="ack">
          <label className="ack-check">
            <input
              type="checkbox"
              checked={findingsAcknowledged}
              onChange={(e) => setFindingsAcknowledged(e.target.checked)}
              disabled={deciding}
            />
            <span>
              <span className="ack-title">{ack.title}</span>
              <span className="ack-detail">{ack.detail}</span>
            </span>
          </label>
        </div>
      )}

      <label className="field mt-16">
        <span className="field-label">Your name</span>
        <input
          type="text"
          value={approverName}
          onChange={(e) => setApproverName(e.target.value)}
          disabled={deciding}
        />
      </label>
      <label className="field mt-12">
        <span className="field-label">Note (optional)</span>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={2}
          disabled={deciding}
        />
      </label>

      {selfApproval && (
        <p id="decision-self" className="self-approval-note">
          You made or submitted this request, so approving it will be recorded as a
          self-approval.
        </p>
      )}

      <div className="decision-buttons">
        <button
          className="btn btn-approve"
          onClick={() => decide("approve")}
          disabled={deciding || remaining > 0}
          aria-describedby={approveDescribedBy}
        >
          {deciding ? "Working…" : "Approve & publish"}
        </button>
        <button
          className="btn btn-reject"
          onClick={() => decide("reject")}
          disabled={deciding}
        >
          Reject
        </button>
      </div>
      <p className="rail-foot">Your decision is added to the audit trail.</p>
      {error && (
        <div className="msg msg-error mt-12" role="alert">
          {error}
        </div>
      )}
    </section>
  );
}
