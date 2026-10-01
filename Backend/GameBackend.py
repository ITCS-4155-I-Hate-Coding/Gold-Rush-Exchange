"""
Fetches upcoming NCAA games and syncs them into the games table

The primary source will be ESPNs public scoreboard endpoint (no API key but unofficial and undocumented)
The backup will be CollegeFootballData / CollegeBasketballData (documented and has free API keys) -- will stay commented out for now

"""

import requests
from datetime import datetime, timedelta, timezone
from db import query

ESPN_URLS = {
    "football": "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard",
    "basketball": "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard",
}
# ESPN has group id for the FBS football group
FBS_GROUP = 80

STATUS_MAP = {
    "STATUS_SCHEDULED": "scheduled",
    "STATUS_IN_PROGRESS": "in_progress",
    "STATUS_FINAL": "final",
}

# ESPN conference ids -> display names (others are left as None and only show under "All")
CONFERENCES = {
    "1": "ACC", "4": "Big 12", "5": "Big Ten", "8": "SEC", "9": "Pac-12",
    "12": "Conference USA", "15": "MAC", "17": "Mountain West", "18": "Independents",
    "37": "Sun Belt", "151": "American",
}

def _rank(competitor):
    # ESPN uses 99 for unranked
    r = competitor.get("curatedRank", {}).get("current")
    return r if isinstance(r, int) and 1 <= r <= 25 else None

def fetch_espn_games(sport, days_ahead=7):
    games = []
    today = datetime.now(timezone.utc).date()
    for offset in range(days_ahead):
        params = {"dates": (today + timedelta(days=offset)).strftime("%Y%m%d")}
        if sport == "football":
            params["groups"] = FBS_GROUP # inserting the group id for NCAA football; not necessary for basketball
        resp = requests.get(ESPN_URLS[sport], params=params, timeout=10)
        resp.raise_for_status()
        for event in resp.json().get("events", []):
            
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
                    "status": STATUS_MAP.get(competition["status"]["type"]["name"], "scheduled"),
                    "home_score": int(home["score"]) if home.get("score") is not None else None,
                    "away_score": int(away["score"]) if away.get("score") is not None else None,
                    "home_rank": _rank(home),
                    "away_rank": _rank(away),
                    "home_conference": CONFERENCES.get(str(home["team"].get("conferenceId"))),
                    "away_conference": CONFERENCES.get(str(away["team"].get("conferenceId"))),
                })
            except (KeyError, IndexError, StopIteration):
                continue # skip malformed or incomplete events instead of aborting the whole sync

    return games


# -- Backup source that will stay commented out and only brought in only if the ESPN endpoint stops working properly
# Requires pip install cfbd, and CFBD_API_KEY / CBBD_API_KEY in .env (free signup on websites)
#
#

# import cfbd
# def fetch_cfbd_games(year, week=None):
#     config = cfbd.Configuration(access_token=os.environ["CFBD_API_KEY"])
#     with cfbd.ApiClient(config) as client:
#         games = cfbd.GamesApi(client).get)games(year=year, week=week, season_type="regular")
#         return [(
#             "external_id": str(g.id), 
#             "sport": "football",
#             "home_team": g.home_team, 
#             "away_team": g.away_team,
#             "start_time": g.start_date,
#             "status": "final" if g.completed else "scheduled",
#             "home_score": g.home_points, "away_score": g.away_points,

#         ) for g in games]


# def fetch_cbbd_games(year, week=None):
#     config = cbbd.Configuration(access_token=os.environ["CFBD_API_KEY"])
#     with cfbd.ApiClient(config) as client:
#         games = cbbd.GamesApi(client).get)games(year=year, week=week, season_type="regular")
#         return [(
#             "external_id": str(g.id), 
#             "sport": "football",
#             "home_team": g.home_team, 
#             "away_team": g.away_team,
#             "start_time": g.start_date,
#             "status": "final" if g.completed else "scheduled",
#             "home_score": g.home_points, "away_score": g.away_points,

#         ) for g in games]

def sync_games(sport, days_ahead=7):
    games = fetch_espn_games(sport, days_ahead)
    for g in games:
        query(
            "INSERT INTO games (external_id, sport, home_team, away_team, start_time, status, home_score, away_score," \
            " home_rank, away_rank, home_conference, away_conference)" \
            " VALUES (%(external_id)s, %(sport)s, %(home_team)s, %(away_team)s, %(start_time)s, %(status)s, %(home_score)s, %(away_score)s," \
            " %(home_rank)s, %(away_rank)s, %(home_conference)s, %(away_conference)s)" \
            " ON CONFLICT (external_id) DO UPDATE SET status = EXCLUDED.status, home_score = EXCLUDED.home_score, away_score = EXCLUDED.away_score," \
            " home_rank = EXCLUDED.home_rank, away_rank = EXCLUDED.away_rank," \
            " home_conference = EXCLUDED.home_conference, away_conference = EXCLUDED.away_conference",
            g, fetch=False
        )
    return len(games)


def view_upcoming_games(sport=None):
    if sport:
        return query("SELECT * FROM games WHERE sport = %s AND status != 'final' ORDER BY start_time ASC", (sport,))
    return query("SELECT * FROM games WHERE status != 'final' ORDER BY start_time ASC")


if __name__ == "__main__":
    print(f"Synced {sync_games('football')} football games")

