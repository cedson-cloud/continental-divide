"use client";

import Link from "next/link";
import { Fragment, useId, useMemo, useState } from "react";
import { CatalogPlatform, CatalogView, CatalogViewEvent, SharedShape } from "@/lib/api";
import {
  SOURCE_FILTERS,
  SourceFilter,
  catalogSummary,
  defaultsSentence,
  hasCaveat,
  matchesField,
  matchesReserved,
  matchesSearch,
  matchesSource,
  platformLabel,
  plural,
  propertySummary,
} from "@/lib/catalog";
import { Icon } from "./icons";
import {
  CommonFieldsPanel,
  EvidenceTag,
  ReservedNamesPanel,
  SourceLinks,
} from "./PlatformDetails";

// Persistent and honest: the review's view of the catalog is narrower than this
// page, and papering over that would misrepresent what the tool checks.
export const REVIEW_GAP_NOTICE =
  "New requests are checked for duplicates against the sample plan and the " +
  "events the analytics SDK sends on its own. Events approved through this tool " +
  "appear here but are not yet part of what the check compares against.";

export const COLLISION_WARNING = "Two definitions share this name.";

function eventKey(event: CatalogViewEvent): string {
  return `${event.source}:${event.request_id ?? ""}:${event.category}:${event.name}`;
}

function SourceTag({ event }: { event: CatalogViewEvent }) {
  if (event.source === "approved_request") {
    return (
      <Link className="catalog-source-tag catalog-source-tag-request" href={`/requests/${event.request_id}`}>
        From request #{event.request_id}
      </Link>
    );
  }
  if (event.source === "system_event") {
    return <span className="catalog-source-tag catalog-source-tag-system">System event</span>;
  }
  return <span className="catalog-source-tag">Sample plan</span>;
}

function ShapeRows({ name, shape }: { name: string; shape: SharedShape }) {
  return (
    <div className="catalog-shape">
      <p className="catalog-shape-lede">
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
              <td>{p.name}</td>
              <td>{p.type}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// What the platform file says about a system event beyond its properties: which
// libraries send it by default, any caveat, and where the claims come from.
function SystemEventFacts({
  event,
  platform,
}: {
  event: CatalogViewEvent;
  platform: CatalogPlatform | null;
}) {
  const defaults = platform ? defaultsSentence(event.default_on, platform.libraries) : null;
  return (
    <>
      {defaults && <p className="catalog-event-meta">{defaults}</p>}
      {hasCaveat(event) && (
        <p className="catalog-event-meta catalog-fact">
          <EvidenceTag evidence={event.evidence} /> {event.note}
        </p>
      )}
    </>
  );
}

function EventRow({
  event,
  shapes,
  collision,
  platform,
}: {
  event: CatalogViewEvent;
  shapes: Record<string, SharedShape>;
  collision: boolean;
  platform: CatalogPlatform | null;
}) {
  const [expanded, setExpanded] = useState(false);
  const [openShape, setOpenShape] = useState<string | null>(null);
  const bodyId = useId();

  // A property that arrived after the entry itself: approved on a different
  // request than the one (if any) that created the event.
  const mergedCount = event.properties.filter(
    (p) => p.source === "approved_request" && p.request_id !== event.request_id,
  ).length;
  const system = event.source === "system_event";
  const platformProps = event.properties.filter((p) => p.source === "system_event").length;

  const shapeProp = openShape
    ? event.properties.find((p) => p.name === openShape)
    : undefined;
  const openShapeDef = shapeProp?.shape ? shapes[shapeProp.shape] : undefined;

  return (
    <div className="catalog-event">
      <div className="catalog-event-head">
        <button
          type="button"
          className="catalog-event-toggle"
          aria-expanded={expanded}
          aria-controls={expanded ? bodyId : undefined}
          onClick={() => setExpanded((v) => !v)}
        >
          <Icon name="chevron" size={16} />
          <span className="catalog-event-name">{event.name}</span>
        </button>
        <SourceTag event={event} />
        <p className="catalog-event-meta">{event.description}</p>
        <span className="catalog-event-count">
          {propertySummary(event, mergedCount)}
        </span>
        {system && (
          <p className="catalog-event-meta">
            Sent automatically as {event.sent_as} by {event.sent_by}.
          </p>
        )}
      </div>
      {collision && <div className="msg msg-error catalog-warning">{COLLISION_WARNING}</div>}
      {event.unresolved_target && (
        <div className="msg msg-error catalog-warning">
          Property request whose target event was not found in the catalog. The
          properties below have nowhere to attach.
        </div>
      )}
      {expanded && (
        <div id={bodyId} className="catalog-event-body">
          {system && <SystemEventFacts event={event} platform={platform} />}
          {system && !event.properties_listed && (
            <p className="catalog-event-meta">
              The properties the SDK sends with this event aren&apos;t listed here yet.
            </p>
          )}
          {system && event.properties_listed && platformProps === 0 && (
            <p className="catalog-event-meta">
              The sources list no properties of its own for this event.
            </p>
          )}
          {!system && event.properties.length === 0 && (
            <p className="catalog-event-meta">No properties are listed for this event.</p>
          )}
          {event.properties.length > 0 && (
            <table
              className="prop-table catalog-props"
              role="table"
              aria-label={`${event.name} properties`}
            >
              <thead role="rowgroup">
                <tr role="row">
                  <th role="columnheader" scope="col">
                    Property
                  </th>
                  <th role="columnheader" scope="col">
                    Type
                  </th>
                  <th role="columnheader" scope="col">
                    Source
                  </th>
                </tr>
              </thead>
              <tbody role="rowgroup">
                {event.properties.map((p) => (
                  <tr key={p.name} role="row">
                    <td role="cell">
                      {p.name}
                      {p.note && <span className="catalog-prop-note">{p.note}</span>}
                    </td>
                    <td role="cell" className="catalog-prop-type">
                      {p.type ?? <span className="catalog-prop-unlisted">not listed yet</span>}
                      {p.shape && shapes[p.shape] && (
                        <button
                          type="button"
                          className="catalog-shape-toggle"
                          aria-expanded={openShape === p.name}
                          onClick={() =>
                            setOpenShape((v) => (v === p.name ? null : p.name))
                          }
                        >
                          <Icon name="chevron" size={14} />
                          {p.shape}
                        </button>
                      )}
                    </td>
                    <td role="cell" className="catalog-prop-source">
                      {p.source === "approved_request" && p.request_id != null ? (
                        <Link
                          className="catalog-request-link"
                          href={`/requests/${p.request_id}`}
                        >
                          #{p.request_id}
                        </Link>
                      ) : p.source === "system_event" ? (
                        <span className="catalog-prop-platform">
                          <span className="muted">
                            {platform ? platformLabel(platform.name) : "platform"}
                          </span>
                          <EvidenceTag evidence={p.evidence} />
                        </span>
                      ) : (
                        <span className="muted">plan</span>
                      )}
                      {p.also_requested_by.length > 0 && (
                        <span className="muted catalog-also">
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
          {shapeProp?.shape && openShapeDef && (
            <ShapeRows name={shapeProp.shape} shape={openShapeDef} />
          )}
          {system && <SourceLinks sources={event.sources} checked={platform?.checked} />}
        </div>
      )}
    </div>
  );
}

function CategoryGroup({
  category,
  events,
  shapes,
  collidingNames,
  platform,
  open,
  onToggle,
}: {
  category: string;
  events: CatalogViewEvent[];
  shapes: Record<string, SharedShape>;
  collidingNames: Set<string>;
  platform: CatalogPlatform | null;
  open: boolean;
  onToggle: () => void;
}) {
  const listId = useId();
  return (
    <section className="panel catalog-group">
      <h2 className="catalog-group-title">
        <button
          type="button"
          className="catalog-group-toggle"
          aria-expanded={open}
          aria-controls={open ? listId : undefined}
          onClick={onToggle}
        >
          <Icon name="chevron" size={16} />
          {category}
          <span className="catalog-group-count">
            {plural(events.length, "event", "events")}
          </span>
        </button>
      </h2>
      {open && (
        <div id={listId}>
          {events.map((event) => (
            <EventRow
              key={eventKey(event)}
              event={event}
              shapes={shapes}
              collision={collidingNames.has(event.name)}
              platform={platform}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function NewRequestLink({ className }: { className: string }) {
  return (
    <Link href="/request" className={className}>
      <Icon name="plus" size={16} />
      New request
    </Link>
  );
}

export function CatalogBrowser({ catalog }: { catalog: CatalogView }) {
  const [search, setSearch] = useState("");
  const [source, setSource] = useState<SourceFilter>("all");
  // Held here rather than in each group, so a category a search hides comes back
  // the way it was left.
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const { counts } = catalog;

  // Names carried by two or more real definitions. Unresolved property requests
  // are excluded: they are orphans, not rival definitions.
  const collidingNames = useMemo(() => {
    const seen = new Map<string, number>();
    for (const event of catalog.events) {
      if (event.unresolved_target) continue;
      seen.set(event.name, (seen.get(event.name) ?? 0) + 1);
    }
    return new Set([...seen].filter(([, n]) => n > 1).map(([name]) => name));
  }, [catalog.events]);

  const sourceCounts = useMemo(() => {
    const result = {} as Record<SourceFilter, number>;
    for (const { value } of SOURCE_FILTERS) {
      result[value] = catalog.events.filter((e) => matchesSource(e, value)).length;
    }
    return result;
  }, [catalog.events]);

  const byCategory = useMemo(() => {
    const groups = new Map<string, CatalogViewEvent[]>();
    for (const event of catalog.events) {
      if (!matchesSource(event, source) || !matchesSearch(event, search)) continue;
      const list = groups.get(event.category) ?? [];
      list.push(event);
      groups.set(event.category, list);
    }
    return groups;
  }, [catalog.events, source, search]);

  // System events come from the platform the governance profile names; with no
  // platform there are none, and a filter that can only ever be empty is noise.
  const filters = SOURCE_FILTERS.filter(
    (f) => f.value !== "system_event" || counts.system_events > 0,
  );

  const requested = sourceCounts.requests > 0;
  let shown = 0;
  for (const events of byCategory.values()) shown += events.length;

  // The platform's common fields and reserved names sit beside its system events,
  // and a search reaches them too: asking for utm_source should find it already sent.
  const { platform } = catalog;
  const platformShown =
    platform && (source === "all" || source === "system_event") ? platform : null;
  const platformMatches = platformShown
    ? platformShown.common_fields.filter((f) => matchesField(f, search)).length +
      platformShown.reserved_names.filter((r) => matchesReserved(r, search)).length
    : 0;
  const platformPanels = platformShown && platformMatches > 0 && (
    <>
      <CommonFieldsPanel platform={platformShown} search={search} />
      <ReservedNamesPanel platform={platformShown} search={search} />
    </>
  );
  const systemCategory = catalog.events.find((e) => e.source === "system_event")?.category;

  // A search can match only platform fields; saying "0 events" then would mislead.
  const eventsShown = `${shown} of ${counts.total} events shown`;
  const liveSummary =
    search.trim() && platformMatches > 0
      ? `${eventsShown}, plus ${plural(
          platformMatches,
          "match among the fields and names the platform sends",
          "matches among the fields and names the platform sends",
        )}`
      : shown === counts.total
        ? ""
        : eventsShown;

  function showAll() {
    setSearch("");
    setSource("all");
  }

  function toggleCategory(category: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(category)) next.delete(category);
      else next.add(category);
      return next;
    });
  }

  return (
    <>
      <div className="panel catalog-tools">
        <label className="field">
          <span className="field-label">Search events</span>
          <input
            type="text"
            placeholder="Event or property name, e.g. coupon_id"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <div className="catalog-filters" role="group" aria-label="Show events from">
          {filters.map((f) => (
            <button
              key={f.value}
              type="button"
              className="catalog-filter"
              aria-pressed={source === f.value}
              onClick={() => setSource(f.value)}
            >
              {f.label}
              <span className="catalog-filter-count">{sourceCounts[f.value]}</span>
            </button>
          ))}
        </div>
        <p className="catalog-summary">{catalogSummary(counts)}</p>
        {!requested && source !== "requests" && (
          <p className="catalog-summary">
            Events you request join this plan once they&apos;re approved.{" "}
            <Link href="/request">Make a request</Link>
          </p>
        )}
        <p className="catalog-note">{REVIEW_GAP_NOTICE}</p>
        <p className="visually-hidden" aria-live="polite">
          {liveSummary}
        </p>
      </div>

      {byCategory.size === 0 &&
        platformMatches === 0 &&
        (source === "requests" && !requested && !search.trim() ? (
          <section className="panel catalog-empty" aria-labelledby="catalog-empty-title">
            <h2 id="catalog-empty-title" className="panel-title">
              Nothing from requests yet
            </h2>
            <p className="panel-sub">
              Describe an event in a sentence, submit the draft, then approve it from the
              queue. It lands here, marked with the request it came from.
            </p>
            <NewRequestLink className="btn btn-primary catalog-empty-action" />
          </section>
        ) : (
          <section className="panel catalog-empty" aria-labelledby="catalog-empty-title">
            <h2 id="catalog-empty-title" className="panel-title">
              No events match
            </h2>
            <p className="panel-sub">
              {search.trim()
                ? `Nothing here matches “${search.trim()}”.`
                : "Nothing here comes from that source."}{" "}
              An event that isn&apos;t in the plan yet can be requested.
            </p>
            <div className="row">
              <button type="button" className="btn btn-primary" onClick={showAll}>
                Show all events
              </button>
              <NewRequestLink className="btn catalog-empty-action" />
            </div>
          </section>
        ))}

      {[...byCategory.entries()].map(([category, events]) => (
        <Fragment key={category}>
          <CategoryGroup
            category={category}
            events={events}
            shapes={catalog.shapes}
            collidingNames={collidingNames}
            platform={platform}
            open={!collapsed.has(category)}
            onToggle={() => toggleCategory(category)}
          />
          {category === systemCategory && platformPanels}
        </Fragment>
      ))}
      {!(systemCategory && byCategory.has(systemCategory)) && platformPanels}
    </>
  );
}
