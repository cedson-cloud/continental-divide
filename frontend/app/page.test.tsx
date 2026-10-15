import { existsSync } from "fs";
import path from "path";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ADR_INDEX_URL, REPO_URL } from "@/lib/demo";
import LandingPage from "./page";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("LandingPage", () => {
  it("sends Try it to the request form and offers the guide beside it", () => {
    render(<LandingPage />);
    expect(screen.getByRole("link", { name: "Try it" })).toHaveAttribute("href", "/request");
    expect(screen.getByRole("link", { name: "How to use this" })).toHaveAttribute(
      "href",
      "/guide",
    );
  });

  it("opens no sandbox for a visitor who only reads", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(<LandingPage />);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("states the sandbox's terms, including the 7-day deletion", () => {
    render(<LandingPage />);
    const hero = screen.getByRole("heading", { level: 1 }).parentElement as HTMLElement;
    expect(hero).toHaveTextContent("private to this browser and holds 5 requests");
    expect(hero).toHaveTextContent("Nothing is sent to Jira, Confluence or Notion.");
    expect(hero).toHaveTextContent(
      "A sandbox unused for 7 days is deleted, with its requests and audit trail.",
    );
  });

  it("shows a request crossing the divide, with the rules and the person on the crest", () => {
    const { container } = render(<LandingPage />);
    const crossing = screen.getByRole("list", { name: "How a request crosses" });
    const steps = within(crossing)
      .getAllByRole("listitem")
      .map((li) => li.querySelector(".landing-crossing-step")?.textContent);
    expect(steps).toEqual(["Ask", "Draft", "Check", "Approve", "Publish"]);
    const crest = Array.from(crossing.querySelectorAll("li.crest .landing-crossing-step")).map(
      (s) => s.textContent,
    );
    expect(crest).toEqual(["Check", "Approve"]);
    expect(container.querySelector(".landing-ridge")).toHaveAttribute("aria-hidden", "true");
  });

  it("tells the 60-second story in order", () => {
    render(<LandingPage />);
    const story = screen.getByRole("heading", { name: "The 60-second story" })
      .parentElement as HTMLElement;
    const beats = within(story)
      .getAllByRole("heading", { level: 3 })
      .map((h) => h.textContent);
    expect(beats).toEqual(["Ask", "Already there", "Approve", "Ship"]);
  });

  it("links to the guide's explainer rather than repeating it", () => {
    render(<LandingPage />);
    expect(screen.getByRole("link", { name: "what a tracking plan is" })).toHaveAttribute(
      "href",
      "/guide#tracking-plans",
    );
  });

  it("links the repo, the decision records, and only records that exist", () => {
    render(<LandingPage />);
    expect(screen.getByRole("link", { name: "code is on GitHub" })).toHaveAttribute(
      "href",
      REPO_URL,
    );
    expect(screen.getByRole("link", { name: "Every decision record" })).toHaveAttribute(
      "href",
      ADR_INDEX_URL,
    );
    const adrLinks = screen
      .getAllByRole("link")
      .map((a) => a.getAttribute("href") ?? "")
      .filter((href) => href.includes("/docs/adr/") && href.endsWith(".md"));
    expect(adrLinks).toHaveLength(3);
    for (const href of adrLinks) {
      const file = href.split("/docs/adr/")[1];
      expect(existsSync(path.resolve(__dirname, "../../docs/adr", file))).toBe(true);
    }
  });
});
