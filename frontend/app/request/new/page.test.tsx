import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import GuidedRequestPage from "./page";

vi.mock("@/lib/api", () => ({
  getGovernanceProfile: vi.fn().mockResolvedValue({ destinations: [] }),
  friendlyError: (err: unknown) => String(err),
}));

afterEach(cleanup);

describe("GuidedRequestPage step 1", () => {
  it("tells a screen reader which kind of data is picked", () => {
    render(<GuidedRequestPage />);

    const revenue = screen.getByRole("button", { name: /Money \/ revenue/ });
    const action = screen.getByRole("button", { name: /Something a user did/ });
    expect(revenue).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(revenue);
    expect(revenue).toHaveAttribute("aria-pressed", "true");
    expect(action).toHaveAttribute("aria-pressed", "false");
  });
});
