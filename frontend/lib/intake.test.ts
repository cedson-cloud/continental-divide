import { describe, expect, it } from "vitest";
import { missingFieldsSentence, missingIntakeFields, sideLabel } from "./intake";

describe("sideLabel", () => {
  it("says where a stored side happens in a requester's words", () => {
    expect(sideLabel("Client")).toBe("In the browser or app");
    expect(sideLabel("Server")).toBe("On our servers");
    expect(sideLabel("Unsure")).toBe("I'm not sure");
  });

  it("shows an unknown value as stored and a missing one as a dash", () => {
    expect(sideLabel("Edge")).toBe("Edge");
    expect(sideLabel(null)).toBe("—");
  });
});

describe("missingIntakeFields", () => {
  const filled = {
    submitterName: "Ana",
    submitterTeam: "Product",
    text: "track when a shopper empties their cart",
    businessValue: "shows where checkout stalls",
    urgent: false,
    urgencyReason: "",
  };

  it("needs nothing when every required field is filled", () => {
    expect(missingIntakeFields(filled)).toEqual([]);
  });

  it("names each blank field in the order the form shows them", () => {
    expect(
      missingIntakeFields({ ...filled, submitterName: "  ", submitterTeam: "", text: "" }),
    ).toEqual(["your name", "your team", "what to track"]);
  });

  it("asks why only when the request is marked urgent", () => {
    expect(missingIntakeFields({ ...filled, urgent: true })).toEqual(["why it's urgent"]);
  });

  it("ignores a field the step does not show", () => {
    expect(missingIntakeFields({ submitterName: "", submitterTeam: "" })).toEqual([
      "your name",
      "your team",
    ]);
  });
});

describe("missingFieldsSentence", () => {
  it("says nothing when nothing is missing", () => {
    expect(missingFieldsSentence([])).toBeNull();
  });

  it("lists one, two or more fields as a sentence", () => {
    expect(missingFieldsSentence(["your name"])).toBe("Still needed: your name.");
    expect(missingFieldsSentence(["your name", "your team"])).toBe(
      "Still needed: your name and your team.",
    );
    expect(missingFieldsSentence(["your name", "your team", "what to track"])).toBe(
      "Still needed: your name, your team and what to track.",
    );
  });
});
