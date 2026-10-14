import { describe, expect, it } from "vitest";
import { AuditEntry } from "./api";
import { requestProgress } from "./progress";

function entry(step: string, detail: Record<string, unknown> | null = null): AuditEntry {
  return { id: 1, request_id: 1, step, detail, created_at: "2026-10-07 09:00:00" };
}

function summary(status: string, log: AuditEntry[] = []) {
  return requestProgress(status, log).map(
    (s) => `${s.label}:${s.current ? "current" : s.done ? "done" : "upcoming"}`,
  );
}

describe("requestProgress", () => {
  it("puts a draft at the first step with the whole path ahead", () => {
    expect(summary("draft")).toEqual([
      "Draft:current",
      "Pending approval:upcoming",
      "Approved:upcoming",
      "Published:upcoming",
    ]);
  });

  it("treats a flagged duplicate as pending approval, which is where it waits", () => {
    expect(summary("flagged_duplicate")).toEqual(summary("pending_approval"));
    expect(summary("pending_approval")[1]).toBe("Pending approval:current");
  });

  it("leaves Published ahead when an approval has not published yet", () => {
    expect(summary("approved")).toEqual([
      "Draft:done",
      "Pending approval:done",
      "Approved:current",
      "Published:upcoming",
    ]);
  });

  it("marks every step done once published, with Published as the current one", () => {
    const steps = requestProgress("published", []);
    expect(steps.every((s) => s.done)).toBe(true);
    expect(steps.filter((s) => s.current).map((s) => s.label)).toEqual(["Published"]);
  });

  it("ends an approver's rejection after Pending approval", () => {
    const log = [entry("submitted"), entry("decision_received", { decision: "reject" })];
    expect(summary("rejected", log)).toEqual([
      "Draft:done",
      "Pending approval:done",
      "Rejected:current",
    ]);
    expect(requestProgress("rejected", log).at(-1)?.tone).toBe("stop");
  });

  it("ends a rule rejection before the queue, because it never reached an approver", () => {
    const log = [entry("rules_evaluated"), entry("routed", { decision: "rejected" })];
    expect(summary("rejected", log)).toEqual(["Draft:done", "Rejected:current"]);
  });

  it("ends a withdrawn or superseded draft in a neutral tone", () => {
    expect(summary("withdrawn")).toEqual(["Draft:done", "Withdrawn:current"]);
    expect(summary("superseded")).toEqual(["Draft:done", "Superseded:current"]);
    expect(requestProgress("withdrawn", []).at(-1)?.tone).toBe("end");
  });
});
