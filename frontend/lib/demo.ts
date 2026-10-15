// The public demo's terms, stated on the landing page and in the guide. They mirror the
// backend's DEMO_REQUESTS_PER_VISITOR and DEMO_SANDBOX_IDLE_DAYS; reading them from the
// API would open a sandbox for a visitor who only came to read (ADR 0010).
export const SANDBOX_REQUESTS = 5;
export const SANDBOX_IDLE_DAYS = 7;

export const SANDBOX_DELETED = `A sandbox unused for ${SANDBOX_IDLE_DAYS} days is deleted, with its requests and audit trail.`;
export const NOTHING_SENT = "Nothing is sent to Jira, Confluence or Notion.";

export const REPO_URL = "https://github.com/cedson-cloud/continental-divide";
export const ADR_INDEX_URL = `${REPO_URL}/tree/main/docs/adr`;

export function adrUrl(file: string): string {
  return `${REPO_URL}/blob/main/docs/adr/${file}.md`;
}
