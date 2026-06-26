"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  RequestDetail,
  RuleCheck,
  decideRequest,
  friendlyError,
  getRequest,
} from "@/lib/api";
import { isActionable } from "@/lib/format";
import { AuditTimeline } from "@/components/AuditTimeline";
import { DefinitionView } from "@/components/DefinitionView";
import { PublishCards } from "@/components/PublishCards";
import { RuleChecks } from "@/components/RuleChecks";
import { StatusBadge } from "@/components/StatusBadge";

function evaluationFrom(detail: RequestDetail): { checks: RuleCheck[]; flags: string[] } {
  const entry = detail.audit_log.find((e) => e.step === "rules_evaluated");
  const d = entry?.detail || {};
  return {
    checks: (d.checks as RuleCheck[]) || [],
    flags: (d.flags as string[]) || [],
  };
}

export default function RequestDetailPage({ params }: { params: { id: string } }) {
  const id = Number(params.id);
  const [detail, setDetail] = useState<RequestDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [deciding, setDeciding] = useState(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);

  const load = useCallback(() => {
    getRequest(id)
      .then((d) => {
        setDetail(d);
        setLoadError(null);
      })
      .catch((err) => setLoadError(friendlyError(err)));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function decide(decision: "approve" | "reject") {
    setDeciding(true);
    setDecisionError(null);
    try {
      await decideRequest(id, decision, note);
      setNote("");
      load();
    } catch (err) {
      setDecisionError(friendlyError(err));
      load();
    } finally {
      setDeciding(false);
    }
  }

  if (loadError) {
    return (
      <main className="container">
        <Link className="back-link" href="/queue">
          ← Back to queue
        </Link>
        <div className="msg msg-error">{loadError}</div>
      </main>
    );
  }

  if (!detail) {
    return (
      <main className="container">
        <div className="skeleton">Loading request…</div>
      </main>
    );
  }

  const evaluation = evaluationFrom(detail);

  return (
    <main className="container">
      <Link className="back-link" href="/queue">
        ← Back to queue
      </Link>

      <div className="row spread">
        <h1 className="page-title" style={{ marginBottom: 0 }}>
          Request #{detail.id}
        </h1>
        <StatusBadge status={detail.status} />
      </div>
      <p className="page-subtitle" style={{ marginTop: 8 }}>
        {detail.raw_intake_text}
      </p>

      {detail.parsed_definition && (
        <div className="panel">
          <div className="panel-title">Definition</div>
          <DefinitionView definition={detail.parsed_definition} />
        </div>
      )}

      {evaluation.checks.length > 0 && (
        <div className="panel">
          <div className="panel-title">Evaluation</div>
          <RuleChecks checks={evaluation.checks} flags={evaluation.flags} />
        </div>
      )}

      {isActionable(detail.status) && (
        <div className="panel">
          <div className="panel-title">Decision</div>
          <input
            type="text"
            placeholder="Note (optional)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            disabled={deciding}
          />
          <div className="row mt-12">
            <button
              className="btn btn-approve"
              onClick={() => decide("approve")}
              disabled={deciding}
            >
              {deciding ? "Working…" : "Approve & publish"}
            </button>
            <button
              className="btn btn-reject"
              onClick={() => decide("reject")}
              disabled={deciding}
            >
              Reject
            </button>
          </div>
          {decisionError && <div className="msg msg-error mt-16">{decisionError}</div>}
        </div>
      )}

      {detail.published_artifact && (
        <div className="panel">
          <div className="panel-title">
            Published · via {detail.published_artifact.publisher} publisher
          </div>
          <PublishCards artifact={detail.published_artifact} />
        </div>
      )}

      <div className="panel">
        <div className="panel-title">Audit log</div>
        <AuditTimeline entries={detail.audit_log} />
      </div>
    </main>
  );
}
