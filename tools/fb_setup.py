"""One-time helper (run by the owner, locally): turns a short-lived Facebook user token into a non-expiring PAGE token for the
"Euro Fuel Prices" Page and stores it, with the Page id, as GitHub secrets. Nothing is printed or written to disk; the values are
typed at hidden prompts and passed to `gh secret set` on stdin, so they never appear in a terminal log, a file, or a chat.

    python tools/fb_setup.py            # asks for: App ID, App Secret (hidden), short-lived user token (hidden)
    python tools/fb_setup.py --check    # only verifies that the stored secrets exist (names), nothing else

Needs the GitHub CLI (`gh`) logged in with access to the repository.
"""
import getpass
import json
import subprocess
import sys
import urllib.parse
import urllib.request

REPO = "ThorstenGru/nordic-fuel-prices"
PAGE_NAME = "Euro Fuel Prices"
GRAPH = "https://graph.facebook.com"


def get(path, params):
    with urllib.request.urlopen(f"{GRAPH}/{path}?{urllib.parse.urlencode(params)}", timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def set_secret(name, value):
    r = subprocess.run(["gh", "secret", "set", name, "--repo", REPO], input=value.encode(), capture_output=True)
    if r.returncode != 0:
        raise SystemExit(f"could not set secret {name}: {r.stderr.decode(errors='replace').strip()}")


def main():
    if "--check" in sys.argv:
        out = subprocess.run(["gh", "secret", "list", "--repo", REPO], capture_output=True).stdout.decode()
        print("FB_PAGE_ID:", "present" if "FB_PAGE_ID" in out else "MISSING")
        print("FB_PAGE_TOKEN:", "present" if "FB_PAGE_TOKEN" in out else "MISSING")
        return 0
    app_id = input("App ID: ").strip()
    secret = getpass.getpass("App Secret (hidden): ").strip()
    short = getpass.getpass("Short-lived user token from the Graph API Explorer (hidden): ").strip()
    long_user = get("oauth/access_token", {"grant_type": "fb_exchange_token", "client_id": app_id, "client_secret": secret,
                                           "fb_exchange_token": short})["access_token"]
    pages = get("me/accounts", {"access_token": long_user, "fields": "id,name,access_token", "limit": "100"}).get("data", [])
    page = next((p for p in pages if p.get("name") == PAGE_NAME), None)
    if not page:
        names = ", ".join(p.get("name", "?") for p in pages) or "none"
        raise SystemExit(f'Page "{PAGE_NAME}" not found for this user. Pages seen: {names}. '
                         "Re-generate the token and tick the Page in the Facebook dialog.")
    me = get("me", {"access_token": page["access_token"], "fields": "id,name"})
    if me.get("name") != PAGE_NAME or str(me.get("id")) != str(page["id"]):
        raise SystemExit("token check failed - not storing anything")
    set_secret("FB_PAGE_ID", str(page["id"]))
    set_secret("FB_PAGE_TOKEN", page["access_token"])
    print(f'OK: secrets FB_PAGE_ID and FB_PAGE_TOKEN stored for "{PAGE_NAME}" in {REPO}.')
    return 0


if __name__ == "__main__":
    sys.exit(main())
