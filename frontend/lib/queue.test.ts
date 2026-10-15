import { describe, expect, it } from "vitest";
import type { QueueItem } from "./api";
import { groupQueue, queueSummary } from "./queue";

function item(id: number, status: string): QueueItem {
  return {
    id,
    name: `Event ${id}`,
    call_type: "track",
    category: null,
    status,
    created_at: "2026-10-15 09:00:00",
  };
}

describe("groupQueue", () => {
  it("puts requests waiting on a decision first, oldest first, and the rest newest first", () => {
    const groups = groupQueue([
      item(1, "published"),
      item(2, "pending_approval"),
      item(3, "draft_failed"),
      item(4, "flagged_duplicate"),
      item(5, "rejected"),
      item(6, "pending_approval"),
    ]);

    expect(groups.waiting.map((i) => i.id)).toEqual([2, 4, 6]);
    expect(groups.others.map((i) => i.id)).toEqual([5, 3, 1]);
  });
});

describe("queueSummary", () => {
  it("counts what is waiting and the total", () => {
    expect(queueSummary(groupQueue([item(1, "pending_approval"), item(2, "approved")]))).toBe(
      "1 waiting on a decision, 2 requests in total.",
    );
  });

  it("says plainly when nothing is waiting", () => {
    expect(queueSummary(groupQueue([item(1, "published")]))).toBe(
      "Nothing is waiting on a decision. 1 request in total.",
    );
  });
});
