import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Snippet } from "@/lib/api";
import { ForEngineers } from "./ForEngineers";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const BROWSER: Snippet = {
  surface: "browser",
  label: "In the browser",
  checked: "2026-10-15",
  sources: [
    "https://www.twilio.com/docs/segment/connections/sources/catalog/libraries/website/javascript",
  ],
  code: '// Analytics.js, @segment/analytics-next 1.84.3\n\nanalytics.track("Cart Cleared");\n',
};
const SERVER: Snippet = {
  ...BROWSER,
  surface: "server",
  label: "On your server",
  code: '// Node\n\nanalytics.track({\n  userId: "USER_ID",\n  event: "Cart Cleared",\n});\n',
};

function stubClipboard(writeText: (text: string) => Promise<void>) {
  vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });
}

describe("ForEngineers", () => {
  it("shows nothing before a request is approved", () => {
    const { container } = render(<ForEngineers snippets={[]} side="Client" />);
    expect(container.innerHTML).toBe("");
  });

  it("shows the one surface the request fires on", () => {
    render(<ForEngineers snippets={[BROWSER]} side="Client" />);
    expect(screen.getByRole("heading", { name: "For engineers" })).toBeTruthy();
    expect(screen.getByText(/It fires in the browser\./)).toBeTruthy();
    expect(screen.getByRole("heading", { name: "In the browser" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "On your server" })).toBeNull();
  });

  it("says why both are shown when the requester was unsure", () => {
    render(<ForEngineers snippets={[BROWSER, SERVER]} side="Unsure" />);
    expect(screen.getByText(/wasn't sure where it fires, so both are here/)).toBeTruthy();
    const titles = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(titles).toEqual(["In the browser", "On your server"]);
  });

  it("says the request doesn't say where it fires when it never did", () => {
    render(<ForEngineers snippets={[BROWSER, SERVER]} side={null} />);
    expect(screen.getByText(/doesn't say where it fires/)).toBeTruthy();
  });

  it("links the docs with the date checked", () => {
    render(<ForEngineers snippets={[SERVER]} side="Server" />);
    expect(screen.getByText(/Sources, checked 15 October 2026/)).toBeTruthy();
    const link = screen.getByRole("link", { name: /opens in a new tab/ });
    expect(link.getAttribute("href")).toBe(SERVER.sources[0]);
  });

  it("shows the code as written, in a region a keyboard can scroll", () => {
    render(<ForEngineers snippets={[SERVER]} side="Server" />);
    const code = screen.getByRole("region", { name: "On your server" });
    expect(code.tagName).toBe("PRE");
    expect(code.getAttribute("tabindex")).toBe("0");
    expect(code.textContent).toBe(SERVER.code);
  });

  it("copies exactly the snippet's code and says so", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    stubClipboard(writeText);
    render(<ForEngineers snippets={[BROWSER, SERVER]} side="Unsure" />);
    fireEvent.click(screen.getByRole("button", { name: "Copy code, on your server" }));
    await waitFor(() =>
      expect(screen.getByText("On your server code copied to the clipboard")).toBeTruthy(),
    );
    expect(writeText).toHaveBeenCalledWith(SERVER.code);
    expect(screen.getByRole("button", { name: "Copied, on your server" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Copy code, in the browser" })).toBeTruthy();
  });

  it("goes back to Copy code after a moment, so a second copy is announced", async () => {
    vi.useFakeTimers();
    try {
      stubClipboard(vi.fn().mockResolvedValue(undefined));
      render(<ForEngineers snippets={[BROWSER]} side="Client" />);
      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "Copy code, in the browser" }));
      });
      expect(screen.getByRole("button", { name: "Copied, in the browser" })).toBeTruthy();
      act(() => vi.advanceTimersByTime(2500));
      expect(screen.getByRole("button", { name: "Copy code, in the browser" })).toBeTruthy();
      expect(screen.queryByText(/copied to the clipboard/)).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("says what to do when the clipboard refuses", async () => {
    stubClipboard(vi.fn().mockRejectedValue(new Error("denied")));
    render(<ForEngineers snippets={[BROWSER]} side="Client" />);
    fireEvent.click(screen.getByRole("button", { name: "Copy code, in the browser" }));
    expect((await screen.findByRole("alert")).textContent).toMatch(
      /Select the code and copy it yourself/,
    );
  });
});
