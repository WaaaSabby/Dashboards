#!/usr/bin/env python3
"""Publish a dashboard to the site.

Usage: python3 tools/publish.py <sport> <dashboard.html> "<slate label>" [YYYY-MM-DD]

- Copies the dashboard to <sport>/index.html (the permanent link friends bookmark)
- Keeps a dated copy at <sport>/archive/<date>.html
- Adds a small "All dashboards" link at the top of both copies
- Updates updates.json (last-updated time, slate label, archive list)
"""
import json, sys, datetime, pathlib
from zoneinfo import ZoneInfo

SPORTS = ["mlb", "nhl", "nfl", "cfb", "nba", "wnba"]
ROOT = pathlib.Path(__file__).resolve().parent.parent
TZ = ZoneInfo("America/Toronto")

NAV = ('<div id="sd-nav" style="background:#0b0912;border-bottom:1px solid #2c2244;'
       'padding:8px 16px;font:600 13px system-ui,-apple-system,Segoe UI,Roboto,sans-serif">'
       '<a href="{href}" style="color:#a970ff;text-decoration:none">&larr; All dashboards</a></div>')


def add_nav(html, href):
    if 'id="sd-nav"' in html:
        return html
    i = html.lower().find("<body")
    if i == -1:
        return NAV.format(href=href) + html
    j = html.find(">", i) + 1
    return html[:j] + NAV.format(href=href) + html[j:]


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    sport, src, slate = sys.argv[1].lower(), pathlib.Path(sys.argv[2]), sys.argv[3]
    if sport not in SPORTS:
        sys.exit(f"sport must be one of {SPORTS}")
    now = datetime.datetime.now(TZ)
    date = sys.argv[4] if len(sys.argv) > 4 else now.strftime("%Y-%m-%d")
    html = src.read_text(encoding="utf-8")

    d = ROOT / sport
    (d / "archive").mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(add_nav(html, "../"), encoding="utf-8")
    (d / "archive" / f"{date}.html").write_text(add_nav(html, "../../"), encoding="utf-8")

    up_path = ROOT / "updates.json"
    data = json.loads(up_path.read_text()) if up_path.exists() else {}
    info = data.setdefault(sport, {"updated": None, "slate": None, "archive": []})
    info["updated"] = now.isoformat(timespec="seconds")
    info["slate"] = slate
    arch = [e for e in info.get("archive", []) if e.get("date") != date]
    arch.append({"date": date, "slate": slate, "file": f"{sport}/archive/{date}.html"})
    info["archive"] = sorted(arch, key=lambda e: e["date"], reverse=True)
    up_path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Published {sport} ({date}): {slate}")


if __name__ == "__main__":
    main()
