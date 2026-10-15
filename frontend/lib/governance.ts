// Governance in the words a reader would use. The raw identifiers stay on screen as a
// secondary line, because they are what an engineer finds in the profile's YAML.

export type Choice = { value: string; label: string };

type ConventionText = { label: string; example: string };

const CONVENTIONS: Record<string, ConventionText> = {
  title_case_object_action: { label: "Title Case Object Action", example: "Cart Cleared" },
  snake_case_object_action: { label: "snake_case object_action", example: "cart_cleared" },
  snake_case: { label: "snake_case", example: "cart_id" },
};

export function conventionLabel(convention: string): ConventionText {
  return CONVENTIONS[convention] ?? { label: convention, example: "" };
}

// The setup wizard's curated choices. Every value must match the Literal sets in
// backend/app/governance_draft.py; the labels are only what the visitor reads.
export const BUSINESS_TYPES: Choice[] = [
  { value: "ecommerce", label: "E-commerce" },
  { value: "saas", label: "SaaS" },
  { value: "marketplace", label: "Marketplace" },
  { value: "media", label: "Media" },
  { value: "fintech", label: "Fintech" },
];

export const PLATFORMS: Choice[] = [
  { value: "segment", label: "Segment" },
  { value: "posthog", label: "PostHog" },
  { value: "amplitude", label: "Amplitude" },
  { value: "mixpanel", label: "Mixpanel" },
  { value: "hightouch", label: "Hightouch" },
  { value: "none", label: "None yet" },
];

export const SIDES: Choice[] = [
  { value: "client", label: "The browser or app" },
  { value: "server", label: "Our servers" },
  { value: "both", label: "Both" },
];

const EVENT_NAMING_STYLES: Record<string, string> = {
  title_case_object_action: "Segment style",
  snake_case_object_action: "PostHog style",
};

export const NAMING_CONVENTIONS: Choice[] = Object.entries(EVENT_NAMING_STYLES).map(
  ([value, style]) => {
    const { label, example } = CONVENTIONS[value];
    return { value, label: `${label} (${style}), like “${example}”` };
  },
);

export const DESTINATIONS: Choice[] = [
  { value: "warehouse", label: "Warehouse" },
  { value: "product_analytics", label: "Product analytics" },
  { value: "crm", label: "CRM" },
  { value: "engagement", label: "Engagement" },
  { value: "advertising", label: "Advertising" },
];

// Shown as written, in mono: each is a property name the blocklist will match.
export const PII_ADDITIONS = [
  "device_id",
  "latitude",
  "longitude",
  "national_id",
  "passport_number",
  "drivers_license",
  "bank_account",
];

export function choiceLabel(choices: Choice[], value: string): string {
  return choices.find((c) => c.value === value)?.label ?? value;
}
