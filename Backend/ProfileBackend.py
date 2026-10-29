from db import query
import RepBackend as rep

# how many recent actions to show on a profile
RECENT_LIMIT = 20


def get_profile(user_id, recent_limit=RECENT_LIMIT, viewer_id=None):
    # only pull public-safe columns (never email or password_hash)
    user = query(
        "SELECT id, username, reputation, created_at FROM users WHERE id = %s",
        (user_id,),
        fetchone=True,
    )
    if not user:
        return None

    # one pass over the user's predictions to get every number the profile needs
    stats = query(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE result = 'correct')   AS correct,
            COUNT(*) FILTER (WHERE result = 'incorrect') AS incorrect,
            COUNT(*) FILTER (WHERE result = 'pending')   AS pending,
            COUNT(*) FILTER (WHERE result = 'void')      AS void,  -- refunded picks (ties, cancelled games)
            COALESCE(SUM(points) FILTER (WHERE result = 'correct'), 0)   AS rep_gained,
            COALESCE(SUM(points) FILTER (WHERE result = 'incorrect'), 0) AS rep_lost
        FROM predictions
        WHERE user_id = %s
        """,
        (user_id,),
        fetchone=True,
    )
    
    # follower counts, and whether the person looking at this profile already follows them
    follow = query(
        """
        SELECT
            (SELECT COUNT(*) FROM follows WHERE followed_id = %s) AS followers,
            (SELECT COUNT(*) FROM follows WHERE follower_id = %s) AS following,
            EXISTS(SELECT 1 FROM follows WHERE follower_id = %s AND followed_id = %s) AS is_following,
            EXISTS(SELECT 1 FROM follows WHERE follower_id = %s AND followed_id = %s) AS follows_me
        """,
        (user_id, user_id, viewer_id, user_id, user_id, viewer_id),
        fetchone=True,
    )

    # accuracy only counts settled predictions, pending ones haven't been decided yet
    # (void picks were refunded, so they count as neither right nor wrong)
    settled = stats["correct"] + stats["incorrect"]
    accuracy = round(stats["correct"] * 100 / settled, 1) if settled else None

    # posts, comments and predictions merged into one newest-first feed
    activity = query(
        """
        SELECT type, title, body, result, points, created_at FROM (
            SELECT 'post' AS type, NULL::text AS title, content AS body,
                   NULL::text AS result, NULL::int AS points, created_at
            FROM posts WHERE user_id = %s
            UNION ALL
            SELECT 'comment', NULL::text, content, NULL::text, NULL::int, created_at
            FROM comments WHERE user_id = %s
            UNION ALL
            SELECT 'prediction', game, prediction_text, result, points, created_at
            FROM predictions WHERE user_id = %s
        ) AS feed
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (user_id, user_id, user_id, recent_limit),
    )

    return {
        "id": user["id"],
        "username": user["username"],
        "reputation": user["reputation"],
        "rep_community": rep.community_rep(user_id),  # earned from posts, comments and likes
        "member_since": user["created_at"],
        "followers": follow["followers"],
        "following": follow["following"],
        "is_following": follow["is_following"],
        "is_friend": bool(follow["is_following"] and follow["follows_me"]),
        "is_me": viewer_id == user["id"],
        "predictions": {
            "total": stats["total"],
            "correct": stats["correct"],
            "incorrect": stats["incorrect"],
            "pending": stats["pending"],
            "void": stats["void"],
            "settled": settled,
            "accuracy": accuracy,  # percent, or None when nothing has been settled yet
            "rep_gained": stats["rep_gained"],
            "rep_lost": stats["rep_lost"],
        },
        "recent_activity": activity,
    }


def get_profile_by_username(username, viewer_id=None):
    user = query("SELECT id FROM users WHERE username = %s", (username,), fetchone=True)
    return get_profile(user["id"], viewer_id=viewer_id) if user else None


# the columns shown for each pick; games is LEFT JOINed so older picks without a game still show
PICK_COLUMNS = (
    "p.id, p.game, p.prediction_text, p.points, p.result, p.created_at, "
    "g.home_team, g.away_team, g.start_time, g.status, g.home_score, g.away_score"
)
PAST_LIMIT = 50


def get_predictions_by_username(username):
    user = query("SELECT id FROM users WHERE username = %s", (username,), fetchone=True)
    if not user:
        return None

    # current = still pending, soonest game first
    current = query(
        "SELECT " + PICK_COLUMNS + " FROM predictions p LEFT JOIN games g ON g.id = p.game_id "
        "WHERE p.user_id = %s AND p.result = 'pending' "
        "ORDER BY g.start_time ASC NULLS LAST, p.created_at DESC",
        (user["id"],),
    )
    # past = already settled (correct or incorrect), newest first
    past = query(
        "SELECT " + PICK_COLUMNS + " FROM predictions p LEFT JOIN games g ON g.id = p.game_id "
        "WHERE p.user_id = %s AND p.result <> 'pending' "
        "ORDER BY p.created_at DESC LIMIT %s",
        (user["id"], PAST_LIMIT),
    )
    return {"username": username, "current": current, "past": past}    