# Documentation

Mutombo's Heavenly Data is a dashboard that ranks the teams in the Mutombo's Heavenly Block
Party fantasy basketball league across nine stat categories, using data from the Yahoo
Fantasy API.

> **Status (2026-10-13):** sub-project 1 (stability refactor + backend/frontend split) is
> implemented on branch `stability-refactor` (PR #1) and tested against synthetic Yahoo data.
> The Vercel project, env vars and a verified preview are in place. Two things are pending:
> Yahoo API access approval (see [deployment.md](deployment.md)) and the cutover. Production
> still runs the old app on Cloud Run, which is down because of the Yahoo access change.

## Contents

| Doc | What's in it |
|---|---|
| [architecture.md](architecture.md) | How the backend, frontend, Yahoo and Vercel fit together |
| [api.md](api.md) | Backend endpoint reference and response shapes |
| [deployment.md](deployment.md) | Vercel setup, env vars, Yahoo app and token, local dev, rollback |
| [decisions.md](decisions.md) | Dated log of key decisions and why we made them |
| [specs/](specs/) | One design spec per sub-project |
| [plans/](plans/) | One implementation plan per sub-project |

## Roadmap

1. **Stability refactor + split:** [spec](specs/2026-10-12-stability-refactor-design.md), [plan](plans/2026-10-12-stability-refactor.md)
2. Pick any week + trends over time
3. Head-to-head matchups

## Keeping these docs current

When a change alters the architecture, API or deployment, update the matching doc and add an
entry to `decisions.md` in the same commit.
