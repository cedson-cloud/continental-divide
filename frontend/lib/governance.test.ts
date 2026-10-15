import { describe, expect, it } from "vitest";
import { NAMING_CONVENTIONS, PLATFORMS, choiceLabel, conventionLabel } from "./governance";

describe("conventionLabel", () => {
  it("gives a name and an example for each convention the engine knows", () => {
    expect(conventionLabel("title_case_object_action")).toEqual({
      label: "Title Case Object Action",
      example: "Cart Cleared",
    });
    expect(conventionLabel("snake_case").example).toBe("cart_id");
  });

  it("falls back to the identifier for a convention it doesn't know", () => {
    expect(conventionLabel("kebab_case")).toEqual({ label: "kebab_case", example: "" });
  });
});

describe("NAMING_CONVENTIONS", () => {
  it("builds each setup label from the same text the Governance page shows", () => {
    expect(choiceLabel(NAMING_CONVENTIONS, "title_case_object_action")).toBe(
      "Title Case Object Action (Segment style), like “Cart Cleared”",
    );
  });
});

describe("PLATFORMS", () => {
  it("offers Hightouch", () => {
    expect(choiceLabel(PLATFORMS, "hightouch")).toBe("Hightouch");
  });
});
