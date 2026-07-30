import { RuleCheck } from "@/lib/api";

// What the engine found about the name itself, kept visually separate from the agent
// review. The distinction is the point of the whole seam: this panel states a fact or
// a mechanical judgment about spelling, the agent panel makes an argument about
// meaning. See docs/adr/0001.
//
// The flag sentences come from the engine verbatim rather than being reassembled here,
// so the wording the audit log records and the wording the requester reads are the
// same string.
const HEADINGS: Record<string, string> = {
  duplicate: "This name is already in the tracking plan",
  near_duplicate: "This is a name you already have, written differently",
};

export function EngineDuplicates({
  checks,
  flags,
}: {
  checks: RuleCheck[];
  flags: string[];
}) {
  const hit = checks.find(
    (c) => !c.passed && (c.rule === "duplicate" || c.rule === "near_duplicate"),
  );
  if (!hit || flags.length === 0) return null;

  return (
    <div className="agent-review">
      <div className="agent-review-label">Engine check — the name itself</div>
      <div className="finding-group">
        <div className="finding-group-heading">{HEADINGS[hit.rule]}</div>
        <div className="flags">
          {flags.map((flag, i) => (
            <div key={i}>⚑ {flag}</div>
          ))}
        </div>
      </div>
    </div>
  );
}
