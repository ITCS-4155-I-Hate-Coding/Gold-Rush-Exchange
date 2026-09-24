const $ = (id) => document.getElementById(id);
let me = null;            // { id, username, reputation } when logged in
let mode = "login";       // or "register"

async function api(path, method = "GET", body) {
  const res = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Something went wrong");
  return data;
}

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const when = (d) => (d ? new Date(d).toLocaleDateString() : "");

// ---------- Tabs ----------
document.querySelectorAll(".tab").forEach((btn) =>
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === btn));
    $("posts").hidden = btn.dataset.tab !== "posts";
    $("predictions").hidden = btn.dataset.tab !== "predictions";
  })
);

// ---------- Auth ----------
async function refresh() {
  me = await api("/api/me").catch(() => null);
  $("authBtn").textContent = me ? "Log out" : "Log in";
  $("userLabel").hidden = $("repBadge").hidden = !me;
  if (me) {
    $("userLabel").textContent = me.username;
    $("repBadge").textContent = `${me.reputation} rep`;
  }
  $("postForm").hidden = $("predForm").hidden = !me;
  $("postsHint").hidden = $("predHint").hidden = !!me;
  loadPosts();
  loadPredictions();
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
$("authSwitch").addEventListener("click", () => setMode(mode === "login" ? "register" : "login"));

$("authForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (e.submitter.value === "cancel") return $("authDialog").close();
  const email = $("email").value.trim();
  const password = $("password").value;
  try {
    if (mode === "register") await api("/api/register", "POST", { username: $("username").value.trim(), email, password });
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
async function loadPosts() {
  const list = $("postList");
  try {
    const posts = await api("/api/posts");
    if (!posts.length) return (list.innerHTML = '<p class="hint">No posts yet. Be the first to post.</p>');
    list.innerHTML = posts.map((p) => `
      <article class="card" data-post="${p.id}">
        <div class="meta">${esc(p.username)} · ${when(p.created_at)}</div>
        <p class="post-text">${esc(p.content)}</p>
        <button class="like" data-like-post="${p.id}">Like · ${p.likes}</button>
        <div class="comments">
          <div class="comment-list"></div>
          ${me ? `<form class="comment-form"><input placeholder="Add a comment" required><button class="btn">Comment</button></form>` : ""}
        </div>
      </article>`).join("");
    posts.forEach((p) => loadComments(p.id));
  } catch (err) {
    list.innerHTML = `<p class="error">Couldn't load posts: ${esc(err.message)}</p>`;
  }
}

async function loadComments(postId) {
  const box = document.querySelector(`[data-post="${postId}"] .comment-list`);
  try {
    const comments = await api(`/api/posts/${postId}/comments`);
    box.innerHTML = comments.map((c) => `
      <div class="comment"><b>${esc(c.username)}</b> ${esc(c.content)}
        <button class="like" data-like-comment="${c.id}" data-post="${postId}">Like · ${c.likes}</button>
      </div>`).join("");
  } catch { box.innerHTML = ""; }
}

$("postForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/api/posts", "POST", { content: $("postBody").value });
    e.target.reset();
    loadPosts();
  } catch (err) { alert(err.message); }
});

$("postList").addEventListener("submit", async (e) => {
  e.preventDefault();
  const postId = e.target.closest("[data-post]").dataset.post;
  const input = e.target.querySelector("input");
  try {
    await api(`/api/posts/${postId}/comments`, "POST", { content: input.value });
    input.value = "";
    loadComments(postId);
  } catch (err) { alert(err.message); }
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
  } catch (err) { alert(err.message); }
});

// ---------- Predictions ----------
async function loadPredictions() {
  const list = $("predList");
  try {
    const preds = await api("/api/predictions");
    list.innerHTML = preds.length
      ? preds.map((p) => `
        <article class="card">
          <h3>${esc(p.game)}</h3>
          <div class="meta">${esc(p.username)} · ${when(p.created_at)}</div>
          <div class="pred-row">
            <span class="pick">${esc(p.prediction_text)}</span>
            <span>${p.points} pts wagered</span>
            <span class="result ${esc(p.result)}">${esc(p.result)}</span>
          </div>
        </article>`).join("")
      : '<p class="hint">No predictions yet.</p>';
  } catch (err) {
    list.innerHTML = `<p class="error">Couldn't load predictions: ${esc(err.message)}</p>`;
  }
}

$("predForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/api/predictions", "POST", {
      game: $("predGame").value,
      prediction_text: $("predText").value,
      points: Number($("predPoints").value),
    });
    e.target.reset();
    loadPredictions();
  } catch (err) { alert(err.message); }
});

refresh();