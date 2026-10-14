import { NextResponse, type NextRequest } from "next/server";

// Header name and value must match the backend's PROXY_SECRET_HEADER and DEMO_PROXY_SECRET.
export const PROXY_SECRET_HEADER = "x-demo-proxy-secret";
// Must match the backend's CLIENT_IP_HEADER. The backend trusts it only alongside the
// proxy secret, so only this middleware can have written it.
export const CLIENT_IP_HEADER = "x-demo-client-ip";

// On the public demo the browser calls /api/* on the frontend's own origin, so the
// workspace cookie is first-party, and this forwards each call to the backend with the
// proxy secret attached (docs/adr/0010). Both values are server-side settings, never
// NEXT_PUBLIC_, so neither reaches the browser.
export function middleware(request: NextRequest) {
  const origin = (process.env.DEMO_BACKEND_ORIGIN || "").replace(/\/+$/, "");
  const secret = process.env.DEMO_PROXY_SECRET || "";
  // Fail closed: a deploy missing either value says so, rather than reaching the
  // backend without the secret and looking like a rejected proxy.
  if (!origin || !secret) {
    return NextResponse.json({ detail: "the demo proxy is not configured" }, { status: 503 });
  }

  const path = request.nextUrl.pathname.replace(/^\/api/, "") || "/";
  const destination = new URL(`${origin}${path}${request.nextUrl.search}`);

  const headers = new Headers(request.headers);
  headers.set(PROXY_SECRET_HEADER, secret);
  // Vercel sets x-real-ip to the address it received the request from, replacing any the
  // client sent, but it does not reach the backend through the rewrite.
  headers.delete(CLIENT_IP_HEADER);
  const address = request.headers.get("x-real-ip")?.trim();
  if (address) {
    headers.set(CLIENT_IP_HEADER, address);
  }
  return NextResponse.rewrite(destination, { request: { headers } });
}

export const config = {
  matcher: ["/api/:path*"],
};
