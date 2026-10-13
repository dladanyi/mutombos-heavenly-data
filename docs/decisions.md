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
- **Keep yfpy** for Yahoo OAuth. Replace it only if it can't renew from a refresh token
  without an interactive login.
- **Yahoo secrets in Secret Manager, never written to disk.** The Cloud Run filesystem is
  ephemeral, and writing to `.env` was fragile.
- **Keep the existing Cloud Run GitHub link for deploys; GitHub Actions only runs CI.** No
  deploy credentials in GitHub, and nothing new to set up.
- **Missing stat values rank worst.** Previously a missing TO became 0 and ranked best.
- **No IaC (Terraform) for now.** One service plus three secrets; documented `gcloud`
  commands are enough.
- **Work split into three sub-projects:** stability + split, then week picker + trends, then
  matchups.
