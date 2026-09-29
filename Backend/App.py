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
import os
import GameBackend as games

FRONTEND = Path(__file__).resolve().parent.parent / "Frontend"
app = Flask(__name__, static_folder=str(FRONTEND), static_url_path="")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-me")


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
    rep = auth.get_user_reputation(session["user_id"])
    return jsonify(id=session["user_id"], username=session["username"], reputation=rep)


# ---------- Posts ----------
@app.get("/api/posts")
def get_posts():
    return jsonify(posts.view_posts(session.get("user_id")))


@app.post("/api/posts")
def add_post():
    if "user_id" not in session:
        return need_login()
    d = request.get_json(silent=True) or {}
    return answer(*posts.create_post(session["user_id"], (d.get("content") or "").strip()))


@app.post("/api/posts/<int:post_id>/like")
def like_post(post_id):
    if "user_id" not in session:
        return need_login()
    return answer(*posts.like_post(session["user_id"], post_id))


# ---------- Comments ----------
@app.get("/api/posts/<int:post_id>/comments")
def get_comments(post_id):
    return jsonify(comments.view_comments(post_id, session.get("user_id")))


@app.post("/api/posts/<int:post_id>/comments")
def add_comment(post_id):
    if "user_id" not in session:
        return need_login()
    d = request.get_json(silent=True) or {}
    return answer(*comments.create_comment(session["user_id"], post_id, (d.get("content") or "").strip()))


@app.post("/api/comments/<int:comment_id>/like")
def like_comment(comment_id):
    if "user_id" not in session:
        return need_login()
    return answer(*comments.like_comment(session["user_id"], comment_id))


# ---------- Predictions ----------
@app.get("/api/predictions")
def get_predictions():
    # same as view_predictions() but joined with users so the page can show who made each one
    rows = query(
        "SELECT predictions.*, users.username FROM predictions "
        "JOIN users ON users.id = predictions.user_id ORDER BY predictions.created_at DESC"
    )
    return jsonify(rows)


@app.post("/api/predictions")
def add_prediction():
    if "user_id" not in session:
        return need_login()
    d = request.get_json(silent=True) or {}
    try:
        points = int(d.get("points"))
    except (TypeError, ValueError):
        return jsonify(error="Points must be a number."), 400
    return answer(*preds.create_prediction(session["user_id"], d.get("game_id"), d.get("pick"), points))

# ---------- Profiles ----------
@app.get("/api/profile")
def my_profile():
    if "user_id" not in session:
        return need_login()
    data = profile.get_profile(session["user_id"])
    return (jsonify(data), 200) if data else (jsonify(error="User not found."), 404)


@app.get("/api/users/<username>/profile")
def user_profile(username):
    # public, like posts and predictions, so usernames can link to a profile
    data = profile.get_profile_by_username(username)
    return (jsonify(data), 200) if data else (jsonify(error="User not found."), 404)


# ---------- Games ----------
@app.get("/api/games")
def get_games():
    return jsonify(games.view_upcoming_games(request.args.get("sport")))


@app.post("/api/games/sync")
def sync_games_route():
    football = games.sync_games("football")
    basketball = games.sync_games("basketball")
    return jsonify(football_synced=football, basketball_synced=basketball)

if __name__ == "__main__":
    app.run(debug=True)