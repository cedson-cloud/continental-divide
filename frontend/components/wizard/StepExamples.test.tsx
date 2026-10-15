import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { examplesForKind } from "@/lib/examples";
import type { DataKind } from "@/lib/wizard";
import { StepExamples } from "./StepExamples";

afterEach(cleanup);

function renderStep(kind: DataKind, busy = false, status: string | null = null) {
  const onFill = vi.fn();
  render(<StepExamples kind={kind} busy={busy} status={status} onFill={onFill} />);
  return { onFill };
}

describe("StepExamples", () => {
  it("shows the examples for the kind picked in step 1", () => {
    renderStep("revenue");
    expect(
      screen.getByRole("heading", { name: "Start from an example" }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("button").map((b) => b.textContent)).toEqual([
      expect.stringContaining("A new subscription"),
      expect.stringContaining("A refund"),
    ]);
    expect(screen.queryByRole("button", { name: "A clean request" })).toBeNull();
  });

  it("fills this step from an example and says so on the tile", () => {
    const { onFill } = renderStep("revenue");
    const tile = screen.getByRole("button", { name: "A refund" });
    expect(tile).toHaveAccessibleDescription(/Order Refunded.*Fills in this step$/);

    fireEvent.click(tile);
    expect(onFill).toHaveBeenCalledWith(examplesForKind("revenue")[1]);
  });

  it("disables every example while the draft is in flight", () => {
    renderStep("unknown", true);
    for (const tile of screen.getAllByRole("button")) expect(tile).toBeDisabled();
  });

  it("announces what a fill did through a status region", () => {
    renderStep("user_trait", false, "Filled this step with “A plan change”.");
    expect(screen.getByRole("status")).toHaveTextContent(
      "Filled this step with “A plan change”.",
    );
  });
});
