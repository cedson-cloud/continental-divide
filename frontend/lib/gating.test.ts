import { describe, expect, it } from "vitest";
import { missingPiiReasons, piiReasonsToSend } from "./gating";

const hits = { email: "email", subscriber_first_name: "first_name" };

describe("missingPiiReasons", () => {
  it("lists every flagged property before any reason is written", () => {
    expect(missingPiiReasons(hits, {})).toEqual(["email", "subscriber_first_name"]);
  });

  it("treats a blank reason as no reason, as the server does", () => {
    expect(
      missingPiiReasons(hits, { email: "to send the newsletter", subscriber_first_name: "  " }),
    ).toEqual(["subscriber_first_name"]);
  });

  it("is empty once each flagged property has a reason", () => {
    expect(
      missingPiiReasons(hits, {
        email: "to send the newsletter",
        subscriber_first_name: "to greet the subscriber by name",
      }),
    ).toEqual([]);
  });

  it("asks for nothing when no rule flagged PII", () => {
    expect(missingPiiReasons({}, {})).toEqual([]);
  });
});

describe("piiReasonsToSend", () => {
  it("drops reasons for properties the current draft no longer flags", () => {
    expect(
      piiReasonsToSend(
        { email: "email" },
        { email: " to send the newsletter ", phone_number: "left from an earlier draft" },
      ),
    ).toEqual({ email: "to send the newsletter" });
  });
});
