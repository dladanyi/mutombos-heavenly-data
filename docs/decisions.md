# Decision log

Newest first. Each entry: what we decided, and why.

## 2026-11-06: Sub-project 1 complete; start sub-project 2

- **Sub-project 1 is done.** After Yahoo approved API access, the post-approval checklist
  passed: real fixtures (#7), the league week calendar (#8, playoff weeks provisional), and
  production checks of the page, `/healthz`, the cache headers on every route, CDN hits, and
  the `?refresh=1` bypass (`deployment.md`, "Current state", lists exactly what was checked).
- **Next is sub-project 2** (pick any week + trends over time), starting from a design
  spec. The deferred minors from the sub-project 1 final review stay deferred unless
  sub-project 2 touches them.

## 2026-11-06: Keep using Yahoo's game calendar for week finality

- **League 46425's weeks match `game/nba/game_weeks` for 2026-27** (spec risk 3), so
  finality stays on the game calendar, and there's no switch to the scoreboard's
  `week_start`/`week_end`. All 19 regular-season weeks match exactly, including the
  two-week weeks 7 and 17. **Playoff weeks 20-22 are provisional:** they have no matchups
  until the bracket is set, so only their combined span (2027-03-15..04-04, ending on the
  league's `end_date`) could be checked, not each week's own dates. Re-run the check after
  week 19 ends on 2027-03-14.
- **Why not switch anyway:** the calendar is one cached request for the whole season, whereas
  scoreboard bounds would need a request per week. The two are equivalent as long as the
  league follows the game calendar.
- **Re-check every season** with `backend/scripts/check_league_weeks.py`, and again once
  the playoff bracket is set. Exit codes: 0 match (it prints PROVISIONAL if any week had no
  matchups), 1 mismatch, 2 couldn't check. Its comparison logic has unit tests.

## 2026-11-05: Real Yahoo fixtures replace the synthetic ones

- **Yahoo approved the new app** (created 2026-10-21): `/api/league?refresh=1` returns live
  data instead of 503.
- **The test fixtures are now real responses**, captured by `capture_fixtures.py`, and
  `make_synthetic.py` is gone. The parsers handled the real shape without changes. The only
  test updates were for the scenario: 10 teams (not 12), current week 3 (not 7), and the real
  calendar. Its weeks mostly run Monday to Sunday (the synthetic ones ran Tuesday to Monday),
  but some are irregular: week 1 is six days (Tuesday 2026-10-20 to Sunday 2026-10-25), and
  Yahoo's game weeks 7 (2026-11-30..12-13) and 17 (2027-02-15..02-28, the All-Star break) are
  two weeks long.
- **The capture script filters responses through allowlists, not a denylist,** because the
  repo is public. The goal is to keep out data that **isn't already public**: managers
  (nicknames, GUIDs, possibly emails) and `is_owned_by_current_login` (which team is the repo
  owner's). The first version of this PR used a denylist, which let the ownership flag
  through. Team metadata now keeps only `team_key`, `team_id`, the name and the stats. League
  metadata keeps the fields the parser and tests read, plus the season and dates for context.
  A field Yahoo adds later is dropped by default. The script raises an error instead of
  saving anything for shapes it hasn't been written for: a team without a `team_id`, or a
  league part other than the metadata and `teams` (such as standings or a scoreboard).
- **Renaming teams to `Team <team_id>` is cosmetic.** Team names and stats are already public
  on the dashboard (the 2026-10-13 fixture-privacy decision in the sub-project 1 spec), so the
  rename hides nothing. It just keeps the fixtures neutral.
- **Yahoo doesn't send the league `is_finished` flag mid-season** (checklist step 4). The
  allowlist keeps it in case it appears after the season. Until then, the season end comes
  from calendar dates, as before.

## 2026-10-13: Cutover to Vercel

- **Production moved to Vercel** (https://mutombos-heavenly-data.vercel.app) when PR #1 was
  merged. Cloud Run, its Cloud Build trigger, the `helloworld` sample service and the Artifact
  Registry images were deleted, so GCP no longer hosts or bills anything for this app.
- The API returns 503 until Yahoo approves API access. That was already true of the Cloud Run
  site, so the cutover didn't need to wait for approval.

## 2026-10-13: PR #1 review fixes

- **The last week of the season goes final by its calendar date.** Yahoo leaves `current_week`
  on the last week after the season, so `week >= current_week` alone kept it "current"
  forever. A week Yahoo calls current now follows the calendar once its end date has passed.
  Without a calendar date it stays current. Week responses report `state`, and the UI shows
  "Season over" instead of "● Live" when the last week has ended.
- **Strip `managers` from captured fixtures**, since the repo is public.
- **Rows carry `team_key`**, and the UI keys rows by it (team names aren't unique).
- **Token handling:** concurrent 401s renew the token once, and a malformed token response is a
  503 with the 30 s cooldown instead of a 500.
- **UI:** a failed Refresh shows "Couldn't update: …" above the table, "Just refreshed" ignores
  final data, and changing week clears the old table.
- **Week aliases keep 60 s CDN headers.** After the `week_state` change, `/week/current` could
  get the 1-year final headers once the season ended. That's harmless in the intended case,
  but if `game_weeks` doesn't match the league (spec risk 3) the live URL would freeze
  mid-season. Aliases change meaning at every rollover, so they are capped at 60 s. Only
  numbered weeks get the long cache.
- **`/week/previous` alias.** The frontend requests last week in parallel with
  `/api/league` instead of waiting to learn the week number. A 404 (first week) hides the
  section.

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
- **Median rank shown next to average rank, informational only (2026-11-13).** Teams are
  still ordered, and medals still assigned, by the mean. With 9 categories the median is a
  whole number, so ordering by it would create many ties between the 10 teams.
- **Weekly head-to-head results on the last-week table (2026-11-13).** Each team row of a
  finished week carries its matchup result (W/L/T, category score, opponent) from Yahoo's
  scoreboard, cached by the same week-state rules as the stats. The live week isn't fetched,
  so the current week costs no extra Yahoo call. If the scoreboard fails, the rankings are
  still served (results null, not cached) rather than failing the whole week. This is the
  first piece of sub-project 3 (matchups).
- **Past seasons via Yahoo's `renew` links (2026-11-13).** Full Season gets ‹ › arrows. The
  backend follows each league's `renew` link to the previous season's league, so a new season
  needs no config change. A 403 on a previous league means this account wasn't in it and ends
  the walk (2024-25 today). It only counts as that when the current league loaded fine, since
  Yahoo also returns 403 for a bad credential. Rejected: listing past leagues in config (a
  yearly manual step) and folding past seasons into `/api/rankings/season` (different shape
  and caching).
- **A finished season shows a champion line and final standings, with medals on the standings
  only.** Its stat table keeps the per-category colours but not the Avg Rank medals, so there
  aren't two sets of medals on one screen. The stat table uses Yahoo's whole-season totals,
  playoff weeks included (one cached call), with a caption, because the standings record is
  regular season only. Once the current season is finished, the section opens on its final
  view during the off-season.
  The standings rows also carry each team's Avg/Med Rk and per-category ranks (user request),
  so a team's finish and its stat ranks can be compared on one line.
- **The current season's Full Season table shows each team's record (2026-11-13).** It's the
  category W–L–T from Yahoo's standings (completed weeks), next to the stat ranks, so how a team
  is doing in matchups and how it ranks on stats read side by side. The standings are cached for
  5 minutes like the rest of the live data. If they fail, the rankings are still served
  (records null, not cached).
- **The current week shows its live matchups (2026-11-13), reversing "the live week isn't
  fetched".** The current week table opens with a Matchup column: categories won so far
  ("7–2 vs Team D"), coloured by who's leading, without W/L until it's final. It costs one
  scoreboard call per 5 minutes per instance, the same TTL as the week's stats.
