"""
one off file to load last season and this seasons games so far so there is something to learn from 

run once using 
    python BackfillGames.py
"""

from datetime import date, timedelta
import GameBackend as games
import OddsBackend as odds

SEASON_DAYS = {"football": ((8, 20), (1, 20)),
               "basketball": ((11, 1), (4, 10))}

def season_range(sport, season):
    (m1, d1), (m2, d2) = SEASON_DAYS[sport]
    return date(season, m1, d1), min(date(season + 1, m2, d2), date.today())


if __name__ == "__main__":
    today = date.today()
    this_season = today.year if today.month >= 7 else today.year - 1
    for sport in SEASON_DAYS:
        for season in (this_season - 1, this_season):
            day, end = season_range(sport, season)
            saved = 0
            while day <= end:
                saved += games.save_games(games.fetch_day(sport, day) or [])
                day += timedelta(days=1)
            print(f"{sport} {season}: {saved} games")
    print(f"odds set on {odds.update_odds()} upcoming games")


