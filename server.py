#!/usr/bin/env python3
"""Local server for the Situation Monitor dashboard."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
sys.path.insert(0, str(ROOT))

from monitor.board import Service  # noqa: E402
from monitor.rank import check_rank  # noqa: E402
from monitor.xclient import XError  # noqa: E402

SERVICE = Service(ROOT)
STATIC = {
    "/": WEB / "index.html",
    "/index.html": WEB / "index.html",
    "/styles.css": WEB / "styles.css",
    "/app.js": WEB / "app.js",
    "/favicon.svg": WEB / "favicon.svg",
}
TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "situation-monitor"

    def log_message(self, fmt: str, *args) -> None:
        if str(args[0]).startswith("GET /api/") or args[-1] not in {200, "200"}:
            super().log_message(fmt, *args)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        fresh = urllib.parse.parse_qs(parsed.query).get("fresh", ["0"])[0] in {"1", "true", "yes"}
        try:
            if path == "/api/health":
                self._json(200, {"ok": True})
                return
            if path == "/api/meta":
                self._json(200, SERVICE.meta())
                return
            if path == "/api/overview":
                self._json(200, SERVICE.overview(fresh))
                return
            if path.startswith("/api/lanes/"):
                lane_id = path.removeprefix("/api/lanes/").strip("/")
                try:
                    self._json(200, SERVICE.lane(lane_id, fresh))
                except KeyError:
                    self._json(404, {"error": f"Unknown lane '{lane_id}'."})
                return
            file_path = STATIC.get(path)
            if file_path is None or not file_path.is_file():
                self._json(404, {"error": "Not found."})
                return
            body = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", TYPES.get(file_path.suffix, "application/octet-stream"))
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
        except XError as exc:
            self._json(502, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._json(500, {"error": str(exc)})

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def check() -> int:
    check_rank()
    print("rank checks passed")
    overview = SERVICE.overview(fresh=True)
    world = len(overview["worldwide"]["trends"])
    states = len(overview["united_states"]["trends"])
    moving = len(overview["moving"])
    print(f"overview worldwide={world} us={states} moving={moving} warnings={len(overview['warnings'])}")
    for warning in overview["warnings"]:
        print(f"  warn: {warning}")
    lane = SERVICE.lane("ai", fresh=True)
    print(f"lane ai posts={len(lane['posts'])} topics={len(lane['topics'])} news={len(lane['news'])}")
    for warning in lane["warnings"]:
        print(f"  warn: {warning}")
    if lane["posts"]:
        sample = lane["posts"][0]
        print(f"  top: @{sample['user']['screen_name']} {sample['text'][:90]!r}")
    if world < 5 or states < 5 or not lane["posts"]:
        print("check failed", file=sys.stderr)
        return 1
    print("check ok")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Situation Monitor")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--check", action="store_true", help="Read X once and exit")
    parser.add_argument("--no-open", action="store_true", help="Do not open a browser")
    args = parser.parse_args()
    if args.check:
        sys.exit(check())
    try:
        httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError as exc:
        print(f"Could not bind {args.host}:{args.port}: {exc}", file=sys.stderr)
        sys.exit(1)
    url = f"http://{args.host}:{args.port}"
    print(f"Situation Monitor at {url}")
    if not args.no_open:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
