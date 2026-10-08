"use client";

// One written reason per property the PII rule flagged (ADR 0003). The flag never
// stops a request; the reason is what puts the requester on the record, and the
// approver reads it before acknowledging. Rendered beside every submit door, so the
// gate in lib/gating.ts and the server's PiiReasonRequired cannot be met by surprise.
export function PiiReasons({
  hits,
  value,
  onChange,
  disabled,
}: {
  hits: Record<string, string>;
  value: Record<string, string>;
  onChange: (reasons: Record<string, string>) => void;
  disabled: boolean;
}) {
  const names = Object.keys(hits);
  if (names.length === 0) return null;

  return (
    <div className="mt-16">
      <div className="panel-title">Personal data needs a reason</div>
      <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
        {names.length === 1 ? "This property looks" : "These properties look"} like
        personal data. Say why the request needs each one. The approver reads your
        reason before approving.
      </p>
      {names.map((name) => (
        <label key={name} className="field mt-12">
          <span className="field-label">
            Why is {name} needed? (matched {hits[name]})
          </span>
          <textarea
            value={value[name] ?? ""}
            onChange={(e) => onChange({ ...value, [name]: e.target.value })}
            rows={2}
            disabled={disabled}
          />
        </label>
      ))}
    </div>
  );
}
