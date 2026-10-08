const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export type RuleCheck = { rule: string; passed: boolean; detail: string };

export type EventProperty = {
  name: string;
  type: string;
  required: boolean;
  items: string | null;
};

export type EventDefinition = {
  name: string;
  category: string;
  description: string | null;
  properties: EventProperty[];
};

export type ReviewFinding = {
  // Absent on rows written before findings carried a kind; default it to
  // "duplicate_event" at the render site.
  kind?: "duplicate_event" | "property_extension" | "property_already_exists";
  existing_event: string;
  category: string;
  property_names: string[];
  reason: string;
  confidence: "high" | "medium" | "low";
  // Derived in the response layer from the catalog at read time; never stored.
  existing_event_description?: string | null;
  existing_event_properties?: string[];
};

export type IntakeResult = {
  id: number;
  status: string;
  routed_to_approval: boolean;
  checks: RuleCheck[];
  flags: string[];
  duplicate_candidates: ReviewFinding[];
};

export type QueueItem = {
  id: number;
  name: string | null;
  category: string | null;
  status: string;
  created_at: string;
};

export type AuditEntry = {
  id: number;
  request_id: number;
  step: string;
  detail: Record<string, unknown> | null;
  created_at: string;
};

export type ConfluenceDoc = {
  id: string;
  title: string;
  category: string;
  description: string;
  properties: { name: string; type: string; required: boolean }[];
};

export type JiraTicket = { key: string; summary: string; body: string };

export type PublishArtifact = {
  publisher: string;
  confluence_doc: ConfluenceDoc;
  jira_ticket: JiraTicket;
};

export type RequestDetail = {
  id: number;
  raw_intake_text: string;
  parsed_definition: EventDefinition | null;
  category: string | null;
  status: string;
  pii_flagged: boolean;
  pii_details: string | null;
  duplicate_candidates: ReviewFinding[];
  submitter_name: string | null;
  submitter_team: string | null;
  call_type: string | null;
  side: string | null;
  business_value: string | null;
  urgent: boolean;
  urgency_reason: string | null;
  needed_by: string | null;
  request_kind: string | null;
  existing_event: string | null;
  destinations: string[] | null;
  published_artifact: PublishArtifact | null;
  created_at: string;
  updated_at: string;
  audit_log: AuditEntry[];
  // Derived server-side at read time from the stored name and the active profile:
  // names the engine itself accepts. Empty when the request was not name-rejected,
  // or when no purely structural repair of the name passes.
  name_suggestions: string[];
  // Each property the PII rule flagged, mapped to the blocklist entry it matched, and
  // the requester's written reason for each (ADR 0003). Requests submitted before
  // reasons were required have hits and no reasons.
  pii_hits: Record<string, string>;
  pii_reasons: Record<string, string>;
};

export type Dispute = {
  request_id: number;
  event_name: string | null;
  request_status: string;
  rule: string;
  note: string;
  profile: string;
  profile_digest: string;
  created_at: string;
};

export type CatalogViewProperty = {
  name: string;
  type: string;
  // For array properties, the shared shape its items follow. The shape itself
  // is returned once under CatalogView.shapes, never inlined per event.
  shape: string | null;
  source: "sample_plan" | "approved_request" | "system_event";
  request_id: number | null;
  // Requests that asked for this property when the event already carried it.
  also_requested_by: number[];
};

export type CatalogViewEvent = {
  name: string;
  category: string;
  description: string;
  properties: CatalogViewProperty[];
  source: "sample_plan" | "approved_request" | "system_event";
  request_id: number | null;
  approved_at: string | null;
  // A property addition whose target event is nowhere in the catalog.
  unresolved_target: boolean;
  // For a system event: the name or call the SDK sends, and which SDK sends it.
  sent_as: string | null;
  sent_by: string | null;
};

export type SharedShape = {
  description: string;
  properties: { name: string; type: string }[];
};

export type CatalogView = {
  events: CatalogViewEvent[];
  shapes: Record<string, SharedShape>;
  counts: {
    total: number;
    from_sample_plan: number;
    new_events_from_requests: number;
    property_additions_merged: number;
    unresolved_targets: number;
    system_events: number;
  };
};

export type GovernanceExample = {
  name: string;
  passes: boolean;
  reason: string | null;
};

export type GovernanceProfileInfo = {
  name: string;
  source: string | null;
  event_naming: {
    convention: string;
    connectors: string[];
    particles: string[];
    irregular_past: string[];
  };
  property_naming: { convention: string };
  pii: { mode: string; blocklist: string[] };
  categories: { values: string[]; source: "profile" | "sample_plan" };
  destinations: string[];
  examples: GovernanceExample[];
};

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "cannot reach the API server");
  }
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail =
      data && typeof data.detail === "string" ? data.detail : res.statusText;
    throw new ApiError(res.status, detail);
  }
  return data as T;
}

export type IntakeMeta = {
  submitter_name?: string;
  submitter_team?: string;
  call_type?: string;
  side?: string;
  business_value?: string;
  urgent?: boolean;
  urgency_reason?: string | null;
  needed_by?: string | null;
  request_kind?: "new_event" | "new_property_on_existing";
  existing_event?: string | null;
  destinations?: string[];
};

export function submitIntake(
  raw_intake_text: string,
  meta: IntakeMeta = {},
): Promise<IntakeResult> {
  return request("/requests", {
    method: "POST",
    body: JSON.stringify({ raw_intake_text, ...meta }),
  });
}

export function submitRawDefinition(
  definition: unknown,
  raw_intake_text?: string,
  meta: IntakeMeta = {},
): Promise<IntakeResult> {
  return request("/requests/raw", {
    method: "POST",
    body: JSON.stringify({ definition, raw_intake_text, ...meta }),
  });
}

export function getGovernanceProfile(): Promise<GovernanceProfileInfo> {
  return request("/governance/profile");
}

export type GovernanceDraftAnswers = {
  business_type: string;
  current_platform: string;
  call_side: string;
  naming_convention: string;
  destinations: string[];
  pii_additions: string[];
};

export type GovernanceDraftResult = {
  yaml: string;
  valid: boolean;
  errors: string[];
};

export function draftGovernanceProfile(
  answers: GovernanceDraftAnswers,
): Promise<GovernanceDraftResult> {
  return request("/governance/draft", {
    method: "POST",
    body: JSON.stringify(answers),
  });
}

export function getCatalog(): Promise<CatalogView> {
  return request("/catalog");
}

export function listRequests(): Promise<QueueItem[]> {
  return request("/requests");
}

export function getRequest(id: number): Promise<RequestDetail> {
  return request(`/requests/${id}`);
}

export type SubmitResolution = {
  duplicateNote?: string;
  duplicateUnsure?: boolean;
  piiReasons?: Record<string, string>;
};

export function submitRequest(
  id: number,
  resolution: SubmitResolution = {},
): Promise<{ id: number; status: string }> {
  return request(`/requests/${id}/submit`, {
    method: "POST",
    body: JSON.stringify({
      duplicate_note: resolution.duplicateNote || null,
      duplicate_unsure: resolution.duplicateUnsure ?? false,
      pii_reasons: resolution.piiReasons ?? {},
    }),
  });
}

export function withdrawRequest(
  id: number,
  existingEvent: string,
  reason?: string,
): Promise<{ id: number; status: string }> {
  return request(`/requests/${id}/withdraw`, {
    method: "POST",
    body: JSON.stringify({ existing_event: existingEvent, reason: reason || null }),
  });
}

// The name must be one the server itself derived for this request — see
// RequestDetail.name_suggestions. A name from anywhere else comes back 422.
export function renameRequest(
  id: number,
  newName: string,
): Promise<{ id: number; status: string }> {
  return request(`/requests/${id}/rename`, {
    method: "POST",
    body: JSON.stringify({ new_name: newName }),
  });
}

// Records the disagreement and amends nothing — no profile change, no status change.
export function disputeRule(
  id: number,
  rule: string,
  note: string,
): Promise<{ id: number; status: string }> {
  return request(`/requests/${id}/dispute-rule`, {
    method: "POST",
    body: JSON.stringify({ rule, note }),
  });
}

export function listDisputes(): Promise<Dispute[]> {
  return request("/disputes");
}

export function convertRequest(
  id: number,
  existingEvent: string,
): Promise<{ id: number; status: string }> {
  return request(`/requests/${id}/convert`, {
    method: "POST",
    body: JSON.stringify({ existing_event: existingEvent }),
  });
}

export function decideRequest(
  id: number,
  decision: "approve" | "reject",
  opts: {
    note?: string;
    approver_name?: string;
    pii_acknowledged?: boolean;
    findings_acknowledged?: boolean;
  } = {},
): Promise<{ id: number; status: string; published_artifact: PublishArtifact | null }> {
  return request(`/requests/${id}/decision`, {
    method: "POST",
    body: JSON.stringify({
      decision,
      note: opts.note || null,
      approver_name: opts.approver_name || null,
      pii_acknowledged: opts.pii_acknowledged ?? false,
      findings_acknowledged: opts.findings_acknowledged ?? false,
    }),
  });
}

export function friendlyError(err: unknown): string {
  if (err instanceof ApiError) {
    switch (err.status) {
      case 0:
        return "Cannot reach the API server. Is the backend running?";
      case 404:
        return "Request not found.";
      case 409:
        return err.detail || "This request can no longer be decided.";
      case 422:
        return err.detail || "The request was not accepted.";
      case 429:
        return "Rate limit reached. Wait a moment and try again.";
      case 502:
        return "The model could not draft a definition. Try rephrasing, or check the server's API key.";
      default:
        return err.detail || "Something went wrong.";
    }
  }
  return "Something went wrong.";
}
