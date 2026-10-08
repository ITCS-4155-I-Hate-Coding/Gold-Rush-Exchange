const $ = (id) => document.getElementById(id);
let me = null; // { id, username, reputation } when logged in
let mode = "login"; // or "register"
let allPreds = [];
let predView = "mine";
const myPicks = new Map(); // game_id is the team name the user picked

let allPosts = [];
let postView = "global"; // or "following"
let followingSet = new Set(); // usernames the current user follows

let lbView = "global"; // or "following"

async function api(path, method = "GET", body) {
  const res = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Something went wrong");
  return data;
}

const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ]
  );
const when = (d) => (d ? new Date(d).toLocaleDateString() : "");
const userLink = (u) =>
  `<button type="button" class="user-link" data-user="${esc(u)}">${esc(u)}</button>`;
const initial = (u) => esc((u || "?").trim().charAt(0).toUpperCase() || "?");

// ---------- Tabs ----------
const TABS = ["posts", "predictions", "leaderboard", "following", "profile"];

function showTab(name) {
  document
    .querySelectorAll(".tab")
    .forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  TABS.forEach((t) => ($(t).hidden = t !== name));
}

document.querySelectorAll(".tab").forEach((btn) =>
  btn.addEventListener("click", () => {
    if (btn.dataset.tab === "profile") return openProfile(); // your own profile
    if (btn.dataset.tab === "following") return openFollowing();
    if (btn.dataset.tab === "leaderboard") return openLeaderboard();
    showTab(btn.dataset.tab);
  })
);

// any username (on a post, comment or prediction) opens that user's profile
document.addEventListener("click", (e) => {
  const link = e.target.closest(".user-link");
  if (link) openProfile(link.dataset.user);
});

// ---------- Auth ----------
async function refresh() {
  me = await api("/api/me").catch(() => null);
  $("authBtn").textContent = me ? "Log out" : "Log in";
  $("userLabel").hidden = $("repBadge").hidden = !me;
  if (me) {
    $("userLabel").textContent = me.username;
    $("repBadge").textContent = `${me.reputation} rep`;
  }
  $("profileTab").hidden = !me;
  if (!me && !$("profile").hidden) showTab("posts"); // logged out while on Profile
  $("followingTab").hidden = !me;
  if (!me && !$("following").hidden) showTab("posts"); // logged out while on Following
  if (!me) {
    $("userSearch").value = "";
    $("searchResults").innerHTML = "";
  }
  $("postForm").hidden = $("predForm").hidden = !me;
  $("postsHint").hidden = $("predHint").hidden = !!me;

  // Global/Following toggle only makes sense when logged in
  $("postView").hidden = !me;
  if (!me) {
    postView = "global";
    $("postView")
      .querySelectorAll("button")
      .forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === "global")));
  }

  // Leaderboard's Following view only makes sense when logged in
  $("lbView").hidden = !me;
  if (!me) {
    lbView = "global";
    $("lbView")
      .querySelectorAll("button")
      .forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === "global")));
  }
  if (!$("leaderboard").hidden) loadLeaderboard();

  loadPosts();
  loadPredictions();
  loadGames();
}

function setMode(m) {
  mode = m;
  const reg = m === "register";
  $("authTitle").textContent = reg ? "Create account" : "Log in";
  $("authSubmit").textContent = reg ? "Create account" : "Log in";
  $("authSwitch").textContent = reg ? "I have an account" : "Create account";
  $("username").hidden = !reg;
  $("username").required = reg;
  $("authError").hidden = true;
}

$("authBtn").addEventListener("click", async () => {
  if (me) {
    await api("/api/logout", "POST");
    refresh();
  } else {
    setMode("login");
    $("authDialog").showModal();
  }
});
$("authSwitch").addEventListener("click", () =>
  setMode(mode === "login" ? "register" : "login")
);

$("authForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (e.submitter.value === "cancel") return $("authDialog").close();
  const email = $("email").value.trim();
  const password = $("password").value;
  try {
    if (mode === "register")
      await api("/api/register", "POST", {
        username: $("username").value.trim(),
        email,
        password
      });
    await api("/api/login", "POST", { email, password });
    $("authForm").reset();
    $("authDialog").close();
    refresh();
  } catch (err) {
    $("authError").textContent = err.message;
    $("authError").hidden = false;
  }
});

// ---------- Posts + comments ----------

// Global / Following toggle
$("postView").addEventListener("click", (e) => {
  const b = e.target.closest("[data-v]");
  if (!b || !me) return;
  postView = b.dataset.v;
  $("postView")
    .querySelectorAll("button")
    .forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
  renderPosts();
});

async function loadPosts() {
  const list = $("postList");
  try {
    const [posts, followList] = await Promise.all([
      api("/api/posts"),
      me ? api("/api/following").catch(() => []) : Promise.resolve([])
    ]);
    allPosts = posts;
    followingSet = new Set(followList.map((u) => u.username));
    renderPosts();
  } catch (err) {
    list.innerHTML = `<p class="error">Couldn't load posts: ${esc(err.message)}</p>`;
  }
}

function renderPosts() {
  const list = $("postList");
  const rows =
    postView === "following" && me
      ? allPosts.filter((p) => followingSet.has(p.username))
      : allPosts;

  if (!rows.length) {
    list.innerHTML =
      postView === "following"
        ? '<p class="hint">No posts yet from people you follow. Find people to follow on the Following tab.</p>'
        : '<p class="hint">No posts yet. Be the first to post.</p>';
    return;
  }

  list.innerHTML = rows
    .map(
      (p) => `
      <article class="card post-card" data-post="${p.id}">
        <div class="post-head">
          <span class="avatar" aria-hidden="true">${initial(p.username)}</span>
          <div class="meta">${userLink(p.username)} · ${when(p.created_at)}</div>
        </div>
        <p class="post-text">${esc(p.content)}</p>
        <div class="post-foot">
          <button class="like ${p.liked_by_me ? "liked" : ""}" data-like-post="${p.id}">${p.liked_by_me ? "Unlike" : "Like"} · ${p.likes}</button>
        </div>
        <div class="comments">
          <div class="comment-list"></div>
          ${me ? `<form class="comment-form"><input placeholder="Add a comment" required><button class="btn">Comment</button></form>` : ""}
        </div>
      </article>`
    )
    .join("");
  rows.forEach((p) => loadComments(p.id));
}

async function loadComments(postId) {
  const box = document.querySelector(`[data-post="${postId}"] .comment-list`);
  if (!box) return;
  try {
    const comments = await api(`/api/posts/${postId}/comments`);
    box.innerHTML = comments
      .map(
        (c) => `
      <div class="comment">${userLink(c.username)} ${esc(c.content)}
        <button class="like ${c.liked_by_me ? "liked" : ""}" data-like-comment="${c.id}" data-post="${postId}">${c.liked_by_me ? "Unlike" : "Like"} · ${c.likes}</button>
      </div>`
      )
      .join("");
  } catch {
    box.innerHTML = "";
  }
}

$("postForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/api/posts", "POST", { content: $("postBody").value });
    e.target.reset();
    loadPosts();
  } catch (err) {
    alert(err.message);
  }
});

$("postList").addEventListener("submit", async (e) => {
  e.preventDefault();
  const postId = e.target.closest("[data-post]").dataset.post;
  const input = e.target.querySelector("input");
  try {
    await api(`/api/posts/${postId}/comments`, "POST", {
      content: input.value
    });
    input.value = "";
    loadComments(postId);
  } catch (err) {
    alert(err.message);
  }
});

$("postList").addEventListener("click", async (e) => {
  const btn = e.target.closest(".like");
  if (!btn) return;
  try {
    if (btn.dataset.likePost) {
      await api(`/api/posts/${btn.dataset.likePost}/like`, "POST");
      loadPosts();
    } else {
      await api(`/api/comments/${btn.dataset.likeComment}/like`, "POST");
      loadComments(btn.dataset.post);
    }
  } catch (err) {
    alert(err.message);
  }
});

// ---------- Predictions ----------

async function loadPredictions() {
  const list = $("predList");
  try {
    allPreds = await api("/api/predictions");
    myPicks.clear();
    for (const p of allPreds)
      if (me && p.user_id === me.id && p.game_id)
        myPicks.set(p.game_id, p.prediction_text.replace(/ wins$/, ""));
    renderPredictions();
    renderGames(); // tiles show your picks
  } catch (err) {
    list.innerHTML = `<p class="error">Couldn't load predictions: ${esc(err.message)}</p>`;
  }
}

function renderPredictions() {
  const rows = allPreds.filter(
    (p) => predView === "all" || (me && p.user_id === me.id)
  );
  $("predList").innerHTML = rows.length
    ? rows
        .map(
          (p) =>
            `
    <article class="pcard ${esc(p.result)}">
      <div>
        <h4>${esc(p.game)}</h4>
        <p class="meta">${predView === "all" ? userLink(p.username) + " · " : ""}${when(p.created_at)}</p>
      </div>
      <div class="pred-row">
        <span class="pick">${esc(p.prediction_text)}</span>
        <span class="wager">${p.points} rep wagered${
          p.result === "correct"
            ? ` · <b class="w">+${p.points}</b>`
            : p.result === "incorrect"
              ? ` · <b class="l">−${p.points}</b>`
              : ""
        }</span>
        <span class="result ${esc(p.result)}">${esc(p.result)}</span>
      </div>
    </article>
  `
        )
        .join("")
    : `<p class="hint">${predView === "mine" ? "No predictions yet. Pick a game above." : "No predictions yet."}</p>`;
}

$("predView").addEventListener("click", (e) => {
  const b = e.target.closest("[data-v]");
  if (!b) return;
  predView = b.dataset.v;
  $("predView")
    .querySelectorAll("button")
    .forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
  renderPredictions();
});

// Dialog for predictions
let predGame = null;
let predPick = null;

const fmtWhen = (t) => {
  const d = new Date(t);
  const day = d.toLocaleDateString([], {
    weekday: "short",
    month: "short",
    day: "numeric"
  });
  const time = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  return `${day} at ${time}`;
};

function openPredict(g) {
  if (!me) return $("authBtn").click(); // if logged out then open the login dialog instead
  predGame = g;
  predPick = null;
  $("predMeta").textContent =
    `${g.sport[0].toUpperCase() + g.sport.slice(1)} · ${fmtWhen(g.start_time)}`;
  for (const side of ["away", "home"]) {
    const b = document.querySelector(`.pick-btn[data-pick="${side}"]`);
    b.innerHTML = `<small>${side}</small>${teamLabel(g[`${side}_team`], g[`${side}_rank`])}`;
    b.setAttribute("aria-pressed", "false");
  }
  $("predBalance").textContent = `Balance: ${me.reputation} rep`;
  $("predPoints").value = "";
  $("predPoints").max = me.reputation;
  $("predError").textContent = "";
  updateOutcome();
  $("predDialog").showModal();
}

function updateOutcome() {
  const n = Number($("predPoints").value);
  document.querySelectorAll("#predChips .chip").forEach((c) => {
    const v = c.dataset.pts === "max" ? me.reputation : Number(c.dataset.pts);
    c.setAttribute("aria-pressed", String(n > 0 && n === v));
  });
  $("predOutcome").innerHTML =
    n > 0 ? `Win <b class="w">+${n}</b> · Lose <b class="l">-${n}</b> rep` : "";
}

function showSuccessMessage(msg) {
  const t = $("successMessage");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => (t.hidden = true), 3000);
}

$("gamesList").addEventListener("click", (e) => {
  const b = e.target.closest(".predict");
  if (b) openPredict(allGames.find((g) => g.id === Number(b.dataset.id)));
});

document.querySelectorAll(".pick-btn").forEach((b) =>
  b.addEventListener("click", () => {
    predPick = b.dataset.pick;
    $("predError").textContent = "";
    document
      .querySelectorAll(".pick-btn")
      .forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
  })
);

$("predChips").addEventListener("click", (e) => {
  const c = e.target.closest(".chip");
  if (!c) return;
  $("predPoints").value =
    c.dataset.pts === "max" ? me.reputation : c.dataset.pts;
  $("predError").textContent = "";
  updateOutcome();
});

$("predPoints").addEventListener("input", () => {
  $("predError").textContent = "";
  updateOutcome();
});
$("predCancel").addEventListener("click", () => $("predDialog").close());

$("predForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const points = Number($("predPoints").value);
  if (!predPick)
    return void ($("predError").textContent = "Choose a team to win.");
  if (!(points > 0))
    return void ($("predError").textContent =
      "Enter a wager of at least 1 rep.");
  if (points > me.reputation)
    return void ($("predError").textContent =
      `You only have ${me.reputation} rep to wager.`);
  $("predSubmit").disabled = true;
  try {
    await api("/api/predictions", "POST", {
      game_id: predGame.id,
      pick: predPick,
      points
    });
    $("predDialog").close();
    showSuccessMessage(
      `Picked ${predGame[predPick + "_team"]} · ${points} rep`
    );
    await refresh(); // reloads balance, predictions list, and tile badges
  } catch (err) {
    $("predError").textContent = err.message;
  } finally {
    $("predSubmit").disabled = false;
  }
});

// ------------ Games ----------------
let allGames = [];
const gameFilter = { view: "all", sport: "all", conf: "all" };
const GAMES_PER_PAGE = 12;
let gamesShown = GAMES_PER_PAGE;

const isCharlotte = (g) => /charlotte/i.test(g.home_team + " " + g.away_team);
const isTop25 = (g) => g.home_rank || g.away_rank;
const teamLabel = (name, rank) =>
  (rank ? `<b class="rank">#${rank}</b> ` : "") + esc(name);

async function loadGames() {
  const list = $("gamesList");
  try {
    allGames = await api("/api/games");
    renderGames();
  } catch (err) {
    list.innerHTML = `<p class="error">Couldn't load games: ${esc(err.message)}</p>`;
  }
}

function renderGames() {
  const list = $("gamesList");
  if (!allGames.length) {
    $("gameFilters").innerHTML = "";
    $("gamesMore").hidden = true;
    list.innerHTML = '<p class="hint">No upcoming games. Try syncing.</p>';
    return;
  }

  const confs = [
    ...new Set(
      allGames
        .flatMap((g) => [g.home_conference, g.away_conference])
        .filter(Boolean)
    )
  ].sort();
  const chip = (group, value, label, count) =>
    `<button type="button" class="chip" aria-pressed="${gameFilter[group] === value}" data-group="${group}" data-value="${value}">${label}<small>${count}</small></button>`;
  $("gameFilters").innerHTML =
    chip("view", "all", "All", allGames.length) +
    chip(
      "view",
      "charlotte",
      "Charlotte",
      allGames.filter(isCharlotte).length
    ) +
    chip("view", "top25", "Top 25", allGames.filter(isTop25).length) +
    `<span class="chip-gap"></span>` +
    chip("sport", "all", "All sports", allGames.length) +
    chip(
      "sport",
      "football",
      "Football",
      allGames.filter((g) => g.sport === "football").length
    ) +
    chip(
      "sport",
      "basketball",
      "Basketball",
      allGames.filter((g) => g.sport === "basketball").length
    ) +
    `<select id="confFilter" aria-label="Filter by conference">
       <option value="all">All conferences</option>
       ${confs.map((c) => `<option value="${esc(c)}" ${gameFilter.conf === c ? "selected" : ""}>${esc(c)}</option>`).join("")}
     </select>`;

  const shown = allGames.filter(
    (g) =>
      (gameFilter.view === "all" ||
        (gameFilter.view === "charlotte" ? isCharlotte(g) : isTop25(g))) &&
      (gameFilter.sport === "all" || g.sport === gameFilter.sport) &&
      (gameFilter.conf === "all" ||
        g.home_conference === gameFilter.conf ||
        g.away_conference === gameFilter.conf)
  );
  if (!shown.length) {
    $("gamesMore").hidden = true;
    list.innerHTML = '<p class="hint">No games match these filters.</p>';
    return;
  }

  const visible = shown.slice(0, gamesShown);
  const days = new Map();
  for (const g of visible) {
    const day = new Date(g.start_time).toLocaleDateString([], {
      weekday: "short",
      month: "short",
      day: "numeric"
    });
    if (!days.has(day)) days.set(day, []);
    days.get(day).push(g);
  }
  list.innerHTML = [...days]
    .map(
      ([day, games]) => `
    <section class="day">
      <h3 class="day-h">${esc(day)}<span>${games.length} game${games.length > 1 ? "s" : ""}</span></h3>
      <div class="game-grid">
        ${games
          .map(
            (g) => `
        <article class="tile">
          <div class="tile-top"><span class="sport ${esc(g.sport)}">${esc(g.sport)}</span><span>${esc(g.status)}</span></div>
          <div class="teams">
            <div><i>AWAY</i><span>${teamLabel(g.away_team, g.away_rank)}</span></div>
            <div><i>HOME</i><span>${teamLabel(g.home_team, g.home_rank)}</span></div>
          </div>
          <div class="tile-foot">
            <span class="time">${new Date(g.start_time).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</span>
            ${
              myPicks.has(g.id)
                ? `<span class="picked">Your pick: ${esc(myPicks.get(g.id))}</span>`
                : `<button type="button" class="predict" data-id="${g.id}">Predict</button>`
            }
            
          </div>
        </article>`
          )
          .join("")}
      </div>
    </section>`
    )
    .join("");

  const left = shown.length - visible.length;
  $("gamesMore").hidden = left <= 0;
  $("gamesMore").textContent =
    `Show ${Math.min(left, GAMES_PER_PAGE)} more (${left} left)`;
}

$("gameFilters").addEventListener("click", (e) => {
  const b = e.target.closest("[data-group]");
  if (!b) return;
  gameFilter[b.dataset.group] = b.dataset.value;
  gamesShown = GAMES_PER_PAGE;
  renderGames();
});
$("gameFilters").addEventListener("change", (e) => {
  if (e.target.id !== "confFilter") return;
  gameFilter.conf = e.target.value;
  gamesShown = GAMES_PER_PAGE;
  renderGames();
});
$("gamesMore").addEventListener("click", () => {
  gamesShown += GAMES_PER_PAGE;
  renderGames();
});
// for the sync games button
$("syncGamesBtn").addEventListener("click", async () => {
  const btn = $("syncGamesBtn");
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Syncing...";
  try {
    const result = await api("/api/games/sync", "POST");
    await refresh(); // refresh games, predictions, and posts; pulls from api again
    btn.textContent = `Synced (${result.predictions_settled} settled)`;
  } catch (err) {
    alert(`Couldn't sync games: ${err.message}`);
    btn.textContent = originalText;
  } finally {
    btn.disabled = false;
    setTimeout(() => (btn.textContent = originalText), 2500);
  }
});

// ---------- Profile ----------
function openProfile(username) {
  showTab("profile");
  loadProfile(username);
}

async function loadProfile(username) {
  const box = $("profileBody");
  box.innerHTML = '<p class="hint">Loading profile…</p>';
  try {
    const path = username
      ? `/api/users/${encodeURIComponent(username)}/profile`
      : "/api/profile";
    box.innerHTML = renderProfile(await api(path));
  } catch (err) {
    box.innerHTML = `<p class="error">Couldn't load profile: ${esc(err.message)}</p>`;
  }
}

function renderProfile(p) {
  const s = p.predictions;
  const accuracy = s.accuracy === null ? "—" : `${Math.round(s.accuracy)}%`;
  const accuracyNote = s.settled
    ? `${s.correct} of ${s.settled} settled correct`
    : "No settled predictions yet";
  const stat = (num, label, note = "") => `
      <div class="stat">
        <div class="stat-num">${esc(num)}</div>
        <div class="stat-label">${esc(label)}</div>
        ${note ? `<div class="stat-note">${esc(note)}</div>` : ""}
      </div>`;

  const activity = p.recent_activity.length
    ? p.recent_activity.map(renderActivity).join("")
    : '<p class="hint">No activity yet.</p>';

  const followBtn =
    me && !p.is_me
      ? `<button type="button" class="btn ${p.is_following ? "btn-outline" : ""}"
           data-follow="${esc(p.username)}" data-following="${p.is_following ? 1 : 0}">
           ${p.is_following ? "Unfollow" : "Follow"}</button>`
      : "";
  const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

  return `
    <article class="card profile-head">
      <div>
        <h2>${esc(p.username)}</h2>
        <div class="meta">Member since ${when(p.member_since)} · ${plural(p.followers, "follower")} · ${p.following} following</div>
      </div>
      ${followBtn}
    </article>
    <div class="stats">
      ${stat(p.reputation, "Reputation")}
      ${stat(accuracy, "Prediction accuracy", accuracyNote)}
      ${stat(`${s.correct}–${s.incorrect}`, "Record (W–L)", `${s.pending} pending · ${s.total} total`)}
      ${stat(`+${s.rep_gained}`, "Rep won", `−${s.rep_lost} lost on incorrect picks`)}
    </div>
    <h3 class="section-title">Recent activity</h3>
    <div class="activity">${activity}</div>`;
}

function renderActivity(a) {
  const label = { post: "Post", comment: "Comment", prediction: "Prediction" }[
    a.type
  ];
  const body =
    a.type === "prediction"
      ? `<strong>${esc(a.title)}</strong>
         <div class="pred-row">
           <span class="pick">${esc(a.body)}</span>
           <span>${a.points} pts wagered</span>
           <span class="result ${esc(a.result)}">${esc(a.result)}</span>
         </div>`
      : `<p class="post-text">${esc(a.body)}</p>`;
  return `
    <div class="activity-item">
            <div class="meta"><span class="kind kind-${esc(a.type)}">${label}</span> ${a.username ? userLink(a.username) + " · " : ""}${when(a.created_at)}</div>
      ${body}
    </div>`;
}

// ---------- Following ----------
function openFollowing() {
  showTab("following");
  loadFollowing();
}

async function loadFollowing() {
  const box = $("followingBody");
  box.innerHTML = '<p class="hint">Loading…</p>';
  try {
    const [people, feed] = await Promise.all([
      api("/api/following"),
      api("/api/following/feed")
    ]);
    box.innerHTML = renderFollowing(people, feed);
  } catch (err) {
    box.innerHTML = `<p class="error">Couldn't load following: ${esc(err.message)}</p>`;
  }
}

function renderFollowing(people, feed) {
  if (!people.length)
    return `
      <h3 class="section-title">Following (0)</h3>
      <p class="hint">You're not following anyone yet. Click a username on a post or prediction to open their profile and follow them.</p>`;

  const rows = people
    .map(
      (u) => `
      <div class="follow-row">
        <div>
          ${userLink(u.username)}
          <span class="meta">${u.reputation} rep · following since ${when(u.followed_at)}</span>
        </div>
        <button type="button" class="btn btn-outline"
          data-follow="${esc(u.username)}" data-following="1" data-where="list">Unfollow</button>
      </div>`
    )
    .join("");

  const activity = feed.length
    ? feed.map(renderActivity).join("")
    : '<p class="hint">No posts or predictions from the people you follow yet.</p>';

  return `
    <h3 class="section-title">Following (${people.length})</h3>
    <div class="follow-list">${rows}</div>
    <h3 class="section-title">Their activity</h3>
    <div class="activity">${activity}</div>`;
}

// Follow / Unfollow buttons (on a profile and in the Following list)
document.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-follow]");
  if (!btn) return;
  const name = btn.dataset.follow;
  btn.disabled = true;
  try {
    await api(
      `/api/users/${encodeURIComponent(name)}/follow`,
      btn.dataset.following === "1" ? "DELETE" : "POST"
    );
    if (btn.dataset.where === "list" || btn.dataset.where === "search") {
      loadFollowing(); // the list and feed change
      runSearch(); // search results show the new Follow/Unfollow state
    } else loadProfile(name);
    if (postView === "following") loadPosts(); // keep the Posts filter in sync too
  } catch (err) {
    alert(err.message);
    btn.disabled = false;
  }
});

// ---------- Leaderboard ----------
function openLeaderboard() {
  showTab("leaderboard");
  $("lbView").hidden = !me;
  loadLeaderboard();
}

$("lbView").addEventListener("click", (e) => {
  const b = e.target.closest("[data-v]");
  if (!b || !me) return;
  lbView = b.dataset.v;
  $("lbView")
    .querySelectorAll("button")
    .forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
  loadLeaderboard();
});

async function loadLeaderboard() {
  const list = $("lbList");
  list.innerHTML = '<p class="hint">Loading…</p>';
  try {
    let rows;
    if (lbView === "following" && me) {
      const following = await api("/api/following");
      rows = following.map((u) => ({ username: u.username, reputation: u.reputation }));
      rows.push({ username: me.username, reputation: me.reputation });
    } else {
      rows = await api("/api/leaderboard");
    }
    rows.sort((a, b) => b.reputation - a.reputation);
    renderLeaderboard(rows);
  } catch (err) {
    list.innerHTML = `<p class="error">Couldn't load leaderboard: ${esc(err.message)}</p>`;
  }
}

function renderLeaderboard(rows) {
  const list = $("lbList");
  if (!rows.length) {
    list.innerHTML =
      lbView === "following"
        ? '<p class="hint">Follow people to compare reputation here.</p>'
        : '<p class="hint">No ranked users yet.</p>';
    return;
  }
  list.innerHTML = rows
    .map(
      (u, i) => `
    <div class="lb-row ${me && u.username === me.username ? "lb-me" : ""}">
      <span class="lb-rank">${i + 1}</span>
      <span class="avatar" aria-hidden="true">${initial(u.username)}</span>
      ${userLink(u.username)}
      <span class="badge">${u.reputation} rep</span>
    </div>`
    )
    .join("");
}

// ---------- Search users ----------
let searchTimer;

async function runSearch() {
  const q = $("userSearch").value.trim();
  const box = $("searchResults");
  if (!q) return (box.innerHTML = "");
  try {
    const users = await api(`/api/users/search?q=${encodeURIComponent(q)}`);
    if (q !== $("userSearch").value.trim()) return; // a newer search is already running
    box.innerHTML = users.length
      ? users
          .map(
            (u) => `
      <div class="follow-row">
        <div>
          ${userLink(u.username)}
          <span class="meta">${u.reputation} rep</span>
        </div>
        <button type="button" class="btn ${u.is_following ? "btn-outline" : ""}"
          data-follow="${esc(u.username)}" data-following="${u.is_following ? 1 : 0}" data-where="search">
          ${u.is_following ? "Unfollow" : "Follow"}</button>
      </div>`
          )
          .join("")
      : `<p class="hint">No users match "${esc(q)}".</p>`;
  } catch (err) {
    box.innerHTML = `<p class="error">Search failed: ${esc(err.message)}</p>`;
  }
}

// wait for a short pause in typing before searching
$("userSearch").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(runSearch, 300);
});

refresh();