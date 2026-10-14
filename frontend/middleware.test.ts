// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import {
  getRewrittenUrl,
  unstable_doesMiddlewareMatch,
} from "next/experimental/testing/server";
import { PROXY_SECRET_HEADER, config, middleware } from "./middleware";

const ORIGIN = "https://backend.example.test";
const SECRET = "test-proxy-secret";

function configure(origin = ORIGIN, secret = SECRET) {
  vi.stubEnv("DEMO_BACKEND_ORIGIN", origin);
  vi.stubEnv("DEMO_PROXY_SECRET", secret);
}

function call(path: string, headers: Record<string, string> = {}) {
  return middleware(new NextRequest(`https://demo.example.test${path}`, { headers }));
}

// What the backend receives: Next applies these overrides to the forwarded request.
function forwardedHeader(response: Response, name: string) {
  return response.headers.get(`x-middleware-request-${name}`);
}

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("matcher", () => {
  it("runs on /api and everything under it", () => {
    for (const url of ["/api", "/api/session", "/api/requests/3/submit"]) {
      expect(unstable_doesMiddlewareMatch({ config, url })).toBe(true);
    }
  });

  it("leaves the app's own pages alone", () => {
    for (const url of ["/", "/queue", "/request/3", "/apiary"]) {
      expect(unstable_doesMiddlewareMatch({ config, url })).toBe(false);
    }
  });
});

describe("middleware", () => {
  it("forwards /api/* to the backend with the prefix removed", () => {
    configure();
    expect(getRewrittenUrl(call("/api/requests/3"))).toBe(`${ORIGIN}/requests/3`);
    expect(getRewrittenUrl(call("/api"))).toBe(`${ORIGIN}/`);
  });

  it("keeps the query string", () => {
    configure();
    expect(getRewrittenUrl(call("/api/demo/echo?x=1"))).toBe(`${ORIGIN}/demo/echo?x=1`);
  });

  it("tolerates a trailing slash on the configured origin", () => {
    configure(`${ORIGIN}/`);
    expect(getRewrittenUrl(call("/api/health"))).toBe(`${ORIGIN}/health`);
  });

  it("attaches the proxy secret", () => {
    configure();
    expect(forwardedHeader(call("/api/session"), PROXY_SECRET_HEADER)).toBe(SECRET);
  });

  it("replaces a proxy secret the client sent", () => {
    configure();
    const response = call("/api/session", { [PROXY_SECRET_HEADER]: "forged" });
    expect(forwardedHeader(response, PROXY_SECRET_HEADER)).toBe(SECRET);
  });

  it("passes the request's other headers through unchanged", () => {
    configure();
    const response = call("/api/session", { cookie: "cd_workspace=abc", "x-real-ip": "203.0.113.7" });
    expect(forwardedHeader(response, "cookie")).toBe("cd_workspace=abc");
    expect(forwardedHeader(response, "x-real-ip")).toBe("203.0.113.7");
  });

  it.each([
    ["the backend origin", "", SECRET],
    ["the proxy secret", ORIGIN, ""],
  ])("answers 503 and forwards nothing without %s", async (_, origin, secret) => {
    configure(origin, secret);
    const response = call("/api/session");
    expect(response.status).toBe(503);
    expect(getRewrittenUrl(response)).toBeNull();
    expect(await response.json()).toEqual({ detail: "the demo proxy is not configured" });
  });
});
