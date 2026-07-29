export type NaturalLanguageExample = {
  key: string;
  label: string;
  text: string;
  businessValue: string;
};

export const NATURAL_LANGUAGE_EXAMPLES: NaturalLanguageExample[] = [
  {
    key: "clean",
    label: "Standard request",
    text: "track when a shopper empties their entire cart",
    businessValue:
      "tells merchandising how often shoppers abandon by emptying the cart",
  },
  {
    key: "pii",
    label: "Request containing PII",
    text: "track when someone subscribes to our newsletter and capture their email address",
    businessValue: "measures newsletter growth against campaign spend",
  },
];

export type RawExample = {
  key: string;
  label: string;
  definition: Record<string, unknown>;
};

export const RAW_EXAMPLES: RawExample[] = [
  {
    key: "naming",
    label: "Naming violation",
    definition: {
      name: "add_to_cart",
      category: "Core Ordering",
      description: "Naming violation: not Object Action, Title Case.",
      properties: [{ name: "cart_id", type: "string" }],
    },
  },
  {
    key: "duplicate",
    label: "Duplicate",
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
