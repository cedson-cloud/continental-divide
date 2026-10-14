import type { AuditEntry } from "./api";

// The request's place on the happy path, derived from its status. Rejected, withdrawn
// and superseded requests leave the path, so their last step names where they stopped
// instead of offering steps they will never reach.
export type ProgressStep = {
  label: string;
  done: boolean;
  current: boolean;
  tone: "normal" | "stop" | "end";
};

const PATH = ["Draft", "Pending approval", "Approved", "Published"];

const POSITION: Record<string, number> = {
  draft: 0,
  pending_approval: 1,
  flagged_duplicate: 1,
  approved: 2,
  published: 3,
};

const OFF_PATH: Record<string, { label: string; tone: "stop" | "end" }> = {
  rejected: { label: "Rejected", tone: "stop" },
  withdrawn: { label: "Withdrawn", tone: "end" },
  superseded: { label: "Superseded", tone: "end" },
};

export function requestProgress(status: string, auditLog: AuditEntry[]): ProgressStep[] {
  if (status in POSITION) {
    const at = POSITION[status];
    const finished = status === "published";
    return PATH.map((label, i) => ({
      label,
      done: i < at || finished,
      current: i === at,
      tone: "normal",
    }));
  }

  const stop = OFF_PATH[status] ?? { label: status, tone: "end" as const };
  // An approver's rejection happened in the queue; a rule rejection never got there.
  const reachedApproval =
    status === "rejected" &&
    auditLog.some(
      (e) => e.step === "decision_received" && e.detail?.decision === "reject",
    );
  const before = reachedApproval ? PATH.slice(0, 2) : PATH.slice(0, 1);
  return [
    ...before.map((label) => ({
      label,
      done: true,
      current: false,
      tone: "normal" as const,
    })),
    { label: stop.label, done: false, current: true, tone: stop.tone },
  ];
}
