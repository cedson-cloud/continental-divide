"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Fragment, useCallback, useEffect, useState } from "react";
import {
  RequestDetail,
  ReviewFinding,
  RuleCheck,
  SubmitResolution,
  convertRequest,
  decideRequest,
  disputeRule,
  friendlyError,
  getRequest,
  renameRequest,
  submitRequest,
  withdrawRequest,
} from "@/lib/api";
import { isActionable } from "@/lib/format";
import { AuditTimeline } from "@/components/AuditTimeline";
import { DefinitionView } from "@/components/DefinitionView";
import { AgentReview } from "@/components/AgentReview";
import { DuplicateResolution } from "@/components/DuplicateResolution";
import { EngineDuplicates } from "@/components/EngineDuplicates";
import {
  gatingDuplicateFindings,
  missingPiiReasons,
  piiReasonsToSend,
  submissionNeedsAnswer,
} from "@/lib/gating";
import { PiiReasons } from "@/components/PiiReasons";
import { PublishCards } from "@/components/PublishCards";
import { RejectedRecourse } from "@/components/RejectedRecourse";
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
  const [piiReasons, setPiiReasons] = useState<Record<string, string>>({});
  const [findingsAcknowledged, setFindingsAcknowledged] = useState(false);
  const [deciding, setDeciding] = useState(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [convertingEvent, setConvertingEvent] = useState<string | null>(null);
  const [convertError, setConvertError] = useState<string | null>(null);
  const [recourseBusy, setRecourseBusy] = useState(false);
  const [recourseError, setRecourseError] = useState<string | null>(null);

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

  // Rename lands on the NEW request, the way convert already does — the replacement
  // is what the requester needs to look at, not the rejection they left behind.
  async function rename(newName: string) {
    setRecourseBusy(true);
    setRecourseError(null);
    try {
      const res = await renameRequest(id, newName);
      router.push(`/requests/${res.id}`);
    } catch (err) {
      setRecourseError(friendlyError(err));
      setRecourseBusy(false);
      load();
    }
  }

  async function dispute(rule: string, note: string) {
    setRecourseBusy(true);
    setRecourseError(null);
    try {
      await disputeRule(id, rule, note);
      load();
    } catch (err) {
      setRecourseError(friendlyError(err));
    } finally {
      setRecourseBusy(false);
    }
  }

  async function submitDraft(resolution: SubmitResolution = {}) {
    setSubmitting(true);
    setSubmitError(null);
    try {
      await submitRequest(id, {
        ...resolution,
        piiReasons: piiReasonsToSend(detail?.pii_hits ?? {}, piiReasons),
      });
      load();
    } catch (err) {
      setSubmitError(friendlyError(err));
      load();
    } finally {
      setSubmitting(false);
    }
  }

  async function withdraw(existingEvent: string) {
    setSubmitting(true);
    setSubmitError(null);
    try {
      await withdrawRequest(id, existingEvent);
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
  const duplicateFindings = gatingDuplicateFindings(findings);
  const isRejected = detail.status === "rejected";
  const disputes = detail.audit_log.filter((e) => e.step === "rule_disputed");
  const renameEntry = detail.audit_log.find(
    (e) => e.step === "renamed_and_resubmitted",
  );
  const isWithdrawn = detail.status === "withdrawn";
  const withdrawnEntry = detail.audit_log.find((e) => e.step === "withdrawn");
  const requesterUnsure =
    detail.audit_log.find((e) => e.step === "submitted")?.detail
      ?.duplicate_unsure === true;

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

      {(isSuperseded || (isRejected && supersededById !== null)) && (
        <div className="msg msg-info">
          This request was replaced by{" "}
          {supersededById !== null ? (
            <Link href={`/requests/${supersededById}`}>
              request #{supersededById}
            </Link>
          ) : (
            "a newer request"
          )}
          ,{" "}
          {isRejected
            ? "which asks for the same thing under a name the convention accepts."
            : "which asks for the same thing as a property on an existing event."}
        </div>
      )}

      {supersedesId !== null && (
        <div className="msg msg-info">
          This request replaces{" "}
          <Link href={`/requests/${supersedesId}`}>request #{supersedesId}</Link>
          {renameEntry ? (
            <>
              , renamed from{" "}
              {typeof renameEntry.detail?.original_name === "string"
                ? renameEntry.detail.original_name
                : "its rejected name"}{" "}
              by the requester after{" "}
              {typeof renameEntry.detail?.failed_rule === "string"
                ? renameEntry.detail.failed_rule
                : "a rule"}{" "}
              rejected it. The name was chosen from the set the engine derived, not
              drafted by the model.
            </>
          ) : (
            ", converted to a property on an existing event."
          )}
        </div>
      )}

      {isWithdrawn && (
        <div className="msg msg-info">
          This request was withdrawn — the requester agreed that{" "}
          {typeof withdrawnEntry?.detail?.existing_event === "string"
            ? withdrawnEntry.detail.existing_event
            : "an existing event"}{" "}
          already covers it.
        </div>
      )}

      <div className="panel">
        <div className="panel-title">Requester</div>
        <dl className="kv">
          <dt>Submitted By</dt>
          <dd>{detail.submitter_name || "—"}</dd>
          <dt>Team</dt>
          <dd>{detail.submitter_team || "—"}</dd>
          <dt>Date you need this by</dt>
          <dd>{detail.needed_by || "—"}</dd>
          <dt>Server/Client side</dt>
          <dd>
            {detail.side === "Unsure"
              ? "Open question — the requester wasn't sure whether this fires client or server side."
              : detail.side || "—"}
          </dd>
          {detail.urgent && (
            <>
              <dt>Urgency</dt>
              <dd>Urgent — {detail.urgency_reason || "no reason recorded"}</dd>
            </>
          )}
        </dl>
      </div>

      {detail.business_value && (
        <div className="panel">
          <div className="panel-title">Why this event</div>
          <p style={{ margin: 0 }}>{detail.business_value}</p>
          {(detail.request_kind === "new_property_on_existing" ||
            (detail.destinations?.length ?? 0) > 0) && (
            <p className="muted" style={{ fontSize: 13, marginBottom: 0 }}>
              {[
                detail.request_kind === "new_property_on_existing"
                  ? `New property on: ${detail.existing_event || "unspecified"}`
                  : null,
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
          {isRejected ? (
            // The same component the wizard and the single-screen form render: a
            // rejection offers the compliant name and the dispute door everywhere.
            <>
              <RejectedRecourse
                checks={evaluation.checks}
                flags={evaluation.flags}
                suggestions={detail.name_suggestions}
                busy={recourseBusy}
                onRename={rename}
                onDispute={dispute}
                error={recourseError}
              />
              {disputes.length > 0 && (
                <div className="msg msg-info mt-16">
                  {disputes.length === 1 ? "A dispute is" : `${disputes.length} disputes are`}{" "}
                  on record for this request and waiting for the data team. The rules
                  are unchanged.
                </div>
              )}
            </>
          ) : (
            <RuleChecks checks={evaluation.checks} flags={evaluation.flags} />
          )}
        </div>
      )}

      <EngineDuplicates checks={evaluation.checks} flags={evaluation.flags} />

      {findings.length > 0 && (
        <div className="panel">
          <AgentReview
            findings={findings}
            variant={isDraft ? "requester" : "approver"}
            onConvert={isDraft ? convert : undefined}
            convertingEvent={convertingEvent}
          />
          {!isDraft && requesterUnsure && (
            <div className="msg msg-info mt-16">
              The requester wasn&apos;t sure whether this duplicates the existing
              event and asked the approver to decide.
            </div>
          )}
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
          <PiiReasons
            hits={detail.pii_hits}
            value={piiReasons}
            onChange={setPiiReasons}
            disabled={submitting || convertingEvent !== null}
          />
          {submissionNeedsAnswer(findings, evaluation.checks) ? (
            <DuplicateResolution
              findings={duplicateFindings}
              busy={submitting || convertingEvent !== null}
              submitBlocked={missingPiiReasons(detail.pii_hits, piiReasons).length > 0}
              onWithdraw={withdraw}
              onSubmit={submitDraft}
            />
          ) : (
            <div className="row mt-12">
              <button
                className="btn btn-primary"
                onClick={() => submitDraft()}
                disabled={
                  submitting ||
                  convertingEvent !== null ||
                  missingPiiReasons(detail.pii_hits, piiReasons).length > 0
                }
              >
                {submitting ? "Submitting…" : "Submit request"}
              </button>
            </div>
          )}
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
          {detail.pii_flagged && Object.keys(detail.pii_hits).length > 0 && (
            <dl className="kv mt-12">
              {Object.entries(detail.pii_hits).map(([name, entry]) => (
                <Fragment key={name}>
                  <dt>
                    {name} ({entry})
                  </dt>
                  <dd>
                    {detail.pii_reasons[name] ||
                      "No reason recorded: submitted before reasons were required."}
                  </dd>
                </Fragment>
              ))}
            </dl>
          )}
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
