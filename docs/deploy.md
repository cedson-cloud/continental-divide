# Deploying the public demo

How the public demo (ADR 0010) is hosted: the backend on Render, the frontend on Vercel,
and the browser talking only to Vercel. Values in angle brackets are placeholders. Secrets
and service addresses live in the Render and Vercel dashboards, never in this repo.

## How a request travels

The browser calls `/api/...` on the Vercel site. `frontend/middleware.ts` removes the
`/api` prefix, forwards the call to the Render backend, and adds the `x-demo-proxy-secret`
header. Because the browser only ever sees the Vercel origin, the workspace cookie is
first-party and the backend needs no CORS entry for Vercel.

If either Vercel setting the middleware needs is missing, every `/api/*` call answers 503
with "the demo proxy is not configured" and nothing reaches the backend.

## Backend: Render

The service is configured in the Render dashboard, not from a `render.yaml`.

| Setting | Value |
| --- | --- |
| Service type | Web service, Python 3 |
| Root directory | `backend` |
| Region | Ohio |
| Instance | Smallest paid instance, one uvicorn worker |
| Disk | 1 GB, mounted at `/var/data` |
| Build command | `pip install -r requirements.txt` (Render's default for Python) |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/health` |

Environment variables:

| Name | Value |
| --- | --- |
| `PYTHON_VERSION` | The Python version the backend is tested on |
| `AUTH_MODE` | `demo` |
| `DEMO_COOKIE_SECRET` | A long random string. Generate it, never reuse one |
| `DEMO_COOKIE_SECURE` | `true` |
| `DEMO_PROXY_SECRET` | A long random string, also set on Vercel (below) |
| `DEMO_SESSIONS_PER_HOUR` | `40` |
| `DEMO_SESSIONS_PER_IP_PER_HOUR` | `10` (the default; set it to make it visible) |
| `RATE_LIMIT_MAX` | `10` (the default, per 60 seconds) |
| `SANDBOX_DIR` | A folder under `/var/data` |
| `DATABASE_PATH` | A file under `/var/data` |
| `SPEND_LEDGER_PATH` | A file under `/var/data` |
| `DEMO_ECHO_ROUTE` | `true` only while running the echo check below, then `false` |

Added later, when the model is turned on:

| Name | Value |
| --- | --- |
| `ANTHROPIC_API_KEY` | The demo's own key, with a $20 monthly limit set in the Anthropic console |
| `ANTHROPIC_MODEL` | The pinned model |
| `DEMO_DAILY_BUDGET_USD` | `2` |
| `MODEL_INPUT_USD_PER_MTOK`, `MODEL_OUTPUT_USD_PER_MTOK` | The pinned model's prices |
| `DEMO_CLIENT_IP_HEADER` | The header the echo check shows Vercel sets outright |

Until the key, the budget and both prices are set, every model call is refused and the
model-free path still works.

## Frontend: Vercel

On the Hobby plan.

1. Import the GitHub repository as a new project.
2. Set the root directory to `frontend`. Vercel detects Next.js.
3. Add three environment variables, scoped to **Production** only, so preview deploys
   answer 503 instead of reaching the backend:

   | Name | Value |
   | --- | --- |
   | `NEXT_PUBLIC_API_BASE` | `/api` |
   | `DEMO_BACKEND_ORIGIN` | `https://<render-service-address>`, no trailing path |
   | `DEMO_PROXY_SECRET` | The same value as `DEMO_PROXY_SECRET` on Render. Mark it Sensitive |

4. Deploy.

`NEXT_PUBLIC_API_BASE` is baked into the build, so a change to it, or to any of the three,
takes effect only after a redeploy. `DEMO_BACKEND_ORIGIN` and `DEMO_PROXY_SECRET` have no
`NEXT_PUBLIC_` prefix, so they stay on the server and never reach the browser.

## The echo check

This shows what the backend actually receives through the rewrite, before the backend
starts relying on it.

1. Set `DEMO_ECHO_ROUTE=true` on Render and wait for the redeploy.
2. Open `https://<vercel-site-address>/api/demo/echo` in a browser. Save the JSON.
3. Reload the page. Save the JSON again.
4. Set `DEMO_ECHO_ROUTE=false` on Render.

What to read in the result:

- `proxy_secret_matched` should be `true`. If it is `false`, the secret did not survive
  the rewrite, and the backend must not start enforcing it.
- `ip_candidates` shows which headers carry your address. Choose one Vercel sets outright
  (`x-real-ip` or `x-vercel-forwarded-for`), never the first entry of `x-forwarded-for`,
  which a client can write.
- `cookie_names` should be empty on the first load and include `cd_echo` on the second.
  That shows cookies make the round trip.

Before trusting a header, send the same request with a made-up value for it and confirm
the echo still shows your real address.

## Running the proxy locally

To try the `/api` path on your own machine, put these in `frontend/.env.local`, with the
secret matching `DEMO_PROXY_SECRET` in `backend/.env`:

```
NEXT_PUBLIC_API_BASE=/api
DEMO_BACKEND_ORIGIN=http://localhost:8000
DEMO_PROXY_SECRET=<the same local value>
```

Leave `NEXT_PUBLIC_API_BASE` unset to go back to calling the backend directly on port 8000.

## Not yet in place

- The backend reports whether the proxy secret matched but does not yet refuse a request
  without it, so the Render address can still be called directly.
- `DEMO_CLIENT_IP_HEADER` is unset, so per-address limits key on the address Render sees.
