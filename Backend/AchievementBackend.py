"""
Achievement backend 

1. catalog will hold possible achievements
2. sync with database 
3. check db and make sure everything is properly assigned

Tiers will decide rarity so bronze = 10, silver = 25, gold = 50, platinum = 100, diamond = 250. These scores are representative of difficulty.
Achievements will not give reputation.
Achievements will be permanent unless acount is deleted
*** rep won will be different than the balance of your account so you can have won 5,000 rep but your current balance only be 250.


"""

from db import query

# amount of badges user can show at once
MAX_FEATURED = 3

# leaderboard based achievements will only count once a user has made at least 5-10 wagers
# can change the amount but will be set at 10 for now
RANK_MIN_SETTLED = 10

# Tiers
TIERS = {
    "bronze": {"label": "Bronze", "value": 10},
    "silver": {"label": "Silver", "value": 25},
    "gold": {"label": "Gold", "value": 50},
    "platinum": {"label": "Platinum", "value": 100},
    "diamond": {"label": "Diamond", "value": 250},
}

# Track - the category of achievements
# label = heading shown on profile
# stat = the key that threshold is compared with

TRACKS = {
    "rep_won":        {"label": "Rep won",            "stat": "rep_won",        "unit": "rep won"},
    "reputation":     {"label": "Bankroll",           "stat": "reputation",     "unit": "rep balance"},
    "correct":        {"label": "Correct picks",      "stat": "correct",        "unit": "correct picks"},
    "predictions":    {"label": "Predictions made",   "stat": "total_preds",    "unit": "predictions"},
    "streak":         {"label": "Win streak",         "stat": "best_streak",    "unit": "in a row"},
    "big_win":        {"label": "Big wins",           "stat": "biggest_win",    "unit": "rep on one winning pick"},
    "upsets":         {"label": "Upsets",             "stat": "upsets",         "unit": "upsets called"},
    "charlotte":      {"label": "Niner Nation",       "stat": "charlotte_wins", "unit": "Charlotte wins called"},
    "posts":          {"label": "Posts",              "stat": "posts",          "unit": "posts"},
    "comments":       {"label": "Comments",           "stat": "comments",       "unit": "comments"},
    "likes":          {"label": "Likes received",     "stat": "likes_received", "unit": "likes received"},
    "followers":      {"label": "Followers",          "stat": "followers",      "unit": "followers"},
    "rank":           {"label": "Leaderboard",        "stat": "rank",           "unit": "rank", "lower_is_better": True},
}

ACHIEVEMENT_DESCRIPTIONS = [
    # winnings from correct picks (net gain, so the starting 1,000 doesn't count)
    ("rep_won", 250,   "bronze",    "Prospector",      "Win 250 rep from correct predictions."),
    ("rep_won", 1000,  "silver",  "Panning for Gold", "Win 1,000 rep from correct predictions."),
    ("rep_won", 5000,  "gold",      "Struck Gold",     "Win 5,000 rep from correct predictions."),
    ("rep_won", 10000, "platinum",      "Gold Baron",      "Win 10,000 rep from correct predictions."),
    ("rep_won", 25000, "diamond", "Mother Lode",     "Win 25,000 rep from correct predictions."),
 
    # current balance (starts at 1,500 because everyone already has 1,000)
    ("reputation", 1500,  "bronze",    "Nest Egg",      "Reach a balance of 1,500 rep."),
    ("reputation", 2500,  "silver",  "Bankroll",      "Reach a balance of 2,500 rep."),
    ("reputation", 5000,  "gold",      "The Vault",     "Reach a balance of 5,000 rep."),
    ("reputation", 10000, "platinum",      "Fort Knox",     "Reach a balance of 10,000 rep."),
    ("reputation", 25000, "diamond", "Gold Standard", "Reach a balance of 25,000 rep."),
 
    ("correct", 1,   "bronze",    "On the Board", "Get your first prediction right."),
    ("correct", 10,  "silver",  "Sharp",        "Get 10 predictions right."),
    ("correct", 50,  "gold",      "Sharpshooter", "Get 50 predictions right."),
    ("correct", 100, "platinum",      "Oracle",       "Get 100 predictions right."),
    ("correct", 250, "diamond", "Prophet",      "Get 250 predictions right."),
 
    # just for taking part (no legendary: volume alone shouldn't be the rarest thing)
    ("predictions", 1,   "bronze",   "First Pick", "Make your first prediction."),
    ("predictions", 25,  "silver", "Regular",    "Make 25 predictions."),
    ("predictions", 100, "gold",     "Grinder",    "Make 100 predictions."),
    ("predictions", 250, "platinum",     "Ironman",    "Make 250 predictions."),
 
    # streaks start at uncommon: 3 in a row is already harder than a single correct pick
    ("streak", 3,  "silver",  "Heating Up",   "Get 3 settled predictions right in a row."),
    ("streak", 5,  "gold",      "On Fire",      "Get 5 settled predictions right in a row."),
    ("streak", 10, "platinum",      "Unstoppable",  "Get 10 settled predictions right in a row."),
    ("streak", 15, "diamond", "Untouchable",  "Get 15 settled predictions right in a row."),
 
    # rewards confidence: winning a pick with a big wager on it
    ("big_win", 100,  "silver", "Risk Taker",  "Win a prediction that wagered at least 100 rep."),
    ("big_win", 500,  "gold",     "High Roller", "Win a prediction that wagered at least 500 rep."),
    ("big_win", 2500, "platinum",     "All In",      "Win a prediction that wagered at least 2,500 rep."),
 
    # an upset = you picked an unranked team and it beat a Top 25 team
    ("upsets", 1, "gold", "Giant Killer",      "Correctly pick an unranked team to beat a Top 25 team."),
    ("upsets", 5, "platinum", "Upset Specialist",  "Correctly pick 5 unranked teams to beat Top 25 teams."),
 
    # school spirit: correctly picking Charlotte to win
    ("charlotte", 1,  "bronze", "Niner Nation",   "Correctly pick a Charlotte 49ers win."),
    ("charlotte", 10, "gold",   "Niner Faithful", "Correctly pick 10 Charlotte 49ers wins."),
 
    # social achievements are capped at rare/epic so the top tier stays about predicting
    ("posts", 1,   "bronze",   "First Words", "Write your first post."),
    ("posts", 25,  "silver", "Town Crier",  "Write 25 posts."),
    ("posts", 100, "gold",     "Columnist",   "Write 100 posts."),
 
    ("comments", 1,  "bronze",   "Chiming In",        "Leave your first comment."),
    ("comments", 50, "silver", "Conversationalist", "Leave 50 comments."),
 
    ("likes", 10,  "silver", "Crowd Pleaser",    "Get 10 likes from other people on your posts and comments."),
    ("likes", 100, "gold",     "Fan Favorite",     "Get 100 likes from other people on your posts and comments."),
    ("likes", 500, "platinum",     "Campus Celebrity", "Get 500 likes from other people on your posts and comments."),
 
    ("followers", 5,   "silver", "Rising Star", "Have 5 followers."),
    ("followers", 25,  "gold",     "Influencer",  "Have 25 followers."),
    ("followers", 100, "platinum",     "Icon",        "Have 100 followers."),
 
    # threshold is a rank here, and lower is better (see TRACKS["rank"])
    ("rank", 10, "platinum",      "Top Ten",         f"Reach the top 10 on the global leaderboard (after {RANK_MIN_SETTLED} settled picks)."),
    ("rank", 1,  "diamond", "King of the Hill", f"Reach #1 on the global leaderboard (after {RANK_MIN_SETTLED} settled picks)."),
]

# turning tuples into dictionaries for easier access
CATALOG = []
for order, (track, threshold, tier, name, description) in enumerate(ACHIEVEMENT_DESCRIPTIONS):
    CATALOG.append({
        "code": f"{track}_{threshold}",
        "track": track,
        "track_label": TRACKS[track]["label"],
        "name": name,
        "description": description,
        "tier": tier,
        "tier_label": TIERS[tier]["label"],
        "value": TIERS[tier]["value"],
        "threshold": threshold,
        "lower_is_better": TRACKS[track].get("lower_is_better", False),
        "sort_order": order, # breaking ties when sorting badges by value

    })

BY_CODE = {a["code"]: a for a in CATALOG}

# the catalog in the database
def sync_catalog():
    # copying catalog into achievements table and will be called once App.py starts

    for a in CATALOG:
        query(
            """
            INSERT INTO achievements (code, track, name, description, tier, value, threshold, sort_order)
             VALUES (%(code)s, %(track)s, %(name)s, %(description)s, %(tier)s, %(value)s, %(threshold)s, %(sort_order)s)
             ON CONFLICT (code) DO UPDATE SET track = EXCLUDED.track, name = EXCLUDED.name,
             description = EXCLUDED.description, tier = EXCLUDED.tier, value = EXCLUDED.value,
             threshold = EXCLUDED.threshold, sort_order = EXCLUDED.sort_order
            """,
            a, fetch=False,
        )

    # remove achievements that are deleted from ACHIEVEMENT_DESCRRIPTIONS
    query(
        "DELETE FROM achievements WHERE NOT (code = ANY(%s))", ([a["code"] for a in CATALOG],), fetch=False
    )
    return len(CATALOG)


def get_catalog():
    # will house everything the frontend needs to draw any badge. There wont be a database call at this ppoint it will be in memory
    return {"tiers": TIERS, "tracks": TRACKS, "max_featured": MAX_FEATURED, "achievements": CATALOG}


STATS_SQL = """
WITH me AS (
    SELECT id, reputation FROM users WHERE id = %(uid)s
),
pred AS (
    SELECT
        COUNT(*) AS total_preds,
        COUNT(*) FILTER (WHERE p.result = 'correct') AS correct,
        COUNT(*) FILTER (WHERE p.result <> 'pending') AS settled,
        COALESCE(SUM(p.points) FILTER (WHERE p.result = 'correct'), 0) AS rep_won,
        COALESCE(MAX(p.points) FILTER (WHERE p.result = 'correct'), 0) AS biggest_win,
        COUNT(*) FILTER (WHERE p.result = 'correct' AND (
            (p.pick = 'home' AND g.home_rank IS NULL AND g.away_rank IS NOT NULL) OR
            (p.pick = 'away' AND g.away_rank IS NULL AND g.home_rank IS NOT NULL)
        )) AS upsets,
        COUNT(*) FILTER (WHERE p.result = 'correct' AND
            (CASE p.pick WHEN 'home' THEN g.home_team WHEN 'away' THEN g.away_team END) ILIKE '%%charlotte%%'
        ) AS charlotte_wins
    FROM predictions p
    LEFT JOIN games g ON g.id = p.game_id
    WHERE p.user_id = %(uid)s
),
ordered AS (
    SELECT p.result,
        ROW_NUMBER() OVER (ORDER BY COALESCE(g.start_time, p.created_at), p.id)
        - ROW_NUMBER() OVER (PARTITION BY p.result ORDER BY COALESCE(g.start_time, p.created_at), p.id) AS grp
    FROM predictions p
    LEFT JOIN games g ON g.id = p.game_id
    WHERE p.user_id = %(uid)s AND p.result <> 'pending'
),
streak AS (
    SELECT COALESCE(MAX(n), 0) AS best_streak
    FROM (SELECT COUNT(*) AS n FROM ordered WHERE result = 'correct' GROUP BY grp) runs
)
SELECT
    me.reputation,
    pred.*,
    streak.best_streak,
    (SELECT COUNT(*) FROM posts WHERE user_id = me.id) AS posts, 
    (SELECT COUNT(*) FROM comments WHERE user_id = me.id) AS comments,
    -- likes from other people only, so liking your own posts does NOT count
    -- counted from likes table
    (SELECT COUNT(*) FROM post_likes pl JOIN posts po ON po.id = pl.post_id WHERE po.user_id = me.id AND pl.user_id <> me.id)
    + (SELECT COUNT(*) FROM comment_likes cl JOIN comments co ON co.id = cl.comment_id WHERE co.user_id = me.id AND cl.user_id <> me.id) AS likes_recieved,
    (SELECT COUNT(*) FROM follows WHERE followed_id = me.id) AS followers,
    1 + (SELECT COUNT(*) FROM users u WHERE u.reputation > me.reputation) AS rank,
    (SELECT COALESCE(json_agg(json_build_object('code', ua.code, 'earned_at', ua.earned_at, 'featured', ua.featured)), '[]')
        FROM user_achievements ua WHERE ua.user_id = me.id) AS earned
FROM me, pred, streak

"""

def compute_stats(user_id):
    # run stats sql for the user and return a dict of stats 
    row = query(
        STATS_SQL, {"uid": user_id}, fetchone=True)
    if not row:
        return None
    stats = dict(row)
    if stats["settled"] < RANK_MIN_SETTLED:
        # not eligible for achievements yet
        stats["rank"] = None
    return stats

def qualifies(achievement, stats):
    # will be true if the user meets the qualifications for achievements
    value = stats.get(TRACKS[achievement["track"]]["stat"])
    if value is None:
        return False
    if achievement["lower_is_better"]:
        return value <= achievement["threshold"]
    return value >= achievement["threshold"]

# awarding achievements
def check_achievements(user_id):
    # award anything the user qualifies for and return the achievements and stats
    stats = compute_stats(user_id)
    if not stats:
        return [], None
    have = {e["code"] for e in stats["earned"]}
    # everythhing the user now qualifies for that they didnt before
    new = [a["code"] for a in CATALOG if a["code"] not in have and qualifies(a, stats)]
    if new:
        # insert all in a statement
        # make sure it covers requests even if they are done at the same time
        inserted = query(
            """
            INSERT INTO user_achievements (user_id, code) SELECT %s, code FROM unnest(%s::text[]) AS code
             ON CONFLICT DO NOTHING RETURNING code,
             earned_at
            """, (user_id, new),
        )
        for row in inserted:
            stats["earned"].append({"code": row["code"], "earned_at": row["earned_at"], "featured": False})
        new = [row["code"] for row in inserted]
    return new, stats

# check users
# 
def try_check(*user_ids):
    for uid in {u for u in user_ids if u}:
        try:
            check_achievements(uid)
        except Exception as e: # catching everything
            print(f"[achievements] check failed for user {uid}: {e}")



def try_check_username(username):
    # After someone follows this user: check their follower achievements.
    row = query("SELECT id FROM users WHERE username = %s", (username,), fetchone=True)
    if row:
        try_check(row["id"])
 
 
def try_check_post_author(post_id):
    # After someone likes a post: the likes count toward the author, not the person liking it.
    row = query("SELECT user_id FROM posts WHERE id = %s", (post_id,), fetchone=True)
    if row:
        try_check(row["user_id"])
 
 
def try_check_comment_author(comment_id):
    # Same as try_check_post_author, for comment likes.
    row = query("SELECT user_id FROM comments WHERE id = %s", (comment_id,), fetchone=True)
    if row:
        try_check(row["user_id"])
 
 
def check_all_users():
    # Backfill: check every user. Run once after deploying (python AchievementBackend.py).
    total = 0
    for row in query("SELECT id FROM users ORDER BY id"):
        new, _ = check_achievements(row["id"])
        total += len(new)
    return total
 
 
def pop_unseen(user_id):
    # New achievements that the user has not seen yet and marks them as seen
    #
    rows = query(
        "UPDATE user_achievements SET seen = true WHERE user_id = %s AND NOT seen RETURNING code",
        (user_id,),
    )
    codes = {r["code"] for r in rows}
    return [a["code"] for a in sorted(CATALOG, key=lambda a: -a["value"]) if a["code"] in codes]
 
 
# ---------- Reading ----------
def _featured_sorted(earned):
    # featured codes with most valuable first and ties in the catalog order
    feats = [e for e in earned if e["featured"] and e["code"] in BY_CODE]
    feats.sort(key=lambda e: (-BY_CODE[e["code"]]["value"], BY_CODE[e["code"]]["sort_order"]))
    return [e["code"] for e in feats]
 
 
def get_user_achievements(username):
    """Everything the profile's Achievements section shows for one user (None if not found)."""
    user = query("SELECT id, username FROM users WHERE username = %s", (username,), fetchone=True)
    if not user:
        return None
    # check first, so anything they qualify for appears right away, then reuse those stats
    _, stats = check_achievements(user["id"])
 
    # rarity = share of all users who hold each achievement ("8% of players").
    # LEFT JOIN so achievements nobody has yet still appear with 0 holders.
    rarity = query(
        "SELECT a.code, COUNT(ua.user_id) AS holders, (SELECT COUNT(*) FROM users) AS players"
        " FROM achievements a LEFT JOIN user_achievements ua ON ua.code = a.code GROUP BY a.code"
    )
    rarity = {r["code"]: r for r in rarity}
 
    earned = {e["code"]: e for e in stats["earned"]}
    items = []
    for a in CATALOG:  # catalog order, so the page shows each track easiest to hardest
        e = earned.get(a["code"])
        r = rarity.get(a["code"])
        players = r["players"] if r else 0
        items.append({
            "code": a["code"],  # the frontend looks up name/tier/value in its copy of the catalog
            "earned": bool(e),
            "earned_at": e["earned_at"] if e else None,
            "featured": bool(e and e["featured"]),
            # the user's current number for this track, for the progress bar.
            # sent even for earned ones: it's cheap and lets the page show "825 / 1,000"
            "progress": stats.get(TRACKS[a["track"]]["stat"]),
            "holders_pct": round(r["holders"] * 100 / players, 1) if players else 0,
        })
 
    # "c in BY_CODE" guards against an old row for an achievement that was removed from the code
    score = sum(BY_CODE[c]["value"] for c in earned if c in BY_CODE)
    return {
        "username": user["username"],
        "score": score,
        "earned_count": len([c for c in earned if c in BY_CODE]),
        "total_count": len(CATALOG),
        "max_score": sum(a["value"] for a in CATALOG),
        "featured": _featured_sorted(stats["earned"]),
        "rank_min_settled": RANK_MIN_SETTLED,
        "achievements": items,
    }
 
 
def set_featured(user_id, codes):
    # save which badges the user shows next to their name
    # the request body comes from the browser, so check its shape before using it
    if not isinstance(codes, list) or not all(isinstance(c, str) for c in codes):
        return False, "Send a list of achievement codes."
    codes = list(dict.fromkeys(codes))  # drop duplicates, keep order
    if len(codes) > MAX_FEATURED:
        return False, f"You can show up to {MAX_FEATURED} badges."
    if codes:
        # every code must be one this user has actually earned.
        # (otherwise someone could send a request to show "King of the Hill" without earning it)
        owned = query(
            "SELECT code FROM user_achievements WHERE user_id = %s AND code = ANY(%s)",
            (user_id, codes),
        )
        if len(owned) != len(codes):
            return False, "You can only show badges you have earned."
    # one UPDATE sets featured = true for the chosen codes and false for everything else.
    # an empty list hides them all.
    query(
        "UPDATE user_achievements SET featured = (code = ANY(%s)) WHERE user_id = %s",
        (codes, user_id),
        fetch=False,
    )
    return True, "Badges updated."
 
 
def attach_badges(rows, key="username"):

    # adding badges and achievement score to each row that has a username
    # will be used by any route that returns usernames (posts, comments, predictions, people, compare, profile)
    rows = rows or []
    names = list({r[key] for r in rows if r.get(key)})  # each username once
    if not names:
        return rows
    # per user: total value of everything earned, and the featured codes in display order.
    # array_agg(... ORDER BY ...) FILTER (WHERE featured) builds the list of featured codes;
    # COALESCE(..., '{}') turns "no featured badges" into an empty list instead of NULL.
    data = query(
        """
        SELECT u.username,
               COALESCE(SUM(a.value), 0)::int AS score,
               COALESCE(array_agg(ua.code ORDER BY a.value DESC, a.sort_order)
                        FILTER (WHERE ua.featured), '{}'::text[]) AS badges
        FROM users u
        LEFT JOIN user_achievements ua ON ua.user_id = u.id
        LEFT JOIN achievements a ON a.code = ua.code
        WHERE u.username = ANY(%s)
        GROUP BY u.username
        """,
        (names,),
    )
    by_name = {d["username"]: d for d in data}
    for r in rows:
        d = by_name.get(r.get(key))
        r["badges"] = d["badges"] if d else []
        r["achievement_score"] = d["score"] if d else 0
    return rows
 
 
def leaderboard(sort="reputation", limit=100):
   
    # the top users with reputation, achievement score/count and featured badges
    # will be ranked by achievement score
    # the ORDER BY can't be a %s parameter (parameters are values, not SQL), so it's chosen
    # from two fixed strings. The user's text never goes into the SQL, so this is still safe.
    order = (
        "achievement_score DESC, u.reputation DESC"
        if sort == "achievements"
        else "u.reputation DESC, achievement_score DESC"
    )
    # this is an f-string, so {{}} below becomes {} (an empty array) in the SQL
    return query(
        f"""
        SELECT u.username, u.reputation,
               COALESCE(SUM(a.value), 0)::int AS achievement_score,
               COUNT(a.code)::int AS achievement_count,
               COALESCE(array_agg(ua.code ORDER BY a.value DESC, a.sort_order)
                        FILTER (WHERE ua.featured), '{{}}'::text[]) AS badges
        FROM users u
        LEFT JOIN user_achievements ua ON ua.user_id = u.id
        LEFT JOIN achievements a ON a.code = ua.code
        GROUP BY u.id, u.username, u.reputation
        ORDER BY {order}, u.username
        LIMIT %s
        """,
        (limit,),
    )
 
 
if __name__ == "__main__":
    # one-off maintenance: make sure the catalog is in the database, then give every
    # existing user the achievements they already qualify for
    print(f"Synced {sync_catalog()} achievements")
    print(f"Awarded {check_all_users()} achievements to existing users")
