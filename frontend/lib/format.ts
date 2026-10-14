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
  intake_received: "Request received",
  model_interpreted: "Model drafted the definition",
  definition_provided: "Definition supplied directly",
  model_error: "Model call failed",
  schema_parsed: "Definition read",
  schema_rejected: "Definition could not be read",
  rules_evaluated: "Rules checked",
  duplicate_review: "Model reviewed for duplicates",
  duplicate_review_failed: "Duplicate review failed",
  routed: "Routed",
  submitted: "Submitted for approval",
  notion_pushed: "Added to the Notion approval board",
  notion_push_failed: "Could not add to the Notion approval board",
  decision_received: "Decision recorded",
  pii_acknowledged: "Personal data acknowledged",
  findings_acknowledged: "Duplicates acknowledged",
  published: "Published",
  publish_failed: "Publishing failed",
  rejection_recorded: "Rejection recorded",
  superseded_by: "Replaced by a new request",
  supersedes: "Replaces an earlier request",
  withdrawn: "Withdrawn",
  renamed_and_resubmitted: "Renamed and resubmitted",
  rule_disputed: "Rule disputed",
};

export function stepLabel(step: string): string {
  return STEP_LABELS[step] || step;
}

// Rule names as the engine writes them (backend/app/rules.py), said the way a
// requester would.
const RULE_LABELS: Record<string, string> = {
  event_naming: "Event name",
  property_naming: "Property names",
  trait_naming: "Trait names",
  group_naming: "Group name",
  category: "Category",
  pii: "Personal data",
  duplicate: "Exact duplicate",
  near_duplicate: "Near duplicate",
};

export function ruleLabel(rule: string): string {
  return RULE_LABELS[rule] || rule;
}

const AUDIT_KEY_LABELS: Record<string, string> = {
  raw_intake_text: "Request text",
  submitter_name: "Requested by",
  submitter_team: "Team",
  call_type: "Call type",
  side: "Fires on",
  business_value: "Why it matters",
  urgent: "Urgent",
  urgency_reason: "Why it is urgent",
  needed_by: "Needed by",
  request_kind: "Request type",
  existing_event: "Existing event",
  destinations: "Destinations",
  pii_reasons: "Personal data reasons",
  pii_details: "Personal data found",
  decision: "Decision",
  routed_to_approval: "Sent for approval",
  flags: "Flags",
  name: "Event name",
  category: "Category",
  properties: "Properties",
  traits: "Traits",
  profile: "Governance profile",
  profile_digest: "Profile version",
  model: "Model",
  findings: "Findings",
  parse_error: "Parse error",
  raw_response: "Raw model response",
  error: "Error",
  errors: "Errors",
  reason: "Reason",
  duplicate_note: "Why the existing event will not work",
  duplicate_unsure: "Asked the approver to decide",
  new_request_id: "New request",
  original_request_id: "Original request",
  original_name: "Original name",
  new_name: "New name",
  failed_rule: "Rule that failed",
  rule: "Rule",
  approver: "Approver",
  note: "Note",
  message: "Summary",
  candidates: "Existing events reviewed",
  publisher: "Publisher",
  confluence_doc_id: "Confluence doc",
  jira_ticket_key: "Jira ticket",
  url: "Link",
};

export function auditKeyLabel(key: string): string {
  if (AUDIT_KEY_LABELS[key]) return AUDIT_KEY_LABELS[key];
  const words = key.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
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
