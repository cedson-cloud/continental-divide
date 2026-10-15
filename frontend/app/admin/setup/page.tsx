"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  GovernanceDraftAnswers,
  GovernanceDraftResult,
  draftGovernanceProfile,
  friendlyError,
} from "@/lib/api";
import {
  BUSINESS_TYPES,
  Choice,
  DESTINATIONS,
  NAMING_CONVENTIONS,
  PII_ADDITIONS,
  PLATFORMS,
  SIDES,
} from "@/lib/governance";

function Options({ choices }: { choices: Choice[] }) {
  return (
    <>
      {choices.map((c) => (
        <option key={c.value} value={c.value}>
          {c.label}
        </option>
      ))}
    </>
  );
}

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

      <div className="msg msg-info gov-setup-note">
        This does not change what the app enforces. Commit the file to
        governance/templates/ and point active.yaml at it.
      </div>

      <div className="panel">
        <h2 className="panel-title">Your organization</h2>
        <div className="fields">
          <label className="field">
            <span className="field-label">Business type</span>
            <select
              value={answers.business_type}
              onChange={(e) => set("business_type", e.target.value)}
            >
              <Options choices={BUSINESS_TYPES} />
            </select>
          </label>
          <label className="field">
            <span className="field-label">Current platform</span>
            <select
              value={answers.current_platform}
              onChange={(e) => set("current_platform", e.target.value)}
            >
              <Options choices={PLATFORMS} />
            </select>
          </label>
          <label className="field">
            <span className="field-label">Calls come from</span>
            <select
              value={answers.call_side}
              onChange={(e) => set("call_side", e.target.value)}
            >
              <Options choices={SIDES} />
            </select>
          </label>
        </div>

        <label className="field mt-12">
          <span className="field-label">Event naming convention</span>
          <select
            value={answers.naming_convention}
            onChange={(e) => set("naming_convention", e.target.value)}
          >
            <Options choices={NAMING_CONVENTIONS} />
          </select>
        </label>

        <fieldset className="gov-fieldset">
          <legend className="field-label">Allowed destinations</legend>
          <div className="gov-options">
            {DESTINATIONS.map((d) => (
              <label key={d.value} className="gov-option">
                <input
                  type="checkbox"
                  checked={answers.destinations.includes(d.value)}
                  onChange={() => toggle("destinations", d.value)}
                />
                <span>{d.label}</span>
              </label>
            ))}
          </div>
          <p className="gov-hint">Leave all unchecked to allow any destination.</p>
        </fieldset>

        <fieldset className="gov-fieldset">
          <legend className="field-label">
            Also flag these as personal data (the standard list is always included)
          </legend>
          <div className="gov-options">
            {PII_ADDITIONS.map((p) => (
              <label key={p} className="gov-option">
                <input
                  type="checkbox"
                  checked={answers.pii_additions.includes(p)}
                  onChange={() => toggle("pii_additions", p)}
                />
                <span className="mono">{p}</span>
              </label>
            ))}
          </div>
        </fieldset>
      </div>

      <div className="panel">
        <div className="row spread">
          <div>
            <h2 className="panel-title gov-preview-title">Profile preview</h2>
            <p className="gov-id">
              <span className="mono">{fileName}</span>
            </p>
          </div>
          <div className="row gov-preview-actions">
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

        <p className="visually-hidden" aria-live="polite">
          {copied ? "Profile copied to the clipboard" : ""}
        </p>
        {error && <div className="msg msg-error mt-12">{error}</div>}
        {result && !result.valid && (
          <div className="msg msg-error mt-12">
            {result.errors.join("; ")}
          </div>
        )}
        {result && <pre className="mono gov-yaml">{result.yaml}</pre>}
      </div>

      <p className="gov-footnote">
        <Link href="/admin">Back to the active profile</Link>
      </p>
    </main>
  );
}
