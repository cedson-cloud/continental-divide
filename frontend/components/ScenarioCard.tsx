"use client";

import {
  NATURAL_LANGUAGE_EXAMPLES,
  NaturalLanguageExample,
  RAW_EXAMPLES,
  RawExample,
} from "@/lib/examples";
import { Icon, IconName } from "@/components/icons";

// The demo's front door. The two kinds of scenario do different things when clicked:
// one fills the form for the visitor to send through the model, the other posts a
// pre-built definition straight to the rules. Each tile says which, so neither click
// surprises anyone.
export function ScenarioCard({
  busy,
  status,
  onFill,
  onRun,
}: {
  busy: boolean;
  status: string | null;
  onFill: (example: NaturalLanguageExample) => void;
  onRun: (example: RawExample) => void;
}) {
  return (
    <section className="panel" aria-labelledby="scenario-title">
      <h2 id="scenario-title" className="panel-title">
        Try a scenario
      </h2>
      <p className="panel-sub">
        Each one shows a different part of the review. Pick one to see what the rules
        and the approver do with it.
      </p>
      <div className="scenarios">
        {NATURAL_LANGUAGE_EXAMPLES.map((ex) => (
          <ScenarioTile
            key={ex.key}
            example={ex}
            icon="pencil"
            action="Fills in the form"
            busy={busy}
            onClick={() => onFill(ex)}
          />
        ))}
        {RAW_EXAMPLES.map((ex) => (
          <ScenarioTile
            key={ex.key}
            example={ex}
            icon="play"
            action="Skips the model and your review"
            busy={busy}
            onClick={() => onRun(ex)}
          />
        ))}
      </div>
      <p className="scenario-status" role="status">
        {status}
      </p>
    </section>
  );
}

// The title is the button's name; the summary and what the click does are read after it
// as its description, rather than as one long name.
function ScenarioTile({
  example,
  icon,
  action,
  busy,
  onClick,
}: {
  example: { key: string; label: string; summary: string };
  icon: IconName;
  action: string;
  busy: boolean;
  onClick: () => void;
}) {
  const id = `scenario-${example.key}`;
  return (
    <button
      className="scenario"
      onClick={onClick}
      disabled={busy}
      aria-labelledby={`${id}-title`}
      aria-describedby={`${id}-summary ${id}-action`}
    >
      <span id={`${id}-title`} className="scenario-title">
        {example.label}
      </span>
      <span id={`${id}-summary`} className="scenario-summary">
        {example.summary}
      </span>
      <span id={`${id}-action`} className="scenario-action">
        <Icon name={icon} size={14} />
        {action}
      </span>
    </button>
  );
}
