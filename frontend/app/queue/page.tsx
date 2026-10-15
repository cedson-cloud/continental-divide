"use client";

import { useEffect, useState } from "react";
import { QueueItem, friendlyError, listRequests } from "@/lib/api";
import { RequestQueue } from "@/components/RequestQueue";

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
      <span className="role-hint page-role-hint">You&apos;re the approver</span>
      <h1 className="page-title">Request queue</h1>
      <p className="page-subtitle">
        Requests waiting on a decision come first. Open one to approve or reject it.
        In this demo you play both parts: you made these requests, and you decide them.
      </p>

      {error && <div className="msg msg-error">{error}</div>}

      {!items && !error && <div className="skeleton">Loading requests…</div>}

      {items && <RequestQueue items={items} />}
    </main>
  );
}
