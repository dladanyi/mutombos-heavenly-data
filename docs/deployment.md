# Deployment

> **Status:** target setup from sub-project 1 (Vercel). Production still runs the original app
> on Google Cloud Run (`mutombos-heavenly-data`, `us-west1`) until the cutover described below.

## How it deploys

The GitHub repo is connected to a Vercel project.

- A push to `main` deploys to **production**.
- Every other branch and every PR gets a **preview deployment** with its own URL.
- GitHub Actions only runs CI (tests and builds). It does not deploy.

`vercel.json` defines two **Services** in one project:

- `frontend` (root `frontend/`): Vite, auto-detected, built to static files on the CDN.
- `backend` (root `backend/`): Flask as a Python function. The entrypoint is `wsgi:app`
  (`backend/wsgi.py` calls `create_app()`), dependencies come from `backend/requirements.txt`,
  and the Python version is pinned by `backend/.python-version` (3.12).

Rewrites send `/api/*` and `/healthz` to `backend` and everything else to `frontend`. Flask
sees the original request path (`/api/league`, etc.).

## Cost: $0/month

The project is on the **Hobby** plan, which is free and for personal, non-commercial use.
Hobby usage is capped rather than billed: if a limit were ever reached, functions pause until
the next cycle, and nothing is charged. Caching keeps usage tiny:

- The CDN caches API responses (`Vercel-CDN-Cache-Control`). Finished weeks are cached for a
  year, so most requests never reach the function.
- The function's in-memory cache absorbs the rest.

## Environment variables

Set in Vercel → Project → Settings → Environment Variables, for **Production and Preview**:

| Name | Sensitive | Notes |
|---|---|---|
| `YAHOO_CONSUMER_KEY` | yes | From the Yahoo developer app |
| `YAHOO_CONSUMER_SECRET` | yes | From the Yahoo developer app |
| `YAHOO_REFRESH_TOKEN` | yes | See below |
| `YAHOO_LEAGUE_ID` | no | `46425` for the 2026-27 season |

Changing an env var only takes effect on the next deployment (redeploy from the dashboard).

## Yahoo API access (required)

Since about **2026-07-22**, Yahoo only serves Fantasy Sports API data to apps approved through
its developer access program. Any other app gets HTTP 403 "This application is not authorized
to perform this action" on **every** endpoint (even `game/nba`), although login and token refresh
still succeed. This is what took the old Cloud Run site down.

Steps, as reported by other developers (yfpy issue #84), since Yahoo hasn't published an
official announcement:

1. Apply at https://sports.yahoo.com/developer/access/ and sign the agreement Yahoo sends
   (DocuSign).
2. After Yahoo confirms enablement, submit the app's Client ID at
   https://sports.yahoo.com/developer/application-confirmation/.
3. If the 403 continues, create a **new** app at https://developer.yahoo.com/apps/create/ (apps
   created before enablement reportedly can't be fixed), submit its Client ID, and get a new
   refresh token. Refresh tokens are tied to the app that issued them.
4. Don't rely on the confirmation email. Test with a real call:
   `curl -H "Authorization: Bearer <token>" "https://fantasysports.yahooapis.com/fantasy/v2/game/nba?format=json"`
   must return 200. `backend/scripts/capture_fixtures.py` does the same check.

Reported approval times are 3-8 weeks.

**Status (2026-10-12):** application pending. The app (Client ID in `.env`) returns 403.

## Refresh token

To get a refresh token (once, and again if Yahoo revokes it), run this in your own terminal:

```sh
set -a; source .env; set +a
.venv/bin/python backend/scripts/get_refresh_token.py
```

It prints a Yahoo sign-in URL, asks for the code Yahoo shows, and prints only the refresh
token. Put it in `.env` and in the Vercel env var `YAHOO_REFRESH_TOKEN`, then redeploy.

## Local development

```sh
# backend (terminal 1)
set -a; source .env; set +a
cd backend && ../.venv/bin/flask --app app:create_app run --port 8080

# frontend (terminal 2), proxies /api to :8080
cd frontend && npm run dev
```

## Smoke test after deploy

```sh
curl -fsS https://<deployment-url>/healthz
curl -fsS https://<deployment-url>/api/league
curl -sSI https://<deployment-url>/api/rankings/season | grep -i x-vercel-cache   # HIT on repeat
```

## Rollback

Promote the previous production deployment: `vercel rollback`, or Dashboard → Deployments →
⋯ → Promote.

## Current state (2026-10-13)

- **Project:** `mutombos-heavenly-data` in the personal Hobby scope (`ladanyi77-gmailcoms-projects`),
  created 2026-03-15. This repo is linked to it (`.vercel/`, git-ignored).
- **Framework preset:** Services. Install, build and output settings are on auto-detect.
- **Env vars (Production + Preview):** `YAHOO_CONSUMER_KEY`, `YAHOO_CONSUMER_SECRET`,
  `YAHOO_REFRESH_TOKEN` (sensitive, from the new Yahoo app), and `YAHOO_LEAGUE_ID=46425`. The old
  `YAHOO_ACCESS_TOKEN`, `YAHOO_GUID`, `YAHOO_TOKEN_TIME` and `YAHOO_TOKEN_TYPE` were removed.
  The *Development* copies still hold old values and are only used by `vercel dev` / `env pull`.
- **Deployment Protection:** previews only. The production URL is public.
- **Git:** linked to `dladanyi/mutombos-heavenly-data`, production branch `main`. Pushes trigger
  deployments again (fixed 2026-10-13 by restoring the Vercel GitHub app's access to the repo):
  branches get previews, and `main` deploys to production.
- **Preview verified** (prebuilt upload and Git-triggered build):
  `/healthz` returns 200, the page loads, the API returns a clean 503 (Yahoo 403, see above),
  unknown `/api` paths return 404 JSON, and the logs are JSON.

To deploy a preview by hand (uploads only the build output, never source or `.env`):

```sh
npx vercel@latest build && npx vercel@latest deploy --prebuilt
npx vercel@latest curl https://<preview-url>/healthz   # previews are protected; this authenticates
```

## Cutover from Cloud Run (one time)

1. Create the Vercel project from the GitHub repo (framework preset: **Services**, detected
   from `vercel.json`) and add the env vars above.
2. Check the preview deployment of the `stability-refactor` branch.
3. Merge to `main`, which deploys to Vercel production.
4. With the user's approval: disconnect the Cloud Run GitHub trigger (Cloud Build trigger
   `aa70e010-…`, global) and delete the Cloud Run service `mutombos-heavenly-data`
   (`us-west1`), so pushes stop deploying to GCP.
