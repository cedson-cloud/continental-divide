import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppNav } from "./AppNav";

const pathname = vi.hoisted(() => ({ current: "/" }));

vi.mock("next/navigation", () => ({
  usePathname: () => pathname.current,
}));

afterEach(cleanup);

function currentLinks(): string[] {
  return screen
    .getAllByRole("link")
    .filter((a) => a.getAttribute("aria-current") === "page")
    .map((a) => a.textContent ?? "");
}

describe("AppNav", () => {
  it.each([
    ["/guide", "How to use this"],
    ["/request", "New request"],
    ["/request/new", "New request"],
    ["/queue", "Queue"],
    ["/requests/15", "Queue"],
    ["/catalog", "Tracking plan"],
    ["/admin", "Governance"],
    ["/admin/setup", "Governance"],
  ])("marks only the right link as current on %s", (path, label) => {
    pathname.current = path;
    render(<AppNav />);
    expect(currentLinks()).toEqual([label]);
  });

  it("marks no link as current on the landing page, which the brand links to", () => {
    pathname.current = "/";
    render(<AppNav />);
    expect(currentLinks()).toEqual([]);
    expect(screen.getByRole("link", { name: /Continental Divide/ })).toHaveAttribute("href", "/");
  });

  it("lists the guide first, where a newcomer looks", () => {
    pathname.current = "/";
    render(<AppNav />);
    const links = screen.getByRole("navigation", { name: "Main" }).querySelectorAll("a");
    expect(links[0]).toHaveTextContent("How to use this");
    expect(links[0]).toHaveAttribute("href", "/guide");
  });

  it("opens the menu from the button and closes it when a link is chosen", () => {
    pathname.current = "/";
    render(<AppNav />);
    const button = screen.getByRole("button", { name: "Menu" });
    const nav = screen.getByRole("navigation", { name: "Main" });

    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(nav).not.toHaveClass("open");

    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(nav).toHaveClass("open");

    // jsdom cannot follow links; cancel the navigation and keep the click handler.
    document.addEventListener("click", (e) => e.preventDefault(), { once: true });
    fireEvent.click(screen.getByRole("link", { name: "Tracking plan" }));
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(nav).not.toHaveClass("open");
  });
});
