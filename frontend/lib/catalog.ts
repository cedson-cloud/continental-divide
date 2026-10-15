import type {
  CatalogView,
  CatalogViewEvent,
  CommonField,
  Evidence,
  PlatformLibrary,
  ReservedName,
} from "./api";
import { PLATFORMS, choiceLabel } from "./governance";

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

function searchTerm(needle: string): string {
  return needle.trim().toLowerCase();
}

export function matchesSearch(event: CatalogViewEvent, needle: string): boolean {
  const q = searchTerm(needle);
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

function joinWords(words: string[]): string {
  return words.length <= 1
    ? words.join("")
    : `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`;
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
  return `${plural(counts.total, "event", "events")}: ${joinWords(parts)}.`;
}

export function propertyCount(total: number, merged: number): string {
  if (total === 0) return "No properties listed";
  const all = plural(total, "property", "properties");
  return merged > 0 ? `${all}, ${merged} added by request` : all;
}

// What a system event's head says about its properties. The platform file may not
// list them yet, which is never the same as the event carrying none.
export function propertySummary(event: CatalogViewEvent, merged: number): string {
  if (event.source === "system_event" && event.properties.length === 0) {
    return event.properties_listed ? "No properties of its own" : "Properties not listed yet";
  }
  return propertyCount(event.properties.length, merged);
}

// docs is the default and goes untagged; the other two say how far to trust a claim.
export const EVIDENCE_LABELS: Record<Exclude<Evidence, "docs">, string> = {
  sdk_code: "From SDK code",
  disputed: "Sources disagree",
};

export function isTagged(evidence: Evidence | null): evidence is Exclude<Evidence, "docs"> {
  return evidence !== null && evidence !== "docs";
}

// Whether a claim needs a line of its own: a caveat, or evidence weaker than the docs.
export function hasCaveat(claim: { note: string | null; evidence: Evidence | null }): boolean {
  return Boolean(claim.note) || isTagged(claim.evidence);
}

export function platformLabel(name: string): string {
  return choiceLabel(PLATFORMS, name);
}

function libraryName(id: string, libraries: PlatformLibrary[]): string {
  return libraries.find((l) => l.id === id)?.name ?? id;
}

export function defaultsSentence(
  defaultOn: Record<string, boolean>,
  libraries: PlatformLibrary[],
): string {
  const ids = Object.keys(defaultOn);
  const on = ids.filter((id) => defaultOn[id]).map((id) => libraryName(id, libraries));
  const off = ids.filter((id) => !defaultOn[id]).map((id) => libraryName(id, libraries));
  const parts = [];
  if (on.length) parts.push(`On by default in ${joinWords(on)}.`);
  if (off.length) parts.push(`Off by default in ${joinWords(off)}.`);
  return parts.length
    ? parts.join(" ")
    : "Which libraries send it by default isn't listed yet.";
}

export function librariesLabel(ids: string[], libraries: PlatformLibrary[]): string[] {
  if (libraries.length > 1 && libraries.every((l) => ids.includes(l.id))) {
    return ["Every library"];
  }
  return ids.map((id) => libraryName(id, libraries));
}

export function matchesField(field: CommonField, needle: string): boolean {
  const q = searchTerm(needle);
  if (!q) return true;
  return (
    field.path.toLowerCase().includes(q) ||
    field.plain_name.toLowerCase().includes(q) ||
    field.group.toLowerCase().includes(q)
  );
}

export function matchesReserved(reserved: ReservedName, needle: string): boolean {
  const q = searchTerm(needle);
  if (!q) return true;
  return (
    reserved.name.toLowerCase().includes(q) ||
    reserved.records.toLowerCase().includes(q) ||
    (reserved.properties ?? []).some((p) => p.name.toLowerCase().includes(q))
  );
}

export function groupFields(fields: CommonField[]): [string, CommonField[]][] {
  const groups = new Map<string, CommonField[]>();
  for (const field of fields) {
    const list = groups.get(field.group) ?? [];
    list.push(field);
    groups.set(field.group, list);
  }
  return [...groups];
}

// The one list of sources every row cites, or null when any row differs.
export function sharedSources(lists: string[][]): string[] | null {
  if (lists.length < 2) return null;
  const first = lists[0].join("\n");
  return lists.every((l) => l.join("\n") === first) ? lists[0] : null;
}
