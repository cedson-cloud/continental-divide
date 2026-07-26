export type StatusMeta = { label: string; tone: string };

const STATUS_META: Record<string, StatusMeta> = {
  pending_approval: { label: "Pending approval", tone: "pending" },
  flagged_duplicate: { label: "Flagged duplicate", tone: "flagged" },
  approved: { label: "Approved", tone: "approved" },
  published: { label: "Published", tone: "published" },
  rejected: { label: "Rejected", tone: "rejected" },
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
  published: "Published",
  rejection_recorded: "Rejection recorded",
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
