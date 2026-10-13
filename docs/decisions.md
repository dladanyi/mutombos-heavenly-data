# Decision log

Newest first. Each entry: what we decided, and why.

## 2026-10-12: Sub-project 1 design

- **Split into backend (Flask JSON API) and frontend (React + Vite + TypeScript), in one
  repo and one Cloud Run service.** Keeps the data logic and the UI clearly apart, suits the
  planned interactive features, and avoids running two services and setting up CORS.
- **Target $0/month.** Scale to zero (`min-instances=0`), `max-instances=2` as a cost cap,
  request-based billing, no paid add-ons (no Redis or database).
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
- **Yahoo secrets in Secret Manager, never written to disk.** The Cloud Run filesystem is
  ephemeral, and writing to `.env` was fragile.
- **Keep the existing Cloud Run GitHub link for deploys; GitHub Actions only runs CI.** No
  deploy credentials in GitHub, and nothing new to set up.
- **Missing stat values rank worst.** Previously a missing TO became 0 and ranked best.
- **No IaC (Terraform) for now.** One service plus three secrets; documented `gcloud`
  commands are enough.
- **Work split into three sub-projects:** stability + split, then week picker + trends, then
  matchups.
