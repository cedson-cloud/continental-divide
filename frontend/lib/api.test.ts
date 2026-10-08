import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, listRequests } from "./api";

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
