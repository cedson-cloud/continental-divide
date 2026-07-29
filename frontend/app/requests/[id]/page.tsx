"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  RequestDetail,
  ReviewFinding,
  RuleCheck,
  convertRequest,
  decideRequest,
  friendlyError,
  getRequest,
  submitRequest,
} from "@/lib/api";
import { isActionable } from "@/lib/format";
import { AuditTimeline } from "@/components/AuditTimeline";
import { DefinitionView } from "@/components/DefinitionView";
import { AgentReview } from "@/components/AgentReview";
import { PublishCards } from "@/components/PublishCards";
import { RuleChecks } from "@/components/RuleChecks";
import { StatusBadge } from "@/components/StatusBadge";

function evaluationFrom(detail: RequestDetail): { checks: RuleCheck[]; flags: string[] } {
  const entry = detail.audit_log.find((e) => e.step === "rules_evaluated");
  const d = entry?.detail || {};
  return {
    checks: (d.checks as RuleCheck[]) || [],
    flags: (d.flags as string[]) || [],
  };
}

const KIND_PHRASES: Record<string, string> = {
  duplicate_event: "possible duplicates",
  property_extension: "possible property extensions",
  property_already_exists: "possibly existing properties",
};

function acknowledgeLabel(findings: ReviewFinding[]): string {
  const kinds = Array.from(
    new Set(findings.map((f) => f.kind ?? "duplicate_event")),
  );
  if (kinds.length === 1 && kinds[0] === "duplicate_event") {
    const names = Array.from(new Set(findings.map((f) => f.existing_event)));
    return `Possible duplicates reviewed — this event is not ${names.join(", ")}`;
  }
  return `Agent findings reviewed — ${kinds
    .map((k) => KIND_PHRASES[k] ?? k)
    .join(", ")}`;
}

function auditNumber(
  detail: RequestDetail,
  step: string,
  key: string,
): number | null {
  const value = detail.audit_log.find((e) => e.step === step)?.detail?.[key];
  return typeof value === "number" ? value : null;
}

export default function RequestDetailPage({ params }: { params: { id: string } }) {
  const id = Number(params.id);
  const router = useRouter();
  const [detail, setDetail] = useState<RequestDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [approverName, setApproverName] = useState("");
  const [piiAcknowledged, setPiiAcknowledged] = useState(false);
  const [findingsAcknowledged, setFindingsAcknowledged] = useState(false);
  const [deciding, setDeciding] = useState(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [duplicateNote, setDuplicateNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [convertingEvent, setConvertingEvent] = useState<string | null>(null);
  const [convertError, setConvertError] = useState<string | null>(null);

  const load = useCallback(() => {
    getRequest(id)
      .then((d) => {
        setDetail(d);
        setLoadError(null);
      })
      .catch((err) => setLoadError(friendlyError(err)));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function decide(decision: "approve" | "reject") {
    setDeciding(true);
    setDecisionError(null);
    try {
      await decideRequest(id, decision, {
        note,
        approver_name: approverName,
        pii_acknowledged: piiAcknowledged,
        findings_acknowledged: findingsAcknowledged,
      });
      setNote("");
      setPiiAcknowledged(false);
      setFindingsAcknowledged(false);
      load();
    } catch (err) {
      setDecisionError(friendlyError(err));
      load();
    } finally {
      setDeciding(false);
    }
  }

  async function convert(existingEvent: string) {
    setConvertingEvent(existingEvent);
    setConvertError(null);
    try {
      const res = await convertRequest(id, existingEvent);
      router.push(`/requests/${res.id}`);
    } catch (err) {
      setConvertError(friendlyError(err));
      setConvertingEvent(null);
      load();
    }
  }

  async function submitDraft() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      await submitRequest(id, noteRequired ? duplicateNote : undefined);
      setDuplicateNote("");
      load();
    } catch (err) {
      setSubmitError(friendlyError(err));
      load();
    } finally {
      setSubmitting(false);
    }
  }

  if (loadError) {
    return (
      <main className="container">
        <Link className="back-link" href="/queue">
          ← Back to queue
        </Link>
        <div className="msg msg-error">{loadError}</div>
      </main>
    );
  }

  if (!detail) {
    return (
      <main className="container">
        <div className="skeleton">Loading request…</div>
      </main>
    );
  }

  const evaluation = evaluationFrom(detail);
  const isDraft = detail.status === "draft";
  const isSuperseded = detail.status === "superseded";
  const supersededById = auditNumber(detail, "superseded_by", "new_request_id");
  const supersedesId = auditNumber(detail, "supersedes", "original_request_id");
  const findings = detail.duplicate_candidates;
  const noteRequired =
    isDraft &&
    findings.some((f) => (f.kind ?? "duplicate_event") === "duplicate_event");

  return (
    <main className="container">
      <Link className="back-link" href="/queue">
        ← Back to queue
      </Link>

      <div className="row spread">
        <h1 className="page-title" style={{ marginBottom: 0 }}>
          Request #{detail.id}
        </h1>
        <StatusBadge status={detail.status} />
      </div>
      <p className="page-subtitle" style={{ marginTop: 8 }}>
        {detail.raw_intake_text}
      </p>

      {isSuperseded && (
        <div className="msg msg-info">
          This request was replaced by{" "}
          {supersededById !== null ? (
            <Link href={`/requests/${supersededById}`}>
              request #{supersededById}
            </Link>
          ) : (
            "a newer request"
          )}
          , which asks for the same thing as a property on an existing event.
        </div>
      )}

      {supersedesId !== null && (
        <div className="msg msg-info">
          This request replaces{" "}
          <Link href={`/requests/${supersedesId}`}>request #{supersedesId}</Link>,
          converted to a property on an existing event.
        </div>
      )}

      {detail.business_value && (
        <div className="panel">
          <div className="panel-title">Why this event</div>
          <p style={{ margin: 0 }}>{detail.business_value}</p>
          {(detail.request_kind === "new_property_on_existing" ||
            detail.needed_by ||
            (detail.destinations?.length ?? 0) > 0) && (
            <p className="muted" style={{ fontSize: 13, marginBottom: 0 }}>
              {[
                detail.request_kind === "new_property_on_existing"
                  ? `New property on: ${detail.existing_event || "unspecified"}`
                  : null,
                detail.needed_by ? `Needed by: ${detail.needed_by}` : null,
                detail.destinations?.length
                  ? `Destinations: ${detail.destinations.join(", ")}`
                  : null,
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
          )}
        </div>
      )}

      {detail.parsed_definition && (
        <div className="panel">
          <div className="panel-title">Definition</div>
          <DefinitionView definition={detail.parsed_definition} />
        </div>
      )}

      {evaluation.checks.length > 0 && (
        <div className="panel">
          <div className="panel-title">Evaluation</div>
          <RuleChecks checks={evaluation.checks} flags={evaluation.flags} />
        </div>
      )}

      {findings.length > 0 && (
        <div className="panel">
          <AgentReview
            findings={findings}
            variant={isDraft ? "requester" : "approver"}
            onConvert={isDraft ? convert : undefined}
            convertingEvent={convertingEvent}
          />
          {convertingEvent !== null && (
            <div className="msg msg-info mt-16">
              Creating a new request on {convertingEvent} — the model is drafting
              and reviewing it, which takes a few seconds…
            </div>
          )}
          {convertError && <div className="msg msg-error mt-16">{convertError}</div>}
        </div>
      )}

      {isDraft && (
        <div className="panel">
          <div className="panel-title">Submit for approval</div>
          <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
            This draft has not been submitted. It enters the approval queue when you
            submit it.
          </p>
          {noteRequired && (
            <label className="field">
              <span className="field-label">These are different because…</span>
              <textarea
                value={duplicateNote}
                onChange={(e) => setDuplicateNote(e.target.value)}
                rows={2}
                disabled={submitting}
              />
            </label>
          )}
          <div className="row mt-12">
            <button
              className="btn btn-primary"
              onClick={submitDraft}
              disabled={
                submitting ||
                convertingEvent !== null ||
                (noteRequired && duplicateNote.trim().length === 0)
              }
            >
              {submitting ? "Submitting…" : "Submit request"}
            </button>
          </div>
          {submitError && <div className="msg msg-error mt-16">{submitError}</div>}
        </div>
      )}

      {!isDraft && isActionable(detail.status) && (
        <div className="panel">
          <div className="panel-title">Decision</div>
          <input
            type="text"
            placeholder="Approver name"
            value={approverName}
            onChange={(e) => setApproverName(e.target.value)}
            disabled={deciding}
          />
          <input
            type="text"
            className="mt-12"
            placeholder="Note (optional)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            disabled={deciding}
          />
          {detail.pii_flagged && (
            <label className="row mt-12" style={{ gap: 8, fontSize: 14 }}>
              <input
                type="checkbox"
                checked={piiAcknowledged}
                onChange={(e) => setPiiAcknowledged(e.target.checked)}
                disabled={deciding}
              />
              <span>
                PII acknowledged
                {detail.pii_details ? ` — ${detail.pii_details}` : ""}
              </span>
            </label>
          )}
          {findings.length > 0 && (
            <label className="row mt-12" style={{ gap: 8, fontSize: 14 }}>
              <input
                type="checkbox"
                checked={findingsAcknowledged}
                onChange={(e) => setFindingsAcknowledged(e.target.checked)}
                disabled={deciding}
              />
              <span>{acknowledgeLabel(findings)}</span>
            </label>
          )}
          <div className="row mt-12">
            <button
              className="btn btn-approve"
              onClick={() => decide("approve")}
              disabled={
                deciding ||
                (detail.pii_flagged && !piiAcknowledged) ||
                (findings.length > 0 && !findingsAcknowledged)
              }
            >
              {deciding ? "Working…" : "Approve & publish"}
            </button>
            <button
              className="btn btn-reject"
              onClick={() => decide("reject")}
              disabled={deciding}
            >
              Reject
            </button>
          </div>
          {decisionError && <div className="msg msg-error mt-16">{decisionError}</div>}
        </div>
      )}

      {!isDraft && detail.published_artifact && (
        <div className="panel">
          <div className="panel-title">
            Published · via {detail.published_artifact.publisher} publisher
          </div>
          <PublishCards artifact={detail.published_artifact} />
        </div>
      )}

      {!isDraft && (
        <div className="panel">
          <div className="panel-title">Audit log</div>
          <AuditTimeline entries={detail.audit_log} />
        </div>
      )}
    </main>
  );
}
