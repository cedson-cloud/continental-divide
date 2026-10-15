import type { QueueItem } from "./api";
import { isActionable } from "./format";

export type QueueGroups = { waiting: QueueItem[]; others: QueueItem[] };

// Requests waiting on a decision come first, oldest first, so the longest wait is
// decided next. Everything else follows, newest first. Ids rise with creation, so they
// order the queue without parsing timestamps.
export function groupQueue(items: QueueItem[]): QueueGroups {
  const waiting = items.filter((i) => isActionable(i.status)).sort((a, b) => a.id - b.id);
  const others = items.filter((i) => !isActionable(i.status)).sort((a, b) => b.id - a.id);
  return { waiting, others };
}

export function queueSummary({ waiting, others }: QueueGroups): string {
  const total = waiting.length + others.length;
  const all = `${total} ${total === 1 ? "request" : "requests"} in total`;
  if (waiting.length === 0) return `Nothing is waiting on a decision. ${all}.`;
  return `${waiting.length} waiting on a decision, ${all}.`;
}
