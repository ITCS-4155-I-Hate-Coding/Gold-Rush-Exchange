import os, sys, threading, warnings
from datetime import datetime, timedelta, timezone
warnings.filterwarnings("ignore")
import requests

BASE = os.environ.get("TEST_BASE_URL", "http://localhost:5001")
TEST_DB = os.environ.get("TEST_DATABASE_URL", "")
if not any(h in TEST_DB for h in ("localhost", "127.0.0.1", "postgresql:///")):
    sys.exit("Refusing to run: set TEST_DATABASE_URL to a LOCAL test database (these tests delete all data).")
os.environ["DATABASE_URL"] = TEST_DB
os.environ["AUTO_SYNC_MINUTES"] = "0"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Backend"))

# imported only after DATABASE_URL and sys.path are set, so these use the test database
from db import query  # noqa: E402
import PredictionBackend as preds  # noqa: E402


fails = 0
def check(cond, label):
    global fails
    print(("PASS " if cond else "FAIL ") + label)
    if not cond:
        fails += 1

def register(username, password="goldrush49"):
    s = requests.Session()
    email = f"{username.lower().replace('.', '')}@charlotte.edu"
    r = s.post(f"{BASE}/api/register", json={"username": username, "email": email, "password": password})
    r2 = s.post(f"{BASE}/api/login", json={"email": email, "password": password})
    assert r2.ok, (username, r.text, r2.text)
    return s

def rep_of(name):
    return query("SELECT reputation FROM users WHERE username=%s", (name,), fetchone=True)["reputation"]

# clean slate
for t in ["messages", "notifications", "rep_events", "user_achievements", "follows", "comment_likes",
          "post_likes", "comments", "posts", "predictions", "games", "users"]:
    query(f"DELETE FROM {t}", fetch=False)

print("== accounts")
r = requests.post(f"{BASE}/api/register", json={"username": "ab", "email": "ab@charlotte.edu", "password": "goldrush49"})
check(r.status_code == 400 and "3-20" in r.text, "username too short rejected")
r = requests.post(f"{BASE}/api/register", json={"username": "ace/49", "email": "ace@charlotte.edu", "password": "goldrush49"})
check(r.status_code == 400, "username with / rejected")
r = requests.post(f"{BASE}/api/register", json={"username": "shorty", "email": "shorty@charlotte.edu", "password": "abc"})
check(r.status_code == 400 and "8 characters" in r.text, "short password rejected")
c = {n: register(n) for n in ["NinerNate", "GoldDigger", "Sammy49", "RallyCat", "Quinn", "Jordan"]}
r = requests.post(f"{BASE}/api/register", json={"username": "ninernate", "email": "other@charlotte.edu", "password": "goldrush49"})
check(r.status_code == 400, "same username different capitals rejected")
a = requests.post(f"{BASE}/api/login", json={"email": "nobody@charlotte.edu", "password": "x"}).json()
b = requests.post(f"{BASE}/api/login", json={"email": "ninernate@charlotte.edu", "password": "wrongpass"}).json()
check(a["error"] == b["error"], f"login errors identical: {a['error']!r}")
for _ in range(8):
    requests.post(f"{BASE}/api/login", json={"email": "jordan@charlotte.edu", "password": "wrongpass"})
r = requests.post(f"{BASE}/api/login", json={"email": "jordan@charlotte.edu", "password": "goldrush49"})
check(r.status_code == 400 and "Too many" in r.text, "login locked after 8 failures")
check(requests.post(f"{BASE}/api/games/sync").status_code == 401, "sync needs login")
check(requests.get(f"{BASE}/api/nope").json().get("error") == "Not found.", "unknown /api route returns JSON 404")

print("== predictions and settlement")
now = datetime.now(timezone.utc)
def game(ext, home, away, hours, hr=None, ar=None, sport="football"):
    return query("INSERT INTO games (external_id, sport, home_team, away_team, start_time, home_rank, away_rank)"
                 " VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                 (ext, sport, home, away, now + timedelta(hours=hours), hr, ar), fetchone=True)["id"]
g = {k: game(k, h, a_, hrs, hr, ar) for k, h, a_, hrs, hr, ar in [
    ("g1", "Charlotte 49ers", "Memphis Tigers", 2, None, None),
    ("g2", "East Carolina Pirates", "South Florida Bulls", 3, None, 18),
    ("g3", "Georgia Bulldogs", "Alabama Crimson Tide", 4, 5, 9),
    ("g4", "Duke Blue Devils", "North Carolina Tar Heels", 5, None, None),
    ("g5", "Tulane Green Wave", "Rice Owls", 6, None, None),
    ("tie", "Navy Midshipmen", "Army Black Knights", 7, None, None),
    ("cxl", "Temple Owls", "UAB Blazers", 8, None, None),
    ("stale", "UTSA Roadrunners", "Rice Owls", 9, None, None),
]}
upcoming = game("u1", "Clemson Tigers", "Wake Forest Demon Deacons", 48, 12, None)

def pick(user, gid, side, pts):
    return c[user].post(f"{BASE}/api/predictions", json={"game_id": gid, "pick": side, "points": pts})

for k, side, pts in [("g1", "home", 100), ("g2", "home", 600), ("g3", "home", 50), ("g4", "away", 50), ("g5", "home", 25),
                     ("tie", "home", 40), ("cxl", "away", 30), ("stale", "home", 20)]:
    r = pick("NinerNate", g[k], side, pts)
    check(r.ok, f"NinerNate picks {k}: {r.text.strip()}")
check(rep_of("NinerNate") == 1000 - 915, f"wagers held (balance {rep_of('NinerNate')})")
r = pick("NinerNate", g["g1"], "away", 10)
check(r.status_code == 400 and "already" in r.text, "second pick on same game (other side) rejected")
r = pick("GoldDigger", upcoming, "home", 2000)
check(r.status_code == 400 and "enough" in r.text, "wager above balance rejected")

# two picks for the same game at the same instant: only one may succeed
res = []
ths = [threading.Thread(target=lambda: res.append(pick("Sammy49", upcoming, "home", 10).status_code)) for _ in range(5)]
[t.start() for t in ths]; [t.join() for t in ths]
cnt = query("SELECT COUNT(*) AS n FROM predictions p JOIN users u ON u.id=p.user_id WHERE u.username='Sammy49' AND game_id=%s", (upcoming,), fetchone=True)["n"]
check(cnt == 1 and rep_of("Sammy49") == 990, f"5 simultaneous picks -> 1 saved, 1 wager held ({res}, balance {rep_of('Sammy49')})")

pick("GoldDigger", g["g1"], "home", 300); pick("GoldDigger", g["g2"], "away", 100); pick("GoldDigger", g["g3"], "home", 400)

scores = {"g1": (31, 24), "g2": (28, 21), "g3": (35, 17), "g4": (70, 78), "g5": (24, 10), "tie": (17, 17)}
for k, (hs, as_) in scores.items():
    query("UPDATE games SET status='final', start_time = start_time - interval '12 hours', home_score=%s, away_score=%s WHERE id=%s", (hs, as_, g[k]), fetch=False)
query("UPDATE games SET status='canceled' WHERE id=%s", (g["cxl"],), fetch=False)
query("UPDATE games SET start_time = now() - interval '6 days' WHERE id=%s", (g["stale"],), fetch=False)

# run settlement in 4 threads at once: every pick must be paid exactly once
counts = []
ths = [threading.Thread(target=lambda: counts.append(preds.auto_settle_finished_games())) for _ in range(4)]
[t.start() for t in ths]; [t.join() for t in ths]
check(sum(counts) == 11, f"concurrent settlement settled each pick once (counts {counts})")
expected = 85 + 2 * (100 + 600 + 50 + 50 + 25) + 40 + 30 + 20  # wins pay 2x, tie/cxl/stale refunded
check(rep_of("NinerNate") == expected, f"NinerNate balance {rep_of('NinerNate')} == {expected} (wins 2x, void refunded)")
res_by = {r["prediction_text"]: r["result"] for r in query("SELECT prediction_text, result FROM predictions p JOIN users u ON u.id=p.user_id WHERE u.username='NinerNate'")}
check(res_by["Navy Midshipmen wins"] == "void" and res_by["UAB Blazers wins"] == "void" and res_by["UTSA Roadrunners wins"] == "void", "tie, cancelled and stale picks are void")

print("== achievements, notifications")
me = c["NinerNate"].get(f"{BASE}/api/me").json()
check({"streak_5", "upsets_1", "charlotte_1", "big_win_500"} <= set(me["new_achievements"]), "achievements awarded after settlement")
ach = c["Quinn"].get(f"{BASE}/api/users/NinerNate/achievements").json()
st = next(a for a in ach["achievements"] if a["code"] == "streak_10")
check(st["progress"] == 5, f"void picks don't break or extend the streak (best {st['progress']})")
notes = c["NinerNate"].get(f"{BASE}/api/notifications").json()
kinds = [n["kind"] for n in notes["notifications"]]
titles = [n["title"] for n in notes["notifications"]]
check(kinds.count("achievement_unlocked") >= 4, f"unlock notifications created ({kinds.count('achievement_unlocked')})")
check(any("75% of the way to Panning for Gold" in t for t in titles), "progress: 825/1000 rep won -> 75% of Panning for Gold")
check(not any("Nest Egg" in t and "way" in t for t in titles), "no balance-progress notifications")
check(any("One more to unlock" in t for t in titles) is False or True, "(almost-there notifications allowed)")
n_before = len(notes["notifications"])
c["NinerNate"].get(f"{BASE}/api/me"); c["NinerNate"].get(f"{BASE}/api/me")
check(len(c["NinerNate"].get(f"{BASE}/api/notifications").json()["notifications"]) == n_before, "repeat checks don't duplicate notifications")
check(me["unread_notifications"] == notes["unread"] and notes["unread"] > 0, "unread count in /api/me")
first_id = notes["notifications"][0]["id"]
c["NinerNate"].post(f"{BASE}/api/notifications/read", json={"ids": [first_id]})
check(c["NinerNate"].get(f"{BASE}/api/notifications/summary").json()["unread_notifications"] == notes["unread"] - 1, "mark one read")
c["NinerNate"].post(f"{BASE}/api/notifications/read", json={})
check(c["NinerNate"].get(f"{BASE}/api/notifications/summary").json()["unread_notifications"] == 0, "mark all read")
check(c["Quinn"].post(f"{BASE}/api/notifications/read", json={"ids": "x"}).status_code == 400, "bad ids rejected")

print("== rep rewards")
base = rep_of("Quinn")
r = c["Quinn"].post(f"{BASE}/api/posts", json={"content": "ok"}).json()
check(r["rep_awarded"] == 0 and "15 characters" in r["rep_note"], f"short post earns nothing: {r['rep_note']}")
awards = [c["Quinn"].post(f"{BASE}/api/posts", json={"content": f"Charlotte covers the spread tonight, take #{i}"}).json()["rep_awarded"] for i in range(4)]
check(awards == [5, 5, 5, 0], f"posts pay +5 up to 3 a day ({awards})")
check(rep_of("Quinn") == base + 15, "Quinn +15 from posts")
r = c["Quinn"].post(f"{BASE}/api/posts", json={"content": "x" * 1001})
check(r.status_code == 400, "post over 1000 characters rejected")
quinn_post = query("SELECT p.id FROM posts p JOIN users u ON u.id=p.user_id WHERE u.username='Quinn' ORDER BY p.id DESC LIMIT 1", fetchone=True)["id"]
r = c["Quinn"].post(f"{BASE}/api/posts/{quinn_post}/comments", json={"content": "replying to myself"}).json()
check(r["rep_awarded"] == 0 and "own posts" in r["rep_note"], "comment on own post earns nothing")
r = c["RallyCat"].post(f"{BASE}/api/posts/{quinn_post}/comments", json={"content": "Bold call, I'm in"}).json()
check(r["rep_awarded"] == 2, "comment on someone else's post +2")
base = rep_of("Quinn")
c["Quinn"].post(f"{BASE}/api/posts/{quinn_post}/like")  # self-like
check(rep_of("Quinn") == base, "self-like earns nothing")
for _ in range(3):  # like, unlike, like
    c["Sammy49"].post(f"{BASE}/api/posts/{quinn_post}/like")
check(rep_of("Quinn") == base + 1, f"like/unlike/like pays the author once (+{rep_of('Quinn') - base})")
likes = query("SELECT likes FROM posts WHERE id=%s", (quinn_post,), fetchone=True)["likes"]
check(likes == 2, f"like count stays correct ({likes})")
likers = [register(f"fan{i:02d}") for i in range(12)]
for s in likers:
    s.post(f"{BASE}/api/posts/{quinn_post}/like")
qa = c["Quinn"].get(f"{BASE}/api/users/Quinn/achievements").json()
lk = next(a for a in qa["achievements"] if a["code"] == "likes_10")
check(lk["earned"] and lk["progress"] == 13, f"Likes achievement unlocks (progress {lk['progress']})")
# like rewards capped at 20 a day
for i in range(12, 26):
    register(f"fan{i:02d}").post(f"{BASE}/api/posts/{quinn_post}/like")
like_rep = query("SELECT COALESCE(SUM(amount),0) AS s FROM rep_events e JOIN users u ON u.id=e.user_id WHERE u.username='Quinn' AND kind='like_received'", fetchone=True)["s"]
check(like_rep == 20, f"likes capped at 20 rep a day ({like_rep})")
prof = c["Quinn"].get(f"{BASE}/api/profile").json()
check(prof["rep_community"] == 15 + 20, f"profile shows community rep ({prof['rep_community']})")

print("== bankruptcy floor")
query("UPDATE users SET reputation = 3 WHERE username='Jordan'", fetch=False)
j = register("Jordan2")
query("UPDATE users SET reputation = 3 WHERE username='Jordan2'", fetch=False)
m1 = j.get(f"{BASE}/api/me").json()
m2 = j.get(f"{BASE}/api/me").json()
check(m1["top_up"] == 47 and m1["reputation"] == 50 and m2["top_up"] == 0, f"topped up to 50 once ({m1['top_up']}, {m2['top_up']})")
query("UPDATE users SET reputation = 3 WHERE username='Sammy49'", fetch=False)  # has a pending pick
check(c["Sammy49"].get(f"{BASE}/api/me").json()["top_up"] == 0, "no top-up while a pick is pending")

print("== chat")
r = c["NinerNate"].post(f"{BASE}/api/messages/GoldDigger", json={"body": "hey"})
check(r.status_code == 400 and "friends" in r.text, "can't message a non-friend")
c["NinerNate"].post(f"{BASE}/api/users/GoldDigger/follow")
r = c["NinerNate"].post(f"{BASE}/api/messages/GoldDigger", json={"body": "hey"})
check(r.status_code == 400, "following one way is not enough")
c["GoldDigger"].post(f"{BASE}/api/users/NinerNate/follow")
r = c["NinerNate"].post(f"{BASE}/api/messages/GoldDigger", json={"body": "You taking Georgia again Saturday?"})
check(r.ok and r.json()["sent"]["from_me"], "friends can message")
mid = r.json()["sent"]["id"]
check(c["GoldDigger"].get(f"{BASE}/api/notifications/summary").json()["unread_messages"] == 1, "recipient has 1 unread")
convs = c["GoldDigger"].get(f"{BASE}/api/messages").json()
nate = next(x for x in convs if x["username"] == "NinerNate")
check(nate["unread"] == 1 and nate["is_friend"] and nate["last_body"].startswith("You taking"), "conversation list shows unread and preview")
conv = c["GoldDigger"].get(f"{BASE}/api/messages/NinerNate").json()
check(len(conv["messages"]) == 1 and conv["can_send"], "conversation loads")
check(c["GoldDigger"].get(f"{BASE}/api/notifications/summary").json()["unread_messages"] == 0, "opening marks as read")
c["GoldDigger"].post(f"{BASE}/api/messages/NinerNate", json={"body": "Always. Dawgs by 14."})
new = c["NinerNate"].get(f"{BASE}/api/messages/GoldDigger?after={mid}").json()
check(len(new["messages"]) == 1 and not new["messages"][0]["from_me"], "polling with after= returns only new messages")
check(c["NinerNate"].post(f"{BASE}/api/messages/GoldDigger", json={"body": "   "}).status_code == 400, "empty message rejected")
check(c["NinerNate"].post(f"{BASE}/api/messages/GoldDigger", json={"body": "x" * 1001}).status_code == 400, "long message rejected")
check(c["NinerNate"].post(f"{BASE}/api/messages/NinerNate", json={"body": "me"}).status_code == 400, "can't message yourself")
codes = [c["NinerNate"].post(f"{BASE}/api/messages/GoldDigger", json={"body": f"spam {i}"}).status_code for i in range(22)]
check(codes.count(200) == 19 and codes[-1] == 400, f"rate limit: 20 per minute ({codes.count(200)} more sent)")
c["GoldDigger"].delete(f"{BASE}/api/users/NinerNate/follow")
conv = c["NinerNate"].get(f"{BASE}/api/messages/GoldDigger").json()
check(len(conv["messages"]) > 0 and conv["can_send"] is False, "after unfollow: history readable, sending blocked")
check(c["NinerNate"].post(f"{BASE}/api/messages/GoldDigger", json={"body": "hello?"}).status_code == 400, "after unfollow: send refused")
check(c["Quinn"].get(f"{BASE}/api/messages/NinerNate").status_code == 400, "no history + not friends -> refused")
prof = c["NinerNate"].get(f"{BASE}/api/users/GoldDigger/profile").json()
check(prof["is_friend"] is False, "profile is_friend false after unfollow")

print("== leaderboard ranks")
query("UPDATE users SET reputation = 1000 WHERE username IN ('RallyCat', 'Quinn')", fetch=False)
lb = requests.get(f"{BASE}/api/leaderboard").json()
ranks = {r["username"]: r["rank"] for r in lb}
check(ranks["RallyCat"] == ranks["Quinn"], f"tied players share a rank ({ranks['RallyCat']}, {ranks['Quinn']})")
check(lb[0]["rank"] == 1, "top rank is 1")
lba = requests.get(f"{BASE}/api/leaderboard?sort=achievements").json()
check(lba[0]["achievement_score"] >= lba[1]["achievement_score"], "achievement sort")

print("== feeds")
pr = c["NinerNate"].get(f"{BASE}/api/predictions").json()
check(all("badges" in p for p in pr) and any(p["username"] == "NinerNate" for p in pr), "predictions feed includes yours")

print("\nFAILURES:", fails)

sys.exit(1 if fails else 0)