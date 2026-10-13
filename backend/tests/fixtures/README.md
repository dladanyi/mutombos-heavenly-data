# Test fixtures

**These files are SYNTHETIC** (generated 2026-10-12 by `make_synthetic.py`).

Yahoo restricted the Fantasy Sports API to apps approved through its developer access program
(enforced from about 2026-07-22), and this app's access is pending. Real responses couldn't
be captured, so these follow Yahoo's JSON shape as used by the original `app.py` and
documented by yfpy. The scenario is a mid-season league (current week 7; week stats are for
week 6) with 12 invented team names.

Once Yahoo approves access:

```sh
set -a; source .env; set +a
.venv/bin/python backend/scripts/capture_fixtures.py   # overwrites the four JSON files
cd backend && ../.venv/bin/pytest
```

Fix any parsing differences the tests reveal, then delete `make_synthetic.py` and update this
README.
