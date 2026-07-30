"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Dispute,
  GovernanceProfileInfo,
  friendlyError,
  getGovernanceProfile,
  listDisputes,
} from "@/lib/api";

export default function AdminPage() {
  const [profile, setProfile] = useState<GovernanceProfileInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [disputes, setDisputes] = useState<Dispute[]>([]);

  useEffect(() => {
    getGovernanceProfile()
      .then(setProfile)
      .catch((err) => setError(friendlyError(err)));
    // A failure here must not take down the profile view beside it.
    listDisputes()
      .then(setDisputes)
      .catch(() => setDisputes([]));
  }, []);

  return (
    <main className="container">
      <h1 className="page-title">Governance</h1>
      <p className="page-subtitle">
        The rules the active profile enforces on every incoming request. Read-only:
        this page shows what the engine is checking right now.{" "}
        <Link href="/admin/setup">Draft a new profile →</Link>
      </p>

      {error && <div className="msg msg-error">{error}</div>}

      {!profile && !error && <div className="skeleton">Loading profile…</div>}

      {profile && (
        <>
          <div className="panel">
            <div className="panel-title">Active profile</div>
            <p style={{ fontSize: 15, fontWeight: 600 }}>{profile.name}</p>
            {profile.source && (
              <p className="muted" style={{ fontSize: 13.5, marginTop: 4 }}>
                Convention source:{" "}
                <a href={profile.source} target="_blank" rel="noreferrer">
                  {profile.source}
                </a>
              </p>
            )}
          </div>

          <div className="panel">
            <div className="panel-title">Event naming</div>
            <p style={{ fontSize: 14 }}>
              Convention: <span className="mono">{profile.event_naming.convention}</span>
            </p>
            <p className="muted" style={{ fontSize: 13, margin: "8px 0 10px" }}>
              Illustrative names, checked against the active rule when this page
              loaded. These are not events in any plan — they exist to show what the
              convention accepts and rejects.
            </p>
            <div className="checks">
              {profile.examples.map((example) => (
                <div className="check" key={example.name}>
                  <span className={`check-mark ${example.passes ? "pass" : "fail"}`}>
                    {example.passes ? "✓" : "✕"}
                  </span>
                  <span>
                    <span className="check-rule mono">{example.name}</span>
                    {example.reason && (
                      <span className="check-detail"> — {example.reason}</span>
                    )}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="panel">
            <div className="panel-title">Property naming and PII</div>
            <p style={{ fontSize: 14 }}>
              Property names must be{" "}
              <span className="mono">{profile.property_naming.convention}</span>.
            </p>
            <p style={{ fontSize: 14, margin: "10px 0 8px" }}>
              PII mode: <span className="mono">{profile.pii.mode}</span>. A flagged
              property does not block the request — it routes to approval, where a
              human must acknowledge the PII before approving.
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {profile.pii.blocklist.map((entry) => (
                <span className="tag" key={entry}>
                  {entry}
                </span>
              ))}
            </div>
          </div>

          <div className="panel">
            <div className="panel-title">Categories</div>
            {profile.categories.source === "sample_plan" && (
              <p className="muted" style={{ fontSize: 13.5, marginBottom: 10 }}>
                This profile declares no categories, so intake falls back to the
                sample tracking plan.
              </p>
            )}
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {profile.categories.values.map((category) => (
                <span className="tag" key={category}>
                  {category}
                </span>
              ))}
            </div>
          </div>

          <div className="panel">
            <div className="panel-title">Destinations</div>
            {profile.destinations.length === 0 ? (
              <p className="muted" style={{ fontSize: 13.5 }}>
                The profile lists no destinations, so requests may name any
                destination.
              </p>
            ) : (
              <>
                <p className="muted" style={{ fontSize: 13.5, marginBottom: 10 }}>
                  Requests may only send event data to these destinations. An empty
                  list would mean unconstrained.
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {profile.destinations.map((destination) => (
                    <span className="tag" key={destination}>
                      {destination}
                    </span>
                  ))}
                </div>
              </>
            )}
          </div>

          <div className="panel">
            <div className="panel-title">Rule disputes</div>
            <p className="muted" style={{ fontSize: 13.5, marginTop: 0 }}>
              Requesters who think a rule is wrong for this team. Read-only, and
              deliberately not a workflow: nothing here amends a rule. Changing a
              convention happens in the governance profile, by a human, in a
              versioned file.
            </p>
            {disputes.length === 0 ? (
              <p className="muted" style={{ fontSize: 13.5, marginBottom: 0 }}>
                No disputes on record.
              </p>
            ) : (
              <div className="checks">
                {disputes.map((dispute) => (
                  <div
                    className="check"
                    key={`${dispute.request_id}-${dispute.created_at}`}
                  >
                    <span className="check-mark advisory" aria-label="advisory">
                      ⚑
                    </span>
                    <span>
                      <span className="check-rule mono">{dispute.rule}</span>
                      <span className="check-detail">
                        {" "}
                        — {dispute.note}
                      </span>
                      <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>
                        <Link href={`/requests/${dispute.request_id}`}>
                          request #{dispute.request_id}
                        </Link>
                        {dispute.event_name ? ` · ${dispute.event_name}` : ""} ·{" "}
                        {dispute.request_status} · profile {dispute.profile}{" "}
                        <span className="mono">{dispute.profile_digest}</span>
                      </div>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <p className="muted" style={{ fontSize: 13.5 }}>
            Governance is versioned in the repo and reviewed through git. Edit the
            active profile and reload this page — no restart needed.
          </p>
        </>
      )}
    </main>
  );
}
