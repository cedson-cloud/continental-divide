import { describe, expect, it } from "vitest";
import {
  KIND_PLACEHOLDERS,
  NATURAL_LANGUAGE_EXAMPLES,
  clearUntouchedExample,
  examplesForKind,
  fillFromExample,
} from "./examples";
import type { DataKind } from "./wizard";

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

const KINDS: DataKind[] = [
  "revenue",
  "user_action",
  "user_trait",
  "existing_event_detail",
  "unknown",
];
const keys = (kind: DataKind) => examplesForKind(kind).map((ex) => ex.key);

describe("examplesForKind", () => {
  it("offers money examples for money, including the refund the plan already tracks", () => {
    expect(keys("revenue")).toEqual(["subscription", "refund"]);
  });

  it("offers the form's scenarios for something a user did", () => {
    expect(examplesForKind("user_action")).toEqual(NATURAL_LANGUAGE_EXAMPLES);
  });

  it("offers one example each for a user trait and for detail on an existing event", () => {
    expect(keys("user_trait")).toEqual(["plan_change"]);
    expect(keys("existing_event_detail")).toEqual(["signed_in"]);
  });

  it("offers every new-event example when the visitor is not sure", () => {
    expect(keys("unknown")).toEqual(["clean", "pii", "subscription", "refund", "plan_change"]);
  });

  it("gives every example a unique key, since the key names its tile", () => {
    const all = KINDS.flatMap((kind) => examplesForKind(kind));
    const byKey = new Map(all.map((ex) => [ex.key, ex]));
    for (const ex of all) expect(byKey.get(ex.key)).toBe(ex);
  });

  it("never uses an example's own text as a placeholder", () => {
    for (const kind of KINDS) {
      for (const ex of examplesForKind(kind)) {
        expect(KIND_PLACEHOLDERS[kind].text).not.toBe(ex.text);
        expect(KIND_PLACEHOLDERS[kind].businessValue).not.toBe(ex.businessValue);
      }
    }
  });
});

describe("fillFromExample with the guided examples", () => {
  it("swaps one money example for the other", () => {
    const [subscription, refund] = examplesForKind("revenue");
    const afterFirst = fillFromExample({ text: "", businessValue: "" }, subscription);
    expect(fillFromExample(afterFirst, refund)).toEqual({
      text: refund.text,
      businessValue: refund.businessValue,
    });
  });

  it("swaps a guided example for a form scenario", () => {
    const [planChange] = examplesForKind("user_trait");
    const afterFirst = fillFromExample({ text: "", businessValue: "" }, planChange);
    expect(fillFromExample(afterFirst, CLEAN)).toEqual({
      text: CLEAN.text,
      businessValue: CLEAN.businessValue,
    });
  });
});

describe("clearUntouchedExample", () => {
  it("clears an untouched example when the kind changes", () => {
    const [signedIn] = examplesForKind("existing_event_detail");
    expect(
      clearUntouchedExample({ text: signedIn.text, businessValue: signedIn.businessValue }),
    ).toEqual({ text: "", businessValue: "" });
  });

  it("keeps what the visitor typed, including an edited example", () => {
    const edited = `${CLEAN.text} on mobile`;
    expect(
      clearUntouchedExample({ text: edited, businessValue: CLEAN.businessValue }),
    ).toEqual({ text: edited, businessValue: "" });
  });
});
