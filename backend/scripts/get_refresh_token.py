"""One-time Yahoo login that prints a refresh token for YAHOO_REFRESH_TOKEN.

Run locally (never on the server):
    set -a; source .env; set +a
    .venv/bin/python backend/scripts/get_refresh_token.py
"""
import os
import sys
from urllib.parse import urlencode

import requests

TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
AUTHORIZE_URL = "https://api.login.yahoo.com/oauth2/request_auth"


def main() -> int:
    key = os.environ.get("YAHOO_CONSUMER_KEY")
    secret = os.environ.get("YAHOO_CONSUMER_SECRET")
    if not key or not secret:
        print("Set YAHOO_CONSUMER_KEY and YAHOO_CONSUMER_SECRET first.", file=sys.stderr)
        return 1

    # Must match the redirect URI registered on the Yahoo app ("oob" if it shows a code on screen).
    redirect_uri = os.environ.get("YAHOO_REDIRECT_URI", "oob")
    url = AUTHORIZE_URL + "?" + urlencode({"client_id": key, "redirect_uri": redirect_uri, "response_type": "code"})
    print("1. Open this URL, sign in to Yahoo and approve access:\n\n   " + url + "\n")
    if redirect_uri != "oob":
        print("   After approving, your browser goes to " + redirect_uri + "?code=... (the page may not load).\n"
              "   Copy the value after code= from the address bar.\n")
    code = input("2. Paste the code: ").strip()

    response = requests.post(
        TOKEN_URL, auth=(key, secret), timeout=10,
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri})
    if response.status_code != 200:
        # Yahoo's error body names the cause (e.g. invalid_grant, invalid_client) and holds no secrets.
        print(f"Yahoo rejected the code (HTTP {response.status_code}): {response.text}", file=sys.stderr)
        return 1

    print("\n3. Store this in your local .env and in Vercel (Settings → Environment Variables, Sensitive) as YAHOO_REFRESH_TOKEN, then redeploy:\n")
    print(response.json()["refresh_token"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
