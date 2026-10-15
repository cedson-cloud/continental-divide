"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  AuditEntry,
  EventDefinition,
  RequestDetail,
  RuleCheck,
  SubmitResolution,
  disputeRule,
  friendlyError,
  getGovernanceProfile,
  getRequest,
  renameRequest,
  submitIntake,
  submitRawDefinition,
  submitRequest,
  withdrawRequest,
} from "@/lib/api";
import { NaturalLanguageExample, fillFromExample } from "@/lib/examples";
import {
  SIDE_HINT,
  SIDE_OPTIONS,
  missingFieldsSentence,
  missingIntakeFields,
} from "@/lib/intake";
import { ruleInSentence } from "@/lib/format";
import { ProposedDefinition } from "@/components/AuditTimeline";
import { AgentReview } from "@/components/AgentReview";
import { EventPicker } from "@/components/EventPicker";
import { DuplicateResolution } from "@/components/DuplicateResolution";
import { EngineDuplicates } from "@/components/EngineDuplicates";
import {
  gatingDuplicateFindings,
  missingPiiReasons,
  piiReasonsToSend,
  submissionNeedsAnswer,
} from "@/lib/gating";
import { PiiReasons } from "@/components/PiiReasons";
import { RejectedRecourse } from "@/components/RejectedRecourse";
import { RuleChecks } from "@/components/RuleChecks";
import { ScenarioCard } from "@/components/ScenarioCard";
import { StatusBadge } from "@/components/StatusBadge";

function findEntry(log: AuditEntry[], step: string): AuditEntry | undefined {
  return log.find((e) => e.step === step);
}

export default function IntakePage() {
  const [text, setText] = useState("");
  const [businessValue, setBusinessValue] = useState("");
  const [neededBy, setNeededBy] = useState("");
  const [requestKind, setRequestKind] = useState<
    "new_event" | "new_property_on_existing"
  >("new_event");
  const [existingEvent, setExistingEvent] = useState("");
  const [destinations, setDestinations] = useState<string[]>([]);
  const [allowedDestinations, setAllowedDestinations] = useState<string[]>([]);
  const [submitterName, setSubmitterName] = useState("");
  const [submitterTeam, setSubmitterTeam] = useState("");
  const [side, setSide] = useState("Unsure");
  const [urgent, setUrgent] = useState(false);
  const [urgencyReason, setUrgencyReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<RequestDetail | null>(null);
  const [scenarioStatus, setScenarioStatus] = useState<string | null>(null);
  const outcomeRef = useRef<HTMLDivElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  // Synchronous guard: two clicks in the same frame both render with
  // submitting=false, so the disabled prop alone cannot stop the second one.
  const inFlight = useRef(false);

  useEffect(() => {
    // Populates the destinations control; if the profile lists none (or the
    // call fails), the control stays hidden.
    getGovernanceProfile()
      .then((p) => setAllowedDestinations(p.destinations))
      .catch(() => setAllowedDestinations([]));
  }, []);

  // The result and any error render below a long form, and a scenario is started from
  // above it. Moving focus there brings it into view and tells a screen reader it arrived.
  useEffect(() => {
    if (outcome) outcomeRef.current?.focus();
  }, [outcome]);
  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  const missing = missingFieldsSentence(
    missingIntakeFields({
      submitterName,
      submitterTeam,
      text,
      businessValue,
      urgent,
      urgencyReason,
    }),
  );

  function toggleDestination(d: string) {
    setDestinations((prev) =>
      prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d],
    );
  }

  async function run(submit: () => Promise<{ id: number }>) {
    if (inFlight.current) return;
    inFlight.current = true;
    setError(null);
    setScenarioStatus(null);
    setOutcome(null);
    setSubmitting(true);
    try {
      const { id } = await submit();
      setOutcome(await getRequest(id));
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      inFlight.current = false;
      setSubmitting(false);
    }
  }

  function fillScenario(example: NaturalLanguageExample) {
    const next = fillFromExample({ text, businessValue }, example);
    setText(next.text);
    setBusinessValue(next.businessValue);
    const keptTyping =
      next.text !== example.text || next.businessValue !== example.businessValue;
    const missingWho = submitterName.trim().length === 0 || submitterTeam === "";
    setScenarioStatus(
      `Filled the form with “${example.label}”.` +
        (keptTyping ? " Fields you typed in were left alone." : "") +
        (missingWho
          ? " Add your name and team, then select Draft my request."
          : " Select Draft my request to send it."),
    );
  }

  return (
    <main className="container">
      <span className="role-hint page-role-hint">You&apos;re the requester</span>
      <h1 className="page-title">New event request</h1>
      <p className="page-subtitle">
        Describe the event you want to track in plain language. A model drafts a
        structured definition; the rules and a human approver decide what gets through.
      </p>

      <div className="msg msg-info" style={{ marginBottom: 16 }}>
        New to this? Read <Link href="/guide">how to use this</Link>, or{" "}
        <Link href="/request/new">use the guided request →</Link>
      </div>

      <ScenarioCard
        busy={submitting}
        status={scenarioStatus}
        onFill={fillScenario}
        onRun={(ex) =>
          run(() =>
            submitRawDefinition(ex.definition, undefined, {
              business_value:
                "Demo: exercises the deterministic rules with a pre-built definition",
            }),
          )
        }
      />

      <div className="panel">
        <div className="panel-title">Describe the event</div>
        <div className="fields">
          <label className="field">
            <span className="field-label">Your name *</span>
            <input
              type="text"
              placeholder="Your name"
              value={submitterName}
              onChange={(e) => setSubmitterName(e.target.value)}
              disabled={submitting}
            />
          </label>
          <label className="field">
            <span className="field-label">Team *</span>
            <select
              value={submitterTeam}
              onChange={(e) => setSubmitterTeam(e.target.value)}
              disabled={submitting}
            >
              <option value="">Select…</option>
              <option value="Product">Product</option>
              <option value="Marketing">Marketing</option>
              <option value="Data">Data</option>
              <option value="Engineering">Engineering</option>
            </select>
          </label>
          <label className="field">
            <span className="field-label">Where does it happen? *</span>
            <select
              value={side}
              onChange={(e) => setSide(e.target.value)}
              disabled={submitting}
              required
            >
              {SIDE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field-label">Date you need this by</span>
            <input
              type="date"
              value={neededBy}
              onChange={(e) => setNeededBy(e.target.value)}
              disabled={submitting}
            />
          </label>
          <label className="field">
            <span className="field-label">Request kind *</span>
            <select
              value={requestKind}
              onChange={(e) =>
                setRequestKind(
                  e.target.value as "new_event" | "new_property_on_existing",
                )
              }
              disabled={submitting}
              required
            >
              <option value="new_event">New event</option>
              <option value="new_property_on_existing">
                New property on an existing event
              </option>
            </select>
          </label>
        </div>
        <p className="muted" style={{ fontSize: 12.5, marginBottom: 0 }}>
          {SIDE_HINT}
        </p>

        <label className="field mt-12">
          <span className="field-label">What to track *</span>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="e.g. track when a shopper empties their entire cart"
          />
        </label>
        <label className="field mt-12">
          <span className="field-label">
            Business value * — why this event matters, not what it does
          </span>
          <textarea
            value={businessValue}
            onChange={(e) => setBusinessValue(e.target.value)}
            placeholder="e.g. tells merchandising which promotions actually drive checkout"
            rows={2}
            disabled={submitting}
          />
        </label>

        <label className="row mt-12" style={{ gap: 8, fontSize: 14 }}>
          <input
            type="checkbox"
            checked={urgent}
            onChange={(e) => setUrgent(e.target.checked)}
            disabled={submitting}
          />
          <span>Urgent</span>
        </label>
        {urgent && (
          <label className="field mt-12">
            <span className="field-label">Why is this urgent? *</span>
            <textarea
              value={urgencyReason}
              onChange={(e) => setUrgencyReason(e.target.value)}
              rows={2}
              disabled={submitting}
            />
          </label>
        )}

        {requestKind === "new_property_on_existing" && (
          <div className="mt-12">
            <label className="field">
              <span className="field-label">Existing event name</span>
              <EventPicker
                value={existingEvent}
                onChange={setExistingEvent}
                disabled={submitting}
              />
            </label>
            <p className="muted" style={{ fontSize: 12.5, marginBottom: 0 }}>
              Pick from the tracking plan, or type a name it doesn&apos;t have yet.
            </p>
          </div>
        )}

        {allowedDestinations.length > 0 && (
          <div className="mt-12">
            <span className="field-label">Destinations</span>
            <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
              {allowedDestinations.map((d) => (
                <label key={d} className="row" style={{ gap: 6, fontSize: 14 }}>
                  <input
                    type="checkbox"
                    checked={destinations.includes(d)}
                    onChange={() => toggleDestination(d)}
                    disabled={submitting}
                  />
                  {/* Display only: the submitted value keeps its underscores. */}
                  <span>{d.replaceAll("_", " ")}</span>
                </label>
              ))}
            </div>
          </div>
        )}

        <div className="row mt-12">
          <button
            className="btn btn-primary"
            aria-describedby={missing && !submitting ? "draft-missing" : undefined}
            onClick={() =>
              run(() =>
                submitIntake(text, {
                  submitter_name: submitterName,
                  submitter_team: submitterTeam,
                  call_type: "track",
                  side,
                  business_value: businessValue,
                  urgent,
                  urgency_reason: urgent ? urgencyReason : null,
                  needed_by: neededBy || null,
                  request_kind: requestKind,
                  existing_event:
                    requestKind === "new_property_on_existing" && existingEvent
                      ? existingEvent
                      : null,
                  destinations,
                }),
              )
            }
            disabled={submitting || missing !== null}
          >
            {submitting ? "Drafting…" : "Draft my request"}
          </button>
          {missing && !submitting && (
            <span id="draft-missing" className="missing-fields">
              {missing}
            </span>
          )}
        </div>

        {error && (
          <div ref={errorRef} tabIndex={-1} className="msg msg-error mt-16">
            {error}
          </div>
        )}
      </div>

      {outcome && (
        <div
          ref={outcomeRef}
          tabIndex={-1}
          className="outcome"
          role="region"
          aria-label="Result"
        >
          <Outcome detail={outcome} />
        </div>
      )}
    </main>
  );
}

function Outcome({ detail }: { detail: RequestDetail }) {
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [withdrawnTo, setWithdrawnTo] = useState<string | null>(null);
  const [renamed, setRenamed] = useState<{ id: number; name: string } | null>(null);
  const [disputedRule, setDisputedRule] = useState<string | null>(null);

  const log = detail.audit_log;
  const modelEntry = findEntry(log, "model_interpreted");
  const providedEntry = findEntry(log, "definition_provided");
  const rulesEntry = findEntry(log, "rules_evaluated");
  const schemaRejected = findEntry(log, "schema_rejected");

  const proposed = (modelEntry?.detail?.proposed_definition ??
    providedEntry?.detail?.definition ??
    null) as Partial<EventDefinition> | null;
  const source = modelEntry ? "Model proposed" : "Definition provided";
  const checks = (rulesEntry?.detail?.checks as RuleCheck[]) || [];
  const flags = (rulesEntry?.detail?.flags as string[]) || [];

  const isDraft = detail.status === "draft";
  const isRejected = detail.status === "rejected";
  const findings = detail.duplicate_candidates;
  const duplicateFindings = gatingDuplicateFindings(findings);
  const needsAnswer = submissionNeedsAnswer(findings, checks);
  const [piiReasons, setPiiReasons] = useState<Record<string, string>>({});
  const piiBlocked = missingPiiReasons(detail.pii_hits, piiReasons).length > 0;

  async function submit(resolution: SubmitResolution = {}) {
    setSubmitting(true);
    setSubmitError(null);
    try {
      await submitRequest(detail.id, {
        ...resolution,
        piiReasons: piiReasonsToSend(detail.pii_hits, piiReasons),
      });
      setSubmitted(true);
    } catch (err) {
      setSubmitError(friendlyError(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function withdraw(existingEvent: string) {
    setSubmitting(true);
    setSubmitError(null);
    try {
      await withdrawRequest(detail.id, existingEvent);
      setWithdrawnTo(existingEvent);
    } catch (err) {
      setSubmitError(friendlyError(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function rename(newName: string) {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await renameRequest(detail.id, newName);
      setRenamed({ id: res.id, name: newName });
    } catch (err) {
      setSubmitError(friendlyError(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function dispute(rule: string, note: string) {
    setSubmitting(true);
    setSubmitError(null);
    try {
      await disputeRule(detail.id, rule, note);
      setDisputedRule(rule);
    } catch (err) {
      setSubmitError(friendlyError(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (renamed) {
    return (
      <div className="panel">
        <div className="panel-title">Renamed and resubmitted</div>
        <p style={{ marginTop: 0 }}>
          Request #{renamed.id} carries your request under the name {renamed.name},
          which your team&apos;s convention accepts. Request #{detail.id} stays
          rejected, and the two are linked.
        </p>
        <div className="row">
          <Link href={`/requests/${renamed.id}`}>View request #{renamed.id} →</Link>
          <Link href={`/requests/${detail.id}`}>
            View the original #{detail.id} →
          </Link>
        </div>
      </div>
    );
  }

  if (disputedRule) {
    return (
      <div className="panel">
        <div className="panel-title">Sent to the data team</div>
        <p style={{ marginTop: 0 }}>
          Your disagreement with {ruleInSentence(disputedRule)} is recorded against request #
          {detail.id}, along with the version of the profile it applies to. Nothing
          changed: the request stays rejected and the rules stay as they are.
        </p>
        <div className="row">
          <Link href={`/requests/${detail.id}`}>View request #{detail.id} →</Link>
        </div>
      </div>
    );
  }

  if (withdrawnTo) {
    return (
      <div className="panel">
        <div className="panel-title">Request withdrawn</div>
        <p style={{ marginTop: 0 }}>
          Request #{detail.id} was withdrawn — {withdrawnTo} already covers it.
        </p>
        <div className="row">
          <Link href={`/requests/${detail.id}`}>View request #{detail.id} →</Link>
        </div>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="panel">
        <div className="panel-title">Request submitted</div>
        <p style={{ marginTop: 0 }}>
          Request #{detail.id} is now in the approval queue. In a real team someone
          else decides. Here, you do: open the queue and decide it as the approver.
        </p>
        <div className="row">
          <Link href="/queue">Open the queue →</Link>
          <Link href={`/requests/${detail.id}`}>View request #{detail.id} →</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="row spread">
        <div className="panel-title" style={{ margin: 0 }}>
          {isDraft ? "Review your request" : "Outcome"}
        </div>
        <StatusBadge status={detail.status} />
      </div>

      {isDraft && (
        <p className="muted" style={{ fontSize: 13, marginBottom: 0 }}>
          Nothing has been submitted yet. Check the draft below, then send it to the
          approval queue.
        </p>
      )}

      {proposed && (
        <div className="proposal mt-12">
          <div className="proposal-label">{source}</div>
          <ProposedDefinition definition={proposed} />
        </div>
      )}

      <div className="mt-16">
        {isRejected && checks.length > 0 ? (
          // Same component the wizard's step 4 and the detail page render, so a
          // rejection is never a dead end on one screen and a way forward on another.
          <RejectedRecourse
            checks={checks}
            flags={flags}
            suggestions={detail.name_suggestions}
            busy={submitting}
            onRename={rename}
            onDispute={dispute}
          />
        ) : checks.length > 0 ? (
          <RuleChecks checks={checks} flags={flags} />
        ) : schemaRejected ? (
          <div className="msg msg-error">
            The draft did not conform to the schema, so it was rejected before the rules
            ran.
          </div>
        ) : null}
      </div>

      <div className="mt-16">
        <EngineDuplicates checks={checks} flags={flags} />
      </div>

      {findings.length > 0 && (
        <div className="mt-16">
          <AgentReview findings={findings} variant="requester" />
        </div>
      )}

      {isDraft ? (
        <>
          <PiiReasons
            hits={detail.pii_hits}
            value={piiReasons}
            onChange={setPiiReasons}
            disabled={submitting}
          />
          {needsAnswer ? (
            <DuplicateResolution
              findings={duplicateFindings}
              busy={submitting}
              submitBlocked={piiBlocked}
              onWithdraw={withdraw}
              onSubmit={submit}
            />
          ) : (
            <div className="mt-16">
              <button
                className="btn btn-primary"
                onClick={() => submit()}
                disabled={submitting || piiBlocked}
              >
                {submitting ? "Submitting…" : "Submit request"}
              </button>
            </div>
          )}
          {submitError && <div className="msg msg-error mt-16">{submitError}</div>}
        </>
      ) : (
        <div className="mt-16">
          <Link href={`/requests/${detail.id}`}>
            View request #{detail.id} and audit log →
          </Link>
        </div>
      )}
    </div>
  );
}
