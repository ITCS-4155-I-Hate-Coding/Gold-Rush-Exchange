import os
from pathlib import Path

from flask import Flask, jsonify, request, session, send_from_directory

import LoginBackend as auth
import PostBackend as posts
import CommentBackend as comments
import PredictionBackend as preds
import ProfileBackend as profile
import FollowBackend as follow
import CompareBackend as compare
import AchievementBackend as achievements
import GameBackend as games
import RepBackend as rep
import NotificationBackend as notifications
import ChatBackend as chat

FRONTEND = Path(__file__).resolve().parent.parent / "Frontend"
app = Flask(__name__, static_folder=str(FRONTEND), static_url_path="")

app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "dev-only-change-me"
if app.secret_key == "dev-only-change-me":
    print("[config] FLASK_SECRET_KEY is not set: using an insecure development key")

app.config.update(
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE") == "1",  # set to 1 when served over https
    MAX_CONTENT_LENGTH=64 * 1024,  # refuse request bodies over 64 KB
)

# achievements will sync every time the server starts and is wrapped in try/except
# in case the database is down or new tables have not been created yet
try:
    achievements.sync_catalog()
except Exception as e:
    print(f"[achievements] could not sync the catalog: {e}")


def answer(ok, message, **extra):
    return (jsonify(message=message, **extra), 200) if ok else (jsonify(error=message), 400)


def need_login():
    return jsonify(error="Please log in first."), 401


def int_arg(name):
    # a whole number from the query string, or None if missing or not a number
    try:
        return int(request.args[name])
    except (KeyError, ValueError):
        return None


@app.errorhandler(500)
def server_error(_):
    return jsonify(error="Something went wrong on the server. Please try again."), 500


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify(error="Not found."), 404
    return e


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
        session.clear()  # start a fresh session on login
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
    uid = session["user_id"]
    rep_now = auth.get_user_reputation(uid)
    if rep_now is None:  # the account was deleted while logged in
        session.clear()
        return need_login()


    games.maybe_auto_sync(preds.auto_settle_finished_games)
    # bankruptcy floor (back up to 50 rep, at most once a day, if nothing is pending)
    topped_up = 0
    try:
        topped_up = rep.maybe_top_up(uid)
        rep_now += topped_up
    except Exception as e:
        print(f"[rep] top-up check failed: {e}")

    # achievements calls api/me on loading, prediction, and after a sync
    achievements.try_check(uid)
    badge_info = achievements.attach_badges([{"username": session["username"]}])[0]
    try:
        counts = notifications.summary(uid)  # unread counts for the header
    except Exception as e:
        print(f"[notifications] summary failed: {e}")
        counts = {"unread_notifications": 0, "unread_messages": 0}
    return jsonify(
        id=uid,
        username=session["username"],
        reputation=rep_now,
        badges=badge_info["badges"],
        achievement_score=badge_info["achievement_score"],
        new_achievements=achievements.pop_unseen(uid),
        top_up=topped_up,
        unread_notifications=counts["unread_notifications"],
        unread_messages=counts["unread_messages"],
    )


# ---------- Posts ----------
@app.get("/api/posts")
def get_posts():
    # attach badges and score to users name
    return jsonify(achievements.attach_badges(posts.view_posts(session.get("user_id"))))


@app.post("/api/posts")
def add_post():
    if "user_id" not in session:
        return need_login()
    uid = session["user_id"]
    d = request.get_json(silent=True) or {}
    content = d.get("content") or ""
    ok, message, post_id = posts.create_post(uid, content)
    if not ok:
        return answer(ok, message)
    # +5 for the post (capped, see RepBackend); the reply says what was earned and why
    reward = rep.reward_post(uid, post_id, content)
    achievements.try_check(uid)
    return answer(ok, message, **reward)


@app.post("/api/posts/<int:post_id>/like")
def like_post(post_id):
    if "user_id" not in session:
        return need_login()
    ok, message = posts.like_post(session["user_id"], post_id)
    if ok:
        # likes count toward the author's achievements (and +1 rep, inside like_post)
        achievements.try_check_post_author(post_id)
    return answer(ok, message)


# ---------- Comments ----------
@app.get("/api/posts/<int:post_id>/comments")
def get_comments(post_id):
    return jsonify(achievements.attach_badges(comments.view_comments(post_id, session.get("user_id"))))


@app.post("/api/posts/<int:post_id>/comments")
def add_comment(post_id):
    if "user_id" not in session:
        return need_login()
    uid = session["user_id"]
    d = request.get_json(silent=True) or {}
    content = d.get("content") or ""
    ok, message, comment_id, post_author = comments.create_comment(uid, post_id, content)
    if not ok:
        return answer(ok, message)
    # +2 for a comment on someone else's post (capped)
    reward = rep.reward_comment(uid, comment_id, post_author, content)
    achievements.try_check(uid)
    return answer(ok, message, **reward)


@app.post("/api/comments/<int:comment_id>/like")
def like_comment(comment_id):
    if "user_id" not in session:
        return need_login()
    ok, message = comments.like_comment(session["user_id"], comment_id)
    if ok:
        # comment likes also count toward the author's "likes received"
        achievements.try_check_comment_author(comment_id)
    return answer(ok, message)


@app.get("/api/rep/rules")
def rep_rules():
    # the reward table, shown as a hint under the post box
    return jsonify(rep.get_rules())


# ---------- Predictions ----------
@app.get("/api/predictions")
def get_predictions():
    return jsonify(achievements.attach_badges(preds.view_feed(session.get("user_id"))))


@app.post("/api/predictions")
def add_prediction():
    if "user_id" not in session:
        return need_login()
    d = request.get_json(silent=True) or {}
    try:
        points = int(d.get("points"))
    except (TypeError, ValueError):
        return jsonify(error="Points must be a number."), 400
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
        achievements.attach_badges([data])  # same as my profile
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
    return jsonify(achievements.attach_badges(follow.search_users(session["user_id"], request.args.get("q"))))


@app.get("/api/following")
def following_list():
    if "user_id" not in session:
        return need_login()
    return jsonify(achievements.attach_badges(follow.get_following(session["user_id"])))


@app.get("/api/followers")
def followers_list():
    if "user_id" not in session:
        return need_login()
    return jsonify(achievements.attach_badges(follow.get_followers(session["user_id"])))


@app.get("/api/following/feed")
def following_feed():
    if "user_id" not in session:
        return need_login()
    return jsonify(achievements.attach_badges(follow.get_following_feed(session["user_id"])))


# ---------- Games ----------
@app.get("/api/games")
def get_games():
    games.maybe_auto_sync(preds.auto_settle_finished_games)  # keeps games fresh automatically
    return jsonify(games.view_upcoming_games(request.args.get("sport")))


@app.post("/api/games/sync")
def sync_games_route():
    if "user_id" not in session:
        return need_login()
    return jsonify(games.sync_now(preds.auto_settle_finished_games))


# ---------- Compare ----------
@app.get("/api/compare")
def compare_route():
    if "user_id" not in session:
        return need_login()
    names = request.args.get("users", "").split(",")
    data, error = compare.get_comparison(session["user_id"], names)
    return (jsonify(error=error), 400) if error else jsonify(achievements.attach_badges(data))


# ---------- Leaderboard ----------
@app.get("/api/leaderboard")
def get_leaderboard():
    # ?sort=achievements ranks by achievement score instead of reputation
    return jsonify(achievements.leaderboard(request.args.get("sort", "reputation")))


# ---------- Achievements ----------
@app.get("/api/achievements/catalog")
def achievement_catalog():
    # loading every achievement
    return jsonify(achievements.get_catalog())


@app.get("/api/users/<username>/achievements")
def user_achievements(username):
    # what the user has earned, their progress, and how rare each one is
    data = achievements.get_user_achievements(username)
    return (jsonify(data), 200) if data else (jsonify(error="User not found."), 404)


@app.put("/api/achievements/featured")
def set_featured_badges():
    # saves which badges show next to your name
    if "user_id" not in session:
        return need_login()
    d = request.get_json(silent=True) or {}
    return answer(*achievements.set_featured(session["user_id"], d.get("codes")))


# ---------- Notifications ----------
@app.get("/api/notifications")
def get_notifications():
    # the bell panel: newest 30 and the unread count
    if "user_id" not in session:
        return need_login()
    return jsonify(notifications.list_notifications(session["user_id"]))


@app.get("/api/notifications/summary")
def notification_summary():
    # polled every 20 seconds by the page: unread notifications and unread messages
    if "user_id" not in session:
        return need_login()
    return jsonify(notifications.summary(session["user_id"]))


@app.post("/api/notifications/read")
def read_notifications():
    # body {"ids": [1, 2]} marks those as read; an empty body marks all as read
    if "user_id" not in session:
        return need_login()
    d = request.get_json(silent=True) or {}
    return answer(*notifications.mark_read(session["user_id"], d.get("ids")))


# ---------- Chat ----------
@app.get("/api/messages")
def conversations():
    # the list of friends and conversations on the Messages tab
    if "user_id" not in session:
        return need_login()
    return jsonify(achievements.attach_badges(chat.list_conversations(session["user_id"])))


@app.get("/api/messages/<username>")
def conversation(username):
    # ?after=<id> for new messages (polling), ?before=<id> for older ones
    if "user_id" not in session:
        return need_login()
    data, error = chat.get_conversation(session["user_id"], username,
                                        after_id=int_arg("after"), before_id=int_arg("before"))
    return (jsonify(error=error), 400) if error else jsonify(data)


@app.post("/api/messages/<username>")
def send_message(username):
    if "user_id" not in session:
        return need_login()
    d = request.get_json(silent=True) or {}
    ok, message, saved = chat.send_message(session["user_id"], username, d.get("body"))
    return (jsonify(message=message, sent=saved), 200) if ok else (jsonify(error=message), 400)


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=5001)