"""
Odds for all games using some elo ratings

Every team will have a rating and after each final score, the winner takes rating points from the loser essentially
A teams chance to win is worked out fro mthe difference between their two ratings

The ratings are from each of the final scores

These ratings are going to be different from the AP polls top 25 rankings

"""

import json
import math
from db import query

# will be tuned on the last seasons rankings so this is just 2025 for the moment

"""
1. Rating gap into a chance to win

    P(home wins) = 1 / (1 + 10 ^ (-D/400))
    D = home rating - away rating + home edge

    - using a similar logistic curve to elo for chess
    - 400 sets the scale; every 400 points of gap multiplies odds by 10
        - 

EX:
    Charlotte vs ECU Nov 14th
    - Charlotte home rating: 1221.6
    - ECU away rating: 1533.9 

    D = 1221.6 - 1533.9 + 65 = -247.3
    P(Charlotte) = 1 / (1 + 10 ^ (247.3 / 400))
        = 19.4%
    
    P(ECU) = 1 - P(Charlotte) = 80.6%

2. Updating Ratings after each game

    change = K * M * (result - expected)
    home rating += change
    away rating -= change

    - result = 1 if home win, 0 if lost
    - expected is chance from the ratings (like above Charlotte: 19.4% home and ECU: 80.6% away)

    - so if 90% favorite wins, it only "beat expecetations" by 0.10, so it gains little. If it loses, it missed by
      0.90, so it loses a lot. Average rating stays at 1500 because what every team wins, another team loses

3. Correction
    Formulas used from FiveThirtyEightElo

    M = ln(|margin| + 1) * (2.2 / (0.001 * D(winner) + 2.2))

    - favorite tends to win by more, so when winner was the favorite (D(winner)) positive, the multiplier shrinks
      and grows with the underdog
    - rewards bigger wins with shrinking returns
        - 1pt win = 0.69
        - 7pt win = 2.08
        - 28pt win = 3.37

    EX. Charlotte 38 @ Temple 31 (10/17)

    Before: Temple (home) = 1390.3, Charlotte (away) = 1171.6

            D = 1309.3 - 1172.6 + 65 
                = 282.6
            
            expected (Temple wins) = 0.8358
            result (temple lost) = 0

            M = ln(7 + 1) * (2.2 / (0.001 * (-282.6) + 2.2))
                = 2.386

            change = 40 * 2.386 * (0 - 0.8358) 
                = -79.8

    After: Temple = 1310.5, Charlotte = 1252.4


4. Ratings and New Seasons
    - teams will first get these ratings when it first appears in data (start of the last season and the games before backfilling)

    first rating = 1500 + bonus * ((26 - AP Rank) / 25) --ranked
        bonus = 400(fb), 600(bb)
    
    first rating = 1500 --unranked

    first rating = 1000 (for FCS football) and 600 (outside Div 1 basketball)

    Example. Football ratings will start with this: 

        Rank       #1      #5      #10     #25     unranked       FCS
               
        Rating    1900.   1836    1756     1516      1500         1000

    each team keeps 2/3 distance from the average and gives back the rest 

    new season rating = 1500 + (old rating - 1500) * 0.67

                End of 2025         Start of 2026

    Georgia:    1958                1807
    Indiana:    2110                1909    
    Charlotte:  1187                1290


5. Choosing a fair payout

    fair odds = 1 / P

    kept between 1.01X and 5.00x to make sure the payout cannot be too crazy or potentially losing money for winning


"""



SETTINGS = {

    # 'k' is how far one game can move a voting (40 for football, 28 for basketball since each game is worth less)
    # home rating is the home field advantage in the rating points
    # ranked_bonus os how far above average
    # carry is the share of last seasons ratings that were kept


    "football": {"k": 40, "home": 65, "ranked_bonus": 400, "lower": -500, "carry": 0.67},
    "basketball": {"k": 28, "home": 90, "ranked_bonus": 600, "lower": -900, "carry": 0.67}
}

START = 1500 # an average team
MAX_ODDS = 5.0 # biggest payout
MIN_ODDS = 1.01 # smallest payout

def season_of(start_time):
    return start_time.year if start_time.month >= 7 else start_time.year - 1

def first_rating(sport, rank, conference):
    s = SETTINGS[sport]
    if conference is None:
        return START + s["lower"] # the FCS and non-div 1 basketball teams will start lower
    if rank:
        return START + s["ranked_bonus"] * (26 - rank) / 25
    return START

def home_edge(sport, neutral):
    return 0 if neutral else SETTINGS[sport]["home"]

def win_chance(diff):
    return 1 / (1 + 10 ** (-diff / 400))

def build_ratings(games):
    # will replay the final games in order 
    ratings, seasons, history = {}, {}, []
    for g in sorted(games, key=lambda g: g["start_time"]):
        sport = g["sport"]
        s = SETTINGS[sport]
        season = season_of(g["start_time"])
        for side in ("home", "away"):
            key = (sport, g[f"{side}_team"])
            if key not in ratings:
                ratings[key] = first_rating(sport, g[f"{side}_rank"], g[f"{side}_conference"])
            elif seasons[key] != season:
                ratings[key] = START + (ratings[key] - START) * s["carry"]
                # keep part of last weeks ratings 
            seasons[key] = season
        if g["status"] != "final" or g["home_score"] is None or g["away_score"] is None:
            continue
        home, away = (sport, g["home_team"]), (sport, g["away_team"])
        diff = ratings[home] - ratings[away] + home_edge(sport, g["neutral_site"])
        expected = win_chance(diff)
        history.append((g, expected))
        margin = g["home_score"] - g["away_score"]
        result = 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5

        winner_diff = diff if margin > 0 else -diff
        mov = math.log(abs(margin) + 1) * 2.2 / (0.001 * winner_diff + 2.2)
        change = s["k"] * mov * (result - expected)
        ratings[home] += change
        ratings[away] -= change
    return ratings, history


def odds_for(chance):
    # fair odds so the multiplier that pays back what the pick is worth on average
    return round(min(MAX_ODDS, max(MIN_ODDS, 1 / chance)), 2)

def to_win(points, odds):
    return int(points * (odds - 1) + 1e-9)

def update_odds():
    # rebuild from final scores
    games = query(
        "SELECT id, sport, home_team, away_team, start_time, status, home_score, away_score, home_rank, away_rank,"
        " home_conference, away_conference, neutral_site FROM games"
    )
    ratings, _ = build_ratings(games)
    rows = []
    for g in games:
        if g["status"] != "scheduled":
            continue
        diff = ratings[(g["sport"], g["home_team"])] - ratings[(g["sport"], g["away_team"])]
        chance = win_chance(diff + home_edge(g["sport"], g["neutral_site"]))
        rows.append({"id": g["id"], "chance": round(chance, 3), "home": odds_for(chance), "away": odds_for(1 - chance)})
    if rows:
        # a statement for everygame like save games
        query(
            """
            UPDATE games SET home_chance = x.chance, home_odds = x.home, away_odds = x.away
             FROM json_to_recordset(%s::json) AS x(id int, chance numeric, home numeric, away numeric)
             WHERE games.id = x.id
            """,
            (json.dumps(rows),), fetch=False,
        )
    return len(rows)

if __name__ == "__main__":
    print(f"Updated odds on {update_odds()} upcoming games")