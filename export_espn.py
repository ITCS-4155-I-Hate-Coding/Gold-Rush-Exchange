"""Downloads past and upcoming college games from ESPN into espn_season.json.

Read-only: it doesn't touch the database. Run it from any folder:
    python export_espn.py
It takes a few minutes (one request per day per sport) and writes espn_season.json next to this file.
"""
import json
import time
from datetime import date, timedelta
from pathlib import Path

import requests

URLS = {
    "football": "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard",
    "basketball": "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard",
}
# football: FBS (80). basketball: all of Division I (50), not just the featured games
GROUPS = {"football": 80, "basketball": 50}

today = date.today()
RANGES = {
    "football": [(date(2025, 8, 23), date(2026, 1, 20)), (date(2026, 8, 22), today + timedelta(days=7))],
    "basketball": [(date(2025, 11, 3), date(2026, 4, 7)), (date(2026, 11, 1), today + timedelta(days=7))],
}


def team(c):
    rank = (c.get("curatedRank") or {}).get("current")
    return {
        "id": c["team"].get("id"),
        "name": c["team"].get("displayName"),
        "score": c.get("score"),
        "rank": rank if rank and rank <= 25 else None,
        "conference_id": c["team"].get("conferenceId"),
    }


def clean_odds(odds):
    # keep the betting lines, drop the links and logos
    out = []
    for o in odds or []:
        out.append({k: v for k, v in o.items() if k not in ("links", "provider")}
                   | {"provider": (o.get("provider") or {}).get("name")})
    return out


session = requests.Session()
games = []
for sport, ranges in RANGES.items():
    for start, end in ranges:
        day = start
        while day <= end:
            params = {"dates": day.strftime("%Y%m%d"), "groups": GROUPS[sport], "limit": 500}
            for attempt in range(2):
                try:
                    events = session.get(URLS[sport], params=params, timeout=15).json().get("events", [])
                    break
                except (requests.RequestException, ValueError):
                    events = []
                    time.sleep(1)
            for e in events:
                try:
                    comp = e["competitions"][0]
                    home = next(c for c in comp["competitors"] if c["homeAway"] == "home")
                    away = next(c for c in comp["competitors"] if c["homeAway"] == "away")
                    games.append({
                        "id": e["id"],
                        "sport": sport,
                        "date": e["date"],
                        "neutral": comp.get("neutralSite", False),
                        "state": comp["status"]["type"].get("state"),
                        "completed": comp["status"]["type"].get("completed"),
                        "home": team(home),
                        "away": team(away),
                        "odds": clean_odds(comp.get("odds")),
                    })
                except (KeyError, StopIteration):
                    continue
            print(f"{sport} {day}  {len(events)} games")
            day += timedelta(days=1)

out = Path(__file__).with_name("espn_season.json")
out.write_text(json.dumps(games))
with_odds = sum(1 for g in games if g["odds"])
print(f"\nsaved {len(games)} games ({with_odds} with betting lines) to {out}")