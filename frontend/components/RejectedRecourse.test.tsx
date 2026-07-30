import { cleanup, render, screen } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RuleCheck } from "@/lib/api";
import { RejectedRecourse } from "./RejectedRecourse";

afterEach(cleanup);

const NAMING_FAILURE: RuleCheck = {
  rule: "event_naming",
  passed: false,
  detail: "word 'in' must be Title Case (no camelCase or all-lowercase)",
};

const PII_FLAG: RuleCheck = {
  rule: "pii",
  passed: false,
  detail: "flagged (acknowledgment required to approve): user_email -> email",
};

const CATEGORY_PASS: RuleCheck = {
  rule: "category",
  passed: true,
  detail: "category is in the tracking plan",
};

function renderRecourse(
  suggestions: string[],
  checks: RuleCheck[] = [NAMING_FAILURE, CATEGORY_PASS],
  handlers: {
    onRename?: (name: string) => void;
    onDispute?: (rule: string, note: string) => void;
  } = {},
) {
  const onRename = handlers.onRename ?? vi.fn();
  const onDispute = handlers.onDispute ?? vi.fn();
  render(
    <RejectedRecourse
      checks={checks}
      flags={[]}
      suggestions={suggestions}
      busy={false}
      onRename={onRename}
      onDispute={onDispute}
    />,
  );
  return { onRename, onDispute };
}

describe("RejectedRecourse", () => {
  it("offers a button per compliant candidate when candidates exist", () => {
    const { onRename } = renderRecourse([
      "Back In Stock Alert Requested",
      "Back In Stock Alerted",
    ]);

    const first = screen.getByRole("button", {
      name: "Use Back In Stock Alert Requested",
    });
    expect(first).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Use Back In Stock Alerted" }),
    ).toBeInTheDocument();

    fireEvent.click(first);
    expect(onRename).toHaveBeenCalledWith("Back In Stock Alert Requested");
  });

  it("names the single candidate in the offer, so the requester reads the name before clicking", () => {
    renderRecourse(["Back In Stock Alert Requested"]);
    expect(
      screen.getByText(
        "Back In Stock Alert Requested follows your team's convention — use that instead?",
      ),
    ).toBeInTheDocument();
  });

  it("renders the dispute door and no rename buttons when there are no candidates", () => {
    // "Item Saved for Later" has no compliant repair: the Title-Case fix fails on
    // tense. This is exactly when the requester most needs the dispute door.
    renderRecourse([]);

    expect(screen.queryByRole("button", { name: /^Use / })).toBeNull();
    expect(
      screen.getByRole("button", { name: "This rule looks wrong for us" }),
    ).toBeInTheDocument();
  });

  it("keeps the dispute door available even when a compliant name is offered", () => {
    renderRecourse(["Back In Stock Alert Requested"]);
    expect(
      screen.getByRole("button", { name: "This rule looks wrong for us" }),
    ).toBeInTheDocument();
  });

  it("requires a note before the dispute can be sent", () => {
    const { onDispute } = renderRecourse([]);
    fireEvent.click(
      screen.getByRole("button", { name: "This rule looks wrong for us" }),
    );

    const send = screen.getByRole("button", { name: "Send to the data team" });
    expect(send).toBeDisabled();

    // Whitespace is not an argument.
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "   " } });
    expect(send).toBeDisabled();

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "“Back in Stock” is a product concept here, not a verb phrase." },
    });
    expect(send).toBeEnabled();

    fireEvent.click(send);
    expect(onDispute).toHaveBeenCalledWith(
      "event_naming",
      "“Back in Stock” is a product concept here, not a verb phrase.",
    );
  });

  it("renders a pii check as advisory, not as an error, alongside a real failure", () => {
    renderRecourse([], [NAMING_FAILURE, PII_FLAG, CATEGORY_PASS]);

    // Request #11's requester saw two red ✕ and could not tell which one stopped the
    // request. Exactly one check reads as the failure now.
    expect(screen.getAllByLabelText("fail")).toHaveLength(1);
    expect(screen.getAllByLabelText("advisory")).toHaveLength(1);
    expect(
      screen.getByText("(advisory — this did not stop the request)", {
        exact: false,
      }),
    ).toBeInTheDocument();

    // And the advisory rule is not the one offered up for dispute.
    fireEvent.click(
      screen.getByRole("button", { name: "This rule looks wrong for us" }),
    );
    expect(
      screen.getByText("Why does event_naming look wrong for your team? *"),
    ).toBeInTheDocument();
  });

  it("shows no dispute door when nothing failed a deciding rule", () => {
    // A schema rejection has no rule checks to disagree with.
    renderRecourse([], [PII_FLAG, CATEGORY_PASS]);
    expect(
      screen.queryByRole("button", { name: "This rule looks wrong for us" }),
    ).toBeNull();
  });
});
