import Link from "next/link";
import { Dispute, GovernanceProfileInfo } from "@/lib/api";
import { ruleLabel, sourceHost, statusMeta } from "@/lib/format";
import { DESTINATIONS, choiceLabel, conventionLabel } from "@/lib/governance";
import { Icon } from "./icons";

// The identifier an engineer would search the profile's YAML for.
function InProfile({ path, value }: { path: string; value: string }) {
  return (
    <p className="gov-id">
      In the profile: <span className="mono">{path}: {value}</span>
    </p>
  );
}

function Convention({ convention }: { convention: string }) {
  const { label, example } = conventionLabel(convention);
  return (
    <p className="gov-rule">
      <strong>{label}</strong>
      {example && (
        <>
          , like <span className="mono">{example}</span>
        </>
      )}
      .
    </p>
  );
}

function Disputes({ disputes }: { disputes: Dispute[] }) {
  if (disputes.length === 0) {
    return <p className="gov-empty">No disputes on record.</p>;
  }
  return (
    <ul className="gov-disputes">
      {disputes.map((dispute) => (
        <li className="check" key={`${dispute.request_id}-${dispute.created_at}`}>
          <span className="check-mark advisory" role="img" aria-label="disputed">
            <Icon name="flag" size={12} />
          </span>
          <div>
            <p className="gov-dispute-head">
              <span className="check-rule">{ruleLabel(dispute.rule)}</span>{" "}
              <span className="check-detail">{dispute.note}</span>
            </p>
            <p className="gov-dispute-meta">
              <Link href={`/requests/${dispute.request_id}`}>
                Request #{dispute.request_id}
              </Link>
              {dispute.event_name && <span className="mono">{dispute.event_name}</span>}
              <span>{statusMeta(dispute.request_status).label}</span>
              <span>
                Profile{" "}
                <span className="mono">
                  {dispute.profile} {dispute.profile_digest}
                </span>
              </span>
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}

export function GovernanceProfile({
  profile,
  disputes,
}: {
  profile: GovernanceProfileInfo;
  disputes: Dispute[];
}) {
  return (
    <>
      <section className="panel" aria-labelledby="gov-active">
        <h2 id="gov-active" className="panel-title">
          Active profile
        </h2>
        <p className="gov-profile-name mono">{profile.name}</p>
        {profile.source && (
          <p className="gov-id">
            Convention from{" "}
            <a href={profile.source} target="_blank" rel="noreferrer">
              {sourceHost(profile.source)}
              <span className="visually-hidden"> (opens in a new tab)</span>
            </a>
          </p>
        )}
      </section>

      <section className="panel" aria-labelledby="gov-events">
        <h2 id="gov-events" className="panel-title">
          Event names
        </h2>
        <Convention convention={profile.event_naming.convention} />
        <InProfile path="event_naming.convention" value={profile.event_naming.convention} />
        <p className="panel-sub gov-examples-lede">
          Example names, checked against this rule when the page loaded. They show
          what the rule accepts and rejects; they aren&apos;t events in any plan.
        </p>
        <ul className="checks gov-examples">
          {profile.examples.map((example) => (
            <li className="check" key={example.name}>
              <span
                className={`check-mark ${example.passes ? "pass" : "fail"}`}
                role="img"
                aria-label={example.passes ? "passes" : "fails"}
              >
                <Icon name={example.passes ? "check" : "close"} size={12} />
              </span>
              <span>
                <span className="check-rule mono">{example.name}</span>
                {example.reason && <span className="check-detail"> {example.reason}</span>}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="panel" aria-labelledby="gov-properties">
        <h2 id="gov-properties" className="panel-title">
          Property names
        </h2>
        <Convention convention={profile.property_naming.convention} />
        <InProfile
          path="property_naming.convention"
          value={profile.property_naming.convention}
        />
      </section>

      <section className="panel" aria-labelledby="gov-pii">
        <h2 id="gov-pii" className="panel-title">
          Personal data
        </h2>
        <p className="gov-rule">
          <strong>Flagged, never rejected.</strong> A property or trait whose name contains
          one of these words is flagged. Before the request moves on, the requester writes
          a reason for each one, and an approver acknowledges them before approving.
        </p>
        <InProfile path="pii.mode" value={profile.pii.mode} />
        <ul className="gov-tags">
          {profile.pii.blocklist.map((entry) => (
            <li className="tag" key={entry}>
              {entry}
            </li>
          ))}
        </ul>
      </section>

      <section className="panel" aria-labelledby="gov-categories">
        <h2 id="gov-categories" className="panel-title">
          Categories
        </h2>
        {profile.categories.source === "sample_plan" && (
          <p className="panel-sub">
            This profile names no categories of its own, so requests use the sample
            tracking plan&apos;s.
          </p>
        )}
        <ul className="gov-tags">
          {profile.categories.values.map((category) => (
            <li className="tag tag-text" key={category}>
              {category}
            </li>
          ))}
        </ul>
      </section>

      <section className="panel" aria-labelledby="gov-destinations">
        <h2 id="gov-destinations" className="panel-title">
          Destinations
        </h2>
        {profile.destinations.length === 0 ? (
          <p className="panel-sub">
            The profile names no destinations, so a request may send its data anywhere.
          </p>
        ) : (
          <>
            <p className="panel-sub">Requests may only send event data to these.</p>
            <ul className="gov-tags">
              {profile.destinations.map((destination) => (
                <li className="tag tag-text" key={destination}>
                  {choiceLabel(DESTINATIONS, destination)}
                </li>
              ))}
            </ul>
            <InProfile path="destinations" value={`[${profile.destinations.join(", ")}]`} />
          </>
        )}
      </section>

      <section className="panel" aria-labelledby="gov-disputes">
        <h2 id="gov-disputes" className="panel-title">
          Rule disputes
        </h2>
        <p className="panel-sub">
          Requesters who think a rule is wrong for their team. A record, not a workflow:
          nothing here changes a rule. A rule changes in the profile, by a person, in a
          reviewed commit.
        </p>
        <Disputes disputes={disputes} />
      </section>

      <p className="gov-footnote">
        The profile is a file in the repo, <span className="mono">governance/active.yaml</span>.
        This page reads it and never writes it. On the public demo it stays fixed.
      </p>
    </>
  );
}
