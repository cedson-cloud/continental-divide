import { RuleCheck } from "@/lib/api";

// Rules that report without rejecting. The engine gives one boolean per check, so
// these arrive as passed:false — but they route to a human rather than ending the
// request. Painting them with the same red ✕ as a genuine rejection is why request
// #11's requester saw two failures and could not tell which one stopped the request.
// Mirrors _NON_BLOCKING_RULES in backend/app/rules.py; see docs/adr/0001 for why no
// duplicate check of any kind rejects.
const ADVISORY_RULES = new Set(["pii", "duplicate", "near_duplicate"]);

function checkState(check: RuleCheck): "pass" | "fail" | "advisory" {
  if (check.passed) return "pass";
  return ADVISORY_RULES.has(check.rule) ? "advisory" : "fail";
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
