"""Read public X data.

Trends and account timelines use the same logged-out web client X's own site
uses. An optional bearer token upgrades trends with post counts and adds
X News plus recent search. Query ids were verified on 2026-11-19.
"""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
VIEWER = "__relay_internal__pv__appviewerisloggedinprovider"
USER_TWEETS = "C9mD8fGjyLT1LAyDykuFZA"
TRENDING = "fhyLG-pJs8-QQkOl-hx7ng"
HASHTAG = re.compile(r"(?<!\w)#([A-Za-z0-9_]+)")
TCO = re.compile(r"https://t\.co/\w+")


class XError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def search_url(name: str) -> str:
    query = urllib.parse.quote(name)
    return f"https://x.com/search?q={query}&src=typed_query&f=live"


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _longest_text(node) -> str:
    best = ""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in {"text", "full_text"} and isinstance(value, str) and len(value) > len(best):
                best = value
            else:
                found = _longest_text(value)
                if len(found) > len(best):
                    best = found
    elif isinstance(node, list):
        for value in node:
            found = _longest_text(value)
            if len(found) > len(best):
                best = found
    return best


def _hashtags(details: dict, text: str) -> list[str]:
    found = []
    for item in details.get("hashtag_entities") or []:
        if isinstance(item, str):
            found.append(item)
        elif isinstance(item, dict):
            for key in ("text", "tag", "hashtag"):
                if isinstance(item.get(key), str):
                    found.append(item[key])
                    break
    found.extend(HASHTAG.findall(text))
    cleaned = []
    seen = set()
    for tag in found:
        label = tag.lstrip("#").strip()
        key = label.casefold()
        if label and key not in seen:
            seen.add(key)
            cleaned.append(label)
    return cleaned


def _avatar(url: str) -> str:
    if not isinstance(url, str) or not url.startswith("https://pbs.twimg.com/"):
        return ""
    return url.replace("_normal.", "_bigger.")


def _media(tweet: dict) -> dict:
    preview = ""
    title = ""
    kind = ""
    for item in tweet.get("media_entities2") or []:
        if not isinstance(item, dict):
            continue
        kind = kind or (item.get("type") or "")
        info = item.get("additional_media_info") or {}
        if not title and isinstance(info.get("title"), str):
            title = info["title"].strip()
        url = item.get("media_url_https") or ""
        if not preview and isinstance(url, str) and url.startswith("https://pbs.twimg.com/"):
            preview = url
    return {"type": kind, "preview": preview, "title": title}


def _display_text(text: str, title: str) -> str:
    visible = TCO.sub("", text)
    visible = re.sub(r"\n{3,}", "\n\n", visible).strip()
    if title and len(visible) < 24:
        return title
    return visible or title


def tweet_to_post(tweet: dict, source: str, fallback_screen: str = "") -> dict | None:
    details = tweet.get("details") or {}
    text = (details.get("full_text") or "").strip()
    note = _longest_text(tweet.get("note_tweet") or {}).strip()
    if len(note) > len(text):
        text = note
    media = _media(tweet)
    text = _display_text(text, media["title"])
    created_ms = details.get("created_at_ms")
    rest_id = str(tweet.get("rest_id") or "")
    if not text or not created_ms or not rest_id:
        return None
    user = ((tweet.get("core") or {}).get("user_results") or {}).get("result") or {}
    core = user.get("core") or {}
    screen = core.get("screen_name") or fallback_screen
    name = core.get("name") or screen or "Unknown"
    counts = tweet.get("counts") or {}
    views = tweet.get("views") or {}
    created = datetime.fromtimestamp(created_ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "id": rest_id,
        "text": text,
        "created_at": created,
        "url": f"https://x.com/{screen}/status/{rest_id}" if screen else search_url(text[:80]),
        "user": {
            "name": name,
            "screen_name": screen,
            "avatar": _avatar((user.get("avatar") or {}).get("image_url") or ""),
        },
        "metrics": {
            "likes": _int(counts.get("favorite_count")),
            "reposts": _int(counts.get("retweet_count")),
            "replies": _int(counts.get("reply_count")),
            "quotes": _int(counts.get("quote_count")),
            "views": _int(views.get("count")),
        },
        "hashtags": _hashtags(details, text),
        "media": media,
        "source": source,
    }


def parse_tweets(payload, source: str, fallback_screen: str = "") -> list[dict]:
    found = []

    def walk(node) -> None:
        if isinstance(node, dict):
            if node.get("__typename") == "Tweet" and isinstance(node.get("details"), dict):
                post = tweet_to_post(node, source, fallback_screen)
                if post:
                    found.append(post)
                return
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    deduped = []
    seen = set()
    for post in found:
        if post["id"] in seen:
            continue
        seen.add(post["id"])
        deduped.append(post)
    return deduped


def parse_guest_trends(payload) -> tuple[list[dict], str]:
    block = payload[0] if isinstance(payload, list) and payload else payload
    if not isinstance(block, dict):
        raise XError("X returned an unexpected trend list.")
    trends = []
    for item in block.get("trends") or []:
        if item.get("promoted_content"):
            continue
        name = (item.get("name") or "").strip()
        if not name:
            continue
        volume = item.get("tweet_volume")
        trends.append({
            "rank": len(trends) + 1,
            "name": name,
            "posts": volume if isinstance(volume, int) else None,
            "url": search_url(name),
        })
        if len(trends) >= 30:
            break
    location = ""
    locations = block.get("locations") or []
    if locations and isinstance(locations[0], dict):
        location = locations[0].get("name") or ""
    return trends, location


class GuestClient:
    def __init__(self):
        self._lock = threading.Lock()
        self._token = None
        self._minted = 0.0

    def token(self, force: bool = False) -> str:
        with self._lock:
            fresh = self._token and not force and (time.monotonic() - self._minted) < 8000
            if fresh:
                return self._token
            self._token = self._activate()
            self._minted = time.monotonic()
            return self._token

    def _activate(self) -> str:
        request = urllib.request.Request(
            "https://api.x.com/1.1/guest/activate.json",
            data=b"{}",
            method="POST",
            headers={
                "Authorization": f"Bearer {BEARER}",
                "User-Agent": UA,
                "content-type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            raise XError(f"Could not open a public X session (HTTP {exc.code}).", exc.code) from None
        except urllib.error.URLError as exc:
            raise XError(f"Network error talking to X: {exc.reason}") from None
        token = payload.get("guest_token")
        if not token:
            raise XError("X did not return a public session.")
        return str(token)

    def _get(self, url: str, missing: str):
        last = None
        for attempt in range(2):
            token = self.token(force=attempt > 0)
            request = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bearer {BEARER}",
                    "x-guest-token": token,
                    "User-Agent": UA,
                    "content-type": "application/json",
                    "x-twitter-active-user": "yes",
                    "x-twitter-client-language": "en",
                    "accept": "application/json",
                    "accept-language": "en-US,en;q=0.9",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=25) as response:
                    return json.loads(response.read().decode())
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", "replace")[:300]
                last = XError(f"HTTP {exc.code}: {body}", exc.code)
                if exc.code in {401, 403, 429} and attempt == 0:
                    continue
                if exc.code == 404:
                    raise XError(missing, 404) from None
                raise last from None
            except urllib.error.URLError as exc:
                raise XError(f"Network error talking to X: {exc.reason}") from None
        raise last or XError("X did not answer.")

    def _graphql(self, query_id: str, name: str, variables: dict):
        payload_vars = {**variables, VIEWER: False}
        params = urllib.parse.urlencode({
            "variables": json.dumps(payload_vars, separators=(",", ":")),
        })
        url = f"https://api.x.com/graphql/{query_id}/{name}?{params}"
        payload = self._get(
            url,
            "X changed the logged-out web client. Field timelines need an updated query id in monitor/xclient.py.",
        )
        if isinstance(payload, dict) and payload.get("errors") and not payload.get("data"):
            message = payload["errors"][0].get("message", "X rejected the read.")
            raise XError(str(message))
        return payload

    def trends(self, woeid: int) -> tuple[list[dict], str]:
        url = f"https://api.x.com/1.1/trends/place.json?id={int(woeid)}"
        payload = self._get(url, "The public X trend list is unavailable.")
        return parse_guest_trends(payload)

    def originals(self, screen: str, count: int = 20) -> list[dict]:
        payload = self._graphql(USER_TWEETS, "UserTweets", {"screenName": screen, "count": count})
        return parse_tweets(payload, "account", screen)

    def trending_posts(self, count: int = 20) -> list[dict]:
        try:
            payload = self._graphql(
                TRENDING,
                "GlobalTrendingTimelineLoggedOut",
                {"count": count, "timeFilter": "Day"},
            )
        except XError:
            payload = self._graphql(TRENDING, "GlobalTrendingTimelineLoggedOut", {"count": count})
        return parse_tweets(payload, "trending")


class OfficialClient:
    def __init__(self, token: str):
        self.token = token

    def _get(self, path: str, params: dict):
        query = urllib.parse.urlencode({key: value for key, value in params.items() if value is not None})
        url = f"https://api.x.com{path}"
        if query:
            url = f"{url}?{query}"
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "situation-monitor",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:300]
            raise XError(f"X API HTTP {exc.code}: {body}", exc.code) from None
        except urllib.error.URLError as exc:
            raise XError(f"Network error talking to the X API: {exc.reason}") from None

    def trends(self, woeid: int) -> tuple[list[dict], str]:
        payload = self._get(
            f"/2/trends/by/woeid/{int(woeid)}",
            {"max_trends": 30, "trend.fields": "trend_name,tweet_count"},
        )
        trends = []
        for item in payload.get("data") or []:
            name = (item.get("trend_name") or "").strip()
            if not name:
                continue
            count = item.get("tweet_count")
            trends.append({
                "rank": len(trends) + 1,
                "name": name,
                "posts": count if isinstance(count, int) else None,
                "url": item.get("url") or search_url(name),
            })
        location = ((payload.get("meta") or {}).get("location") or {}).get("name") or ""
        return trends, location

    def news(self, query: str, limit: int = 6) -> list[dict]:
        payload = self._get(
            "/2/news/search",
            {
                "query": query,
                "max_results": limit,
                "max_age_hours": 72,
                "news.fields": "category,hook,name,summary,updated_at",
            },
        )
        stories = []
        for item in payload.get("data") or []:
            story_id = str(item.get("id") or "")
            title = (item.get("name") or "").strip()
            if not story_id or not title:
                continue
            stories.append({
                "id": story_id,
                "title": title,
                "hook": (item.get("hook") or "").strip(),
                "summary": (item.get("summary") or "").strip(),
                "category": item.get("category") or "",
                "updated_at": item.get("updated_at") or "",
                "url": f"https://x.com/i/trending/{story_id}",
            })
        return stories

    def search(self, query: str, limit: int = 20) -> list[dict]:
        payload = self._get(
            "/2/tweets/search/recent",
            {
                "query": query,
                "max_results": max(10, min(limit, 100)),
                "tweet.fields": "created_at,public_metrics,entities,text",
                "expansions": "author_id",
                "user.fields": "name,username,profile_image_url",
            },
        )
        users = {}
        for user in ((payload.get("includes") or {}).get("users") or []):
            users[user.get("id")] = user
        posts = []
        for item in payload.get("data") or []:
            metrics = item.get("public_metrics") or {}
            author = users.get(item.get("author_id")) or {}
            screen = author.get("username") or ""
            hashtags = []
            for tag in ((item.get("entities") or {}).get("hashtags") or []):
                if isinstance(tag, dict) and tag.get("tag"):
                    hashtags.append(tag["tag"])
            text = (item.get("text") or "").strip()
            post_id = str(item.get("id") or "")
            created = item.get("created_at") or ""
            if created.endswith("Z") and "." in created:
                created = created.split(".", 1)[0] + "Z"
            elif created.endswith("+00:00"):
                created = created[:-6] + "Z"
            if not text or not post_id or not created:
                continue
            posts.append({
                "id": post_id,
                "text": text,
                "created_at": created,
                "url": f"https://x.com/{screen}/status/{post_id}" if screen else search_url(text[:80]),
                "user": {
                    "name": author.get("name") or screen or "Unknown",
                    "screen_name": screen,
                    "avatar": _avatar(author.get("profile_image_url") or ""),
                },
                "metrics": {
                    "likes": _int(metrics.get("like_count")),
                    "reposts": _int(metrics.get("retweet_count")),
                    "replies": _int(metrics.get("reply_count")),
                    "quotes": _int(metrics.get("quote_count")),
                    "views": _int(metrics.get("impression_count")),
                },
                "hashtags": hashtags,
                "source": "search",
            })
        return posts
