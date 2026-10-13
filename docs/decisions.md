# Decision log

Newest first. Each entry: what we decided, and why.

## 2026-10-13: Public repo and a ruleset on `main`

- **Protect `main` with a repository ruleset.** Pushing to `main` deploys production, so every
  change goes through a PR with green CI (`backend`, `frontend`). Force pushes and deletion are
  blocked. No approving review is required because there is one maintainer.
- **Make the repo public.** GitHub's free plan only allows rulesets on public repos, and the
  alternative (GitHub Pro) costs money. Before switching, we scanned the history for committed
  secrets and found none. Secrets live only in Vercel env vars and the git-ignored `.env`.

## 2026-10-13: Python 3.13

- **Target Python 3.13** (was 3.12) on Vercel (`backend/.python-version`) and in CI, matching the
  local development `.venv`. Vercel supports 3.12-3.14.

## 2026-10-13: Final review fixes

- **CDN "final" headers only for data that was fetched as final.** A settling-week entry
  served after the week turns final gets settling headers, so a pre-correction snapshot can't
  be cached at the edge for a year.
- **30 s failure cooldown** per cache key and for token refresh. During a Yahoo outage or rate
  limit, requests get stale data or a fast 503 instead of each waiting up to ~30 s on Yahoo.

## 2026-10-12: Yahoo API access program; synthetic fixtures meanwhile

- **Root cause of the production outage:** Yahoo restricted the Fantasy Sports API to apps
  approved through a new access program (enforced from about 2026-07-22). Every endpoint
  returns 403 for unapproved apps. The user is applying (see `deployment.md`).
- **Keep building with synthetic fixtures** generated in Yahoo's JSON shape
  (`backend/tests/fixtures/make_synthetic.py`), instead of pausing for the 3-8 week approval.
  Once approved, capture real responses, rerun the tests and adjust parsing. Risk: small shape
  differences, which would be contained to `parsing.py`.

## 2026-10-12: Move hosting from Cloud Run to Vercel

- **Deploy on Vercel (Hobby) with the GitHub repo connected,** instead of Cloud Run + Cloud
  Build + Secret Manager. Pushes to `main` deploy to production, and other branches get
  preview URLs.
  - **Simpler and guaranteed $0.** No Docker, Artifact Registry, IAM or budget alerts. Hobby
    is capped rather than billed.
  - **Better caching.** The CDN caches API responses (`Vercel-CDN-Cache-Control`), so finished
    weeks stay cached across cold starts, unlike Cloud Run's per-instance memory.
  - **Preview URLs** for reviewing changes before they go live.
  - **Trade-offs:** less in-memory state survives between requests (shorter-lived
    instances), so the stale-on-error fallback is a little weaker. The Hobby plan is for
    non-commercial use only.
- **Secrets live in Vercel project env vars** (marked Sensitive), not GitHub. GitHub Actions
  runs CI only and needs no secrets, because tests use saved fixtures.
- **Drop gunicorn and Docker.** Vercel runs Flask as a WSGI function; locally we use
  `flask run`.
- **Wiring: Vercel Services** (`frontend` = Vite, `backend` = Flask via `wsgi:app`), rather
  than an `api/index.py` shim. It matches the repo layout, needs no `sys.path` tricks, and
  Flask sees the original paths.
- Context: production on Cloud Run was returning 503 at the time, because Yahoo rejects the
  current app credentials with 403. That's unrelated to hosting and has to be fixed either
  way.

## 2026-10-12: Sub-project 1 design

- **Split into backend (Flask JSON API) and frontend (React + Vite + TypeScript), in one
  repo and one deployment.** (Cloud Run at first; now one Vercel project.) Keeps the data logic and the UI clearly apart, suits the
  planned interactive features, and avoids running two services and setting up CORS.
- **Target $0/month.** No paid add-ons (no Redis or database). (Originally Cloud Run
  scale-to-zero; superseded by the move to Vercel Hobby above.)
- **In-memory cache per instance.** Free and simple. Losing it on scale-to-zero is
  acceptable.
- **Finished weeks (and, later, finished seasons) are cached on the server indefinitely.**
  They never change, so there's no reason to refetch them. A week only counts as final once it
  is more than 3 days past its end date (Pacific time) when fetched, which leaves time for
  Yahoo's stat corrections. Until then it's cached for 1 h. Browsers cache them for 1 day rather than forever, so a future API
  change can't leave old JSON stuck in someone's browser.
- **Drop pandas.** About 150 MB of image size and slower cold starts for about 30 lines of
  ranking logic.
- **Replace yfpy with our own ~60-line Yahoo client** (decided after checking the yfpy
  source). yfpy 17.0.0 / yahoo-oauth 2.1.1 fall back to an interactive `input()` login
  prompt when no access token is given, which would hang a Cloud Run request. They also have
  no request timeout, use up retries permanently per instance, call `sys.exit(1)` on config
  errors, and renewed the token on every page load in the old app. Our client uses
  `requests`, renews in memory, and has timeouts and retries. This removes 6 dependencies.
- **Yahoo secrets in the hosting platform's env store, never written to disk.** Writing to
  `.env` at runtime was fragile on an ephemeral filesystem. (Secret Manager at first; now
  Vercel env vars.)
- ~~Keep the existing Cloud Run GitHub link for deploys~~ (superseded by the move to Vercel
  above). GitHub Actions only runs CI.
- **Missing stat values rank worst.** Previously a missing TO became 0 and ranked best.
- **No IaC (Terraform) for now.** One project plus four env vars; the docs are enough.
- **Work split into three sub-projects:** stability + split, then week picker + trends, then
  matchups.
