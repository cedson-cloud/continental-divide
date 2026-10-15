// What both request forms share: the words for where an event happens, and what a
// form still needs before it can draft.

// The values are what the API stores (ADR 0008); the labels are what a requester reads.
export const SIDE_OPTIONS = [
  { value: "Client", label: "In the browser or app" },
  { value: "Server", label: "On our servers" },
  { value: "Unsure", label: "I'm not sure" },
] as const;

export const SIDE_HINT =
  "In the browser or app: on the person's own device, like a tap. On our servers: " +
  "your backend records it, like a payment going through. Not sure is fine: the " +
  "approver decides.";

export function sideLabel(side: string | null | undefined): string {
  return SIDE_OPTIONS.find((o) => o.value === side)?.label ?? side ?? "—";
}

export type IntakeFields = {
  submitterName?: string;
  submitterTeam?: string;
  text?: string;
  businessValue?: string;
  urgent?: boolean;
  urgencyReason?: string;
};

// Only the fields a form shows are passed in, so a step never asks for one it doesn't have.
export function missingIntakeFields(fields: IntakeFields): string[] {
  const blank = (value: string | undefined) => value !== undefined && value.trim() === "";
  const missing: string[] = [];
  if (blank(fields.submitterName)) missing.push("your name");
  if (fields.submitterTeam === "") missing.push("your team");
  if (blank(fields.text)) missing.push("what to track");
  if (blank(fields.businessValue)) missing.push("the business value");
  if (fields.urgent && blank(fields.urgencyReason ?? "")) missing.push("why it's urgent");
  return missing;
}

// Said beside a disabled button, so a newcomer knows why it is disabled.
export function missingFieldsSentence(missing: string[]): string | null {
  if (missing.length === 0) return null;
  const list =
    missing.length === 1
      ? missing[0]
      : `${missing.slice(0, -1).join(", ")} and ${missing[missing.length - 1]}`;
  return `Still needed: ${list}.`;
}
