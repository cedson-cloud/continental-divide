import { AuditEntry, EventDefinition, RuleCheck } from "@/lib/api";
import { definitionTitle, formatTimestamp, stepLabel } from "@/lib/format";

function dotTone(entry: AuditEntry): string {
  const detail = entry.detail || {};
  if (
    entry.step === "schema_rejected" ||
    entry.step === "rejection_recorded" ||
    entry.step === "model_error"
  )
    return "fail";
  if (entry.step === "published") return "pass";
  if (entry.step === "rules_evaluated") {
    const checks = (detail.checks as RuleCheck[]) || [];
    return checks.every((c) => c.passed) ? "pass" : "fail";
  }
  if (entry.step === "routed") {
    const decision = detail.decision as string;
    if (decision === "rejected") return "fail";
    if (decision === "flagged_duplicate") return "flag";
    return "info";
  }
  return "info";
}

type Actor = { email: string; verified: boolean };

function actorLine(entry: AuditEntry): string {
  const actor = entry.detail?.actor as Actor | undefined;
  return actor
    ? `by ${actor.email}${actor.verified ? "" : " · unverified"}`
    : "actor not recorded";
}

export function ProposedDefinition({
  definition,
}: {
  definition: Partial<EventDefinition>;
}) {
  const isTrack = (definition.call_type ?? "track") === "track";
  const fields = (isTrack ? definition.properties : definition.traits) ?? [];
  return (
    <div>
      <div className="row" style={{ gap: 8 }}>
        <span style={{ fontWeight: 600 }}>{definitionTitle(definition)}</span>
        {isTrack
          ? definition.category && <span className="tag">{definition.category}</span>
          : <span className="tag">{definition.call_type}</span>}
      </div>
      {fields.length > 0 && (
        <div className="row" style={{ gap: 6, marginTop: 6 }}>
          {fields.map((p) => (
            <span className="tag" key={p.name}>
              {p.name}: {p.type}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function DetailBody({ entry }: { entry: AuditEntry }) {
  const detail = entry.detail || {};

  if (entry.step === "model_interpreted" || entry.step === "definition_provided") {
    const proposed =
      (detail.proposed_definition as Partial<EventDefinition> | null) ??
      (detail.definition as Partial<EventDefinition> | null);
    return (
      <div>
        {detail.model ? (
          <div className="muted" style={{ fontSize: 13, marginBottom: 6 }}>
            via <span className="mono">{String(detail.model)}</span>
          </div>
        ) : null}
        {proposed ? (
          <ProposedDefinition definition={proposed} />
        ) : (
          <div className="muted">
            No valid definition. {String(detail.parse_error || "")}
          </div>
        )}
      </div>
    );
  }

  if (entry.step === "rules_evaluated") {
    const checks = (detail.checks as RuleCheck[]) || [];
    const flags = (detail.flags as string[]) || [];
    return (
      <div>
        <div>
          {checks.map((c) => (
            <span className="mini-check" key={c.rule}>
              <span className={`mini-dot ${c.passed ? "pass" : "fail"}`} />
              {c.rule}
            </span>
          ))}
        </div>
        {checks
          .filter((c) => !c.passed)
          .map((c) => (
            <div className="muted" key={`r-${c.rule}`} style={{ marginTop: 4 }}>
              {c.rule}: {c.detail}
            </div>
          ))}
        {flags.map((f, i) => (
          <div className="flags" key={i} style={{ marginTop: 8 }}>
            ⚑ {f}
          </div>
        ))}
      </div>
    );
  }

  const entries = Object.entries(detail).filter(
    ([key, v]) => key !== "actor" && v !== null && v !== "",
  );
  if (entries.length === 0) return null;
  return (
    <dl className="kv">
      {entries.map(([key, value]) => (
        <div key={key} style={{ display: "contents" }}>
          <dt>{key}</dt>
          <dd>{typeof value === "object" ? JSON.stringify(value) : String(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function AuditTimeline({ entries }: { entries: AuditEntry[] }) {
  return (
    <ol className="timeline">
      {entries.map((entry) => (
        <li className="timeline-item" key={entry.id}>
          <span className={`timeline-dot ${dotTone(entry)}`} />
          <div className="timeline-head">
            <span className="timeline-step">{stepLabel(entry.step)}</span>
            <span className="timeline-time">{formatTimestamp(entry.created_at)}</span>
          </div>
          <div className="timeline-actor">{actorLine(entry)}</div>
          <div className="timeline-body">
            <DetailBody entry={entry} />
          </div>
        </li>
      ))}
    </ol>
  );
}
