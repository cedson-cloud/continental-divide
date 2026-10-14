import { AuditEntry, EventDefinition, ReviewFinding, RuleCheck } from "@/lib/api";
import {
  auditKeyLabel,
  definitionTitle,
  formatTimestamp,
  ruleLabel,
  statusMeta,
  stepLabel,
} from "@/lib/format";

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

// Keys whose values are event or property names, the only audit values set in code.
const NAME_KEYS = new Set([
  "name",
  "existing_event",
  "original_name",
  "new_name",
  "properties",
  "traits",
  "candidates",
]);

const DECISION_LABELS: Record<string, string> = { approve: "Approve", reject: "Reject" };

function auditValue(key: string, value: unknown): string {
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (key === "rule" || key === "failed_rule") return ruleLabel(String(value));
  if (key === "decision") {
    return DECISION_LABELS[String(value)] ?? statusMeta(String(value)).label;
  }
  if (Array.isArray(value) && value.every((v) => typeof v === "string")) {
    return value.join(", ");
  }
  if (key === "findings" && Array.isArray(value)) {
    return (value as ReviewFinding[])
      .map(
        (f) => `${f.existing_event} (${f.confidence ?? "high"} confidence): ${f.reason}`,
      )
      .join("; ");
  }
  if (
    value &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    Object.values(value).every((v) => typeof v === "string")
  ) {
    return Object.entries(value as Record<string, string>)
      .map(([k, v]) => `${k}: ${v}`)
      .join("; ");
  }
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

type Actor = { email: string; verified: boolean };

function actorLine(entry: AuditEntry): string {
  const actor = entry.detail?.actor as Actor | undefined;
  if (!actor) return "actor not recorded";
  const self = entry.detail?.self_approval === true ? " · self-approval" : "";
  return `by ${actor.email}${actor.verified ? "" : " · unverified"}${self}`;
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
          ? definition.category && (
              <span className="tag tag-text">{definition.category}</span>
            )
          : <span className="tag tag-text">{definition.call_type}</span>}
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
              {ruleLabel(c.rule)}
            </span>
          ))}
        </div>
        {checks
          .filter((c) => !c.passed)
          .map((c) => (
            <div className="muted" key={`r-${c.rule}`} style={{ marginTop: 4 }}>
              {ruleLabel(c.rule)}: {c.detail}
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
    ([key, v]) =>
      key !== "actor" &&
      key !== "self_approval" &&
      v !== null &&
      v !== "" &&
      !(Array.isArray(v) && v.length === 0),
  );
  if (entries.length === 0) return null;
  return (
    <dl className="kv">
      {entries.map(([key, value]) => (
        <div key={key} style={{ display: "contents" }}>
          <dt>{auditKeyLabel(key)}</dt>
          <dd className={NAME_KEYS.has(key) ? "mono" : undefined}>
            {auditValue(key, value)}
          </dd>
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
