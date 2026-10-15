import { describe, expect, it } from "vitest";
import { ruleInSentence, statusMeta, stepLabel } from "./format";

describe("ruleInSentence", () => {
  it("names a known rule the way a requester would", () => {
    expect(ruleInSentence("event_naming")).toBe("the event name rule");
  });

  it("falls back to the engine's name for a rule it has no label for", () => {
    expect(ruleInSentence("custom_rule")).toBe("the custom_rule rule");
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
