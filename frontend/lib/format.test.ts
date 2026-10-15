import { describe, expect, it } from "vitest";
import { publishedHeading, ruleInSentence, statusMeta, stepLabel } from "./format";

describe("ruleInSentence", () => {
  it("names a known rule the way a requester would", () => {
    expect(ruleInSentence("event_naming")).toBe("the event name rule");
  });

  it("falls back to the engine's name for a rule it has no label for", () => {
    expect(ruleInSentence("custom_rule")).toBe("the custom_rule rule");
  });
});

describe("publishedHeading", () => {
  it("never presents the mock publisher's output as something that was sent", () => {
    const heading = publishedHeading("mock");
    expect(heading.title).toBe("What a connected setup would write");
    expect(heading.note).toMatch(/^Nothing was sent anywhere\./);
  });

  it("names a real publisher as the one that published", () => {
    expect(publishedHeading("atlassian")).toEqual({
      title: "Published via the atlassian publisher",
      note: null,
    });
  });
});

describe("a failed drafting", () => {
  it("reads as Couldn't draft in a neutral tone, never as a rejection", () => {
    expect(statusMeta("draft_failed")).toEqual({ label: "Couldn't draft", tone: "neutral" });
  });

  it("names its audit step for every failure kind, not only a failed model call", () => {
    expect(stepLabel("model_error")).toBe("Drafting failed");
  });
});
