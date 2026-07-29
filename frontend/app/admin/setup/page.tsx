"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  GovernanceDraftAnswers,
  GovernanceDraftResult,
  draftGovernanceProfile,
  friendlyError,
} from "@/lib/api";

// Every control is a curated choice; the option values must match the Literal
// sets in backend/app/governance_draft.py. No free text, no user regex.
const BUSINESS_TYPES = ["ecommerce", "saas", "marketplace", "media", "fintech"];
const PLATFORMS = ["segment", "posthog", "amplitude", "mixpanel", "none"];
const SIDES = ["client", "server", "both"];
const CONVENTIONS = [
  {
    value: "title_case_object_action",
    label: "Title Case Object Action (Segment style) — “Cart Cleared”",
  },
  {
    value: "snake_case_object_action",
    label: "snake_case object_action (PostHog style) — “cart_cleared”",
  },
];
const DESTINATIONS = [
  "warehouse",
  "product_analytics",
  "crm",
  "engagement",
  "advertising",
];
const PII_ADDITIONS = [
  "device_id",
  "latitude",
  "longitude",
  "national_id",
  "passport_number",
  "drivers_license",
  "bank_account",
];

const CONVENTION_SLUGS: Record<string, string> = {
  title_case_object_action: "title-case",
  snake_case_object_action: "snake-case",
};

export default function GovernanceSetupPage() {
  const [answers, setAnswers] = useState<GovernanceDraftAnswers>({
    business_type: "ecommerce",
    current_platform: "segment",
    call_side: "both",
    naming_convention: "title_case_object_action",
    destinations: [],
    pii_additions: [],
  });
  const [result, setResult] = useState<GovernanceDraftResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    draftGovernanceProfile(answers)
      .then((r) => {
        if (!cancelled) {
          setResult(r);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(friendlyError(err));
      });
    return () => {
      cancelled = true;
    };
  }, [answers]);

  function set<K extends keyof GovernanceDraftAnswers>(
    key: K,
    value: GovernanceDraftAnswers[K],
  ) {
    setAnswers((prev) => ({ ...prev, [key]: value }));
    setCopied(false);
  }

  function toggle(key: "destinations" | "pii_additions", value: string) {
    set(
      key,
      answers[key].includes(value)
        ? answers[key].filter((v) => v !== value)
        : [...answers[key], value],
    );
  }

  const fileName = `${answers.business_type}-${
    CONVENTION_SLUGS[answers.naming_convention]
  }.yaml`;

  function download() {
    if (!result) return;
    const blob = new Blob([result.yaml], { type: "application/x-yaml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = fileName;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function copy() {
    if (!result) return;
    await navigator.clipboard.writeText(result.yaml);
    setCopied(true);
  }

  return (
    <main className="container">
      <h1 className="page-title">Governance setup</h1>
      <p className="page-subtitle">
        Answer a few questions and get a governance profile as YAML. Download
        only: nothing here writes to the repo or the server.
      </p>

      <div className="msg msg-info" style={{ marginBottom: 16 }}>
        This does not change what the app enforces. Commit the file to
        governance/templates/ and point active.yaml at it.
      </div>

      <div className="panel">
        <div className="panel-title">Your organization</div>
        <div className="fields">
          <label className="field">
            <span className="field-label">Business type</span>
            <select
              value={answers.business_type}
              onChange={(e) => set("business_type", e.target.value)}
            >
              {BUSINESS_TYPES.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field-label">Current platform</span>
            <select
              value={answers.current_platform}
              onChange={(e) => set("current_platform", e.target.value)}
            >
              {PLATFORMS.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field-label">Calls come from</span>
            <select
              value={answers.call_side}
              onChange={(e) => set("call_side", e.target.value)}
            >
              {SIDES.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </label>
        </div>

        <label className="field mt-12">
          <span className="field-label">Event naming convention</span>
          <select
            value={answers.naming_convention}
            onChange={(e) => set("naming_convention", e.target.value)}
          >
            {CONVENTIONS.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </label>

        <div className="mt-12">
          <span className="field-label">Allowed destinations</span>
          <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
            {DESTINATIONS.map((d) => (
              <label key={d} className="row" style={{ gap: 6, fontSize: 14 }}>
                <input
                  type="checkbox"
                  checked={answers.destinations.includes(d)}
                  onChange={() => toggle("destinations", d)}
                />
                <span>{d.replaceAll("_", " ")}</span>
              </label>
            ))}
          </div>
          <p className="muted" style={{ fontSize: 12.5, marginBottom: 0 }}>
            Leave all unchecked to allow any destination.
          </p>
        </div>

        <div className="mt-12">
          <span className="field-label">
            Also flag these as PII (the standard blocklist is always included)
          </span>
          <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
            {PII_ADDITIONS.map((p) => (
              <label key={p} className="row" style={{ gap: 6, fontSize: 14 }}>
                <input
                  type="checkbox"
                  checked={answers.pii_additions.includes(p)}
                  onChange={() => toggle("pii_additions", p)}
                />
                <span>{p.replaceAll("_", " ")}</span>
              </label>
            ))}
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="row spread">
          <div className="panel-title" style={{ margin: 0 }}>
            Profile preview — {fileName}
          </div>
          <div className="row" style={{ gap: 8 }}>
            <button className="btn" onClick={copy} disabled={!result}>
              {copied ? "Copied" : "Copy"}
            </button>
            <button
              className="btn btn-primary"
              onClick={download}
              disabled={!result || !result.valid}
            >
              Download
            </button>
          </div>
        </div>

        {error && <div className="msg msg-error mt-12">{error}</div>}
        {result && !result.valid && (
          <div className="msg msg-error mt-12">
            {result.errors.join("; ")}
          </div>
        )}
        {result && (
          <pre
            className="mono"
            style={{
              fontSize: 12.5,
              background: "var(--bg)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
              padding: 14,
              overflowX: "auto",
              marginBottom: 0,
            }}
          >
            {result.yaml}
          </pre>
        )}
      </div>

      <p className="muted" style={{ fontSize: 13 }}>
        <Link href="/admin">← Back to the active profile</Link>
      </p>
    </main>
  );
}
