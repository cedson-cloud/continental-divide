import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { DefinitionView } from "./DefinitionView";

afterEach(cleanup);

describe("DefinitionView", () => {
  it("shows an identify definition as the identify call and lists its traits", () => {
    render(
      <DefinitionView
        definition={{
          call_type: "identify",
          name: null,
          category: null,
          description: "Facts about a person, sent when they register.",
          properties: [],
          traits: [
            { name: "email", type: "string", required: false, items: null },
            { name: "plan_tier", type: "string", required: true, items: null },
          ],
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Identify traits" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Trait" })).toBeTruthy();
    expect(screen.getByRole("cell", { name: "plan_tier" })).toBeTruthy();
    expect(screen.getByText("identify")).toBeTruthy();
  });

  it("names a group definition by its group type", () => {
    render(
      <DefinitionView
        definition={{
          call_type: "group",
          name: "company",
          category: null,
          description: null,
          properties: [],
          traits: [],
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Group: company" })).toBeTruthy();
    expect(screen.getByText("No traits defined.")).toBeTruthy();
  });

  it("shows a track definition by its event name and category, as before", () => {
    render(
      <DefinitionView
        definition={{
          name: "Cart Cleared",
          category: "Core Ordering",
          description: null,
          properties: [{ name: "cart_id", type: "string", required: true, items: null }],
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Cart Cleared" })).toBeTruthy();
    expect(screen.getByText("Core Ordering")).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Property" })).toBeTruthy();
  });
});
