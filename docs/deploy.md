# Deploying the public demo

How the public demo (ADR 0010) is hosted: the backend on Render, the frontend on Vercel,
and the browser talking only to Vercel. Values in angle brackets are placeholders. Secrets
and service addresses live in the Render and Vercel dashboards, never in this repo.

## How a request travels

The browser calls `/api/...` on the Vercel site. `frontend/middleware.ts` removes the
`/api` prefix, forwards the call to the Render backend, and adds two headers:
`x-demo-proxy-secret`, and `x-demo-client-ip` carrying the address Vercel received the
request from (its `x-real-ip`). Any value the client sent for either header is replaced or
dropped. Because the browser only ever sees the Vercel origin, the workspace cookie is
first-party and the backend needs no CORS entry for Vercel.

In demo mode the backend refuses every request but `/health` that lacks the proxy secret,
with a 403, so it answers only through Vercel. It trusts `x-demo-client-ip` for its
per-address limits only on a request carrying the secret. If `DEMO_PROXY_SECRET` is unset
on Render, every route but `/health` answers 503 with "the demo's proxy secret is not
configured".

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
| `DEMO_ECHO_ROUTE` | `false`. `true` only while running the echo check below |

Added later, when the model is turned on:

| Name | Value |
| --- | --- |
| `ANTHROPIC_API_KEY` | The demo's own key, with a $20 monthly limit set in the Anthropic console |
| `ANTHROPIC_MODEL` | The pinned model |
| `DEMO_DAILY_BUDGET_USD` | `2` |
| `MODEL_INPUT_USD_PER_MTOK`, `MODEL_OUTPUT_USD_PER_MTOK` | The pinned model's prices |

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

This shows what the backend actually receives through the rewrite. Run it after any change
to the proxy path.

1. Set `DEMO_ECHO_ROUTE=true` on Render and wait for the redeploy.
2. Open `https://<vercel-site-address>/api/demo/echo` in a browser. Save the JSON.
3. Reload the page. Save the JSON again.
4. Run the forge check below.
5. Set `DEMO_ECHO_ROUTE=false` on Render.

What to read in the result:

- `proxy_secret_matched` should be `true`. With the secret enforced, a `false` cannot
  reach the route at all: the call answers 403 instead.
- `limiter_address` should be your own public address, the same as
  `ip_candidates["x-demo-client-ip"]`. If `x-demo-client-ip` is `null`, `limiter_address`
  is an address of Vercel's: the middleware found no `x-real-ip`, and every visitor shares
  one per-address limit.
- `cookie_names` should be empty on the first load and include `cd_echo` on the second.
  That shows cookies make the round trip.

### The forge check

A client must not be able to choose the address the limits key on, or call the backend
around Vercel. From a terminal:

```
curl -s https://<vercel-site-address>/api/demo/echo -H "x-demo-client-ip: 198.51.100.66" -H "x-real-ip: 198.51.100.66" -H "x-forwarded-for: 198.51.100.66" -H "x-vercel-forwarded-for: 198.51.100.66"
```

`limiter_address` must be the same address as in the JSON saved at step 2, never
`198.51.100.66`, and `x-demo-client-ip` must not be `null`.

```
curl -s -o /dev/null -w "%{http_code}\n" https://<render-service-address>/requests
```

This calls Render directly, without the secret, and must print `403`.
`https://<render-service-address>/health` must still answer 200, for Render's health check.

## Running the proxy locally

To try the `/api` path on your own machine, put these in `frontend/.env.local`, with the
secret matching `DEMO_PROXY_SECRET` in `backend/.env`:

```
NEXT_PUBLIC_API_BASE=/api
DEMO_BACKEND_ORIGIN=http://localhost:8000
DEMO_PROXY_SECRET=<the same local value>
```

Leave `NEXT_PUBLIC_API_BASE` unset to go back to calling the backend directly on port 8000.
That works only with `AUTH_MODE=local`: in demo mode the backend refuses any call that did
not come through the proxy. If the local server sets no `x-real-ip`, per-address limits
key on the local socket address.
