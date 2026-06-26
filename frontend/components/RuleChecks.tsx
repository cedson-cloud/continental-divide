import { RuleCheck } from "@/lib/api";

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
        {checks.map((check) => (
          <div className="check" key={check.rule}>
            <span className={`check-mark ${check.passed ? "pass" : "fail"}`}>
              {check.passed ? "✓" : "✕"}
            </span>
            <span>
              <span className="check-rule">{check.rule}</span>
              <span className="check-detail"> — {check.detail}</span>
            </span>
          </div>
        ))}
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
