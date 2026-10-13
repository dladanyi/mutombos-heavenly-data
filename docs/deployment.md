# Deployment

> **Status:** target setup from sub-project 1. Today the original app is deployed through the
> same Cloud Run GitHub link.

## How it deploys

A push to `main` triggers the Cloud Run GitHub link, which runs Cloud Build on the root
`Dockerfile` and deploys a new revision. GitHub Actions only runs CI (tests and a Docker
build). It does not deploy.

## Goal: $0/month

Free-tier allowances as understood on 2026-10-12. Check against current Google Cloud pricing
pages.

| Service | Free allowance (approx.) | How we stay inside it |
|---|---|---|
| Cloud Run | ~2M requests, 180k vCPU-s, 360k GiB-s per month (request-based billing) | `min-instances=0`, `max-instances=2`, caching |
| Artifact Registry | 0.5 GB storage | Small image (<300 MB), cleanup policy keeps 3 images |
| Secret Manager | 6 active secret versions, 10k access ops/month | 3 secrets, read only at instance start |
| Cloud Build | Free build-minute allowance | A few minutes per push to `main` |

Guardrails:

- Never set `min-instances` above 0, and never enable "CPU always allocated".
- Keep a $1 billing budget alert on the project.

## Cloud Run service settings

| Setting | Value |
|---|---|
| Min / max instances | 0 / 2 |
| Memory / CPU | 512 MiB / 1 |
| Billing | Request-based |
| Concurrency | 80 |
| Env vars | `YAHOO_LEAGUE_ID` |
| Secrets as env vars | `YAHOO_CONSUMER_KEY`, `YAHOO_CONSUMER_SECRET`, `YAHOO_REFRESH_TOKEN` |

The service account running the service needs `roles/secretmanager.secretAccessor` on those
three secrets.

## Getting a Yahoo refresh token

Needed once, and again if Yahoo revokes the token. The exact local steps will be documented
here after the risk check in the spec (section 10.1).

## Local run

```sh
docker compose up --build      # same image as production, reads .env
```

## Smoke test after deploy

```sh
curl -fsS https://<service-url>/healthz
curl -fsS https://<service-url>/api/league
```

## Rollback

```sh
gcloud run revisions list --service <service> --region <region>
gcloud run services update-traffic <service> --region <region> --to-revisions <previous-revision>=100
```
