import { DuplicateCandidate } from "@/lib/api";

export function DuplicateReview({
  candidates,
}: {
  candidates: DuplicateCandidate[];
}) {
  if (candidates.length === 0) return null;
  return (
    <div className="agent-review">
      <div className="agent-review-label">Agent review — judgment required</div>
      <p className="agent-review-note">
        The deterministic checks above are engine facts. What follows is model
        inference: existing events that may mean the same thing as this draft under a
        different name. It cannot reject the request — a human decides whether each
        argument holds.
      </p>
      <div className="candidates">
        {candidates.map((candidate, i) => (
          <div className="candidate" key={i}>
            <div className="row" style={{ gap: 8 }}>
              <span className="candidate-event">{candidate.existing_event}</span>
              <span className="tag">{candidate.category}</span>
              <span className={`confidence ${candidate.confidence}`}>
                {candidate.confidence} confidence
              </span>
            </div>
            <div className="candidate-reason">{candidate.reason}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
