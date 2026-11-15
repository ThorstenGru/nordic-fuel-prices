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
VIDEO_BASE = os.environ.get("FB_VIDEO_BASE", "https://graph-video.facebook.com")
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


def post_photo(page_id: str, token: str, message: str, image_url: str, call_fn=call, published: bool = True) -> str:
    r = call_fn("POST", f"{page_id}/photos", token, {"url": image_url, "caption": message, "published": "true" if published else "false"})
    return r.get("post_id") or r.get("id") or ""


def post_video(page_id: str, token: str, message: str, path: str, timeout: int = 300) -> str:
    """Upload a (short) video file as the Page. Multipart body built by hand to stay stdlib-only; the token stays out of any log."""
    boundary = "efp" + os.urandom(8).hex()
    crlf = b"\r\n"
    body = b""
    for k, v in (("access_token", token), ("description", message), ("published", "true")):
        body += f"--{boundary}".encode() + crlf + f'Content-Disposition: form-data; name="{k}"'.encode() + crlf + crlf + str(v).encode("utf-8") + crlf
    with open(path, "rb") as f:
        blob = f.read()
    body += (f"--{boundary}".encode() + crlf + b'Content-Disposition: form-data; name="source"; filename="video.mp4"' + crlf
             + b"Content-Type: video/mp4" + crlf + crlf + blob + crlf + f"--{boundary}--".encode() + crlf)
    req = urllib.request.Request(f"{VIDEO_BASE}/{page_id}/videos", data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return str(json.loads(r.read().decode("utf-8")).get("id", ""))
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        raise GraphError(f"POST videos: HTTP {e.code} {msg}".replace(token, "***")) from None
    except urllib.error.URLError as e:
        raise GraphError(f"POST videos: {e.reason}".replace(token, "***")) from None


def post_reel(page_id: str, token: str, description: str, path: str, call_fn=call, upload_fn=None, timeout: int = 300) -> str:
    """Publish a 9:16 video as a Reel (Reels Publishing API): start -> upload the bytes to the returned URL -> finish with PUBLISHED. Returns the video id.
    Raises GraphError at any step; the caller then falls back to a normal video so the post is never lost."""
    start = call_fn("POST", f"{page_id}/video_reels", token, {"upload_phase": "start"})
    vid, url = str(start.get("video_id", "")), start.get("upload_url", "")
    if not vid or not url:
        raise GraphError("reel: no video_id / upload_url from the start phase")
    with open(path, "rb") as f:
        blob = f.read()
    if upload_fn is None:
        def upload_fn(u, data):
            req = urllib.request.Request(u, data=data, method="POST", headers={"Authorization": "OAuth " + token, "offset": "0", "file_size": str(len(data)),
                                                                              "Content-Type": "application/octet-stream"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return json.loads(r.read().decode("utf-8") or "{}")
            except urllib.error.HTTPError as e:
                raise GraphError(f"reel upload: HTTP {e.code}") from None
            except urllib.error.URLError as e:
                raise GraphError(f"reel upload: {e.reason}") from None
    up = upload_fn(url, blob)
    if isinstance(up, dict) and up.get("success") is False:
        raise GraphError("reel upload refused")
    fin = call_fn("POST", f"{page_id}/video_reels", token, {"upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED", "description": description})
    if not fin.get("success", True):
        raise GraphError("reel publish refused")
    return vid


def like(object_id: str, token: str, call_fn=call) -> bool:
    """The Page likes a comment (shows people we read it, and counts as interaction). Best effort: needs pages_manage_engagement."""
    try:
        return bool(call_fn("POST", f"{object_id}/likes", token).get("success"))
    except GraphError:
        return False


def page_stats(page_id: str, token: str, call_fn=call) -> dict:
    """followers_count / fan_count of the Page ({} on error)."""
    try:
        return call_fn("GET", page_id, token, {"fields": "followers_count,fan_count"})
    except GraphError:
        return {}


def recent_posts(page_id: str, token: str, limit: int = 50, call_fn=call) -> list:
    """The Page's latest posts with their basic engagement counts (reactions, comments, shares)."""
    r = call_fn("GET", f"{page_id}/posts", token, {"fields": "id,created_time,shares,reactions.summary(true).limit(0),comments.summary(true).limit(0)", "limit": str(limit)})
    return r.get("data", [])


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


def delete(object_id: str, token: str, call_fn=call) -> bool:
    return bool(call_fn("DELETE", object_id, token).get("success"))
