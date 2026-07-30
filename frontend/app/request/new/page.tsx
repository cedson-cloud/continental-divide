"use client";

import Link from "next/link";
import { useEffect, useReducer, useRef, useState } from "react";
import {
  RuleCheck,
  SubmitResolution,
  disputeRule,
  friendlyError,
  getGovernanceProfile,
  getRequest,
  renameRequest,
  submitIntake,
  submitRequest,
  withdrawRequest,
} from "@/lib/api";
import {
  DataKind,
  canAdvance,
  initialWizardState,
  toIntakePayload,
  wizardReducer,
} from "@/lib/wizard";
import { EventPicker } from "@/components/EventPicker";
import { RejectedRecourse } from "@/components/RejectedRecourse";
import { StepExists } from "@/components/wizard/StepExists";
import { StepReview } from "@/components/wizard/StepReview";

const STEP_TITLES = [
  "What kind of data?",
  "Who's asking",
  "Describe it",
  "Does this already exist?",
  "Your drafted request",
];

const KIND_CARDS: { kind: DataKind; title: string; hint: string }[] = [
  { kind: "revenue", title: "Money / revenue", hint: "someone bought, subscribed, refunded" },
  { kind: "user_action", title: "Something a user did", hint: "clicked, viewed, searched, shared" },
  { kind: "user_trait", title: "Something about a user", hint: "their plan, their company size" },
  {
    kind: "existing_event_detail",
    title: "Add detail to something we already track",
    hint: "a new property on an existing event",
  },
  { kind: "unknown", title: "I'm not sure", hint: "describe it and we'll figure it out" },
];

type Phase =
  | { name: "wizard" }
  | { name: "submitted" }
  | { name: "withdrawn"; existingEvent: string }
  | { name: "renamed"; newId: number; newName: string }
  | { name: "disputed"; rule: string };

export default function GuidedRequestPage() {
  const [state, dispatch] = useReducer(wizardReducer, initialWizardState);
  const [phase, setPhase] = useState<Phase>({ name: "wizard" });
  const [allowedDestinations, setAllowedDestinations] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  // Synchronous guard: two clicks in the same frame both render with
  // busy=false, so the disabled prop alone cannot stop the second one.
  const inFlight = useRef(false);

  useEffect(() => {
    getGovernanceProfile()
      .then((p) => setAllowedDestinations(p.destinations))
      .catch(() => setAllowedDestinations([]));
  }, []);

  async function draft() {
    if (inFlight.current || !canAdvance(state)) return;
    inFlight.current = true;
    dispatch({ type: "DRAFT_STARTED" });
    try {
      const { id } = await submitIntake(state.text, toIntakePayload(state));
      const detail = await getRequest(id);
      dispatch({ type: "DRAFT_SUCCEEDED", detail });
    } catch (err) {
      dispatch({ type: "DRAFT_FAILED", error: friendlyError(err) });
    } finally {
      inFlight.current = false;
    }
  }

  async function submit(resolution: SubmitResolution = {}) {
    if (inFlight.current || !state.detail) return;
    inFlight.current = true;
    setBusy(true);
    setActionError(null);
    try {
      await submitRequest(state.detail.id, resolution);
      setPhase({ name: "submitted" });
    } catch (err) {
      setActionError(friendlyError(err));
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  async function withdraw(existingEvent: string) {
    if (inFlight.current || !state.detail) return;
    inFlight.current = true;
    setBusy(true);
    setActionError(null);
    try {
      await withdrawRequest(state.detail.id, existingEvent);
      setPhase({ name: "withdrawn", existingEvent });
    } catch (err) {
      setActionError(friendlyError(err));
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  async function rename(newName: string) {
    if (inFlight.current || !state.detail) return;
    inFlight.current = true;
    setBusy(true);
    setActionError(null);
    try {
      const res = await renameRequest(state.detail.id, newName);
      setPhase({ name: "renamed", newId: res.id, newName });
    } catch (err) {
      setActionError(friendlyError(err));
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  async function dispute(rule: string, note: string) {
    if (inFlight.current || !state.detail) return;
    inFlight.current = true;
    setBusy(true);
    setActionError(null);
    try {
      await disputeRule(state.detail.id, rule, note);
      setPhase({ name: "disputed", rule });
    } catch (err) {
      setActionError(friendlyError(err));
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  function set(
    field:
      | "existingEvent"
      | "submitterName"
      | "submitterTeam"
      | "side"
      | "neededBy"
      | "text"
      | "businessValue"
      | "urgencyReason",
    value: string,
  ) {
    dispatch({ type: "SET_FIELD", field, value });
  }

  if (phase.name === "withdrawn" && state.detail) {
    return (
      <main className="container">
        <div className="panel">
          <div className="panel-title">Request withdrawn</div>
          <p style={{ marginTop: 0 }}>
            Request #{state.detail.id} was withdrawn — {phase.existingEvent}{" "}
            already covers it.
          </p>
          <div className="row">
            <Link href={`/requests/${state.detail.id}`}>
              View request #{state.detail.id} →
            </Link>
          </div>
        </div>
      </main>
    );
  }

  if (phase.name === "renamed" && state.detail) {
    return (
      <main className="container">
        <div className="panel">
          <div className="panel-title">Renamed and resubmitted</div>
          <p style={{ marginTop: 0 }}>
            Request #{phase.newId} carries your request under the name{" "}
            {phase.newName}, which your team&apos;s convention accepts. Request #
            {state.detail.id} stays rejected, and the two are linked.
          </p>
          <div className="row">
            <Link href={`/requests/${phase.newId}`}>
              View request #{phase.newId} →
            </Link>
            <Link href={`/requests/${state.detail.id}`}>
              View the original #{state.detail.id} →
            </Link>
          </div>
        </div>
      </main>
    );
  }

  if (phase.name === "disputed" && state.detail) {
    return (
      <main className="container">
        <div className="panel">
          <div className="panel-title">Sent to the data team</div>
          <p style={{ marginTop: 0 }}>
            Your disagreement with {phase.rule} is recorded against request #
            {state.detail.id}, along with the version of the profile it applies to.
            Nothing changed: the request stays rejected and the rules stay as they
            are. Changing a rule happens in the governance profile, by a human.
          </p>
          <div className="row">
            <Link href={`/requests/${state.detail.id}`}>
              View request #{state.detail.id} →
            </Link>
          </div>
        </div>
      </main>
    );
  }

  if (phase.name === "submitted" && state.detail) {
    return (
      <main className="container">
        <div className="panel">
          <div className="panel-title">Request submitted</div>
          <p style={{ marginTop: 0 }}>
            Request #{state.detail.id} is now in the approval queue.
          </p>
          <div className="row">
            <Link href="/queue">View the queue →</Link>
            <Link href={`/requests/${state.detail.id}`}>
              View request #{state.detail.id} →
            </Link>
          </div>
        </div>
      </main>
    );
  }

  const detail = state.detail;
  const rejected = detail != null && detail.status !== "draft";

  return (
    <main className="container">
      <h1 className="page-title">Guided request</h1>
      <p className="page-subtitle">
        Step {state.step} of 5 — {STEP_TITLES[state.step - 1]}
      </p>

      <div className="panel">
        {state.step === 1 && (
          <>
            <div className="panel-title">What kind of data do you need?</div>
            <div className="kind-cards">
              {KIND_CARDS.map((card) => (
                <button
                  key={card.kind}
                  className={`kind-card ${state.kind === card.kind ? "selected" : ""}`}
                  onClick={() => dispatch({ type: "SELECT_KIND", kind: card.kind })}
                >
                  <span className="kind-card-title">{card.title}</span>
                  <span className="kind-card-hint">{card.hint}</span>
                </button>
              ))}
            </div>
            {state.kind === "user_trait" && (
              <div className="msg msg-info mt-16">
                We only support track calls today, so this will be captured as an
                event request. Describe it and the approver will see the question.
              </div>
            )}
            {state.kind === "existing_event_detail" && (
              <label className="field mt-16">
                <span className="field-label">Which event are we adding to?</span>
                <EventPicker
                  value={state.existingEvent}
                  onChange={(value) => set("existingEvent", value)}
                />
              </label>
            )}
          </>
        )}

        {state.step === 2 && (
          <>
            <div className="panel-title">Who&apos;s asking, where, and when</div>
            <div className="fields">
              <label className="field">
                <span className="field-label">Submitted By *</span>
                <input
                  type="text"
                  placeholder="Your name"
                  value={state.submitterName}
                  onChange={(e) => set("submitterName", e.target.value)}
                />
              </label>
              <label className="field">
                <span className="field-label">Team *</span>
                <select
                  value={state.submitterTeam}
                  onChange={(e) => set("submitterTeam", e.target.value)}
                >
                  <option value="">Select…</option>
                  <option value="Product">Product</option>
                  <option value="Marketing">Marketing</option>
                  <option value="Data">Data</option>
                  <option value="Engineering">Engineering</option>
                </select>
              </label>
              <label className="field">
                <span className="field-label">Server Side or Client Side</span>
                <select
                  value={state.side}
                  onChange={(e) => set("side", e.target.value)}
                >
                  <option value="Unsure">I&apos;m not sure</option>
                  <option value="Client">Client</option>
                  <option value="Server">Server</option>
                </select>
              </label>
              <label className="field">
                <span className="field-label">Date you need this by</span>
                <input
                  type="date"
                  value={state.neededBy}
                  onChange={(e) => set("neededBy", e.target.value)}
                />
              </label>
            </div>
            <p className="muted" style={{ fontSize: 12.5, marginBottom: 0 }}>
              Browser = the user&apos;s device. Server = your backend. Not sure is
              fine — the approver decides.
            </p>
            {allowedDestinations.length > 0 && (
              <div className="mt-12">
                <span className="field-label">Destinations</span>
                <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
                  {allowedDestinations.map((d) => (
                    <label key={d} className="row" style={{ gap: 6, fontSize: 14 }}>
                      <input
                        type="checkbox"
                        checked={state.destinations.includes(d)}
                        onChange={() =>
                          dispatch({ type: "TOGGLE_DESTINATION", destination: d })
                        }
                      />
                      {/* Display only: the submitted value keeps its underscores. */}
                      <span>{d.replaceAll("_", " ")}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {state.step === 3 && (
          <>
            <div className="panel-title">Describe it</div>
            <label className="field">
              <span className="field-label">What to track *</span>
              <textarea
                value={state.text}
                onChange={(e) => set("text", e.target.value)}
                placeholder="e.g. track when a shopper empties their entire cart"
                disabled={state.drafting}
              />
            </label>
            <label className="field mt-12">
              <span className="field-label">
                Business value * — why this event matters, not what it does
              </span>
              <textarea
                value={state.businessValue}
                onChange={(e) => set("businessValue", e.target.value)}
                placeholder="e.g. tells merchandising which promotions actually drive checkout"
                rows={2}
                disabled={state.drafting}
              />
            </label>
            <label className="row mt-12" style={{ gap: 8, fontSize: 14 }}>
              <input
                type="checkbox"
                checked={state.urgent}
                onChange={(e) =>
                  dispatch({
                    type: "SET_FIELD",
                    field: "urgent",
                    value: e.target.checked,
                  })
                }
                disabled={state.drafting}
              />
              <span>Urgent</span>
            </label>
            {state.urgent && (
              <label className="field mt-12">
                <span className="field-label">Why is this urgent? *</span>
                <textarea
                  value={state.urgencyReason}
                  onChange={(e) => set("urgencyReason", e.target.value)}
                  rows={2}
                  disabled={state.drafting}
                />
              </label>
            )}
            {state.error && <div className="msg msg-error mt-16">{state.error}</div>}
          </>
        )}

        {state.step === 4 && detail && !rejected && (
          <>
            <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
              Before you look at the draft: here is what the catalog already has.
            </p>
            <StepExists
              findings={detail.duplicate_candidates}
              checks={
                ((detail.audit_log.find((e) => e.step === "rules_evaluated")
                  ?.detail?.checks as RuleCheck[]) || [])
              }
              flags={
                ((detail.audit_log.find((e) => e.step === "rules_evaluated")
                  ?.detail?.flags as string[]) || [])
              }
              busy={busy}
              onWithdraw={withdraw}
              onSubmit={submit}
              onNext={() => dispatch({ type: "NEXT" })}
            />
          </>
        )}

        {state.step === 4 && detail && rejected && (
          <>
            <RejectedRecourse
              checks={
                ((detail.audit_log.find((e) => e.step === "rules_evaluated")
                  ?.detail?.checks as RuleCheck[]) || [])
              }
              flags={
                ((detail.audit_log.find((e) => e.step === "rules_evaluated")
                  ?.detail?.flags as string[]) || [])
              }
              suggestions={detail.name_suggestions}
              busy={busy}
              onRename={rename}
              onDispute={dispute}
            />
            <div className="row mt-16">
              <Link href={`/requests/${detail.id}`}>
                View request #{detail.id} →
              </Link>
            </div>
          </>
        )}

        {state.step === 5 && detail && (
          <StepReview
            detail={detail}
            state={state}
            busy={busy}
            onSubmit={() => submit()}
          />
        )}

        {actionError && <div className="msg msg-error mt-16">{actionError}</div>}

        <div className="row mt-16 spread">
          <div>
            {state.step > 1 && (
              <button
                className="btn"
                onClick={() => dispatch({ type: "BACK" })}
                disabled={state.drafting || busy}
              >
                Back
              </button>
            )}
          </div>
          <div>
            {(state.step === 1 || state.step === 2) && (
              <button
                className="btn btn-primary"
                onClick={() => dispatch({ type: "NEXT" })}
                disabled={!canAdvance(state)}
              >
                Next
              </button>
            )}
            {state.step === 3 && (
              <button
                className="btn btn-primary"
                onClick={draft}
                disabled={!canAdvance(state) || state.drafting}
              >
                {state.drafting ? "Drafting…" : "Next"}
              </button>
            )}
          </div>
        </div>
      </div>

      <p className="muted" style={{ fontSize: 13 }}>
        Know exactly what you need?{" "}
        <Link href="/">Use the single-screen form →</Link>
      </p>
    </main>
  );
}
