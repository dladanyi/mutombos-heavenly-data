# Documentation

Mutombo's Heavenly Data is a dashboard that ranks the teams in the Mutombo's Heavenly Block
Party fantasy basketball league across nine stat categories, using data from the Yahoo
Fantasy API.

> **Status (2026-10-12):** sub-project 1 (stability refactor + backend/frontend split) is
> designed and not yet implemented. The repo still contains the original single-file Flask
> app (`app.py`). Docs that describe the new design say so at the top.

## Contents

| Doc | What's in it |
|---|---|
| [architecture.md](architecture.md) | How the backend, frontend, Yahoo and Cloud Run fit together |
| [api.md](api.md) | Backend endpoint reference and response shapes |
| [deployment.md](deployment.md) | Cloud Run setup, secrets, free-tier limits, cost guardrails, rollback |
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
