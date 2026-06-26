"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { QueueItem, friendlyError, listRequests } from "@/lib/api";
import { formatTimestamp, isActionable } from "@/lib/format";
import { StatusBadge } from "@/components/StatusBadge";

export default function QueuePage() {
  const [items, setItems] = useState<QueueItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listRequests()
      .then(setItems)
      .catch((err) => setError(friendlyError(err)));
  }, []);

  return (
    <main className="container">
      <h1 className="page-title">Request queue</h1>
      <p className="page-subtitle">
        Every request and its current status. Pending and flagged requests are waiting on
        a human decision.
      </p>

      {error && <div className="msg msg-error">{error}</div>}

      {!items && !error && <div className="skeleton">Loading requests…</div>}

      {items && items.length === 0 && (
        <div className="panel">
          <div className="empty">
            No requests yet. <Link href="/">Submit one</Link> to get started.
          </div>
        </div>
      )}

      {items && items.length > 0 && (
        <div className="panel" style={{ padding: 0 }}>
          <table className="queue-table">
            <thead>
              <tr>
                <th>Event</th>
                <th>Category</th>
                <th>Status</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <div className="queue-name">{item.name || "—"}</div>
                    <div className="queue-id">#{item.id}</div>
                  </td>
                  <td>{item.category || "—"}</td>
                  <td>
                    <StatusBadge status={item.status} />
                  </td>
                  <td className="muted" style={{ fontSize: 13 }}>
                    {formatTimestamp(item.created_at)}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <Link href={`/requests/${item.id}`}>
                      {isActionable(item.status) ? "Review" : "View"}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
