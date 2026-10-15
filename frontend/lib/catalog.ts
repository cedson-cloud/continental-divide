import type { CatalogView, CatalogViewEvent } from "./api";

type CatalogCounts = CatalogView["counts"];

export type SourceFilter = "all" | "sample_plan" | "requests" | "system_event";

export const SOURCE_FILTERS: { value: SourceFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "sample_plan", label: "Sample plan" },
  { value: "requests", label: "From requests" },
  { value: "system_event", label: "System events" },
];

// An event a request created, or one a request added a property to: either way,
// something a person asked for and an approver let in. A request for a property the
// event already had adds no row, only its id under also_requested_by.
export function touchedByRequest(event: CatalogViewEvent): boolean {
  return (
    event.source === "approved_request" ||
    event.properties.some(
      (p) => p.source === "approved_request" || p.also_requested_by.length > 0,
    )
  );
}

export function matchesSource(event: CatalogViewEvent, filter: SourceFilter): boolean {
  if (filter === "all") return true;
  if (filter === "requests") return touchedByRequest(event);
  return event.source === filter;
}

export function matchesSearch(event: CatalogViewEvent, needle: string): boolean {
  const q = needle.trim().toLowerCase();
  if (!q) return true;
  return (
    event.name.toLowerCase().includes(q) ||
    event.description.toLowerCase().includes(q) ||
    event.properties.some((p) => p.name.toLowerCase().includes(q))
  );
}

export function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

export function catalogSummary(counts: CatalogCounts): string {
  const parts = [`${counts.from_sample_plan} from the sample plan`];
  if (counts.system_events > 0) {
    parts.push(plural(counts.system_events, "system event", "system events"));
  }
  if (counts.new_events_from_requests > 0) {
    parts.push(
      counts.new_events_from_requests === 1
        ? "1 approved as a new event"
        : `${counts.new_events_from_requests} approved as new events`,
    );
  }
  if (counts.property_additions_merged > 0) {
    parts.push(
      plural(
        counts.property_additions_merged,
        "property request merged in",
        "property requests merged in",
      ),
    );
  }
  if (counts.unresolved_targets > 0) {
    parts.push(`${counts.unresolved_targets} with no target event`);
  }
  const list =
    parts.length === 1
      ? parts[0]
      : `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
  return `${plural(counts.total, "event", "events")}: ${list}.`;
}

export function propertyCount(total: number, merged: number): string {
  if (total === 0) return "No properties";
  const all = plural(total, "property", "properties");
  return merged > 0 ? `${all}, ${merged} added by request` : all;
}
