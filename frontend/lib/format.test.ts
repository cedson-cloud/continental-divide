import { describe, expect, it } from "vitest";
import { ruleInSentence } from "./format";

describe("ruleInSentence", () => {
  it("names a known rule the way a requester would", () => {
    expect(ruleInSentence("event_naming")).toBe("the event name rule");
  });

  it("falls back to the engine's name for a rule it has no label for", () => {
    expect(ruleInSentence("custom_rule")).toBe("the custom_rule rule");
  });
});
