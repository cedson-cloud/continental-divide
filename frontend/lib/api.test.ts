import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, friendlyError, listRequests } from "./api";

function reply(status: number, body: unknown = null) {
  return new Response(body === null ? "" : JSON.stringify(body), { status });
}

function stubFetch(...replies: Response[]) {
  const fetchMock = vi.fn();
  for (const r of replies) fetchMock.mockResolvedValueOnce(r);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function calledPaths(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls.map(([url, init]) => `${init?.method ?? "GET"} ${new URL(url).pathname}`);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("request", () => {
  it("sends the session cookie with every call", async () => {
    const fetchMock = stubFetch(reply(200, []));
    await listRequests();
    expect(fetchMock.mock.calls[0][1].credentials).toBe("include");
  });

  it("starts a demo session on a 401 and retries once", async () => {
    const fetchMock = stubFetch(reply(401, { detail: "no demo session" }), reply(200, { status: "ok" }), reply(200, []));
    await expect(listRequests()).resolves.toEqual([]);
    expect(calledPaths(fetchMock)).toEqual(["GET /requests", "POST /session", "GET /requests"]);
  });

  it("gives up after one retry rather than looping", async () => {
    const fetchMock = stubFetch(reply(401, { detail: "no" }), reply(200, { status: "ok" }), reply(401, { detail: "still no" }));
    await expect(listRequests()).rejects.toMatchObject({ status: 401, message: "still no" });
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("keeps the original 401 when the server has no demo sessions", async () => {
    const fetchMock = stubFetch(reply(401, { detail: "authentication is not configured" }), reply(404, { detail: "Not Found" }));
    const error = await listRequests().catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 401, message: "authentication is not configured" });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe("friendlyError", () => {
  it("never asks a visitor about a backend they cannot see", () => {
    expect(friendlyError(new ApiError(0, ""))).toBe(
      "Can't reach the server. Try again in a moment.",
    );
  });

  it("tells a full sandbox apart from a moment's rate limit", () => {
    const full = new ApiError(429, "this sandbox has used all 5 requests the demo allows");
    expect(friendlyError(full)).toMatch(/^This demo sandbox has used all its requests\./);
    expect(friendlyError(new ApiError(429, "rate limit exceeded"))).toBe(
      "Too many actions at once. Wait a moment and try again.",
    );
  });

  it("tells a failed drafting apart from a failed publish", () => {
    const drafting = new ApiError(502, "could not draft a definition (request 4): timeout");
    expect(friendlyError(drafting)).toMatch(/^The model couldn't draft a definition\./);
    const publish = new ApiError(
      502,
      "request 4 is approved but publishing failed (TimeoutError: slow)",
    );
    expect(friendlyError(publish)).toBe(
      "The approval is recorded, but publishing failed. The audit trail shows why.",
    );
  });

  it("says the model-free scenarios still work once the day's budget is spent", () => {
    const spent = new ApiError(
      503,
      "the demo's daily model budget is used up; it resets at midnight UTC",
    );
    expect(friendlyError(spent)).toMatch(/The scenarios that skip the model still work\.$/);
  });
});
