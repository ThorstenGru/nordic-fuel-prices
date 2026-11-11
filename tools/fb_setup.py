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
import urllib.error
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
    gh = subprocess.run(["gh", "--version"], capture_output=True)
    if gh.returncode != 0:
        raise SystemExit("GitHub CLI (gh) not found or not logged in: run `gh auth status` first")
    app_id = input("App ID: ").strip()
    secret = getpass.getpass("App Secret (hidden; nothing is shown while you paste): ").strip()
    short = getpass.getpass("Short-lived user token (hidden; nothing is shown while you paste): ").strip()
    if not (app_id and secret and short):
        raise SystemExit("one of the three values was empty - nothing done")
    print("1/4 exchanging the token ...")
    try:
        long_user = get("oauth/access_token", {"grant_type": "fb_exchange_token", "client_id": app_id, "client_secret": secret,
                                               "fb_exchange_token": short})["access_token"]
        print("2/4 looking for the Page ...")
        pages = get("me/accounts", {"access_token": long_user, "fields": "id,name,access_token", "limit": "100"}).get("data", [])
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Facebook refused the request (HTTP {e.code}): {e.read().decode(errors='replace')[:300]} "
                         "- the token may have expired (they last about an hour) or the App ID/secret is wrong")
    page = next((p for p in pages if p.get("name") == PAGE_NAME), None)
    if not page:
        names = ", ".join(p.get("name", "?") for p in pages) or "none"
        raise SystemExit(f'Page "{PAGE_NAME}" not found for this user. Pages seen: {names}. '
                         "Re-generate the token and tick the Page in the Facebook dialog.")
    me = get("me", {"access_token": page["access_token"], "fields": "id,name"})
    if me.get("name") != PAGE_NAME or str(me.get("id")) != str(page["id"]):
        raise SystemExit("token check failed - not storing anything")
    print("3/4 storing the secrets on GitHub ...")
    set_secret("FB_PAGE_ID", str(page["id"]))
    set_secret("FB_PAGE_TOKEN", page["access_token"])
    print("4/4 checking ...")
    out = subprocess.run(["gh", "secret", "list", "--repo", REPO], capture_output=True).stdout.decode()
    if "FB_PAGE_ID" not in out or "FB_PAGE_TOKEN" not in out:
        raise SystemExit("secrets were not found after storing - check `gh auth status`")
    print(f'OK: secrets FB_PAGE_ID and FB_PAGE_TOKEN stored for "{PAGE_NAME}" in {REPO}.')
    return 0


if __name__ == "__main__":
    sys.exit(main())
