"use client";

import { useEffect, useState } from "react";
import { Snippet } from "@/lib/api";
import { SourceLinks } from "./PlatformDetails";

// Engineering's half of the output (ADR 0008): the approved definition as code for
// each surface it fires on. The server renders the code; this only shows and copies it.
export function ForEngineers({
  snippets,
  side,
}: {
  snippets: Snippet[];
  side: string | null;
}) {
  if (snippets.length === 0) return null;
  return (
    <section className="panel" aria-labelledby="engineers-title">
      <h2 className="panel-title" id="engineers-title">
        For engineers
      </h2>
      <p className="panel-sub">
        Code for this request, built from the approved definition by a fixed
        template, not by a model. {whereItFires(snippets, side)}
      </p>
      {snippets.map((snippet) => (
        <SnippetView key={snippet.surface} snippet={snippet} />
      ))}
    </section>
  );
}

function whereItFires(snippets: Snippet[], side: string | null): string {
  if (snippets.length === 1) {
    return snippets[0].surface === "browser"
      ? "It fires in the browser."
      : "It fires on your server.";
  }
  const reason =
    side === "Unsure"
      ? "The requester wasn't sure where it fires"
      : "The request doesn't say where it fires";
  return `${reason}, so both are here: use the one for where it happens.`;
}

function SnippetView({ snippet }: { snippet: Snippet }) {
  const [copy, setCopy] = useState<"idle" | "copied" | "failed">("idle");
  const titleId = `snippet-${snippet.surface}`;
  const action = copy === "copied" ? "Copied" : "Copy code";

  // Back to "Copy code" after a moment, so a second copy is announced again.
  useEffect(() => {
    if (copy !== "copied") return;
    const timer = setTimeout(() => setCopy("idle"), 2500);
    return () => clearTimeout(timer);
  }, [copy]);

  async function onCopy() {
    try {
      await navigator.clipboard.writeText(snippet.code);
      setCopy("copied");
    } catch {
      setCopy("failed");
    }
  }

  return (
    <div className="snippet">
      <div className="snippet-head">
        {/* The library, version and date checked lead the code itself (ADR 0008). */}
        <h3 className="snippet-title" id={titleId}>
          {snippet.label}
        </h3>
        <button
          type="button"
          className="btn btn-ghost snippet-copy"
          onClick={onCopy}
          aria-label={`${action}, ${snippet.label.toLowerCase()}`}
        >
          {action}
        </button>
      </div>
      {/* Focusable so a keyboard can scroll a long line sideways. */}
      <pre className="snippet-code" role="region" tabIndex={0} aria-labelledby={titleId}>
        <code>
          {snippet.code.replace(/\n$/, "").split("\n").map((line, i) => (
            <span key={i} className={line.startsWith("//") ? "snippet-comment" : undefined}>
              {line}
              {"\n"}
            </span>
          ))}
        </code>
      </pre>
      <p className="visually-hidden" aria-live="polite">
        {copy === "copied" ? `${snippet.label} code copied to the clipboard` : ""}
      </p>
      {copy === "failed" && (
        <p className="msg msg-error mt-12" role="alert">
          Couldn&apos;t copy to the clipboard. Select the code and copy it yourself.
        </p>
      )}
      <SourceLinks sources={snippet.sources} checked={snippet.checked} />
    </div>
  );
}
