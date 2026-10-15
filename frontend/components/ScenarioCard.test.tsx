import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { NATURAL_LANGUAGE_EXAMPLES, RAW_EXAMPLES } from "@/lib/examples";
import { ScenarioCard } from "./ScenarioCard";

afterEach(cleanup);

function renderCard(busy = false, status: string | null = null) {
  const onFill = vi.fn();
  const onRun = vi.fn();
  render(<ScenarioCard busy={busy} status={status} onFill={onFill} onRun={onRun} />);
  return { onFill, onRun };
}

describe("ScenarioCard", () => {
  it("shows every scenario without a click to reveal them", () => {
    renderCard();
    expect(screen.getByRole("heading", { name: "Try a scenario" })).toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(
      NATURAL_LANGUAGE_EXAMPLES.length + RAW_EXAMPLES.length,
    );
  });

  it("fills the form from a plain-language scenario and says so on the tile", () => {
    const { onFill, onRun } = renderCard();
    const tile = screen.getByRole("button", { name: "A clean request" });
    expect(tile).toHaveAccessibleDescription(/Fills in the form$/);

    fireEvent.click(tile);
    expect(onFill).toHaveBeenCalledWith(NATURAL_LANGUAGE_EXAMPLES[0]);
    expect(onRun).not.toHaveBeenCalled();
  });

  it("runs a pre-built definition straight through the rules and says so on the tile", () => {
    const { onFill, onRun } = renderCard();
    const tile = screen.getByRole("button", { name: "A badly named event" });
    expect(tile).toHaveAccessibleDescription(/Skips the model, goes straight to the rules$/);

    fireEvent.click(tile);
    expect(onRun).toHaveBeenCalledWith(RAW_EXAMPLES[0]);
    expect(onFill).not.toHaveBeenCalled();
  });

  it("disables every scenario while a request is in flight", () => {
    renderCard(true);
    for (const tile of screen.getAllByRole("button")) expect(tile).toBeDisabled();
  });

  it("announces what a fill did through a status region", () => {
    renderCard(false, "Filled the form with “Personal data”.");
    expect(screen.getByRole("status")).toHaveTextContent(
      "Filled the form with “Personal data”.",
    );
  });
});
