# Put this in your Backend folder next to LoginBackend.py, PostBackend.py, etc.
# Run:  pip install flask   then   python app.py   and open http://localhost:5000
from pathlib import Path
from flask import Flask, jsonify, request, session, send_from_directory

from db import query
import LoginBackend as auth
import PostBackend as posts
import CommentBackend as comments
import PredictionBackend as preds
import ProfileBackend as profile
import FollowBackend as follow
import CompareBackend as compare
import AchievementBackend as achievements
import os
import GameBackend as games

# Add this route to your app.py (anywhere near the other @app.get routes).
# It powers the "Global" view on the Leaderboard tab.
# No login required -- the global leaderboard is public, like the posts feed.



FRONTEND = Path(__file__).resolve().parent.parent / "Frontend"
app = Flask(__name__, static_folder=str(FRONTEND), static_url_path="")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-me")

# achievements will sync every time the server starts and is wrapped in try/except 
# in case the database is down or new tables have not been created yet
try:
    achievements.sync_catalog()
except Exception as e:
    print(f"[achievements] could not sync the catalog: {e}")

def answer(ok, message):
    return (jsonify(message=message), 200) if ok else (jsonify(error=message), 400)


def need_login():
    return jsonify(error="Please log in first."), 401


@app.route("/")
def home():
    return send_from_directory(FRONTEND, "Base.html")


# ---------- Auth ----------
@app.post("/api/register")
def register():
    d = request.get_json(silent=True) or {}
    return answer(*auth.create_account(d.get("username"), d.get("email"), d.get("password")))


@app.post("/api/login")
def login():
    d = request.get_json(silent=True) or {}
    ok, message, user = auth.login_and_get_user(d.get("email") or "", d.get("password") or "")
    if ok:
        session["user_id"] = user["id"]
        session["username"] = user["username"]
    return answer(ok, message)


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(message="Logged out")


@app.get("/api/me")
def me():
    if "user_id" not in session:
        return need_login()
    # rep = auth.get_user_reputation(session["user_id"])
    # return jsonify(id=session["user_id"], username=session["username"], reputation=rep)
    uid = session["user_id"]
    rep = auth.get_user_reputation(uid)
    # achievements calls api/me on loading, prediction, and after a sync
    achievements.try_check(uid)

    badge_info = achievements.attach_badges([{"username": session["username"]}])[0]
    return jsonify(
        id = uid,
        username = session["username"],
        reputation = rep,
        badges = badge_info["badges"],
        achievement_score = badge_info["achievement_score"],
        new_achievements = achievements.pop_unseen(uid),

    )


# ---------- Posts ----------
@app.get("/api/posts")
def get_posts():
    # return jsonify(posts.view_posts(session.get("user_id")))

    #attach badges and score to users name
    return jsonify(achievements.attach_badges(posts.view_posts(session.get("user_id"))))


@app.post("/api/posts")
def add_post():
    if "user_id" not in session:
        return need_login()
    d = request.get_json(silent=True) or {}
    # return answer(*posts.create_post(session["user_id"], (d.get("content") or "").strip()))

    ok, message = posts.create_post(session["user_id"], (d.get("content") or "").strip())
    if ok:
        achievements.try_check(session["user_id"])
    return answer(ok, message)


@app.post("/api/posts/<int:post_id>/like")
def like_post(post_id):
    if "user_id" not in session:
        return need_login()
    # return answer(*posts.like_post(session["user_id"], post_id))

    ok, message = posts.like_post(session["user_id"], post_id)
    if ok:
        achievements.try_check_post_author(post_id)
    return answer(ok, message)


# ---------- Comments ----------
@app.get("/api/posts/<int:post_id>/comments")
def get_comments(post_id):
    # return jsonify(comments.view_comments(post_id, session.get("user_id")))

    return jsonify(achievements.attach_badges(comments.view_comments(post_id, session.get("user_id"))))


@app.post("/api/posts/<int:post_id>/comments")
def add_comment(post_id):
    if "user_id" not in session:
        return need_login()
    d = request.get_json(silent=True) or {}
    # return answer(*comments.create_comment(session["user_id"], post_id, (d.get("content") or "").strip()))

    ok, message = comments.create_comment(session["user_id"], post_id, (d.get("content") or "").strip())
    if ok:
        achievements.try_check(session["user_id"])
    return answer(ok, message)

@app.post("/api/comments/<int:comment_id>/like")
def like_comment(comment_id):
    if "user_id" not in session:
        return need_login()
    # return answer(*comments.like_comment(session["user_id"], comment_id))

    ok, message = comments.like_comment(session["user_id"], comment_id)
    if ok:
        # comment likes also count toward the author's "likes received"
        achievements.try_check_comment_author(comment_id)
    return answer(ok, message)


# ---------- Predictions ----------
@app.get("/api/predictions")
def get_predictions():
    # same as view_predictions() but joined with users so the page can show who made each one
    rows = query(
        "SELECT predictions.*, users.username FROM predictions "
        "JOIN users ON users.id = predictions.user_id ORDER BY predictions.created_at DESC"
    )
    # return jsonify(rows)
    return jsonify(achievements.attach_badges(rows))


@app.post("/api/predictions")
def add_prediction():
    if "user_id" not in session:
        return need_login()
    d = request.get_json(silent=True) or {}
    try:
        points = int(d.get("points"))
    except (TypeError, ValueError):
        return jsonify(error="Points must be a number."), 400
    # return answer(*preds.create_prediction(session["user_id"], d.get("game_id"), d.get("pick"), points))

    # 
    ok, message = preds.create_prediction(session["user_id"], d.get("game_id"), d.get("pick"), points)
    if ok:
        achievements.try_check(session["user_id"])
    return answer(ok, message)

# ---------- Profiles ----------
@app.get("/api/profile")
def my_profile():
    if "user_id" not in session:
        return need_login()
    data = profile.get_profile(session["user_id"], viewer_id=session["user_id"])
    if data:
        achievements.attach_badges([data])

    return (jsonify(data), 200) if data else (jsonify(error="User not found."), 404)


@app.get("/api/users/<username>/profile")
def user_profile(username):
    # public, like posts and predictions, so usernames can link to a profile
    data = profile.get_profile_by_username(username, viewer_id=session.get("user_id"))
    if data:
        achievements.attach_badges([data]) # same as my profile
    return (jsonify(data), 200) if data else (jsonify(error="User not found."), 404)


@app.get("/api/users/<username>/predictions")
def user_predictions(username):
    # public, like /api/predictions, so a profile can show a user's current and past picks
    data = profile.get_predictions_by_username(username)
    return (jsonify(data), 200) if data else (jsonify(error="User not found."), 404)
    
# ---------- Following ----------
@app.post("/api/users/<username>/follow")
def follow_route(username):
    if "user_id" not in session:
        return need_login()
    # return answer(*follow.follow_user(session["user_id"], username))

    ok, message = follow.follow_user(session["user_id"], username)
    if ok:
        # a new follower counts toward the person being FOLLOWED (Rising Star etc.)
        achievements.try_check_username(username)
    return answer(ok, message)


@app.delete("/api/users/<username>/follow")
def unfollow_route(username):
    if "user_id" not in session:
        return need_login()
    return answer(*follow.unfollow_user(session["user_id"], username))


@app.get("/api/users/search")
def search_users_route():
    if "user_id" not in session:
        return need_login()
    # return jsonify(follow.search_users(session["user_id"], request.args.get("q")))

    # 
    return jsonify(achievements.attach_badges(follow.search_users(session["user_id"], request.args.get("q"))))

@app.get("/api/following")
def following_list():
    if "user_id" not in session:
        return need_login()
    # return jsonify(follow.get_following(session["user_id"]))
    return jsonify(achievements.attach_badges(follow.get_following(session["user_id"])))


# found bug: no route connecting load following and get following
@app.get("/api/followers")
def followers_list():
    if "user_id" not in session:
        return need_login()
    return jsonify(achievements.attach_badges(follow.get_followers(session["user_id"])))



@app.get("/api/following/feed")
def following_feed():
    if "user_id" not in session:
        return need_login()
    # return jsonify(follow.get_following_feed(session["user_id"]))

    return jsonify(achievements.attach_badges(follow.get_following_feed(session["user_id"])))

# ---------- Games ----------
@app.get("/api/games")
def get_games():
    return jsonify(games.view_upcoming_games(request.args.get("sport")))


@app.post("/api/games/sync")
def sync_games_route():
    football = games.sync_games("football")
    basketball = games.sync_games("basketball")
    settled = preds.auto_settle_finished_games()
    return jsonify(football_synced = football, basketball_synced = basketball, predictions_settled = settled,)

# ---------- Compare ----------
@app.get("/api/compare")
def compare_route():
    if "user_id" not in session:
        return need_login()
    names = request.args.get("users", "").split(",")
    data, error = compare.get_comparison(session["user_id"], names)
    # return (jsonify(error=error), 400) if error else jsonify(data)

    return (jsonify(error=error), 400) if error else jsonify(achievements.attach_badges(data))

# ---------- Leaderboard ----------
@app.get("/api/leaderboard")
def get_leaderboard():
    # rows = query(
    #     "SELECT username, reputation FROM users ORDER BY reputation DESC LIMIT 100"
    # )
    # return jsonify(rows)

    # above was moved to achievement backend
    return jsonify(achievements.leaderboard(request.args.get("sort", "reputation")))


# Achievements
@app.get("/api/achievements/catalog")
def achievement_catalog():
    # loading every achievement
    return jsonify(achievements.get_catalog())

@app.get("/api/users/<username>/achievements")
def user_achievements(username):
    # what the user has earned, their progress, and how rare each one is
    data = achievements.get_user_achievements(username)
    return (jsonify(data), 200) if data else (jsonify(error = "User not found."), 404)

@app.put("/api/achievements/featured")
def set_featured_badges():
    # saves which badges show next to your name
    if "user_id" not in session:
        return need_login()
    d = request.get_json(silent = True) or {}
    return answer(*achievements.set_featured(session["user_id"], d.get("codes")))



if __name__ == "__main__":
    app.run(debug=True, port=5001)