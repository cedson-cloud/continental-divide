"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import {
  AuditEntry,
  EventDefinition,
  RequestDetail,
  RuleCheck,
  friendlyError,
  getRequest,
  submitIntake,
  submitRawDefinition,
} from "@/lib/api";
import { NATURAL_LANGUAGE_EXAMPLES, RAW_EXAMPLES } from "@/lib/examples";
import { ProposedDefinition } from "@/components/AuditTimeline";
import { RuleChecks } from "@/components/RuleChecks";
import { StatusBadge } from "@/components/StatusBadge";

function findEntry(log: AuditEntry[], step: string): AuditEntry | undefined {
  return log.find((e) => e.step === step);
}

export default function IntakePage() {
  const [text, setText] = useState("");
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
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="e.g. track when a shopper empties their entire cart"
        />

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
        </div>

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
                }),
              )
            }
            disabled={submitting || text.trim().length === 0 || submitterTeam === ""}
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
                    onClick={() => run(() => submitRawDefinition(ex.definition))}
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

  return (
    <div className="panel">
      <div className="row spread">
        <div className="panel-title" style={{ margin: 0 }}>
          Outcome
        </div>
        <StatusBadge status={detail.status} />
      </div>

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

      <div className="mt-16">
        <Link href={`/requests/${detail.id}`}>
          View request #{detail.id} and audit log →
        </Link>
      </div>
    </div>
  );
}
