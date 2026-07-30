import { RuleCheck } from "@/lib/api";

// A PII hit is advisory, always. The engine reports one boolean per check, so a flag
// arrives as passed:false — but pii.mode is "flag": it routes to approval and a human
// acknowledges it. Painting it with the same red ✕ as a genuine rejection is why
// request #11's requester saw two failures and could not tell which one stopped the
// request. pii.mode "block" is killed in the PRD's anti-scope, so there is no other
// mode to plumb through — the branch is unconditional on purpose.
function checkState(check: RuleCheck): "pass" | "fail" | "advisory" {
  if (check.rule === "pii") return check.passed ? "pass" : "advisory";
  return check.passed ? "pass" : "fail";
}

const MARKS: Record<"pass" | "fail" | "advisory", string> = {
  pass: "✓",
  fail: "✕",
  advisory: "⚑",
};

export function RuleChecks({
  checks,
  flags,
}: {
  checks: RuleCheck[];
  flags: string[];
}) {
  return (
    <div>
      <div className="checks">
        {checks.map((check) => {
          const state = checkState(check);
          return (
            <div className="check" key={check.rule}>
              <span
                className={`check-mark ${state}`}
                data-state={state}
                aria-label={state}
              >
                {MARKS[state]}
              </span>
              <span>
                <span className="check-rule">{check.rule}</span>
                <span className="check-detail"> — {check.detail}</span>
                {state === "advisory" && (
                  <span className="check-detail">
                    {" "}
                    (advisory — this did not stop the request)
                  </span>
                )}
              </span>
            </div>
          );
        })}
      </div>
      {flags.length > 0 && (
        <div className="flags">
          {flags.map((flag, i) => (
            <div key={i}>⚑ {flag}</div>
          ))}
        </div>
      )}
    </div>
  );
}

// The rules that actually decided the request — the ones there is something to
// disagree with. Advisory checks are excluded.
export function decidingFailures(checks: RuleCheck[]): RuleCheck[] {
  return checks.filter((c) => checkState(c) === "fail");
}
