import { describe, expect, it } from "vitest";
import { NATURAL_LANGUAGE_EXAMPLES, fillFromExample } from "./examples";

const [CLEAN, PII] = NATURAL_LANGUAGE_EXAMPLES;

describe("fillFromExample", () => {
  it("fills empty fields", () => {
    expect(fillFromExample({ text: "", businessValue: "  " }, CLEAN)).toEqual({
      text: CLEAN.text,
      businessValue: CLEAN.businessValue,
    });
  });

  it("swaps one example for another, so a second click visibly does something", () => {
    const afterFirst = fillFromExample({ text: "", businessValue: "" }, CLEAN);
    expect(fillFromExample(afterFirst, PII)).toEqual({
      text: PII.text,
      businessValue: PII.businessValue,
    });
  });

  it("never overwrites what the visitor typed", () => {
    expect(
      fillFromExample({ text: "track wishlist shares", businessValue: "" }, PII),
    ).toEqual({ text: "track wishlist shares", businessValue: PII.businessValue });
  });

  it("treats an edited example as the visitor's own typing", () => {
    const edited = `${CLEAN.text} on mobile`;
    expect(
      fillFromExample({ text: edited, businessValue: CLEAN.businessValue }, PII),
    ).toEqual({ text: edited, businessValue: PII.businessValue });
  });
});
