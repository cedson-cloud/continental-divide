"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { CatalogView, CatalogViewEvent, SharedShape } from "@/lib/api";

// Persistent and honest: the review's view of the catalog is narrower than this
// page, and papering over that would misrepresent what the tool checks.
export const REVIEW_GAP_NOTICE =
  "The duplicate review currently checks new requests against the sample plan " +
  "only. Events approved through this tool appear here but are not yet part of " +
  "what the review compares against.";

export const COLLISION_WARNING = "Two definitions share this name.";

function eventKey(event: CatalogViewEvent): string {
  return `${event.source}:${event.request_id ?? ""}:${event.category}:${event.name}`;
}

function matches(event: CatalogViewEvent, needle: string): boolean {
  const q = needle.trim().toLowerCase();
  if (!q) return true;
  return (
    event.name.toLowerCase().includes(q) ||
    event.description.toLowerCase().includes(q) ||
    event.properties.some((p) => p.name.toLowerCase().includes(q))
  );
}

function ShapeRows({ name, shape }: { name: string; shape: SharedShape }) {
  return (
    <div className="mt-12">
      <p className="muted" style={{ fontSize: 12.5, margin: "0 0 4px" }}>
        Each item in this array is a <span className="mono">{name}</span>
        {shape.description ? ` — ${shape.description}` : ""}
      </p>
      <table className="prop-table">
        <thead>
          <tr>
            <th>Property</th>
            <th>Type</th>
          </tr>
        </thead>
        <tbody>
          {shape.properties.map((p) => (
            <tr key={p.name}>
              <td className="mono">{p.name}</td>
              <td>{p.type}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EventRow({
  event,
  shapes,
  collision,
}: {
  event: CatalogViewEvent;
  shapes: Record<string, SharedShape>;
  collision: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [openShape, setOpenShape] = useState<string | null>(null);

  // A property that arrived after the entry itself: approved on a different
  // request than the one (if any) that created the event.
  const mergedCount = event.properties.filter(
    (p) => p.source === "approved_request" && p.request_id !== event.request_id,
  ).length;
  const baseCount = event.properties.length - mergedCount;

  return (
    <div style={{ borderTop: "1px solid var(--border, #e3e3e3)", padding: "8px 0" }}>
      <div className="row spread" style={{ alignItems: "baseline" }}>
        <button
          className="link-button"
          onClick={() => setExpanded((v) => !v)}
          style={{ fontSize: 15 }}
        >
          {expanded ? "▾" : "▸"} {event.name}
        </button>
        {event.source === "approved_request" ? (
          <Link className="badge approved" href={`/requests/${event.request_id}`}>
            Requested
          </Link>
        ) : (
          <span className="badge neutral">Sample plan</span>
        )}
      </div>
      {collision && <div className="msg msg-error mt-12">{COLLISION_WARNING}</div>}
      {event.unresolved_target && (
        <div className="msg msg-error mt-12">
          Property request whose target event was not found in the catalog. The
          properties below have nowhere to attach.
        </div>
      )}
      <p className="muted" style={{ fontSize: 13, margin: "2px 0 0" }}>
        {event.description}
        {mergedCount > 0 && (
          <>
            {" — "}
            {baseCount} from the{" "}
            {event.source === "sample_plan" ? "plan" : "original request"},{" "}
            {mergedCount} added by request
          </>
        )}
      </p>
      {expanded && (
        <div className="mt-12">
          {event.properties.length === 0 ? (
            <p className="muted" style={{ fontSize: 13, margin: 0 }}>
              No properties.
            </p>
          ) : (
            <table className="prop-table">
              <thead>
                <tr>
                  <th>Property</th>
                  <th>Type</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {event.properties.map((p) => (
                  <tr key={p.name}>
                    <td className="mono">{p.name}</td>
                    <td>
                      {p.type}
                      {p.shape && shapes[p.shape] && (
                        <>
                          {" "}
                          <button
                            className="link-button"
                            onClick={() =>
                              setOpenShape((v) => (v === p.name ? null : p.name))
                            }
                          >
                            {openShape === p.name ? "▾" : "▸"} {p.shape}
                          </button>
                        </>
                      )}
                    </td>
                    <td>
                      {p.source === "approved_request" && p.request_id != null ? (
                        <Link
                          className="badge approved"
                          href={`/requests/${p.request_id}`}
                        >
                          #{p.request_id}
                        </Link>
                      ) : (
                        <span className="muted" style={{ fontSize: 12 }}>
                          plan
                        </span>
                      )}
                      {p.also_requested_by.length > 0 && (
                        <span
                          className="muted"
                          style={{ fontSize: 12, marginLeft: 6 }}
                        >
                          also requested by{" "}
                          {p.also_requested_by.map((id) => `#${id}`).join(", ")}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {openShape &&
            (() => {
              const prop = event.properties.find((p) => p.name === openShape);
              const shape = prop?.shape ? shapes[prop.shape] : undefined;
              return prop?.shape && shape ? (
                <ShapeRows name={prop.shape} shape={shape} />
              ) : null;
            })()}
        </div>
      )}
    </div>
  );
}

export function CatalogBrowser({ catalog }: { catalog: CatalogView }) {
  const [filter, setFilter] = useState("");
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  // Names carried by two or more real definitions. Unresolved property requests
  // are excluded: they are orphans, not rival definitions.
  const collidingNames = useMemo(() => {
    const counts = new Map<string, number>();
    for (const event of catalog.events) {
      if (event.unresolved_target) continue;
      counts.set(event.name, (counts.get(event.name) ?? 0) + 1);
    }
    return new Set([...counts].filter(([, n]) => n > 1).map(([name]) => name));
  }, [catalog.events]);

  const byCategory = useMemo(() => {
    const groups = new Map<string, CatalogViewEvent[]>();
    for (const event of catalog.events) {
      if (!matches(event, filter)) continue;
      const list = groups.get(event.category) ?? [];
      list.push(event);
      groups.set(event.category, list);
    }
    return groups;
  }, [catalog.events, filter]);

  function toggleCategory(category: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(category)) next.delete(category);
      else next.add(category);
      return next;
    });
  }

  const { counts } = catalog;
  return (
    <>
      <div className="msg msg-info">{REVIEW_GAP_NOTICE}</div>

      <div className="panel">
        <label className="field">
          <span className="field-label">Filter</span>
          <input
            type="text"
            placeholder="Event name, description, or property name — e.g. coupon_id"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </label>
        <p className="muted" style={{ fontSize: 12.5, marginBottom: 0 }}>
          {counts.total} events — {counts.from_sample_plan} from the sample plan,{" "}
          {counts.new_events_from_requests} approved as new events,{" "}
          {counts.property_additions_merged} property additions merged in
          {counts.unresolved_targets > 0 &&
            `, ${counts.unresolved_targets} with no target event`}
          .
        </p>
      </div>

      {byCategory.size === 0 && (
        <div className="panel">
          <p className="muted" style={{ margin: 0 }}>
            No events match &ldquo;{filter}&rdquo;.
          </p>
        </div>
      )}

      {[...byCategory.entries()].map(([category, events]) => (
        <div className="panel" key={category}>
          <button
            className="link-button"
            onClick={() => toggleCategory(category)}
            style={{ fontSize: 16, fontWeight: 600 }}
          >
            {collapsed.has(category) ? "▸" : "▾"} {category} ({events.length})
          </button>
          {!collapsed.has(category) &&
            events.map((event) => (
              <EventRow
                key={eventKey(event)}
                event={event}
                shapes={catalog.shapes}
                collision={collidingNames.has(event.name)}
              />
            ))}
        </div>
      ))}
    </>
  );
}
