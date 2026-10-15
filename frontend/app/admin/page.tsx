"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Dispute,
  GovernanceProfileInfo,
  friendlyError,
  getGovernanceProfile,
  listDisputes,
} from "@/lib/api";
import { GovernanceProfile } from "@/components/GovernanceProfile";

export default function AdminPage() {
  const [profile, setProfile] = useState<GovernanceProfileInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [disputes, setDisputes] = useState<Dispute[]>([]);

  useEffect(() => {
    getGovernanceProfile()
      .then(setProfile)
      .catch((err) => setError(friendlyError(err)));
    // A failure here must not take down the profile view beside it.
    listDisputes()
      .then(setDisputes)
      .catch(() => setDisputes([]));
  }, []);

  return (
    <main className="container">
      <h1 className="page-title">Governance</h1>
      <p className="page-subtitle">
        The rules every request is checked against. This page shows what the engine
        enforces right now, and changes nothing.
      </p>
      <p className="gov-setup-link">
        <Link href="/admin/setup">Draft a new profile</Link>
      </p>

      {error && <div className="msg msg-error">{error}</div>}

      {!profile && !error && <div className="skeleton">Loading profile…</div>}

      {profile && <GovernanceProfile profile={profile} disputes={disputes} />}
    </main>
  );
}
