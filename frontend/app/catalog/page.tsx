"use client";

import { useEffect, useState } from "react";
import { CatalogView, friendlyError, getCatalog } from "@/lib/api";
import { CatalogBrowser } from "@/components/CatalogBrowser";
import { Icon } from "@/components/icons";

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

      <details className="catalog-intro">
        <summary>
          <Icon name="chevron" size={16} />
          New to tracking plans? Start here
        </summary>
        <div className="catalog-intro-body">
          <p>
            A tracking plan is the agreed list of what a product records about how
            people use it. Each entry is an event, named for something a person did,
            like <span className="mono">Product Added</span> or{" "}
            <span className="mono">Order Completed</span>. Its properties carry the
            details, like the product&apos;s <span className="mono">price</span>.
          </p>
          <p>
            Engineers read the plan to know exactly what to send. Analysts read it to
            know what each number means. Without one, the same action ends up tracked
            three ways under three names, and nobody trusts the dashboards built on
            it.
          </p>
          <p>
            This is the plan for a sample online store, based on Segment&apos;s public
            Ecommerce events. Open any event to see its properties. Events you request
            and approve here join it.
          </p>
        </div>
      </details>

      {error && <div className="msg msg-error">{error}</div>}
      {!error && !catalog && <div className="skeleton">Loading the plan…</div>}
      {catalog && <CatalogBrowser catalog={catalog} />}
    </main>
  );
}
