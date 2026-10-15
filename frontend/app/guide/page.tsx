import Link from "next/link";

// The newcomer's map of the app (TASKS D11). Every step links to the screen it
// describes, and the demo's limits are stated here before a visitor runs into them.
const STEPS: { title: string; role?: string; body: React.ReactNode }[] = [
  {
    title: "Ask",
    role: "You're the requester",
    body: (
      <>
        On <Link href="/">New request</Link>, describe in a sentence what someone did and
        why it matters. Not sure what to write? <Link href="/request/new">The guided
        request</Link> asks one question at a time, and Try a scenario fills the form for
        you.
      </>
    ),
  },
  {
    title: "Check your draft",
    role: "You're the requester",
    body: (
      <>
        A model turns your sentence into a named event with properties. Fixed rules then
        check the name, the category, personal data, and whether the plan already has it.
        A name that breaks the convention is rejected, and you&apos;re offered one that
        passes. Personal data and duplicates are never rejected: they&apos;re flagged for
        a person to look at. A model also looks for events that mean the same thing; it
        can point one out, but it never rejects. Nothing reaches the approver until you
        submit.
      </>
    ),
  },
  {
    title: "Decide",
    role: "You're the approver",
    body: (
      <>
        Open the <Link href="/queue">Queue</Link>. Requests waiting on a decision come
        first. Read the checks, then approve or reject. Personal data and likely
        duplicates each need a tick before Approve works.
      </>
    ),
  },
  {
    title: "See the result",
    body: (
      <>
        An approved event is published. It joins the{" "}
        <Link href="/catalog">tracking plan</Link>, and the request shows engineers the
        Segment code to send it, for the browser, the server, or both.
      </>
    ),
  },
  {
    title: "Look back",
    body: (
      <>
        Every step is written to the request&apos;s audit trail, which nothing can edit.
        Open any request from the Queue to read its trail.
      </>
    ),
  },
];

const RUNS: { name: string; what: string }[] = [
  {
    name: "A clean request",
    what:
      "Fills the form. Add your name and team, draft it, submit it, then approve it " +
      "from the queue. The draft should pass every rule, and the event joins the tracking plan.",
  },
  {
    name: "A badly named event",
    what:
      "Skips the model. The event name rule rejects it, and you're offered a name the " +
      "convention accepts, or a way to dispute the rule.",
  },
  {
    name: "An event that already exists",
    what:
      "Skips the model. It goes straight to the queue, where the approver has to " +
      "acknowledge the duplicate before approving.",
  },
];

const DEMO_FACTS = [
  "Your sandbox is private to this browser. There's no sign-in, and nobody else sees your requests.",
  "A sandbox holds 5 requests, made either way: drafted by the model or from a scenario that skips it.",
  "Drafting shares one daily model budget across every visitor. If it runs out, the scenarios that skip the model still work.",
  "Nothing is sent to Jira, Confluence or Notion. A published request shows what a connected setup would write.",
  "Every approval is recorded as a self-approval, because you made the request you're approving. In a real team, someone else approves.",
  "A sandbox unused for 7 days is deleted, with its requests and audit trail.",
];

const WORDS: { term: string; meaning: string }[] = [
  {
    term: "Event",
    meaning: "Something a person did, named Object Action in Title Case, like Order Completed.",
  },
  { term: "Property", meaning: "A detail sent with an event, like an order's total." },
  {
    term: "Where it happens",
    meaning:
      "In the browser or app means on the person's own device. On our servers means your " +
      "backend records it. Engineers call this the surface: client side or server side.",
  },
  {
    term: "Draft",
    meaning: "A request that passed the rules but that you haven't submitted yet. It's in nobody's queue.",
  },
  { term: "Pending approval", meaning: "Submitted, and waiting on the approver." },
  {
    term: "Published",
    meaning: "Approved and written out: it's in the tracking plan.",
  },
  {
    term: "Rule check",
    meaning:
      "One of the fixed rules every draft is checked against. A failed name or category " +
      "rule rejects the request. Personal data and duplicates are flagged for a person, " +
      "never rejected, and a model never rejects.",
  },
  {
    term: "Duplicate",
    meaning:
      "An event the plan may already have. The rules catch the same name, or the same " +
      "name written differently; the duplicate review is a model reading whether one " +
      "means the same thing under another name. A person decides what to do about each.",
  },
  {
    term: "Governance profile",
    meaning:
      "The conventions, categories and personal-data list requests are checked against. " +
      "See it under Governance.",
  },
];

export default function GuidePage() {
  return (
    <main className="container">
      <h1 className="page-title">How to use this</h1>
      <p className="page-subtitle">
        Continental Divide is where a team agrees what its product records. You ask for an
        event in plain words, fixed rules check it, a person approves it, and it joins the
        tracking plan with code for engineers. In this demo you play every part.
      </p>

      <section className="panel guide-section" aria-labelledby="tracking-plans">
        <h2 id="tracking-plans" className="panel-title">
          What a tracking plan is
        </h2>
        <div className="guide-prose">
          <p>
            A tracking plan is the agreed list of what a product records about how people
            use it. Each entry is an event, named for something a person did, like{" "}
            <span className="mono">Product Added</span> or{" "}
            <span className="mono">Order Completed</span>. Its properties carry the
            details, like the product&apos;s <span className="mono">price</span>.
          </p>
          <p>
            Engineers read the plan to know exactly what to send. Analysts read it to know
            what each number means. Without one, the same action ends up tracked three ways
            under three names, and nobody trusts the dashboards built on it.
          </p>
          <p>
            The plan here belongs to a sample online store, based on Segment&apos;s public
            Ecommerce events. Events you request and approve join it.{" "}
            <Link href="/catalog">Open the tracking plan</Link>.
          </p>
        </div>
      </section>

      <section className="panel guide-section" aria-labelledby="guide-steps">
        <h2 id="guide-steps" className="panel-title">
          How a request moves
        </h2>
        <ol className="guide-steps" role="list">
          {STEPS.map((step) => (
            <li key={step.title} className="guide-step">
              <div className="guide-step-head">
                <h3 className="guide-step-title">{step.title}</h3>
                {step.role && <span className="guide-step-role">{step.role}</span>}
              </div>
              <p className="guide-step-body">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="panel guide-section" aria-labelledby="guide-runs">
        <h2 id="guide-runs" className="panel-title">
          Three runs worth trying
        </h2>
        <p className="panel-sub">
          Each is a tile under Try a scenario on <Link href="/">New request</Link>.
        </p>
        <dl className="guide-runs">
          {RUNS.map((run) => (
            <div key={run.name} className="guide-run">
              <dt>{run.name}</dt>
              <dd>{run.what}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="panel guide-section" aria-labelledby="guide-demo">
        <h2 id="guide-demo" className="panel-title">
          On the public demo
        </h2>
        <ul className="guide-facts">
          {DEMO_FACTS.map((fact) => (
            <li key={fact}>{fact}</li>
          ))}
        </ul>
      </section>

      <section className="panel guide-section" aria-labelledby="guide-words">
        <h2 id="guide-words" className="panel-title">
          Words you&apos;ll see
        </h2>
        <dl className="guide-words">
          {WORDS.map((word) => (
            <div key={word.term} className="guide-word">
              <dt>{word.term}</dt>
              <dd>{word.meaning}</dd>
            </div>
          ))}
        </dl>
      </section>
    </main>
  );
}
