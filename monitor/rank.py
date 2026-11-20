"""Pure ranking helpers. No network."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone


def contains_term(text: str, term: str) -> bool:
    """Match a term in text.

    Multi-word phrases match as substrings. A single word matches only on a
    boundary, so "ai" does not hit "available" and "gene" does not hit
    "generate".
    """
    hay = text.lower()
    needle = term.lower().strip()
    if not needle:
        return False
    if any(char.isspace() for char in needle) or "-" in needle:
        return needle in hay
    return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", hay) is not None


def _parse(iso: str) -> datetime | None:
    if not iso:
        return None
    text = iso.strip().replace("+00:00", "Z")
    if "." in text:
        text = text.split(".", 1)[0] + "Z"
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def age_days(iso: str, now: datetime) -> float:
    parsed = _parse(iso)
    if parsed is None:
        return 9999
    return max((now - parsed).total_seconds() / 86400, 0)


def select_posts(posts: list[dict], window_days: int, now: datetime) -> list[dict]:
    fresh = [post for post in posts if age_days(post["created_at"], now) <= window_days]
    if len(fresh) >= 4:
        return fresh
    wider = [post for post in posts if age_days(post["created_at"], now) <= window_days * 3]
    return wider or list(posts)


def heat(post: dict, now: datetime, boosted: bool) -> float:
    if _parse(post.get("created_at", "")) is None:
        return 0
    metrics = post["metrics"]
    engagement = (
        metrics.get("likes", 0)
        + 2 * metrics.get("reposts", 0)
        + metrics.get("replies", 0)
        + metrics.get("quotes", 0)
    )
    hours = max(age_days(post["created_at"], now) * 24, 0.5)
    score = (engagement + 1) / (hours ** 0.55)
    if boosted:
        score *= 1.75
    return score


def rank_posts(posts: list[dict], boost: tuple[str, ...], window_days: int, now: datetime, limit: int) -> list[dict]:
    chosen = select_posts(posts, window_days, now)
    ranked = []
    for post in chosen:
        boosted = any(contains_term(post["text"], phrase) for phrase in boost)
        scored = dict(post)
        scored["score"] = round(heat(post, now, boosted), 2)
        ranked.append(scored)
    ranked.sort(key=lambda item: item["score"], reverse=True)
    deduped = []
    seen = set()
    for post in ranked:
        if post["id"] in seen:
            continue
        seen.add(post["id"])
        deduped.append(post)
        if len(deduped) >= limit:
            break
    return deduped


def build_topics(posts: list[dict], terms: tuple[str, ...]) -> list[dict]:
    tags: Counter[str] = Counter()
    words: Counter[str] = Counter()
    for post in posts:
        for tag in post.get("hashtags") or []:
            tags[tag.lower()] += 1
        for term in terms:
            if contains_term(post["text"], term):
                words[term] += 1
    topics = []
    for tag, count in tags.most_common(8):
        topics.append({"label": f"#{tag}", "count": count, "kind": "hashtag"})
    for term, count in words.most_common(6):
        if count >= 2:
            topics.append({"label": term, "count": count, "kind": "term"})
    return topics[:10]


def match_trends(groups: list[tuple[str, list[dict]]], terms: tuple[str, ...]) -> list[dict]:
    matched = []
    seen = set()
    for place, trends in groups:
        for trend in trends:
            key = trend["name"].casefold()
            if key in seen:
                continue
            if any(contains_term(trend["name"], term) for term in terms):
                seen.add(key)
                item = dict(trend)
                item["place"] = place
                matched.append(item)
    return matched


def check_rank() -> None:
    assert contains_term("AI model", "ai")
    assert not contains_term("available now", "ai")
    assert not contains_term("generate ideas", "gene")
    assert contains_term("CRISPR gene edit", "gene")
    assert contains_term("Series A round", "series a")
    assert not contains_term("openai", "ai")
    now = datetime(2026, 11, 20, tzinfo=timezone.utc)
    posts = [
        {
            "id": "1",
            "text": "We just launched a new app on the App Store",
            "created_at": "2026-11-19T12:00:00Z",
            "metrics": {"likes": 10, "reposts": 1, "replies": 0, "quotes": 0},
            "hashtags": ["launch"],
        },
        {
            "id": "2",
            "text": "Quiet note",
            "created_at": "2026-11-19T12:00:00Z",
            "metrics": {"likes": 1, "reposts": 0, "replies": 0, "quotes": 0},
            "hashtags": [],
        },
    ]
    ranked = rank_posts(posts, ("just launched",), 7, now, 10)
    assert ranked[0]["id"] == "1"
    assert ranked[0]["score"] > ranked[1]["score"]
    topics = build_topics(ranked, ("app store",))
    assert topics[0]["label"] == "#launch"
    trends = match_trends([("Worldwide", [{"name": "OpenAI", "posts": 3, "url": "https://x.com"}])], ("openai",))
    assert trends[0]["place"] == "Worldwide"
    assert match_trends([("Worldwide", [{"name": "available", "posts": 1, "url": ""}])], ("ai",)) == []
