import { readFileSync } from "fs";
import path from "path";
import { describe, expect, it } from "vitest";
import { SANDBOX_IDLE_DAYS, SANDBOX_REQUESTS } from "./demo";

const config = readFileSync(path.resolve(__dirname, "../../backend/app/config.py"), "utf8");

function backendDefault(setting: string): number {
  const match = config.match(new RegExp(`^\\s*${setting}: int = (\\d+)$`, "m"));
  if (!match) throw new Error(`${setting} not found in backend/app/config.py`);
  return Number(match[1]);
}

describe("the demo's stated terms", () => {
  it("match the backend's defaults, so the pages never promise what the sandbox doesn't do", () => {
    expect(SANDBOX_REQUESTS).toBe(backendDefault("demo_requests_per_visitor"));
    expect(SANDBOX_IDLE_DAYS).toBe(backendDefault("demo_sandbox_idle_days"));
  });
});
