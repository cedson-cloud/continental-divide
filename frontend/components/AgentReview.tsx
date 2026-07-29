import { ReviewFinding } from "@/lib/api";

const KIND_ORDER = [
  "duplicate_event",
  "property_extension",
  "property_already_exists",
] as const;

const KIND_HEADINGS: Record<(typeof KIND_ORDER)[number], string> = {
  duplicate_event: "This may already exist",
  property_extension: "This may belong on an existing event",
  property_already_exists: "That event may already have this",
};

export function AgentReview({
  findings,
  variant,
}: {
  findings: ReviewFinding[];
  variant: "requester" | "approver";
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
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
