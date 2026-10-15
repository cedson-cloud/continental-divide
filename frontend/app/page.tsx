import Link from "next/link";
import {
  ADR_INDEX_URL,
  NOTHING_SENT,
  REPO_URL,
  SANDBOX_DELETED,
  SANDBOX_REQUESTS,
  adrUrl,
} from "@/lib/demo";

// The landing page (TASKS D6). It calls no API: a visitor who reads and leaves never
// opens a sandbox, so only Try it counts against the hourly cap (ADR 0010).

// The ridge's vertices on a 1000-wide viewBox, as [x, y].
const RIDGE_POINTS: [number, number][] = [
  [0, 200], [60, 188], [100, 178], [150, 170], [200, 150], [250, 140], [300, 124],
  [350, 112], [390, 84], [430, 70], [470, 50], [500, 38], [540, 30], [580, 40],
  [620, 28], [660, 36], [700, 40], [740, 72], [780, 96], [820, 120], [860, 146],
  [900, 166], [950, 180], [1000, 192],
];

// Each step sits on a ridge vertex. x is the centre of its label's column in
// .landing-crossing (10%, 30%, ... of the width), so a dot sits above its label.
const CROSSING: { step: string; what: string; x: number; crest?: boolean }[] = [
  { step: "Ask", what: "in plain words", x: 100 },
  { step: "Draft", what: "a model writes it", x: 300 },
  { step: "Check", what: "fixed rules", x: 500, crest: true },
  { step: "Approve", what: "a person decides", x: 700, crest: true },
  { step: "Publish", what: "into the tracking plan", x: 900 },
];

const crestFrom = CROSSING.find((c) => c.crest)!.x;
const crestTo = CROSSING.findLast((c) => c.crest)!.x;

function line(points: [number, number][]): string {
  return points.map(([x, y], i) => `${i ? "L" : "M"}${x} ${y}`).join(" ");
}

function ridgeHeight(x: number): number {
  return RIDGE_POINTS.find((p) => p[0] === x)![1];
}

const RIDGE = line(RIDGE_POINTS);
const CREST = line(RIDGE_POINTS.filter(([x]) => x >= crestFrom && x <= crestTo));

const STORY: { title: string; body: string }[] = [
  {
    title: "Ask",
    body: "Someone in marketing asks, in plain English, for something they want to measure.",
  },
  {
    title: "Already there",
    body:
      "The tool shows them the plan already has it. They take the existing event, no new " +
      "event is made, and the audit trail records why.",
  },
  {
    title: "Approve",
    body:
      "When they ask for something new, the approver decides on one screen, after ticking " +
      "off any personal data or likely duplicate.",
  },
  {
    title: "Ship",
    body:
      "Engineers get the Segment code to send it. Everyone else gets a tracking plan entry " +
      "that says what it means.",
  },
];

const DECISIONS: { file: string; title: string; why: string }[] = [
  {
    file: "0001-three-tiers-of-duplicate-detection",
    title: "Duplicate detection has three tiers",
    why:
      "The same name, the same name written differently, and a different name for the " +
      "same behaviour. Who catches each, and what each may ask of a person.",
  },
  {
    file: "0008-snippets-are-deterministic-and-per-surface",
    title: "Snippets are deterministic and per surface",
    why: "No model writes code. One approved definition gives one snippet per surface, the same every time.",
  },
  {
    file: "0010-a-public-demo-gives-each-visitor-a-private-sandbox",
    title: "A public demo gives each visitor a private sandbox",
    why: "Strangers draft with a paid model, so each visitor gets a separate database, with limits that keep the demo safe to host.",
  },
];

function Divide() {
  return (
    <figure className="landing-divide">
      <svg
        className="landing-ridge"
        viewBox="0 0 1000 220"
        aria-hidden="true"
        focusable="false"
      >
        <path className="landing-ridge-ground" d={`${RIDGE} L1000 220 L0 220 Z`} />
        <path className="landing-ridge-line" d={RIDGE} pathLength={1} />
        <path className="landing-ridge-crest" d={CREST} pathLength={1} />
        {CROSSING.map((c) => (
          <circle
            key={c.step}
            className={c.crest ? "landing-ridge-dot crest" : "landing-ridge-dot"}
            cx={c.x}
            cy={ridgeHeight(c.x)}
            r={8}
          />
        ))}
      </svg>
      <ol className="landing-crossing" aria-label="How a request crosses">
        {CROSSING.map((c) => (
          <li key={c.step} className={c.crest ? "crest" : undefined}>
            <span className="landing-crossing-step">{c.step}</span>
            <span className="visually-hidden">: </span>
            <span className="landing-crossing-what">{c.what}</span>
          </li>
        ))}
      </ol>
      <figcaption className="landing-divide-caption">
        The model only drafts. Fixed rules and a person decide what crosses.
      </figcaption>
    </figure>
  );
}

export default function LandingPage() {
  return (
    <main className="container landing">
      <section className="landing-hero" aria-labelledby="landing-title">
        <p className="landing-byline">A portfolio project by Calvin Edson</p>
        <h1 id="landing-title" className="landing-title">
          Tracking requests in plain English, decided by rules and a person
        </h1>
        <p className="landing-lede">
          Anyone on a team can ask for a new analytics event in a sentence. A model drafts the
          definition, fixed rules check it, a person approves it, and it joins the tracking
          plan with code for engineers. Every step goes into an audit trail that nothing can
          edit.
        </p>
        <div className="landing-actions">
          <Link href="/request" className="btn btn-primary landing-try">
            Try it
          </Link>
          <Link href="/guide" className="btn landing-guide">
            How to use this
          </Link>
        </div>
        <p className="landing-terms">
          No sign-up. Your sandbox is private to this browser and holds {SANDBOX_REQUESTS}{" "}
          requests. {NOTHING_SENT} {SANDBOX_DELETED}
        </p>
      </section>

      <Divide />

      <section className="panel landing-story" aria-labelledby="landing-story-title">
        <h2 id="landing-story-title" className="panel-title">
          The 60-second story
        </h2>
        <ol className="guide-steps" role="list">
          {STORY.map((beat) => (
            <li key={beat.title} className="guide-step">
              <div className="guide-step-head">
                <h3 className="guide-step-title">{beat.title}</h3>
              </div>
              <p className="guide-step-body">{beat.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <div className="landing-more">
        <section aria-labelledby="landing-new-title">
          <h2 id="landing-new-title" className="landing-more-title">
            New to tracking plans?
          </h2>
          <p>
            Start with <Link href="/guide#tracking-plans">what a tracking plan is</Link> and
            why a team keeps one. The guide also walks a request through each step and
            explains the words you&apos;ll meet here.
          </p>
        </section>
        <section aria-labelledby="landing-built-title">
          <h2 id="landing-built-title" className="landing-more-title">
            Built in the open
          </h2>
          <p>
            The <a href={REPO_URL}>code is on GitHub</a>. Each design decision has a written
            record of why it was made and what it ruled out. Three to start with:
          </p>
          <ul className="landing-decisions">
            {DECISIONS.map((d) => (
              <li key={d.file}>
                <a href={adrUrl(d.file)}>{d.title}</a>
                <span>{d.why}</span>
              </li>
            ))}
          </ul>
          <p>
            <a href={ADR_INDEX_URL}>Every decision record</a>
          </p>
        </section>
      </div>
    </main>
  );
}
