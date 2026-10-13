#!/usr/bin/env bash
# Run one gh command as the reviewer bot (GitHub App). See docs/reviewer-bot.md.
# Usage: scripts/gh-as-reviewer api repos/{owner}/{repo}/pulls/1/reviews --input review.json
set -euo pipefail

CONFIG_DIR="${MHD_REVIEWER_DIR:-$HOME/.config/mhd-reviewer}"
# shellcheck source=/dev/null
source "$CONFIG_DIR/config"   # APP_ID, INSTALLATION_ID
KEY="$CONFIG_DIR/private-key.pem"

b64url() { openssl base64 -A | tr '+/' '-_' | tr -d '='; }

now=$(date +%s)
header=$(printf '{"alg":"RS256","typ":"JWT"}' | b64url)
payload=$(printf '{"iat":%d,"exp":%d,"iss":"%s"}' $((now - 60)) $((now + 540)) "$APP_ID" | b64url)
signature=$(printf '%s.%s' "$header" "$payload" | openssl dgst -sha256 -sign "$KEY" -binary | b64url)

token=$(curl -fsS -X POST \
  -H "Authorization: Bearer $header.$payload.$signature" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/app/installations/$INSTALLATION_ID/access_tokens" |
  python3 -c 'import json, sys; print(json.load(sys.stdin)["token"])')

GH_TOKEN="$token" exec gh "$@"
