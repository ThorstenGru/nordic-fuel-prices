"""Minimal Facebook Graph API client for the Euro Fuel Prices Page (stdlib only).

Everything is done with a PAGE access token, so every post and reply is made by the Page itself, never by a person.
`verify_page` refuses to continue unless the token really belongs to the Page named in FB_PAGE_ID / EXPECTED_NAME.
The token is only sent in the request body/query to graph.facebook.com and is never printed.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("FB_GRAPH_BASE", "https://graph.facebook.com")   # unversioned = the app's default version (no expiry surprises)
EXPECTED_NAME = "Euro Fuel Prices"


class GraphError(RuntimeError):
    pass


def call(method: str, path: str, token: str, params: dict = None, timeout: int = 30) -> dict:
    params = dict(params or {})
    params["access_token"] = token
    data = urllib.parse.urlencode(params).encode()
    url = f"{BASE}/{path.lstrip('/')}"
    req = urllib.request.Request(url + ("?" + data.decode() if method == "GET" else ""), data=None if method == "GET" else data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        raise GraphError(f"{method} {path}: HTTP {e.code} {msg}".replace(token, "***")) from None
    except urllib.error.URLError as e:
        raise GraphError(f"{method} {path}: {e.reason}".replace(token, "***")) from None


def verify_page(page_id: str, token: str, call_fn=call) -> str:
    """The token must be a Page token of exactly this Page; otherwise abort before anything is published."""
    me = call_fn("GET", "me", token, {"fields": "id,name"})
    if str(me.get("id")) != str(page_id) or me.get("name") != EXPECTED_NAME:
        raise GraphError("token does not belong to the Euro Fuel Prices Page - refusing to post")
    return me["name"]


def post_photo(page_id: str, token: str, message: str, image_url: str, call_fn=call) -> str:
    r = call_fn("POST", f"{page_id}/photos", token, {"url": image_url, "caption": message, "published": "true"})
    return r.get("post_id") or r.get("id") or ""


def get_comments(object_id: str, token: str, call_fn=call) -> list:
    r = call_fn("GET", f"{object_id}/comments", token, {"fields": "id,message,from,created_time", "limit": "100", "filter": "stream"})
    return r.get("data", [])


def reply(comment_id: str, token: str, message: str, call_fn=call) -> str:
    return call_fn("POST", f"{comment_id}/comments", token, {"message": message}).get("id", "")


def follower_cities(page_id: str, token: str, call_fn=call) -> dict:
    """Aggregate follower counts per city (Page Insights), {} when the API or the Page does not provide it (e.g. too few followers)."""
    try:
        r = call_fn("GET", f"{page_id}/insights", token, {"metric": "page_follows_city", "period": "day"})
        vals = r["data"][0]["values"][-1]["value"]
        return vals if isinstance(vals, dict) else {}
    except Exception:
        return {}
