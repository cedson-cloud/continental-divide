import Link from "next/link";

// Where an approver lands after approving: what the decision produced, and where to see it.
export function PublishedNote({ hasSnippets }: { hasSnippets: boolean }) {
  return (
    <div className="msg msg-done detail-note" role="status">
      Done. This is now in the <Link href="/catalog">tracking plan</Link>
      {hasSnippets
        ? ", and engineers have the code to send it under For engineers below."
        : "."}
    </div>
  );
}
