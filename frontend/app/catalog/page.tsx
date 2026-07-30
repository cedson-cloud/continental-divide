"use client";

import { useEffect, useState } from "react";
import { CatalogView, friendlyError, getCatalog } from "@/lib/api";
import { CatalogBrowser } from "@/components/CatalogBrowser";

export default function CatalogPage() {
  const [catalog, setCatalog] = useState<CatalogView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCatalog()
      .then(setCatalog)
      .catch((err) => setError(friendlyError(err)));
  }, []);

  return (
    <main className="container">
      <h1 className="page-title">Data dictionary</h1>
      <p className="page-subtitle">
        Every event this plan tracks: the sample plan plus events approved through
        this tool, with each entry marked by where it came from.
      </p>

      {error && <div className="msg msg-error">{error}</div>}
      {!error && !catalog && <p className="muted">Loading…</p>}
      {catalog && <CatalogBrowser catalog={catalog} />}
    </main>
  );
}
