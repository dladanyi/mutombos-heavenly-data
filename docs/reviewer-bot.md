# Reviewer bot (GitHub App)

> **Status (2026-10-13):** proposed, not set up yet.

Code reviews from Claude Code are posted under a separate GitHub identity, a GitHub App that
shows up as `<app-name>[bot]`. Your own login (`dladanyi`) stays in place for pushes, PRs and
merges.

Why an app rather than your own account:

- The review is clearly separate from your own comments.
- The bot can submit **Request changes** or **Approve**. GitHub doesn't allow either on your own
  PR, which is why reviews posted as you can only be **Comment**.
- It's free, needs no second account, and its access is limited to this repo and to the
  permissions below.

## 1. Create the app (github.com)

Go to **Settings → Developer settings → GitHub Apps → New GitHub App** and fill in:

| Field | Value |
|---|---|
| GitHub App name | Must be unique across GitHub, e.g. `mhd-reviewer` |
| Homepage URL | `https://github.com/dladanyi/mutombos-heavenly-data` |
| Webhook → Active | **Unchecked** (the app never receives events) |
| Repository permissions → Pull requests | **Read and write** |
| Repository permissions → Contents | **Read-only** |
| Repository permissions → Metadata | Read-only (set automatically) |
| Where can this GitHub App be installed? | **Only on this account** |

Leave every other permission at **No access**, then click **Create GitHub App**.

## 2. Note the App ID and create a private key

On the app's **General** page:

1. Copy the **App ID** (a number).
2. Under **Private keys**, click **Generate a private key**. A `.pem` file downloads.

Move the key out of Downloads and make it readable only by you. Never put it in the repo
(the repo is public):

```sh
mkdir -p ~/.config/mhd-reviewer
mv ~/Downloads/<app-name>.*.private-key.pem ~/.config/mhd-reviewer/private-key.pem
chmod 600 ~/.config/mhd-reviewer/private-key.pem
```

## 3. Install the app on the repo

In the app's settings, open **Install App** → **Install** next to your account → **Only select
repositories** → `mutombos-heavenly-data` → **Install**.

The page you land on has the **installation ID** in its URL:
`https://github.com/settings/installations/<installation-id>`.

Save both IDs. They aren't secret, but keep them next to the key:

```sh
cat > ~/.config/mhd-reviewer/config <<'EOF'
APP_ID=<app-id>
INSTALLATION_ID=<installation-id>
EOF
```

## 4. The wrapper script

App tokens are short-lived. Each run of the script signs a JWT with the private key, exchanges
it for an installation token (valid for 1 hour), and runs **one** `gh` command with that token.
Nothing is written to disk, and the token never reaches your shell environment, so `git push`
and your other `gh` commands still run as you.

Save this as `scripts/gh-as-reviewer` and run `chmod +x` on it:

```bash
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
```

Check that it works. Reading the PR should succeed:

```sh
scripts/gh-as-reviewer pr view 1 --json title -q .title
```

## 5. Using it from Claude Code

Ask for a review and say it should be posted as the reviewer bot, for example "review PR 1 and
post it as the reviewer bot". Claude runs the review, writes the inline comments to a JSON file
in its scratchpad, and posts them with:

```sh
scripts/gh-as-reviewer api repos/{owner}/{repo}/pulls/<n>/reviews --input <review.json>
```

The JSON follows GitHub's
[create a review](https://docs.github.com/en/rest/pulls/reviews#create-a-review-for-a-pull-request)
format. `event` can be `COMMENT`, `REQUEST_CHANGES` or `APPROVE`.

`/code-review --comment` doesn't go through the wrapper, so it posts as **you**. To post as the
bot, run the review without `--comment` and have Claude post the result with the wrapper.

The bot **can't resolve review threads**. GitHub rejects `resolveReviewThread` with "Resource
not accessible by integration", because resolving needs more than the permissions above.
Resolve threads with your own login (plain `gh`, or the "Resolve conversation" button) rather
than giving the app Contents write access, which would also let it push to branches.

## Rotating or revoking

- **Rotate the key:** generate a new private key on the app's General page, replace
  `~/.config/mhd-reviewer/private-key.pem`, then delete the old key on GitHub.
- **Revoke access:** uninstall the app (Settings → Applications → Installed GitHub Apps), or
  delete the app entirely. Tokens already issued stop working within 1 hour, or immediately if
  the app is uninstalled.
