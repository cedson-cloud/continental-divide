import { ReviewFinding } from "@/lib/api";

const KIND_ORDER = [
  "duplicate_event",
  "property_extension",
  "property_already_exists",
] as const;

const KIND_HEADINGS: Record<(typeof KIND_ORDER)[number], string> = {
  duplicate_event: "This sounds like an event you already have",
  property_extension: "This may belong on an existing event",
  property_already_exists: "That event may already have this",
};

export function AgentReview({
  findings,
  variant,
  onConvert,
  convertingEvent,
}: {
  findings: ReviewFinding[];
  variant: "requester" | "approver";
  onConvert?: (existingEvent: string) => void;
  convertingEvent?: string | null;
}) {
  if (findings.length === 0) return null;
  return (
    <div className="agent-review">
      <div className="agent-review-label">Agent review — judgment required</div>
      {KIND_ORDER.map((kind) => {
        const group = findings.filter(
          (f) => (f.kind ?? "duplicate_event") === kind,
        );
        if (group.length === 0) return null;
        return (
          <div className="finding-group" key={kind}>
            <div className="finding-group-heading">{KIND_HEADINGS[kind]}</div>
            <div className="candidates">
              {group.map((finding, i) => (
                <div className="candidate" key={i}>
                  <div className="row" style={{ gap: 8 }}>
                    <span className="candidate-event">{finding.existing_event}</span>
                    <span className="tag">{finding.category}</span>
                    {(finding.property_names || []).map((name) => (
                      <span className="tag" key={name}>
                        {name}
                      </span>
                    ))}
                    {variant === "approver" && (
                      <span className={`confidence ${finding.confidence}`}>
                        {finding.confidence} confidence
                      </span>
                    )}
                  </div>
                  <div className="candidate-reason">{finding.reason}</div>
                  {finding.existing_event_description && (
                    <p className="muted" style={{ fontSize: 13, margin: "6px 0 0" }}>
                      {finding.existing_event} today: {finding.existing_event_description}
                    </p>
                  )}
                  {(finding.existing_event_properties?.length ?? 0) > 0 && (
                    <div className="row" style={{ flexWrap: "wrap", gap: 6, marginTop: 6 }}>
                      {finding.existing_event_properties?.map((name) => (
                        <span className="tag" key={name}>
                          {name}
                        </span>
                      ))}
                    </div>
                  )}
                  {variant === "requester" &&
                    kind === "property_extension" &&
                    onConvert && (
                      <div className="row" style={{ gap: 8, marginTop: 8 }}>
                        <button
                          className="btn"
                          onClick={() => onConvert(finding.existing_event)}
                          disabled={convertingEvent != null}
                        >
                          {convertingEvent === finding.existing_event
                            ? "Creating a new request…"
                            : `Submit as a property on ${finding.existing_event} instead`}
                        </button>
                      </div>
                    )}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
