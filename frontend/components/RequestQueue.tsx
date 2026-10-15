import Link from "next/link";
import { QueueItem } from "@/lib/api";
import { definitionTitle, formatShortTimestamp } from "@/lib/format";
import { groupQueue, queueSummary } from "@/lib/queue";
import { Icon } from "./icons";
import { StatusBadge } from "./StatusBadge";

function RequestName({ item }: { item: QueueItem }) {
  const isEvent = item.call_type === "track";
  // A track request with no name has no definition, as when drafting failed.
  if (isEvent && !item.name) {
    return <span className="queue-name">Request #{item.id}</span>;
  }
  return (
    <>
      <span className={isEvent ? "queue-name mono" : "queue-name"}>
        {definitionTitle(item)}
      </span>{" "}
      <span className="queue-id">#{item.id}</span>
    </>
  );
}

// The explicit roles keep the table a table for screen readers on a phone, where the
// stylesheet lays each row out as a card and some browsers then drop the semantics.
function QueueTable({ items, labelledBy }: { items: QueueItem[]; labelledBy: string }) {
  return (
    <div className="panel queue-panel">
      <table className="queue-table" role="table" aria-labelledby={labelledBy}>
        <thead role="rowgroup">
          <tr role="row">
            <th role="columnheader" scope="col" className="queue-col-event">
              Event
            </th>
            <th role="columnheader" scope="col">
              Category
            </th>
            <th role="columnheader" scope="col" className="queue-col-status">
              Status
            </th>
            <th role="columnheader" scope="col" className="queue-col-created">
              Created
            </th>
          </tr>
        </thead>
        <tbody role="rowgroup">
          {items.map((item) => (
            <tr key={item.id} role="row" className="queue-row">
              <td role="cell" className="queue-event">
                <Link href={`/requests/${item.id}`} className="queue-link">
                  <RequestName item={item} />
                </Link>
              </td>
              <td role="cell" className="queue-category">
                {item.category || "No category"}
              </td>
              <td role="cell" className="queue-status">
                <StatusBadge status={item.status} />
              </td>
              <td role="cell" className="queue-created">
                {formatShortTimestamp(item.created_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function RequestQueue({ items }: { items: QueueItem[] }) {
  if (items.length === 0) {
    return (
      <section className="panel queue-empty" aria-labelledby="queue-empty-title">
        <h2 id="queue-empty-title" className="panel-title">
          No requests yet
        </h2>
        <p className="panel-sub">
          Describe an event in a sentence and the model drafts it for review. Or try a
          scenario to see what the rules catch.
        </p>
        <Link href="/" className="btn btn-primary queue-empty-action">
          <Icon name="plus" size={16} />
          New request
        </Link>
      </section>
    );
  }

  const groups = groupQueue(items);
  return (
    <>
      <p className="queue-summary">{queueSummary(groups)}</p>
      {groups.waiting.length > 0 && (
        <section className="queue-group">
          <h2 id="queue-waiting" className="queue-group-title">
            Waiting on a decision
          </h2>
          <QueueTable items={groups.waiting} labelledBy="queue-waiting" />
        </section>
      )}
      {groups.others.length > 0 && (
        <section className="queue-group">
          <h2 id="queue-others" className="queue-group-title">
            {groups.waiting.length > 0 ? "Everything else" : "All requests"}
          </h2>
          <QueueTable items={groups.others} labelledBy="queue-others" />
        </section>
      )}
    </>
  );
}
