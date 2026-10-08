import { ReviewFinding, RuleCheck } from "@/lib/api";

// What the requester has to answer before a draft can be submitted. Mirrors the gates
// in backend/app/pipeline.py, and exists once so the wizard, the single-screen form,
// and the request detail page cannot drift from each other or from the server — a
// screen that offers Submit where the server returns 422 is the failure to avoid.
//
// Visibility and friction are separate: every finding is shown, only these gate. See
// docs/adr/0001.

// Findings written before confidence was acted on are treated as high, which is what
// they were gated as at the time. Same default the server applies.
export function gatingDuplicateFindings(
  findings: ReviewFinding[],
): ReviewFinding[] {
  return findings.filter(
    (f) =>
      (f.kind ?? "duplicate_event") === "duplicate_event" &&
      (f.confidence ?? "high") === "high",
  );
}

// The engine's near-duplicate rule: the drafted name is one an existing event already
// uses, written differently. There is no finding object behind it — the engine writes
// rule checks, not findings — so it can be answered but never withdrawn to.
export function hasNearDuplicate(checks: RuleCheck[]): boolean {
  return checks.some((c) => c.rule === "near_duplicate" && !c.passed);
}

export function submissionNeedsAnswer(
  findings: ReviewFinding[],
  checks: RuleCheck[],
): boolean {
  return gatingDuplicateFindings(findings).length > 0 || hasNearDuplicate(checks);
}

// Every PII hit needs the requester's written reason before submission (ADR 0003).
// The flagged properties still without one, in the order the engine reported them.
// A blank reason is no reason, matching the server.
export function missingPiiReasons(
  hits: Record<string, string>,
  reasons: Record<string, string>,
): string[] {
  return Object.keys(hits).filter((name) => !(reasons[name] ?? "").trim());
}

// The reasons to send: one per current hit, trimmed. A reason typed for a property an
// earlier draft flagged is dropped, because the server refuses a reason for a
// property no PII rule flagged.
export function piiReasonsToSend(
  hits: Record<string, string>,
  reasons: Record<string, string>,
): Record<string, string> {
  return Object.fromEntries(
    Object.keys(hits)
      .filter((name) => (reasons[name] ?? "").trim())
      .map((name) => [name, reasons[name].trim()]),
  );
}
