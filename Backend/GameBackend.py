"""
Fetches upcoming NCAA games and syncs them into the games table

The primary source will be ESPNs public scoreboard endpoint (no API key but unofficial and undocumented)
The backup will be CollegeFootballData / CollegeBasketballData (documented and has free API keys) -- will stay commented out for now
"""

import os
import threading
import time
from datetime import datetime, timedelta, timezone

import requests
from db import query

ESPN_URLS = {
    "football": "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard",
    "basketball": "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard",
}
# ESPN has group id for the FBS football group
FBS_GROUP = 80

# fallback when ESPN doesn't send a "state" (see _status below)
STATUS_MAP = {
    "STATUS_SCHEDULED": "scheduled",
    "STATUS_IN_PROGRESS": "in_progress",
    "STATUS_HALFTIME": "in_progress",
    "STATUS_END_PERIOD": "in_progress",
    "STATUS_FINAL": "final",
    "STATUS_POSTPONED": "canceled",
    "STATUS_CANCELED": "canceled",
}

# ESPN conference ids -> display names (others are left as None and only show under "All")
CONFERENCES = {
    "1": "ACC", "4": "Big 12", "5": "Big Ten", "8": "SEC", "9": "Pac-12",
    "12": "Conference USA", "15": "MAC", "17": "Mountain West", "18": "Independents",
    "37": "Sun Belt", "151": "American",
}

AUTO_SYNC_MINUTES = int(os.environ.get("AUTO_SYNC_MINUTES", "15"))
SYNC_COOLDOWN_SECONDS = 60  # the Sync button can't start a new sync more often than this

_sync_lock = threading.Lock()  # only one sync runs at a time in this server
_auto_lock = threading.Lock()  # held while a background sync is running
_last_sync = 0.0  # time.time() of the last finished sync
_last_result = None


def _rank(competitor):
    # ESPN uses 99 for unranked
    r = competitor.get("curatedRank", {}).get("current")
    return r if isinstance(r, int) and 1 <= r <= 25 else None


def _status(status_type):
    # ESPN status -> our status
    state = status_type.get("state")
    if state == "pre":
        return "scheduled"
    if state == "in":
        return "in_progress"
    if state == "post":
        return "final" if status_type.get("completed") else "canceled"
    return STATUS_MAP.get(status_type.get("name"), "scheduled")


def fetch_espn_games(sport, days_ahead=7, days_behind=7):
    games = []
    failed_days = 0
    today = datetime.now(timezone.utc).date()
    # a negative days_behind will fetch recent games to get their final scores and settle predictions
    for offset in range(-days_behind, days_ahead):
        params = {"dates": (today + timedelta(days=offset)).strftime("%Y%m%d")}
        if sport == "football":
            params["groups"] = FBS_GROUP
        try:
            resp = requests.get(ESPN_URLS[sport], params=params, timeout=10)
            resp.raise_for_status()
            events = resp.json().get("events", [])
        except (requests.RequestException, ValueError) as e:
            print(f"[games] {sport} {params['dates']} failed: {e}")
            failed_days += 1
            continue
        for event in events:
            try:
                competition = event["competitions"][0]
                home = next(c for c in competition["competitors"] if c["homeAway"] == "home")
                away = next(c for c in competition["competitors"] if c["homeAway"] == "away")
                games.append({
                    "external_id": event["id"],
                    "sport": sport,
                    "home_team": home["team"]["displayName"],
                    "away_team": away["team"]["displayName"],
                    "start_time": event["date"],
                    "status": _status(competition["status"]["type"]),
                    "home_score": int(home["score"]) if home.get("score") not in (None, "") else None,
                    "away_score": int(away["score"]) if away.get("score") not in (None, "") else None,
                    "home_rank": _rank(home),
                    "away_rank": _rank(away),
                    "home_conference": CONFERENCES.get(str(home["team"].get("conferenceId"))),
                    "away_conference": CONFERENCES.get(str(away["team"].get("conferenceId"))),
                })
            except (KeyError, IndexError, StopIteration, ValueError):
                continue

    return games, failed_days


# -- Backup source that will stay commented out and only brought in only if the ESPN endpoint stops working properly
#
# import os
# import cfbd
#
# def fetch_cfbd_games(year, week=None):
#     config = cfbd.Configuration(access_token=os.environ["CFBD_API_KEY"])
#     with cfbd.ApiClient(config) as client:
#             "sport": "football",
#             "home_team": g.home_team,
#             "away_team": g.away_team,
#             "start_time": g.start_date,
#             "status": "final" if g.completed else "scheduled",


def sync_games(sport, days_ahead=7, days_behind=7):
    # fetch one sport and upsert every game. returns the number of games processed
    games, _ = fetch_espn_games(sport, days_ahead, days_behind)
    for g in games:
        query(
            "INSERT INTO games (external_id, sport, home_team, away_team, start_time, status, home_score, away_score,"
            " home_rank, away_rank, home_conference, away_conference)"
            " VALUES (%(external_id)s, %(sport)s, %(home_team)s, %(away_team)s, %(start_time)s, %(status)s, %(home_score)s, %(away_score)s,"
            " %(home_rank)s, %(away_rank)s, %(home_conference)s, %(away_conference)s)"
            " ON CONFLICT (external_id) DO UPDATE SET status = EXCLUDED.status, start_time = EXCLUDED.start_time, home_score = EXCLUDED.home_score, away_score = EXCLUDED.away_score,"
            " home_rank = EXCLUDED.home_rank, away_rank = EXCLUDED.away_rank,"
            " home_conference = EXCLUDED.home_conference, away_conference = EXCLUDED.away_conference",
            g, fetch=False
        )
    return len(games)


def sync_all(settle):
    global _last_sync, _last_result
    with _sync_lock:
        result = {
            "football_synced": sync_games("football"),
            "basketball_synced": sync_games("basketball"),
        }
        result["predictions_settled"] = settle()
        _last_sync = time.time()
        _last_result = result
        return result


def sync_now(settle):
    if time.time() - _last_sync < SYNC_COOLDOWN_SECONDS and _last_result is not None:
        return {**_last_result, "recent": True}
    if _sync_lock.locked():
        last = _last_result or {"football_synced": 0, "basketball_synced": 0, "predictions_settled": 0}
        return {**last, "in_progress": True}
    return sync_all(settle)


def maybe_auto_sync(settle):
    if AUTO_SYNC_MINUTES <= 0 or time.time() - _last_sync < AUTO_SYNC_MINUTES * 60:
        return False
    if not _auto_lock.acquire(blocking=False):
        return False

    def run():
        try:
            sync_all(settle)
        except Exception as e:  # a background sync must never crash the server
            print(f"[games] background sync failed: {e}")
        finally:
            _auto_lock.release()

    threading.Thread(target=run, daemon=True).start()
    return True


def view_upcoming_games(sport=None):
    # only games that havent started yet; older games stay in the table for history
    if sport:
        return query("SELECT * FROM games WHERE sport = %s AND status = 'scheduled' AND start_time > NOW() ORDER BY start_time ASC", (sport,))
    return query("SELECT * FROM games WHERE status = 'scheduled' AND start_time > NOW() ORDER BY start_time ASC")


if __name__ == "__main__":
    print(f"Synced {sync_games('football')} football games")