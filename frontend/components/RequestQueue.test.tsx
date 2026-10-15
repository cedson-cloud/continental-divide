import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { QueueItem } from "@/lib/api";
import { RequestQueue } from "./RequestQueue";

afterEach(cleanup);

function item(overrides: Partial<QueueItem>): QueueItem {
  return {
    id: 1,
    name: "Cart Cleared",
    call_type: "track",
    category: "Ordering",
    status: "pending_approval",
    created_at: "2026-10-15 09:00:00",
    ...overrides,
  };
}

describe("RequestQueue", () => {
  it("sends an empty sandbox to a new request instead of leaving it blank", () => {
    render(<RequestQueue items={[]} />);

    expect(screen.getByRole("heading", { name: "No requests yet" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "New request" })).toHaveAttribute("href", "/");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("shows what is waiting on a decision in its own table, above everything else", () => {
    render(
      <RequestQueue
        items={[
          item({ id: 1, name: "Order Completed", status: "published" }),
          item({ id: 2, name: "Cart Cleared", status: "pending_approval" }),
        ]}
      />,
    );

    const [waiting, others] = screen.getAllByRole("table");
    expect(waiting).toHaveAccessibleName("Waiting on a decision");
    expect(within(waiting).getByRole("link", { name: "Cart Cleared #2" })).toHaveAttribute(
      "href",
      "/requests/2",
    );
    expect(others).toHaveAccessibleName("Everything else");
    expect(within(others).getByText("Published")).toBeInTheDocument();
    expect(
      screen.getByText("1 waiting on a decision, 2 requests in total."),
    ).toBeInTheDocument();
  });

  it("names a request that couldn't be drafted by its number", () => {
    render(<RequestQueue items={[item({ id: 7, name: null, category: null, status: "draft_failed" })]} />);

    expect(screen.getByRole("table")).toHaveAccessibleName("All requests");
    expect(screen.getByRole("link", { name: "Request #7" })).toHaveAttribute(
      "href",
      "/requests/7",
    );
    expect(screen.getByText("Couldn't draft")).toBeInTheDocument();
    expect(screen.getByText("No category")).toBeInTheDocument();
  });
});
