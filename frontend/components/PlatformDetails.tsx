"use client";

import { Fragment, ReactNode, useEffect, useId, useState } from "react";
import { CatalogPlatform, Evidence, ReservedName } from "@/lib/api";
import {
  EVIDENCE_LABELS,
  groupFields,
  hasCaveat,
  isTagged,
  librariesLabel,
  matchesField,
  matchesReserved,
  platformLabel,
  plural,
  sharedSources,
} from "@/lib/catalog";
import { formatChecked, sourceLabel } from "@/lib/format";
import { Icon } from "./icons";

export function EvidenceTag({ evidence }: { evidence: Evidence | null }) {
  if (!isTagged(evidence)) return null;
  return (
    <span className={`catalog-evidence catalog-evidence-${evidence}`}>
      {EVIDENCE_LABELS[evidence]}
    </span>
  );
}

export function SourceLinks({
  sources,
  checked,
}: {
  sources: string[];
  checked?: string;
}) {
  if (sources.length === 0) return null;
  return (
    <p className="catalog-sources">
      {checked ? `Sources, checked ${formatChecked(checked)}: ` : "Sources: "}
      {sources.map((url, i) => (
        <Fragment key={url}>
          {i > 0 && ", "}
          <a href={url} target="_blank" rel="noreferrer">
            {sourceLabel(url)}
            <span className="visually-hidden"> (opens in a new tab)</span>
          </a>
        </Fragment>
      ))}
    </p>
  );
}

// Collapsed until the reader opens it, or until a search finds something inside.
function PlatformPanel({
  title,
  count,
  search,
  children,
}: {
  title: string;
  count: string;
  search: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const bodyId = useId();
  useEffect(() => {
    if (search.trim()) setOpen(true);
  }, [search]);

  return (
    <section className="panel catalog-group">
      <h2 className="catalog-group-title">
        <button
          type="button"
          className="catalog-group-toggle"
          aria-expanded={open}
          aria-controls={open ? bodyId : undefined}
          onClick={() => setOpen((v) => !v)}
        >
          <Icon name="chevron" size={16} />
          {title}
          <span className="catalog-group-count">{count}</span>
        </button>
      </h2>
      {open && (
        <div id={bodyId} className="catalog-platform-body">
          {children}
        </div>
      )}
    </section>
  );
}

export function CommonFieldsPanel({
  platform,
  search,
}: {
  platform: CatalogPlatform;
  search: string;
}) {
  const label = platformLabel(platform.name);
  const fields = platform.common_fields.filter((f) => matchesField(f, search));
  if (fields.length === 0) return null;
  const notes = platform.libraries.filter((l) => l.note);

  return (
    <PlatformPanel
      title="Sent with every event"
      count={plural(fields.length, "field", "fields")}
      search={search}
    >
      <p className="catalog-platform-lede">
        These fields arrive on events without a request asking for them. Each row
        says which of {label}&apos;s libraries send it, and its note says when.
        Checked against {label}&apos;s docs and code on{" "}
        {formatChecked(platform.checked)}.
      </p>
      <p className="catalog-platform-legend">
        <EvidenceTag evidence="sdk_code" /> means it was read in {label}&apos;s
        code on GitHub, which can be ahead of a release.{" "}
        <EvidenceTag evidence="disputed" /> means the sources disagree, and the
        note says how.
      </p>
      {groupFields(fields).map(([group, rows]) => {
        // Fields in a group usually share their sources: say them once, under it.
        const shared = sharedSources(rows.map((f) => f.sources));
        return (
          <div key={group} className="catalog-field-group">
            <h3 className="catalog-field-group-title">{group}</h3>
            <table
              className="prop-table catalog-props catalog-fields"
              role="table"
              aria-label={`${group} fields`}
            >
              <thead role="rowgroup">
                <tr role="row">
                  <th role="columnheader" scope="col">
                    Field
                  </th>
                  <th role="columnheader" scope="col">
                    Sent by
                  </th>
                  <th role="columnheader" scope="col">
                    Notes
                  </th>
                </tr>
              </thead>
              <tbody role="rowgroup">
                {rows.map((f) => (
                  <tr key={f.path} role="row">
                    <td role="cell">
                      <span className="catalog-field-name">{f.plain_name}</span>
                      <span className="catalog-field-path">{f.path}</span>
                    </td>
                    <td role="cell" className="catalog-prop-type">
                      <span className="catalog-libs">
                        {librariesLabel(f.libraries, platform.libraries).map(
                          (name) => (
                            <span key={name} className="catalog-lib">
                              {name}
                            </span>
                          ),
                        )}
                      </span>
                    </td>
                    <td role="cell" className="catalog-prop-source">
                      {hasCaveat(f) && (
                        <p className="catalog-field-note">
                          <EvidenceTag evidence={f.evidence} /> {f.note}
                        </p>
                      )}
                      {!shared && <SourceLinks sources={f.sources} />}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {shared && <SourceLinks sources={shared} />}
          </div>
        );
      })}
      {notes.length > 0 && (
        <div className="catalog-field-group">
          <h3 className="catalog-field-group-title">About the libraries</h3>
          <ul className="catalog-platform-list">
            {notes.map((l) => (
              <li key={l.id}>
                {l.name}: {l.note}
              </li>
            ))}
          </ul>
        </div>
      )}
      {platform.not_listed_yet.length > 0 && (
        <div className="catalog-field-group">
          <h3 className="catalog-field-group-title">Not listed here yet</h3>
          <ul className="catalog-platform-list">
            {platform.not_listed_yet.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </PlatformPanel>
  );
}

function ReservedProperties({ reserved }: { reserved: ReservedName }) {
  if (reserved.properties === null) {
    return (
      <p className="catalog-event-meta">
        Its properties aren&apos;t listed here yet.
      </p>
    );
  }
  if (reserved.properties.length === 0) {
    return (
      <p className="catalog-event-meta">
        The spec gives it no properties of its own.
      </p>
    );
  }
  return (
    <table
      className="prop-table catalog-props"
      role="table"
      aria-label={`${reserved.name} properties`}
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
            Notes
          </th>
        </tr>
      </thead>
      <tbody role="rowgroup">
        {reserved.properties.map((p) => (
          <tr key={p.name} role="row">
            <td role="cell">{p.name}</td>
            <td role="cell" className="catalog-prop-type">
              {p.type ?? (
                <span className="catalog-prop-unlisted">not listed yet</span>
              )}
            </td>
            <td role="cell" className="catalog-prop-source">
              {hasCaveat(p) && (
                <span className="catalog-field-note">
                  <EvidenceTag evidence={p.evidence} /> {p.note}
                </span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function ReservedNamesPanel({
  platform,
  search,
}: {
  platform: CatalogPlatform;
  search: string;
}) {
  const label = platformLabel(platform.name);
  const names = platform.reserved_names.filter((r) =>
    matchesReserved(r, search),
  );
  if (names.length === 0) return null;

  return (
    <PlatformPanel
      title="Reserved names"
      count={plural(names.length, "name", "names")}
      search={search}
    >
      <p className="catalog-platform-lede">
        {label}&apos;s spec defines these names for events its own libraries
        don&apos;t send. If you track one of these, use the name as written: a
        request for it follows the spec, so it isn&apos;t a duplicate. Checked
        against {label}&apos;s docs on {formatChecked(platform.checked)}.
      </p>
      {names.map((r) => (
        <div key={r.name} className="catalog-reserved">
          <h3 className="catalog-reserved-head">
            <span className="catalog-event-name">{r.name}</span>
            <EvidenceTag evidence={r.evidence} />
          </h3>
          <p className="catalog-event-meta">
            Records {r.records}. Who sends it: {r.sent_by}.
          </p>
          {r.note && <p className="catalog-event-meta">{r.note}</p>}
          <ReservedProperties reserved={r} />
          <SourceLinks sources={r.sources} />
        </div>
      ))}
    </PlatformPanel>
  );
}
