import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { NATURAL_LANGUAGE_EXAMPLES, RAW_EXAMPLES } from "@/lib/examples";
import GuidePage from "./page";

afterEach(cleanup);

describe("GuidePage", () => {
  it("walks a request through its steps in order", () => {
    render(<GuidePage />);
    const steps = screen.getByRole("heading", { name: "How a request moves" })
      .parentElement as HTMLElement;
    const titles = within(steps)
      .getAllByRole("heading", { level: 3 })
      .map((h) => h.textContent);
    expect(titles).toEqual(["Ask", "Check your draft", "Decide", "See the result", "Look back"]);
  });

  it("links each step to the screen it describes", () => {
    render(<GuidePage />);
    const hrefs = (name: string) =>
      screen.getAllByRole("link", { name }).map((a) => a.getAttribute("href"));
    expect(hrefs("New request")).toContain("/request");
    expect(hrefs("The guided request")).toEqual(["/request/new"]);
    expect(hrefs("Queue")).toEqual(["/queue"]);
    expect(hrefs("tracking plan")).toEqual(["/catalog"]);
  });

  it("gives the tracking plan explainer the anchor the plan page links to", () => {
    render(<GuidePage />);
    expect(screen.getByRole("heading", { name: "What a tracking plan is" })).toHaveAttribute(
      "id",
      "tracking-plans",
    );
  });

  it("states the demo's limits before a visitor runs into them", () => {
    render(<GuidePage />);
    const demo = screen.getByRole("heading", { name: "On the public demo" })
      .parentElement as HTMLElement;
    expect(demo).toHaveTextContent("A sandbox holds 5 requests");
    expect(demo).toHaveTextContent("A sandbox unused for 7 days is deleted");
    expect(demo).toHaveTextContent("Nothing is sent to Jira, Confluence or Notion.");
  });

  it("names each run exactly as its scenario tile does", () => {
    render(<GuidePage />);
    const tiles = [...NATURAL_LANGUAGE_EXAMPLES, ...RAW_EXAMPLES].map((ex) => ex.label);
    const runs = screen.getByRole("heading", { name: "Three runs worth trying" })
      .parentElement as HTMLElement;
    const names = Array.from(runs.querySelectorAll("dt")).map((dt) => dt.textContent);
    expect(names).toHaveLength(3);
    for (const name of names) expect(tiles).toContain(name);
  });
});
