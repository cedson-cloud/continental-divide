"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useCallback, useEffect, useState } from "react";
import {
  DecisionOptions,
  RequestDetail,
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
import { definitionTitle, isActionable, publishedHeading, ruleInSentence } from "@/lib/format";
import { sideLabel } from "@/lib/intake";
import { AuditTimeline } from "@/components/AuditTimeline";
import { DefinitionView } from "@/components/DefinitionView";
import { ForEngineers } from "@/components/ForEngineers";
import { AgentReview } from "@/components/AgentReview";
import { DecisionCard } from "@/components/DecisionCard";
import { DuplicateResolution } from "@/components/DuplicateResolution";
import { EngineDuplicates } from "@/components/EngineDuplicates";
import {
  gatingDuplicateFindings,
  hasEngineDuplicate,
  missingPiiReasons,
  piiReasonsToSend,
  submissionNeedsAnswer,
} from "@/lib/gating";
import { PiiReasons } from "@/components/PiiReasons";
import { PublishCards } from "@/components/PublishCards";
import { PublishedNote } from "@/components/PublishedNote";
import { RequestProgress } from "@/components/RequestProgress";
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

function auditNumber(
  detail: RequestDetail,
  step: string,
  key: string,
): number | null {
  const value = detail.audit_log.find((e) => e.step === step)?.detail?.[key];
  return typeof value === "number" ? value : null;
}

export default function RequestDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const id = Number(use(params).id);
  const router = useRouter();
  const [detail, setDetail] = useState<RequestDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [piiReasons, setPiiReasons] = useState<Record<string, string>>({});
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

  async function decide(
    decision: "approve" | "reject",
    body: DecisionOptions,
  ): Promise<boolean> {
    setDeciding(true);
    setDecisionError(null);
    try {
      await decideRequest(id, decision, body);
      load();
      return true;
    } catch (err) {
      setDecisionError(friendlyError(err));
      load();
      return false;
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
  const isDraftFailed = detail.status === "draft_failed";
  const withdrawnEntry = detail.audit_log.find((e) => e.step === "withdrawn");
  const requesterUnsure =
    detail.audit_log.find((e) => e.step === "submitted")?.detail
      ?.duplicate_unsure === true;
  // EngineDuplicates prints the flags under its own heading; the list under the
  // checks would repeat them in the same panel.
  const checkFlags = hasEngineDuplicate(evaluation.checks) ? [] : evaluation.flags;
  const canDecide = !isDraft && isActionable(detail.status);
  const hasRail = isDraft || canDecide;
  const published = detail.published_artifact
    ? publishedHeading(detail.published_artifact.publisher)
    : null;

  return (
    <main className={hasRail ? "container container-wide" : "container"}>
      <nav className="crumb" aria-label="Breadcrumb">
        <Link href="/queue">Queue</Link> / Request #{detail.id}
      </nav>

      <header className="detail-head">
        <div>
          <h1 className="page-title">
            {detail.parsed_definition
              ? definitionTitle(detail.parsed_definition)
              : `Request #${detail.id}`}
          </h1>
          <p className="detail-asked">
            <span className="detail-asker">
              {detail.submitter_name ? `${detail.submitter_name} asked:` : "Request:"}
            </span>{" "}
            “{detail.raw_intake_text}”
          </p>
        </div>
        <StatusBadge status={detail.status} />
      </header>

      <RequestProgress status={detail.status} auditLog={detail.audit_log} />

      {detail.status === "published" && (
        <PublishedNote hasSnippets={detail.snippets.length > 0} />
      )}

      {(isSuperseded || (isRejected && supersededById !== null)) && (
        <div className="msg msg-info detail-note">
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
        <div className="msg msg-info detail-note">
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
                ? ruleInSentence(renameEntry.detail.failed_rule)
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
        <div className="msg msg-info detail-note">
          This request was withdrawn — the requester agreed that{" "}
          {typeof withdrawnEntry?.detail?.existing_event === "string"
            ? withdrawnEntry.detail.existing_event
            : "an existing event"}{" "}
          already covers it.
        </div>
      )}

      {isDraftFailed && (
        <div className="msg msg-info detail-note">
          This request couldn&apos;t be drafted: the model didn&apos;t return a usable
          definition, or something failed on our side. It never reached the approval queue,
          and it is not a rejection. To try again, make a new request.
        </div>
      )}

      <div className={hasRail ? "detail-grid" : "detail-grid no-rail"}>
        <div className="detail-main">
          {detail.parsed_definition && (
            <section className="panel">
              <h2 className="panel-title">Definition</h2>
              <DefinitionView definition={detail.parsed_definition} />
            </section>
          )}

          <ForEngineers snippets={detail.snippets} side={detail.side} />

          {evaluation.checks.length > 0 && (
            <section className="panel">
              <h2 className="panel-title">Rule checks</h2>
              <p className="panel-sub">
                Fixed rules, checked the same way every time. No model involved.
              </p>
              {isRejected ? (
                // The same component the wizard and the single-screen form render: a
                // rejection offers the compliant name and the dispute door everywhere.
                <>
                  <RejectedRecourse
                    checks={evaluation.checks}
                    flags={checkFlags}
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
                <RuleChecks checks={evaluation.checks} flags={checkFlags} />
              )}
              <EngineDuplicates checks={evaluation.checks} flags={evaluation.flags} />
            </section>
          )}

          {findings.length > 0 && (
            <section className="panel panel-agent">
              <h2 className="panel-title">Duplicate review</h2>
              <p className="panel-sub">
                The model&apos;s reading of what this event means. It can flag a possible
                duplicate but never reject a request.
              </p>
              <AgentReview
                bare
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
            </section>
          )}

          <section className="panel">
            <h2 className="panel-title">Request</h2>
            <dl className="facts">
              <dt>Requested by</dt>
              <dd>
                {[detail.submitter_name, detail.submitter_team]
                  .filter(Boolean)
                  .join(", ") || "—"}
              </dd>
              <dt>Needed by</dt>
              <dd>{detail.needed_by || "—"}</dd>
              <dt>Where it happens</dt>
              <dd>
                {detail.side === "Unsure"
                  ? "Open question — the requester wasn't sure whether this happens " +
                    "in the browser or app, or on your servers."
                  : sideLabel(detail.side)}
              </dd>
              {detail.urgent && (
                <>
                  <dt>Urgency</dt>
                  <dd>Urgent — {detail.urgency_reason || "no reason recorded"}</dd>
                </>
              )}
              {detail.request_kind === "new_property_on_existing" && (
                <>
                  <dt>New property on</dt>
                  <dd>{detail.existing_event || "unspecified"}</dd>
                </>
              )}
              {(detail.destinations?.length ?? 0) > 0 && (
                <>
                  <dt>Destinations</dt>
                  <dd>{detail.destinations?.join(", ")}</dd>
                </>
              )}
            </dl>
            {detail.business_value && (
              <p className="facts-why">
                <span className="facts-why-label">Why it matters.</span>{" "}
                {detail.business_value}
              </p>
            )}
          </section>

          {!isDraft && detail.published_artifact && published && (
            <section className="panel">
              <h2 className="panel-title">{published.title}</h2>
              {published.note && <p className="panel-sub">{published.note}</p>}
              <PublishCards artifact={detail.published_artifact} />
            </section>
          )}
        </div>

        {hasRail && (
          <aside className="detail-rail" aria-label={isDraft ? "Submit" : "Decision"}>
            {isDraft ? (
              <section className="rail-card" aria-labelledby="submit-title">
                <span className="role-hint">You&apos;re the requester</span>
                <h2 id="submit-title" className="rail-title">
                  Submit for approval
                </h2>
                <p className="rail-lede">
                  This draft has not been submitted. It enters the approval queue when
                  you submit it.
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
              </section>
            ) : (
              <DecisionCard
                detail={detail}
                checks={evaluation.checks}
                deciding={deciding}
                error={decisionError}
                onDecide={decide}
              />
            )}
          </aside>
        )}

        {!isDraft && (
          <section className="panel detail-trail">
            <h2 className="panel-title">Audit trail</h2>
            <p className="panel-sub">Every step is recorded and cannot be edited.</p>
            <AuditTimeline entries={detail.audit_log} />
          </section>
        )}
      </div>
    </main>
  );
}
