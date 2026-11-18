"""
Prints every team's current Elo rating, best first. Nothing is saved: the ratings are rebuilt
from the final scores in the games table, the same way update_odds does it.

Run from the Backend folder:
    python ShowRatings.py                  (football, top 25)
    python ShowRatings.py basketball       (basketball, top 25)
    python ShowRatings.py football 100     (football, top 100)
"""
import sys

import OddsBackend as odds
from db import query

sport = sys.argv[1] if len(sys.argv) > 1 else "football"
top = int(sys.argv[2]) if len(sys.argv) > 2 else 25

games = query(
    "SELECT sport, home_team, away_team, start_time, status, home_score, away_score, home_rank, away_rank,"
    " home_conference, away_conference, neutral_site FROM games WHERE sport = %s",
    (sport,),
)
ratings, history = odds.build_ratings(games)

# only teams that have played a final game this season
this_season = max(odds.season_of(g["start_time"]) for g, _ in history)
played = {}
for g, _ in history:
    if odds.season_of(g["start_time"]) == this_season:
        for side in ("home", "away"):
            played.setdefault(g[f"{side}_team"], [0, 0])
        winner, loser = ("home", "away") if g["home_score"] > g["away_score"] else ("away", "home")
        if g["home_score"] != g["away_score"]:
            played[g[f"{winner}_team"]][0] += 1
            played[g[f"{loser}_team"]][1] += 1

rows = sorted(((ratings[(sport, team)], team, wl) for team, wl in played.items()), reverse=True)
print(f"{sport} ratings, {this_season} season ({len(rows)} teams, average team = {odds.START})\n")
print(f"{'#':>4}  {'team':<38}{'record':>8}{'rating':>9}")
for i, (rating, team, (w, l)) in enumerate(rows[:top], 1):
    print(f"{i:>4}  {team:<38}{f'{w}-{l}':>8}{rating:>9.0f}")