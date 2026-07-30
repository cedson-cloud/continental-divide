import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { EventPicker } from "./EventPicker";

vi.mock("@/lib/api", () => ({
  getCatalog: vi.fn().mockResolvedValue({
    events: [
      { name: "Cart Viewed", category: "Core Ordering" },
      { name: "Products Searched", category: "Browsing" },
    ],
    shapes: {},
    counts: {
      total: 2,
      from_sample_plan: 2,
      new_events_from_requests: 0,
      property_additions_merged: 0,
      unresolved_targets: 0,
    },
  }),
}));

afterEach(cleanup);

function input(): HTMLInputElement {
  return screen.getByPlaceholderText("e.g. Order Completed");
}

async function optionValues(): Promise<string[]> {
  await waitFor(() =>
    expect(document.querySelectorAll("option").length).toBeGreaterThan(0),
  );
  return [...document.querySelectorAll("option")].map((o) =>
    o.getAttribute("value"),
  ) as string[];
}

describe("EventPicker", () => {
  it("renders the catalog's event names as datalist options", async () => {
    render(<EventPicker value="" onChange={() => {}} />);

    expect(await optionValues()).toEqual(["Cart Viewed", "Products Searched"]);
    // The options belong to the datalist the input points at.
    expect(input().getAttribute("list")).toBe(
      document.querySelector("datalist")?.id,
    );
  });

  it("allows a typed value that is not in the list", async () => {
    // Deliberate: a requester may know about an event the catalog does not
    // have yet, so the picker is a free-text input over a datalist, not a select.
    render(<EventPicker value="Totally New Event" onChange={() => {}} />);

    expect((await optionValues()).includes("Totally New Event")).toBe(false);
    expect(input().value).toBe("Totally New Event");
  });

  it("calls onChange with the typed value", async () => {
    const onChange = vi.fn();
    render(<EventPicker value="" onChange={onChange} />);
    await optionValues();

    fireEvent.change(input(), { target: { value: "Totally New Event" } });
    expect(onChange).toHaveBeenCalledWith("Totally New Event");
  });
});
