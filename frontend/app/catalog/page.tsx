"use client";

import Link from "next/link";
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
      <h1 className="page-title">Tracking plan</h1>
      <p className="page-subtitle">
        Every event this plan tracks: a sample online store&apos;s plan, based on
        Segment&apos;s public Ecommerce events, plus events approved here. Each entry
        says where it came from.
      </p>
      <p className="catalog-guide-link">
        New to tracking plans? <Link href="/guide#tracking-plans">Read what one is</Link>{" "}
        and how to use this demo.
      </p>

      {error && <div className="msg msg-error">{error}</div>}
      {!error && !catalog && <div className="skeleton">Loading the plan…</div>}
      {catalog && <CatalogBrowser catalog={catalog} />}
    </main>
  );
}
