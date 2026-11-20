"""Build the overview and one field lane."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from .cache import DiskCache, Flights
from .lanes import LANES, LANES_BY_ID, Lane
from .rank import build_topics, match_trends, rank_posts
from .xclient import GuestClient, OfficialClient, XError

OVERVIEW_TTL = 300
LANE_TTL = 720
PLACES = (
    ("worldwide", "Worldwide", 1),
    ("united_states", "United States", 23424977),
)


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Service:
    def __init__(self, root: Path):
        load_env(root / ".env")
        token = os.environ.get("X_BEARER_TOKEN", "").strip()
        self.official = OfficialClient(token) if token else None
        self.guest = GuestClient()
        self.cache = DiskCache(root / "data" / "cache.json")
        self.flights = Flights()

    @property
    def official_enabled(self) -> bool:
        return self.official is not None

    def meta(self) -> dict:
        return {
            "official": self.official_enabled,
            "overview_ttl": OVERVIEW_TTL,
            "lane_ttl": LANE_TTL,
            "lanes": [lane.public() for lane in LANES],
        }

    def overview(self, fresh: bool = False) -> dict:
        return self._cached("overview", OVERVIEW_TTL, fresh, self._overview)

    def lane(self, lane_id: str, fresh: bool = False) -> dict:
        lane = LANES_BY_ID.get(lane_id)
        if lane is None:
            raise KeyError(lane_id)
        return self._cached(f"lane:{lane_id}", LANE_TTL, fresh, lambda: self._lane(lane))

    def _cached(self, key: str, ttl: float, fresh: bool, producer):
        if not fresh:
            cached = self.cache.get(key, ttl)
            if cached is not None:
                cached["cached"] = True
                return cached

        def run():
            value = producer()
            self.cache.put(key, value)
            return value

        value = self.flights.do(key if not fresh else f"{key}:fresh", run)
        value["cached"] = False
        return value

    def _place(self, woeid: int, label: str) -> tuple[list[dict], str, list[str]]:
        warnings = []
        if self.official:
            try:
                trends, name = self.official.trends(woeid)
                if trends:
                    return trends, name or label, warnings
                warnings.append(f"{label}: the X API returned an empty trend list.")
            except XError as exc:
                warnings.append(f"{label}: official trends failed ({exc}). Using the public list.")
        try:
            trends, name = self.guest.trends(woeid)
            return trends, name or label, warnings
        except XError as exc:
            warnings.append(f"{label} trends are unavailable ({exc}).")
            return [], label, warnings

    def _overview(self) -> dict:
        warnings = []
        places = {}
        for key, label, woeid in PLACES:
            trends, name, place_warnings = self._place(woeid, label)
            warnings.extend(place_warnings)
            places[key] = {"name": name, "trends": trends}
        moving = []
        try:
            moving = rank_posts(
                self.guest.trending_posts(20),
                (),
                2,
                datetime.now(timezone.utc),
                12,
            )
        except XError as exc:
            warnings.append(f"Trending posts are unavailable ({exc}).")
        lane_rows = []
        for lane in LANES:
            hits = match_trends(
                [
                    (places["worldwide"]["name"], places["worldwide"]["trends"]),
                    (places["united_states"]["name"], places["united_states"]["trends"]),
                ],
                lane.terms,
            )
            lane_rows.append({
                "id": lane.id,
                "title": lane.title,
                "accent": lane.accent,
                "trend_count": len(hits),
            })
        return {
            "fetched_at": _now(),
            "official": self.official_enabled,
            "worldwide": places["worldwide"],
            "united_states": places["united_states"],
            "moving": moving,
            "lanes": lane_rows,
            "warnings": warnings,
        }

    def _account_posts(self, lane: Lane) -> tuple[list[dict], list[str]]:
        warnings = []
        posts = []

        def fetch(account: tuple[str, str]):
            handle, name = account
            try:
                return handle, name, self.guest.originals(handle, 20), None
            except XError as exc:
                return handle, name, [], str(exc)

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(fetch, lane.accounts))
        for handle, _name, batch, error in results:
            if error:
                warnings.append(f"@{handle}: {error}")
            posts.extend(batch)
        return posts, warnings

    def _lane(self, lane: Lane) -> dict:
        warnings = []
        posts, account_warnings = self._account_posts(lane)
        warnings.extend(account_warnings)
        news = []
        if self.official:
            try:
                news = self.official.news(lane.news_query)
            except XError as exc:
                warnings.append(f"X News is unavailable ({exc}).")
            try:
                posts.extend(self.official.search(lane.search_query))
            except XError as exc:
                warnings.append(f"Platform search is unavailable ({exc}).")
        now = datetime.now(timezone.utc)
        ranked = rank_posts(posts, lane.boost, lane.window_days, now, 18)
        overview = self.overview(fresh=False)
        trends = match_trends(
            [
                (overview["worldwide"]["name"], overview["worldwide"]["trends"]),
                (overview["united_states"]["name"], overview["united_states"]["trends"]),
            ],
            lane.terms,
        )
        body = lane.public()
        body.update({
            "fetched_at": _now(),
            "official": self.official_enabled,
            "topics": build_topics(ranked, lane.terms),
            "trends": trends,
            "news": news,
            "posts": ranked,
            "warnings": warnings,
            "window_days": lane.window_days,
        })
        return body
