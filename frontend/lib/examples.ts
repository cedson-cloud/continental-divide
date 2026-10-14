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

// A field is replaced when it is empty or still holds an example's untouched value, so
// picking a second scenario swaps the first one out but never overwrites real typing.
export function fillFromExample(
  current: ExampleFields,
  example: NaturalLanguageExample,
): ExampleFields {
  const replaceable = (value: string, field: keyof ExampleFields) =>
    value.trim().length === 0 ||
    NATURAL_LANGUAGE_EXAMPLES.some((ex) => ex[field] === value);
  return {
    text: replaceable(current.text, "text") ? example.text : current.text,
    businessValue: replaceable(current.businessValue, "businessValue")
      ? example.businessValue
      : current.businessValue,
  };
}
