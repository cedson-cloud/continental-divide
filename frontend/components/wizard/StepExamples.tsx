"use client";

import { NaturalLanguageExample, examplesForKind } from "@/lib/examples";
import type { DataKind } from "@/lib/wizard";
import { ScenarioTile } from "@/components/ScenarioCard";

// Step 3's examples follow the kind picked in step 1, so a newcomer who chose
// "Money / revenue" starts from a money example rather than the generic cart one.
export function StepExamples({
  kind,
  busy,
  status,
  onFill,
}: {
  kind: DataKind;
  busy: boolean;
  status: string | null;
  onFill: (example: NaturalLanguageExample) => void;
}) {
  return (
    <section className="step-examples" aria-labelledby="step-examples-title">
      <h2 id="step-examples-title" className="step-examples-title">
        Start from an example
      </h2>
      <p className="panel-sub">
        Pick one to fill in both fields below, then edit it or draft it as it is.
      </p>
      <div className="scenarios">
        {examplesForKind(kind).map((ex) => (
          <ScenarioTile
            key={ex.key}
            example={ex}
            icon="pencil"
            action="Fills in this step"
            busy={busy}
            onClick={() => onFill(ex)}
          />
        ))}
      </div>
      <p className="scenario-status" role="status">
        {status}
      </p>
    </section>
  );
}
