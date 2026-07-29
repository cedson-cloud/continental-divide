"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  AuditEntry,
  EventDefinition,
  RequestDetail,
  RuleCheck,
  friendlyError,
  getGovernanceProfile,
  getRequest,
  submitIntake,
  submitRawDefinition,
  submitRequest,
} from "@/lib/api";
import { NATURAL_LANGUAGE_EXAMPLES, RAW_EXAMPLES } from "@/lib/examples";
import { ProposedDefinition } from "@/components/AuditTimeline";
import { AgentReview } from "@/components/AgentReview";
import { RuleChecks } from "@/components/RuleChecks";
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
  const [callType, setCallType] = useState("track");
  const [side, setSide] = useState("Client");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<RequestDetail | null>(null);
  const [showRaw, setShowRaw] = useState(false);
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

  function toggleDestination(d: string) {
    setDestinations((prev) =>
      prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d],
    );
  }

  async function run(submit: () => Promise<{ id: number }>) {
    if (inFlight.current) return;
    inFlight.current = true;
    setError(null);
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

  return (
    <main className="container">
      <h1 className="page-title">New event request</h1>
      <p className="page-subtitle">
        Describe the event you want to track in plain language. A model drafts a
        structured definition; the rules and a human approver decide what gets through.
      </p>

      <div className="panel">
        <div className="panel-title">Describe the event</div>
        <label className="field">
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
        <label className="field mt-12">
          <span className="field-label">What to track</span>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="e.g. track when a shopper empties their entire cart"
          />
        </label>

        <div className="fields mt-12">
          <label className="field">
            <span className="field-label">Submitter</span>
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
            <span className="field-label">Call type</span>
            <select
              value={callType}
              onChange={(e) => setCallType(e.target.value)}
              disabled={submitting}
            >
              <option value="track">track</option>
            </select>
          </label>
          <label className="field">
            <span className="field-label">Side</span>
            <select
              value={side}
              onChange={(e) => setSide(e.target.value)}
              disabled={submitting}
            >
              <option value="Client">Client</option>
              <option value="Server">Server</option>
            </select>
          </label>
          <label className="field">
            <span className="field-label">Needed by</span>
            <input
              type="text"
              placeholder="Optional, e.g. mid-August launch"
              value={neededBy}
              onChange={(e) => setNeededBy(e.target.value)}
              disabled={submitting}
            />
          </label>
          <label className="field">
            <span className="field-label">Request kind</span>
            <select
              value={requestKind}
              onChange={(e) =>
                setRequestKind(
                  e.target.value as "new_event" | "new_property_on_existing",
                )
              }
              disabled={submitting}
            >
              <option value="new_event">New event</option>
              <option value="new_property_on_existing">
                New property on an existing event
              </option>
            </select>
          </label>
        </div>

        {requestKind === "new_property_on_existing" && (
          <div className="mt-12">
            <label className="field">
              <span className="field-label">Existing event name</span>
              <input
                type="text"
                placeholder="e.g. Order Completed"
                value={existingEvent}
                onChange={(e) => setExistingEvent(e.target.value)}
                disabled={submitting}
              />
            </label>
            <p className="muted" style={{ fontSize: 12.5, marginBottom: 0 }}>
              Free text for now — a picker arrives with the event catalog.
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
                  <span>{d}</span>
                </label>
              ))}
            </div>
          </div>
        )}

        <div className="row spread mt-12">
          <button
            className="btn btn-primary"
            onClick={() =>
              run(() =>
                submitIntake(text, {
                  submitter_name: submitterName,
                  submitter_team: submitterTeam,
                  call_type: callType,
                  side,
                  business_value: businessValue,
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
            disabled={
              submitting ||
              text.trim().length === 0 ||
              businessValue.trim().length === 0 ||
              submitterTeam === ""
            }
          >
            {submitting ? "Drafting…" : "Submit request"}
          </button>
          <div className="row">
            <span className="muted" style={{ fontSize: 12.5 }}>
              Try:
            </span>
            {NATURAL_LANGUAGE_EXAMPLES.map((ex) => (
              <button
                key={ex.key}
                className="btn btn-ghost"
                onClick={() => setText(ex.text)}
                disabled={submitting}
              >
                {ex.label}
              </button>
            ))}
          </div>
        </div>

        <div className="raw-affordance">
          <button className="link-button" onClick={() => setShowRaw((v) => !v)}>
            {showRaw ? "▾" : "▸"} Demo: load a raw definition (skips the model step)
          </button>
          {showRaw && (
            <div className="mt-12">
              <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
                Posts a pre-built definition straight to the rules. Used for violations a
                faithful model would not author from plain English.
              </p>
              <div className="row">
                {RAW_EXAMPLES.map((ex) => (
                  <button
                    key={ex.key}
                    className="btn btn-ghost"
                    onClick={() =>
                      run(() =>
                        submitRawDefinition(ex.definition, undefined, {
                          business_value:
                            "Demo: exercises the deterministic rules with a pre-built definition",
                        }),
                      )
                    }
                    disabled={submitting}
                  >
                    {ex.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {error && <div className="msg msg-error mt-16">{error}</div>}
      </div>

      {outcome && <Outcome detail={outcome} />}
    </main>
  );
}

function Outcome({ detail }: { detail: RequestDetail }) {
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

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
  const findings = detail.duplicate_candidates;
  const noteRequired = findings.some(
    (f) => (f.kind ?? "duplicate_event") === "duplicate_event",
  );

  async function submit() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      await submitRequest(detail.id, noteRequired ? note : undefined);
      setSubmitted(true);
    } catch (err) {
      setSubmitError(friendlyError(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <div className="panel">
        <div className="panel-title">Request submitted</div>
        <p style={{ marginTop: 0 }}>
          Request #{detail.id} is now in the approval queue.
        </p>
        <div className="row">
          <Link href="/queue">View the queue →</Link>
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
        {checks.length > 0 ? (
          <RuleChecks checks={checks} flags={flags} />
        ) : schemaRejected ? (
          <div className="msg msg-error">
            The draft did not conform to the schema, so it was rejected before the rules
            ran.
          </div>
        ) : null}
      </div>

      {findings.length > 0 && (
        <div className="mt-16">
          <AgentReview findings={findings} variant="requester" />
        </div>
      )}

      {isDraft ? (
        <>
          {noteRequired && (
            <label className="field mt-16">
              <span className="field-label">These are different because…</span>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={2}
                disabled={submitting}
              />
            </label>
          )}
          <div className="mt-16">
            <button
              className="btn btn-primary"
              onClick={submit}
              disabled={submitting || (noteRequired && note.trim().length === 0)}
            >
              {submitting ? "Submitting…" : "Submit request"}
            </button>
          </div>
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
