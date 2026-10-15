import type { DataKind } from "./wizard";

export type NaturalLanguageExample = {
  key: string;
  label: string;
  summary: string;
  text: string;
  businessValue: string;
};

export const NATURAL_LANGUAGE_EXAMPLES: NaturalLanguageExample[] = [
  {
    key: "clean",
    label: "A clean request",
    summary: "A shopper empties their cart. The draft should pass every rule.",
    text: "track when a shopper empties their entire cart",
    businessValue:
      "tells merchandising how often shoppers abandon by emptying the cart",
  },
  {
    key: "pii",
    label: "Personal data",
    summary:
      "A newsletter sign-up that captures an email address. The rules should flag it and ask why you need it.",
    text: "track when someone subscribes to our newsletter and capture their email address",
    businessValue: "measures newsletter growth against campaign spend",
  },
];

// The guided request's step 3 examples, by the kind of data picked in step 1. The
// form's two plain-language scenarios are the "Something a user did" examples. Each
// summary says what the rules and the review should do with it, as the scenario tiles do.
const SUBSCRIPTION: NaturalLanguageExample = {
  key: "subscription",
  label: "A new subscription",
  summary:
    "A customer starts a paid subscription. The tracking plan has nothing like it, so the draft should pass every rule.",
  text: "track when a customer starts a paid subscription",
  businessValue: "shows which plans and trial lengths turn into paying customers",
};

const REFUND: NaturalLanguageExample = {
  key: "refund",
  label: "A refund",
  summary:
    "A customer gets a refund. The tracking plan already has Order Refunded, so the review should point you to it.",
  text: "track when a customer gets a refund on an order",
  businessValue: "shows which products and reasons drive refunds",
};

const PLAN_CHANGE: NaturalLanguageExample = {
  key: "plan_change",
  label: "A plan change",
  summary:
    "A user moves to a different pricing plan. It is captured as an event, because only track calls are supported today.",
  text: "track when a user changes their plan",
  businessValue: "shows how many accounts upgrade or downgrade each month",
};

const SIGNED_IN: NaturalLanguageExample = {
  key: "signed_in",
  label: "Signed in or guest",
  summary:
    "Adds one detail to the event you picked: whether the customer was signed in or a guest.",
  text: "add whether the customer was signed in or a guest",
  businessValue: "compares how guests and signed-in customers behave",
};

const KIND_EXAMPLES: Record<DataKind, NaturalLanguageExample[]> = {
  revenue: [SUBSCRIPTION, REFUND],
  user_action: NATURAL_LANGUAGE_EXAMPLES,
  user_trait: [PLAN_CHANGE],
  existing_event_detail: [SIGNED_IN],
  // Every new-event example. Signed in or guest is left out: it needs an event to add to.
  unknown: [...NATURAL_LANGUAGE_EXAMPLES, SUBSCRIPTION, REFUND, PLAN_CHANGE],
};

export function examplesForKind(kind: DataKind): NaturalLanguageExample[] {
  return KIND_EXAMPLES[kind];
}

const NEW_ACTION_PLACEHOLDER = {
  text: "e.g. track when a shopper watches a product video",
  businessValue: "e.g. shows whether product videos lead to more purchases",
};

// Never the same text as an example, so an empty field cannot be mistaken for a filled
// one, and never something the sample plan already tracks.
export const KIND_PLACEHOLDERS: Record<DataKind, { text: string; businessValue: string }> = {
  revenue: {
    text: "e.g. track when a customer pauses their subscription",
    businessValue: "e.g. shows how much revenue pauses put at risk",
  },
  user_action: NEW_ACTION_PLACEHOLDER,
  user_trait: {
    text: "e.g. track when a company's team size changes",
    businessValue: "e.g. lets sales spot accounts that are growing",
  },
  existing_event_detail: {
    text: "e.g. add which device the customer was using",
    businessValue: "e.g. shows whether phone shoppers finish checkout as often as desktop ones",
  },
  unknown: NEW_ACTION_PLACEHOLDER,
};

export type RawExample = {
  key: string;
  label: string;
  summary: string;
  definition: Record<string, unknown>;
};

export const RAW_EXAMPLES: RawExample[] = [
  {
    key: "naming",
    label: "A badly named event",
    summary:
      "Uses snake_case instead of Title Case. The rules reject it and show you what you can do next.",
    definition: {
      name: "add_to_cart",
      category: "Core Ordering",
      description: "Naming violation: not Object Action, Title Case.",
      properties: [{ name: "cart_id", type: "string" }],
    },
  },
  {
    key: "duplicate",
    label: "An event that already exists",
    summary:
      "Asks for an event the tracking plan already has. It goes straight to the queue, where the approver has to acknowledge the duplicate.",
    definition: {
      name: "Order Completed",
      category: "Core Ordering",
      description: "Duplicate: an event with this name already exists in the plan.",
      properties: [
        { name: "order_id", type: "string" },
        { name: "total", type: "number" },
        { name: "currency", type: "string" },
      ],
    },
  },
];

type ExampleFields = { text: string; businessValue: string };

const replaceable = (value: string, field: keyof ExampleFields) =>
  value.trim().length === 0 ||
  Object.values(KIND_EXAMPLES).some((examples) =>
    examples.some((ex) => ex[field] === value),
  );

// A field is replaced when it is empty or still holds an example's untouched value, so
// picking a second scenario swaps the first one out but never overwrites real typing.
export function fillFromExample(
  current: ExampleFields,
  example: NaturalLanguageExample,
): ExampleFields {
  return {
    text: replaceable(current.text, "text") ? example.text : current.text,
    businessValue: replaceable(current.businessValue, "businessValue")
      ? example.businessValue
      : current.businessValue,
  };
}

// Changing the kind changes step 3's examples, so an untouched example from the old kind
// is cleared rather than left in a field that no tile on screen explains.
export function clearUntouchedExample(current: ExampleFields): ExampleFields {
  return {
    text: replaceable(current.text, "text") ? "" : current.text,
    businessValue: replaceable(current.businessValue, "businessValue")
      ? ""
      : current.businessValue,
  };
}
