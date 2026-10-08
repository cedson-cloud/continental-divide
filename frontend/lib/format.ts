import type { CallType } from "./api";

export type StatusMeta = { label: string; tone: string };

// What a definition is called on screen. A track event is its name; the plan has one
// identify call, and one group call per group type (ADR 0003).
export function definitionTitle(definition: {
  call_type?: CallType;
  name?: string | null;
}): string {
  if (definition.call_type === "identify") return "Identify traits";
  if (definition.call_type === "group") return `Group: ${definition.name ?? "—"}`;
  return definition.name || "—";
}

const STATUS_META: Record<string, StatusMeta> = {
  draft: { label: "Draft — not submitted", tone: "neutral" },
  pending_approval: { label: "Pending approval", tone: "pending" },
  flagged_duplicate: { label: "Flagged duplicate", tone: "flagged" },
  approved: { label: "Approved", tone: "approved" },
  published: { label: "Published", tone: "published" },
  rejected: { label: "Rejected", tone: "rejected" },
  superseded: { label: "Superseded", tone: "neutral" },
  withdrawn: { label: "Withdrawn", tone: "neutral" },
};

export function statusMeta(status: string): StatusMeta {
  return STATUS_META[status] || { label: status, tone: "neutral" };
}

const STEP_LABELS: Record<string, string> = {
  intake_received: "Intake received",
  model_interpreted: "Model interpreted",
  definition_provided: "Definition provided",
  model_error: "Model error",
  schema_parsed: "Schema parsed",
  schema_rejected: "Schema rejected",
  rules_evaluated: "Rules evaluated",
  routed: "Routed",
  decision_received: "Decision received",
  pii_acknowledged: "PII acknowledged",
  findings_acknowledged: "Findings acknowledged",
  published: "Published",
  rejection_recorded: "Rejection recorded",
  superseded_by: "Superseded by replacement",
  supersedes: "Supersedes original",
  withdrawn: "Withdrawn",
  renamed_and_resubmitted: "Renamed and resubmitted",
  rule_disputed: "Rule disputed",
};

export function stepLabel(step: string): string {
  return STEP_LABELS[step] || step;
}

export function isActionable(status: string): boolean {
  return status === "pending_approval" || status === "flagged_duplicate";
}

export function formatTimestamp(value: string): string {
  const parsed = new Date(value.includes("T") ? value : value.replace(" ", "T") + "Z");
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
