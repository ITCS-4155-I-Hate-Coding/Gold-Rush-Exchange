const $ = (id) => document.getElementById(id);
let me = null; // { id, username, reputation, badges, achievement_score, new_achievements} when logged in
let mode = "login"; // or "register"
let allPreds = [];
let predView = "mine";
const myPicks = new Map(); // game_id is the team name the user picked

let allPosts = [];
let postView = "global"; // or "following"
let followingSet = new Set(); // usernames the current user follows

let lbView = "global"; // or "following"
let lbSort = "reputation";

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
// every time username is shown, there are badges showing next to it
const userLink = (u, badges) =>
  `<button type="button" class="user-link" data-user="${esc(u)}">${esc(u)}</button>${badgeRow(badges)}`;
const initial = (u) => esc((u || "?").trim().charAt(0).toUpperCase() || "?");

// ACHIEVEMENTS AND BADGES
// 1. loadCatalog() will fetch every achievements name, tier, and value once at startup
// 2. the badgeSvg() will draw a badge from scratch so there are no image files to manage
// 3. badgesRow() will put users featured badges after their name
// 4. showUnlocks() shows achievement unlocked message when the database reports new ones
// 5.

// The catalog (names, tiers, values) comes from /api/achievements/catalog once at startup.
let ACH = null; // { tiers, tracks, max_featured, achievements: [...] }
let ACH_BY_CODE = new Map(); // "streak_5" -> { name: "On Fire", tier: "rare", value: 50, ... }

async function loadCatalog() {
  try {
    ACH = await api("/api/achievements/catalog");
    ACH_BY_CODE = new Map(ACH.achievements.map((a) => [a.code, a]));
  } catch {
    // if this fails the site still works: badgeRow() finds nothing in ACH_BY_CODE
    // and draws no badges, and the profile shows "Achievements are unavailable"
    ACH = null;
  }
}

// one simple line icon per track, drawn on a 24x24 grid (same idea as icon sets like
// Feather or Lucide, but drawn for this site). badgeSvg() places it inside the hexagon.
// The key must match the track names in AchievementBackend.TRACKS.
const BADGE_GLYPHS = {
  // a stack of coins: winnings
  rep_won:
    '<ellipse cx="12" cy="6.5" rx="7" ry="2.8"/><path d="M5 6.5v5c0 1.5 3.1 2.8 7 2.8s7-1.3 7-2.8v-5"/><path d="M5 11.5v5c0 1.5 3.1 2.8 7 2.8s7-1.3 7-2.8v-5"/>',
  // a bank building: balance
  reputation:
    '<path d="M3 9.5 12 4l9 5.5"/><path d="M5.5 10v8M10 10v8M14 10v8M18.5 10v8"/><path d="M3 20h18"/>',
  // a target: correct picks
  correct:
    '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1" fill="#fff"/>',
  // a clipboard: predictions made
  predictions:
    '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 3v2.5h6V3M8.5 11h7M8.5 15h4.5"/>',
  // a flame: win streak
  streak:
    '<path d="M12 3c.8 3.6 5 5.2 5 10.2a5 5 0 0 1-10 0c0-2.4 1.3-3.6 2-5.2.9 1.4 1.6 2 2.6 2.2C11.4 8.3 11 5.8 12 3z"/>',
  // a poker chip: big wins
  big_win:
    '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4"/><path d="M12 3.5v3M12 17.5v3M3.5 12h3M17.5 12h3"/>',
  // a lightning bolt: upsets
  upsets: '<path d="M13.5 2.5 5.5 14h6l-1 7.5 8-11.5h-6z"/>',
  // a pickaxe (the 49ers are named after gold miners): Charlotte wins
  charlotte:
    '<path d="M4 9.5c4.5-4.6 11.5-4.6 16 0"/><path d="M12 6.2 12 21"/><path d="M10.2 21h3.6"/>',
  // a speech bubble: posts
  posts: '<path d="M4 5h16v11H9.5L5 20v-4H4z"/>',
  // a speech bubble with dots: comments
  comments:
    '<path d="M4 5h16v11H9.5L5 20v-4H4z"/><path d="M8.5 10.5h.01M12 10.5h.01M15.5 10.5h.01" stroke-width="2.6"/>',
  // a heart: likes received
  likes:
    '<path d="M12 20s-7.5-4.6-7.5-10.2A4.1 4.1 0 0 1 12 7.4a4.1 4.1 0 0 1 7.5 2.4C19.5 15.4 12 20 12 20z"/>',
  // two people: followers
  followers:
    '<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.4 2.7-6 6-6s6 2.6 6 6"/><circle cx="17" cy="9" r="2.4"/><path d="M15.8 14.2c2.9.3 5.2 2.6 5.2 5.8"/>',
  // a crown: leaderboard rank
  rank: '<path d="M3.5 8 8 12.2 12 5l4 7.2L20.5 8 18.8 19H5.2z"/><path d="M5.2 19h13.6"/>'
};

// each tier's badge is a gradient from a light colour (top left) to a dark one (bottom right).
// Rarity colours follow the convention most games use (grey, green, blue, purple, gold),
// so players can tell how rare a badge is at a glance. Legendary uses the site's gold.
// The same colours are repeated as .tier-* classes in Base.css for text and borders.
const TIER_COLORS = {
  bronze: ["#f2b27a", "#8a4b1f"],
  silver: ["#f1f4f7", "#7d8893"],
  gold: ["#fff0a8", "#c08a1a"],
  platinum: ["#ffffff", "#a9b6c2"],
  diamond: ["#e6f9ff", "#2f9fd8"]
};

// gradients are defined once in a hidden <svg> so every badge can reference them by id
// (fill="url(#tier-rare)"). Defining a gradient inside every badge would repeat the same
// ids many times on the page, which is invalid HTML and can draw the wrong colours.
// This runs once, as soon as the script loads.
(function addBadgeDefs() {
  const stops = Object.entries(TIER_COLORS)
    .map(
      ([t, [a, b]]) =>
        `<linearGradient id="tier-${t}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/></linearGradient>`
    )
    .join("");
  document.body.insertAdjacentHTML(
    "afterbegin",
    `<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>${stops}</defs></svg>`
  );
})();

// returns the SVG markup for one badge.
//   size   = width/height in pixels (18 next to names, 52 on achievement cards)
//   locked = draw it greyed out (not earned yet); the CSS class .locked does the greying
// Drawn on a 48x48 grid: an outer hexagon in the tier gradient, a darker inner hexagon so
// the icon stands out, then the 24x24 icon scaled to 20x20 and centred (14 + 20 + 14 = 48).
function badgeSvg(code, size = 20, locked = false) {
  const a = ACH_BY_CODE.get(code);
  if (!a) return ""; // unknown code (catalog didn't load, or an achievement was removed)
  return `<svg class="bdg-svg tier-${a.tier}${locked ? " locked" : ""}" width="${size}" height="${size}" viewBox="0 0 48 48" aria-hidden="true">
    <polygon points="24,2 43.05,13 43.05,35 24,46 4.95,35 4.95,13" fill="url(#tier-${a.tier})"/>
    <polygon points="24,7.5 38.3,15.75 38.3,32.25 24,40.5 9.7,32.25 9.7,15.75" fill="rgba(6,14,11,.42)"/>
    <g transform="translate(14 14) scale(.8333)" fill="none" stroke="#fff" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round">${BADGE_GLYPHS[a.track] || ""}</g>
  </svg>`;
}

// hover text for a badge, e.g. "On Fire · Rare achievement (50 pts): Get 5 settled predictions right in a row."
const badgeTitle = (a) =>
  `${a.name} · ${a.tier_label} achievement (${a.value} pts): ${a.description}`;

// small featured badges shown after a username.
// Each badge gets a title (hover tooltip) and an aria-label, so people can find out what a
// badge means and screen readers say "On Fire badge" instead of skipping it.
// Returns "" when there's nothing to show, so userLink() output is unchanged for users
// with no featured badges.
function badgeRow(codes, size = 18) {
  const list = (codes || []).filter((c) => ACH_BY_CODE.has(c));
  if (!list.length) return "";
  return `<span class="badges">${list
    .map((c) => {
      const a = ACH_BY_CODE.get(c);
      return `<span class="bdg" title="${esc(badgeTitle(a))}" role="img" aria-label="${esc(a.name)} badge">${badgeSvg(c, size)}</span>`;
    })
    .join("")}</span>`;
}

// 12500 -> "12,500"
const fmtNum = (n) => Number(n).toLocaleString();

// "Achievement unlocked" message, shown once per achievement (the server marks them seen).
// If several unlock at once (common after a sync settles a few games), it names the most
// valuable one and adds "and N more", instead of stacking several messages on screen.
function showUnlocks(codes) {
  const list = (codes || []).filter((c) => ACH_BY_CODE.has(c));
  if (!list.length) return;
  const a = ACH_BY_CODE.get(list[0]); // the server sends the most valuable first
  const t = $("achToast");
  t.innerHTML = `
    ${badgeSvg(a.code, 46)}
    <div>
      <div class="ach-toast-kicker">Achievement unlocked</div>
      <div class="ach-toast-name">${esc(a.name)}</div>
      <div class="ach-toast-meta"><span class="tier-pill tier-${a.tier}">${esc(a.tier_label)}</span> +${a.value} pts${
        list.length > 1 ? ` · and ${list.length - 1} more` : ""
      }</div>
    </div>`;
  t.hidden = false;
  // restart the slide-in animation if a message is already showing.
  // Reading offsetWidth forces the browser to apply the class removal before re-adding it.
  t.classList.remove("show");
  void t.offsetWidth;
  t.classList.add("show");
  // hide after 7 seconds. clearTimeout stops an older message's timer from hiding this one early.
  clearTimeout(t._timer);
  t._timer = setTimeout(() => (t.hidden = true), 7000);
}

// clicking the message opens your own profile and scrolls to the Achievements section
$("achToast").addEventListener("click", () => {
  $("achToast").hidden = true;
  openProfile(null, "achievements");
});

// ---- Achievements section on a profile ----
// which cards to show. "progress" is the default because showing all 43 cards pushed
// the user's picks and activity far down the page; earned + the next goal in each track
// is usually what people want to see.
let achView = "progress"; // "progress" (earned + next goal per track), "earned" or "all"
// the order tiers appear in the key. Needed because Flask sorts JSON object keys
// alphabetically, so ACH.tiers arrives as common, epic, legendary, rare, uncommon.
const TIER_ORDER = ["bronze", "silver", "gold", "platinum", "diamond"];
// message shown under the showcase (e.g. trying to show a 4th badge). Cleared on profile load.
let achError = "";

// the small text under a locked card's progress bar, e.g. "825 / 1,000 rep won"
function achProgressText(a, item) {
  const p = item.progress;
  if (a.lower_is_better) {
    // leaderboard rank: the server sends null until the user has enough settled picks
    if (p == null)
      return `Unlocks after ${profileState.ach.rank_min_settled} settled picks`;
    return `Currently #${fmtNum(p)} · need ${a.threshold === 1 ? "#1" : `top ${a.threshold}`}`;
  }
  // Math.min stops it saying "1,200 / 1,000" for a lower level that's already passed
  return `${fmtNum(Math.min(p ?? 0, a.threshold))} / ${fmtNum(a.threshold)} ${esc(ACH.tracks[a.track].unit)}`;
}

// how full the progress bar is, from 0 to 1
function achFraction(a, item) {
  const p = item.progress;
  if (item.earned) return 1;
  if (p == null || p <= 0) return 0;
  // for rank, being #20 when you need top 10 is 10 / 20 = half way
  return Math.min(1, a.lower_is_better ? a.threshold / p : p / a.threshold);
}

// one achievement card.
//   isMe          = this is your own profile, so earned cards get a Show button
//   featuredCount = how many badges you show now (to explain why a 4th can't be added)
//   showTrack     = print the track name on the card (used when cards aren't grouped by track)
function achCard(item, isMe, featuredCount, showTrack = false) {
  const a = ACH_BY_CODE.get(item.code);
  if (!a) return "";
  const pct = Math.round(achFraction(a, item) * 100);
  const rarity = `${item.holders_pct}% of players`;
  let action = "";
  if (isMe && item.earned) {
    // aria-pressed makes it a toggle button: "Show" when off, "Showing" when on.
    // The button stays clickable when 3 are already shown; clicking it explains the limit.
    const full = !item.featured && featuredCount >= ACH.max_featured;
    action = `<button type="button" class="ach-show" data-feature="${esc(a.code)}" aria-pressed="${item.featured}" ${
      full
        ? `title="You can show up to ${ACH.max_featured} badges. Hide one first."`
        : ""
    }>${item.featured ? "Showing" : "Show"}</button>`;
  }
  // earned cards show the date and rarity; locked cards show a progress bar instead
  return `
    <div class="ach-card ${item.earned ? "earned" : "locked"} tier-${a.tier}">
      <div class="ach-icon">${badgeSvg(a.code, 52, !item.earned)}</div>
      <div class="ach-body">
        ${showTrack ? `<div class="ach-kicker">${esc(ACH.tracks[a.track].label)}</div>` : ""}
        <div class="ach-name">${esc(a.name)}</div>
        <div class="ach-tier"><span class="tier-pill tier-${a.tier}">${esc(a.tier_label)}</span><span class="ach-value">${a.value} pts</span></div>
        <p class="ach-desc">${esc(a.description)}</p>
        ${
          item.earned
            ? `<div class="ach-earned">Earned ${when(item.earned_at)} · ${rarity}</div>`
            : `<div class="ach-bar" aria-hidden="true"><span style="width:${pct}%"></span></div>
               <div class="ach-progress">${achProgressText(a, item)} · ${rarity}</div>`
        }
        ${action}
      </div>
    </div>`;
}

// the whole Achievements section of a profile.
//   data = the response from GET /api/users/<username>/achievements (null if it failed)
//   isMe = true on your own profile (shows Show buttons and empty showcase slots)
// Layout, top to bottom: heading + view toggle, score summary, showcase, cards.
function renderAchievements(data, isMe) {
  if (!ACH)
    return '<p class="hint">Achievements are unavailable right now.</p>';
  if (!data) return '<p class="error">Couldn\'t load achievements.</p>';
  const featured = data.featured;

  // the showcase: the badges that appear next to this user's name, as 3 slots.
  // Empty slots are drawn on your own profile so it's obvious you can fill them.
  const slots = [];
  for (let i = 0; i < ACH.max_featured; i++) {
    const code = featured[i];
    const a = code && ACH_BY_CODE.get(code);
    slots.push(
      a
        ? `<div class="slot filled" title="${esc(badgeTitle(a))}">${badgeSvg(code, 44)}<span>${esc(a.name)}</span></div>`
        : `<div class="slot empty">${isMe ? "Empty slot" : ""}</div>`
    );
  }
  // on someone else's profile the showcase only appears if they chose badges
  const showcase =
    isMe || featured.length
      ? `<div class="showcase">
           <div class="showcase-label">${
             isMe
               ? `Shown next to your name (${featured.length}/${ACH.max_featured}) · pick with <b>Show</b> below`
               : "Featured badges"
           }</div>
           <div class="slots">${slots.join("")}</div>
           ${achError ? `<p class="error" role="alert">${esc(achError)}</p>` : ""}
         </div>`
      : "";

  // pick which cards to show for the current view, grouped by track.
  // data.achievements is in catalog order (easiest -> hardest within each track), so the
  // FIRST locked card met in a track is the next goal.
  const byTrack = new Map();
  const nextShown = new Set(); // tracks whose next locked level is already shown
  for (const item of data.achievements) {
    const a = ACH_BY_CODE.get(item.code);
    if (!a) continue;
    if (!item.earned) {
      if (achView === "earned") continue;
      if (achView === "progress") {
        if (nextShown.has(a.track)) continue; // only the next goal in each track
        nextShown.add(a.track);
      }
    }
    if (!byTrack.has(a.track)) byTrack.set(a.track, []);
    byTrack.get(a.track).push(item);
  }
  // "All" groups the cards by track, one row each with a "2/5" count, so you can see how
  // each series climbs. The shorter views put every card in one grid (with the track name
  // on each card) because one row per track left lots of empty space with only 1-2 cards.
  const flat = achView !== "all";
  const tracks = flat
    ? `<div class="ach-grid">${[...byTrack.values()]
        .flat()
        .sort((x, y) => Number(y.earned) - Number(x.earned)) // earned first, then next goals
        .map((i) => achCard(i, isMe, featured.length, true))
        .join("")}</div>`
    : [...byTrack]
        .map(([track, items]) => {
          const got = data.achievements.filter(
            (i) => i.earned && ACH_BY_CODE.get(i.code).track === track
          ).length;
          const all = ACH.achievements.filter((a) => a.track === track).length;
          return `
      <div class="ach-track">
        <h4 class="picks-title">${esc(ACH.tracks[track].label)} <span>${got}/${all}</span></h4>
        <div class="ach-grid">${items.map((i) => achCard(i, isMe, featured.length)).join("")}</div>
      </div>`;
        })
        .join("");

  // the summary: score, "12 of 43 earned", a progress bar, and the tier key
  // (which explains the colours and what each tier is worth)
  const pct = Math.round((data.earned_count / data.total_count) * 100);
  return `
    <div class="ach-head">
      <h3 class="section-title" id="achievements-title">Achievements</h3>
      <div class="seg" id="achView" role="group" aria-label="Show achievements">
        <button type="button" data-v="progress" aria-pressed="${achView === "progress"}">Next goals</button>
        <button type="button" data-v="earned" aria-pressed="${achView === "earned"}">Earned</button>
        <button type="button" data-v="all" aria-pressed="${achView === "all"}">All ${data.total_count}</button>
      </div>
    </div>
    <div class="ach-summary card">
      <div><div class="stat-num">${fmtNum(data.score)}</div><div class="stat-label">Achievement score</div></div>
      <div class="ach-summary-bar">
        <div class="meta">${data.earned_count} of ${data.total_count} earned · ${fmtNum(data.score)} of ${fmtNum(data.max_score)} pts</div>
        <div class="ach-bar big" aria-hidden="true"><span style="width:${pct}%"></span></div>
        <div class="tier-key">${TIER_ORDER.map((t) => [t, ACH.tiers[t]])
          .map(
            ([t, v]) =>
              `<span class="tier-pill tier-${t}">${esc(v.label)} · ${v.value}</span>`
          )
          .join("")}</div>
      </div>
    </div>
    ${showcase}
    ${tracks || '<p class="hint">No achievements earned yet.</p>'}`;
}

// Show / hide a badge next to your name.
// Listens on the whole document (event delegation) because the cards are redrawn often,
// so listeners attached to individual buttons would be lost on every redraw.
document.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-feature]");
  if (!btn || !profileState || !me) return;
  const code = btn.dataset.feature;
  const cur = profileState.ach.featured;
  // the new full list: remove the badge if it's showing, otherwise add it
  const next = cur.includes(code)
    ? cur.filter((c) => c !== code)
    : [...cur, code];
  // check the limit here too, so the user gets a clear message without a server round trip
  // (the server enforces it as well, because requests can be sent without this page)
  if (next.length > ACH.max_featured) {
    achError = `You can show up to ${ACH.max_featured} badges. Hide one first.`;
    return rerenderProfile();
  }
  btn.disabled = true; // stops double clicks while saving
  try {
    // send the whole list (PUT replaces it), not "add this one"
    await api("/api/achievements/featured", "PUT", { codes: next });
    achError = "";
    // the server sorts featured badges best first; mirror that here so the page matches
    // what everyone else will see without reloading (value high -> low, then catalog order)
    const order = (c) => [
      -(ACH_BY_CODE.get(c)?.value || 0),
      ACH.achievements.findIndex((a) => a.code === c)
    ];
    next.sort((x, y) => {
      const [a1, a2] = order(x),
        [b1, b2] = order(y);
      return a1 - b1 || a2 - b2;
    });
    // update everything already on the page instead of reloading it:
    // the profile data, the profile header, your name in the top bar, and the posts list
    profileState.ach.featured = next;
    for (const item of profileState.ach.achievements)
      item.featured = next.includes(item.code);
    profileState.p.badges = next;
    me.badges = next;
    renderHeader();
    rerenderProfile();
    loadPosts(); // so posts show the new badges
  } catch (err) {
    achError = err.message; // e.g. the server rejected it; shown under the showcase
    rerenderProfile();
  }
});

// Next goals / Earned / All toggle on the Achievements section.
// Only redraws from data already loaded, so switching is instant.
document.addEventListener("click", (e) => {
  const b = e.target.closest("#achView [data-v]");
  if (!b) return;
  achView = b.dataset.v;
  rerenderProfile();
});

// ---------- Tabs ----------
const TABS = [
  "posts",
  "predictions",
  "leaderboard",
  "following",
  "messages", // new tab
  "compare",
  "profile"
];

function showTab(name) {
  document
    .querySelectorAll(".tab")
    .forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  const home = name === "home";
  if ($("landing")) $("landing").hidden = !home;
  document.querySelector("main").hidden = home;
  TABS.forEach((t) => ($(t).hidden = t !== name));
  if (name !== "messages") stopChatPolling(); // stop checking for new messages off the tab
  if (home) window.scrollTo(0, 0);
}

document.querySelectorAll(".tab").forEach((btn) =>
  btn.addEventListener("click", () => {
    if (btn.dataset.tab === "profile") return openProfile(); // your own profile
    if (btn.dataset.tab === "following") return openFollowing();
    if (btn.dataset.tab === "leaderboard") return openLeaderboard();
    if (btn.dataset.tab === "compare") return openCompare();
    if (btn.dataset.tab === "messages") return openMessages();
    showTab(btn.dataset.tab);
  })
);

// any username (on a post, comment or prediction) opens that user's profile
document.addEventListener("click", (e) => {
  const link = e.target.closest(".user-link");
  if (link) openProfile(link.dataset.user);
});

// ---------- Auth ----------
function renderHeader() {
  $("authBtn").textContent = me ? "Log out" : "Log in";
  $("userLabel").hidden = $("repBadge").hidden = !me;
  $("notifBtn").hidden = !me; // the bell
  if (me) {
    $("userLabel").innerHTML = esc(me.username) + badgeRow(me.badges, 16);
    $("repBadge").textContent = `${me.reputation} rep`;
    setCounts(me.unread_notifications, me.unread_messages);
  } else {
    setCounts(0, 0);
    closeNotifPanel();
  }
}

// show newly unlocked achievements and check unlocks with request using refresh()
async function loadMe() {
  me = await api("/api/me").catch(() => null);
  renderHeader();
  if (me) showUnlocks(me.new_achievements);
  // the bankruptcy floor topped the balance back up
  if (me && me.top_up)
    showSuccessMessage(
      `You were topped back up to ${me.reputation} rep. Make it count!`
    );
  return me;
}

async function refresh() {
  await loadMe();

  $("profileTab").hidden = !me;
  if (!me && !$("profile").hidden) showTab("posts"); // logged out while on Profile
  $("followingTab").hidden = !me;
  if (!me && !$("following").hidden) showTab("posts"); // logged out while on Following
  $("compareTab").hidden = !me;
  $("messagesTab").hidden = !me;
  if (!me && !$("messages").hidden) showTab("posts"); // logged out while on Messages
  if (me) startSummaryPolling();
  else stopSummaryPolling();
  if (!me) compareSel = [];
  if (!me && !$("compare").hidden) showTab("posts"); // logged out while on Compare
  if (!me) {
    $("userSearch").value = "";
    $("searchResults").innerHTML = "";
    followView = "following";
    $("followView")
      .querySelectorAll("button")
      .forEach((b) =>
        b.setAttribute("aria-pressed", String(b.dataset.v === "following"))
      );
  }
  $("postForm").hidden = $("predForm").hidden = !me;
  $("postsHint").hidden = $("predHint").hidden = !!me;

  // Global/Following toggle only makes sense when logged in
  $("postView").hidden = !me;
  if (!me) {
    postView = "global";
    $("postView")
      .querySelectorAll("button")
      .forEach((b) =>
        b.setAttribute("aria-pressed", String(b.dataset.v === "global"))
      );
  }

  // Leaderboard's Following view only makes sense when logged in
  $("lbView").hidden = !me;
  if (!me) {
    lbView = "global";
    $("lbView")
      .querySelectorAll("button")
      .forEach((b) =>
        b.setAttribute("aria-pressed", String(b.dataset.v === "global"))
      );
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
  loadPosts(); // re-fetch so the "people you follow" list is up to date
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
          <div class="meta">${userLink(p.username, p.badges)} · ${when(p.created_at)}</div>        </div>
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
      <div class="comment">${userLink(c.username, c.badges)} ${esc(c.content)}
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
    const res = await api("/api/posts", "POST", {
      content: $("postBody").value
    });
    e.target.reset();
    // say what the post earned ("+5 rep") or why it didn't (daily limit, too short)
    showSuccessMessage(res.rep_note ? `Posted · ${res.rep_note}` : "Posted");
    loadPosts();
    loadMe();
  } catch (err) {
    alert(err.message);
  }
});

$("postList").addEventListener("submit", async (e) => {
  e.preventDefault();
  const postId = e.target.closest("[data-post]").dataset.post;
  const input = e.target.querySelector("input");
  try {
    const res = await api(`/api/posts/${postId}/comments`, "POST", {
      content: input.value
    });
    input.value = "";
    if (res.rep_note) showSuccessMessage(`Commented · ${res.rep_note}`);
    loadComments(postId);
    loadMe();
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
      // (refunded 'void' picks don't count: that game can be picked again)
      if (me && p.user_id === me.id && p.game_id && p.result !== "void")
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
        <p class="meta">${predView === "all" ? userLink(p.username, p.badges) + " · " : ""}${when(p.created_at)}</p>
      </div>
      <div class="pred-row">
        <span class="pick">${esc(p.prediction_text)}</span>
        <span class="wager">${wagerText(p)}</span>
        <span class="result ${esc(p.result)}">${esc(resultLabel(p.result))}</span>
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

const resultLabel = (r) => (r === "void" ? "refunded" : r);
function wagerText(p) {
  if (p.result === "void") return `${p.points} rep refunded`;
  const money =
    p.result === "correct"
      ? ` · <b class="w">+${p.points}</b>`
      : p.result === "incorrect"
        ? ` · <b class="l">−${p.points}</b>`
        : "";
  return `${p.points} rep wagered${money}`;
}

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
    btn.textContent = result.in_progress
      ? "Sync already running…"
      : `Synced (${result.predictions_settled} settled)`;
  } catch (err) {
    alert(`Couldn't sync games: ${err.message}`);
    btn.textContent = originalText;
  } finally {
    btn.disabled = false;
    setTimeout(() => (btn.textContent = originalText), 2500);
  }
});

// ---------- Profile ----------
let profileState = null;
function openProfile(username, section) {
  showTab("profile");
  loadProfile(username, section);
}

async function loadProfile(username, section) {
  const box = $("profileBody");
  box.innerHTML = '<p class="hint">Loading profile…</p>';
  achError = "";
  try {
    const path = username
      ? `/api/users/${encodeURIComponent(username)}/profile`
      : "/api/profile";
    const p = await api(path);
    // let picks = null;
    // try {
    //   picks = await api(
    //     `/api/users/${encodeURIComponent(p.username)}/predictions`
    //   );
    // } catch (_) {} // the profile still shows if the picks fail to load
    // box.innerHTML = renderProfile(p, picks);
    const name = encodeURIComponent(p.username);
    // picks and achievements are optional: the profile still shows if either fails.
    // ACHIEVEMENTS this used to load only the picks, in a try/catch. Now it loads picks and
    // achievements at the same time with Promise.all (faster than one after the other), and
    // .catch(() => null) on each keeps the old behaviour of still showing the profile.
    const [picks, ach] = await Promise.all([
      api(`/api/users/${name}/predictions`).catch(() => null),
      api(`/api/users/${name}/achievements`).catch(() => null)
    ]);
    profileState = { p, picks, ach };
    box.innerHTML = renderProfile(p, picks, ach);
    // e.g. section "achievements" scrolls to the element with id "achievements-title"
    if (section)
      $(`${section}-title`)?.scrollIntoView({
        behavior: "smooth",
        block: "start"
      });
  } catch (err) {
    profileState = null;
    box.innerHTML = `<p class="error">Couldn't load profile: ${esc(err.message)}</p>`;
  }
}

function rerenderProfile() {
  if (!profileState) return;
  const y = window.scrollY;
  const { p, picks, ach } = profileState;
  $("profileBody").innerHTML = renderProfile(p, picks, ach);
  window.scrollTo(0, y);
}

function renderProfile(p, picks, ach) {
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
  // friends (following each other) get a Message button on each other's profiles
  const messageBtn =
    me && !p.is_me && p.is_friend
      ? `<button type="button" class="btn btn-gold" data-message="${esc(p.username)}">Message</button>`
      : "";
  const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

  return `
    <article class="card profile-head">
      <div>
        <h2>${esc(p.username)}${badgeRow(p.badges, 28)}</h2>
        <div class="meta">Member since ${when(p.member_since)} · ${plural(p.followers, "follower")} · ${p.following} following</div>
      </div>
      <div class="row">${messageBtn}${followBtn}</div>
    </article>
    <div class="stats">
      ${stat(p.reputation, "Reputation", p.rep_community ? `+${p.rep_community} from posts, comments and likes` : "")}
      ${stat(accuracy, "Prediction accuracy", accuracyNote)}
      ${stat(`${s.correct}–${s.incorrect}`, "Record (W–L)", `${s.pending} pending · ${s.total} total`)}
      ${stat(`+${s.rep_gained}`, "Rep won", `−${s.rep_lost} lost on incorrect picks`)}
    </div>
    ${picks ? renderPicks(picks) : '<p class="error">Couldn\'t load predictions.</p>'}
    <section class="ach">${renderAchievements(ach, p.is_me)}</section>    <h3 class="section-title">Recent activity</h3>
    <div class="activity">${activity}</div>`;
}

// ---------- Picks (current + past predictions) ----------
function pickCard(p) {
  const kickoff = p.start_time
    ? new Date(p.start_time).toLocaleString([], {
        weekday: "short",
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit"
      })
    : "";
  let note = "";
  if (p.result === "pending") {
    note =
      p.status === "in_progress"
        ? "In progress"
        : kickoff
          ? `Starts ${kickoff}`
          : "";
  } else if (
    p.status === "final" &&
    p.home_score != null &&
    p.away_score != null
  ) {
    note = `Final: ${p.away_team} ${p.away_score} – ${p.home_team} ${p.home_score}`;
  }
  if (p.result === "void")
    note = "Refunded: the game was tied, cancelled or never finished";
  return `
    <article class="pcard ${esc(p.result)}">
      <div>
        <h4>${esc(p.game)}</h4>
        <p class="meta">${note ? esc(note) + " · " : ""}picked ${when(p.created_at)}</p>
      </div>
      <div class="pred-row">
        <span class="pick">${esc(p.prediction_text)}</span>
        <span class="wager">${wagerText(p)}</span>
        <span class="result ${esc(p.result)}">${esc(resultLabel(p.result))}</span>
      </div>
    </article>`;
}

// inPanel: small headings inside a Following-tab row; otherwise full section headings (profile)
function renderPicks(picks, inPanel = false) {
  const head = (t) =>
    inPanel
      ? `<h4 class="picks-title">${t}</h4>`
      : `<h3 class="section-title">${t}</h3>`;
  const list = (items, empty) =>
    items.length
      ? items.map(pickCard).join("")
      : `<p class="hint">${empty}</p>`;
  const pastCount = picks.past.length + (picks.past.length >= 50 ? "+" : "");
  return `
    ${head(`Current picks (${picks.current.length})`)}
    ${list(picks.current, "No open picks right now.")}
    ${head(`Past picks (${pastCount})`)}
    ${list(picks.past, "No settled picks yet.")}`;
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
           <span>${a.result === "void" ? `${a.points} rep refunded` : `${a.points} rep wagered`}</span>
           <span class="result ${esc(a.result)}">${esc(resultLabel(a.result))}</span>
         </div>`
      : `<p class="post-text">${esc(a.body)}</p>`;
  return `
    <div class="activity-item">
            <div class="meta"><span class="kind kind-${esc(a.type)}">${label}</span> ${a.username ? userLink(a.username, a.badges) + " · " : ""}${when(a.created_at)}</div>
      ${body}
    </div>`;
}

// ---------- Following ----------
function openFollowing() {
  showTab("following");
  loadFollowing();
}

let followView = "following"; // "following" or "followers"

$("followView").addEventListener("click", (e) => {
  const b = e.target.closest("[data-v]");
  if (!b || !me) return;
  followView = b.dataset.v;
  $("followView")
    .querySelectorAll("button")
    .forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
  loadFollowing();
});

async function loadFollowing() {
  const box = $("followingBody");
  const view = followView;
  box.innerHTML = '<p class="hint">Loading…</p>';
  try {
    let html;
    if (view === "followers") {
      html = renderFollowers(await api("/api/followers"));
    } else {
      const [people, feed] = await Promise.all([
        api("/api/following"),
        api("/api/following/feed")
      ]);
      html = renderFollowing(people, feed);
    }
    if (view !== followView) return; // the toggle changed while loading
    box.innerHTML = html;
  } catch (err) {
    box.innerHTML = `<p class="error">Couldn't load ${view}: ${esc(err.message)}</p>`;
  }
}

// one person in the Following / Followers list, with a Picks button that opens their predictions
function personRow(u, note, isFollowing) {
  return `
    <div class="follow-item">
      <div class="follow-row">
        <span class="avatar" aria-hidden="true">${initial(u.username)}</span>
        <div class="follow-who">
          ${userLink(u.username, u.badges)}
          <span class="meta">${u.reputation} rep · ${note}</span>
        </div>
        <div class="follow-actions">
          <button type="button" class="btn btn-outline" data-picks="${esc(u.username)}" aria-expanded="false">Picks</button>
          <button type="button" class="btn ${isFollowing ? "btn-outline" : ""}"
            data-follow="${esc(u.username)}" data-following="${isFollowing ? 1 : 0}" data-where="list">${isFollowing ? "Unfollow" : "Follow back"}</button>
        </div>
      </div>
      <div class="picks-panel" hidden></div>
    </div>`;
}

function renderFollowing(people, feed) {
  if (!people.length)
    return `
      <h3 class="section-title">Following (0)</h3>
      <p class="hint">You're not following anyone yet. Click a username on a post or prediction to open their profile and follow them.</p>`;

  const rows = people
    .map((u) => personRow(u, `following since ${when(u.followed_at)}`, true))
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

function renderFollowers(people) {
  if (!people.length)
    return `
      <h3 class="section-title">Followers (0)</h3>
      <p class="hint">Nobody follows you yet.</p>`;
  const rows = people
    .map((u) =>
      personRow(u, `followed you ${when(u.followed_at)}`, u.is_following)
    )
    .join("");
  return `
    <h3 class="section-title">Followers (${people.length})</h3>
    <div class="follow-list">${rows}</div>`;
}

// "Picks" button: show or hide that person's current and past predictions under their row
document.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-picks]");
  if (!btn) return;
  const item = btn.closest(".follow-item");
  const panel = item.querySelector(".picks-panel");
  const open = btn.getAttribute("aria-expanded") !== "true";
  btn.setAttribute("aria-expanded", String(open));
  item.classList.toggle("open", open);
  panel.hidden = !open;
  if (!open || panel.dataset.loaded) return;
  panel.innerHTML = '<p class="hint">Loading picks…</p>';
  try {
    const picks = await api(
      `/api/users/${encodeURIComponent(btn.dataset.picks)}/predictions`
    );
    panel.innerHTML = renderPicks(picks, true);
    panel.dataset.loaded = "1";
  } catch (err) {
    panel.innerHTML = `<p class="error">Couldn't load picks: ${esc(err.message)}</p>`;
  }
});

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
    loadMe();
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

$("lbSort").addEventListener("click", (e) => {
  const b = e.target.closest("[data-s]");
  if (!b) return;
  lbSort = b.dataset.s;
  $("lbSort")
    .querySelectorAll("button")
    .forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
  loadLeaderboard();
});

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
      // rows = following.map((u) => ({
      //   username: u.username,
      //   reputation: u.reputation
      // }));
      // ACHIEVEMENTS carry the score and badges along too (the server attaches them to
      // /api/following, and to /api/me for your own row) so this view can rank by either
      rows = following.map((u) => ({
        username: u.username,
        reputation: u.reputation,
        achievement_score: u.achievement_score,
        badges: u.badges
      }));
      rows.push({
        username: me.username,
        reputation: me.reputation,
        achievement_score: me.achievement_score,
        badges: me.badges
      });
      // rows.push({ username: me.username, reputation: me.reputation });
    } else {
      rows = await api(`/api/leaderboard?sort=${lbSort}`);
    }
    // rows.sort((a, b) => b.reputation - a.reputation);
    // sort by the chosen number, and use the other one to break ties.
    const [k1, k2] =
      lbSort === "achievements"
        ? ["achievement_score", "reputation"]
        : ["reputation", "achievement_score"];
    rows.sort((a, b) => b[k1] - a[k1] || b[k2] - a[k2]);
    rows.forEach((r, i) => {
      r.rank = i > 0 && rows[i - 1][k1] === r[k1] ? rows[i - 1].rank : i + 1;
    });
    renderLeaderboard(rows);
  } catch (err) {
    list.innerHTML = `<p class="error">Couldn't load leaderboard: ${esc(err.message)}</p>`;
  }
}

// each row shows badges after the name, the ranking number in the box on the right, and the other number is small grey

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
      <span class="lb-rank">${u.rank ?? i + 1}</span>
      <span class="avatar" aria-hidden="true">${initial(u.username)}</span>
      <span class="lb-who">${userLink(u.username, u.badges)}</span>
      ${
        lbSort === "achievements"
          ? `<span class="lb-sub">${fmtNum(u.reputation)} rep</span><span class="badge badge-ach">${fmtNum(u.achievement_score)} pts</span>`
          : `<span class="lb-sub">${fmtNum(u.achievement_score)} pts</span><span class="badge">${u.reputation} rep</span>`
      }
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
          ${userLink(u.username, u.badges)}
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

// ---------- Compare ----------
const MAX_COMPARE = 5;
let compareSel = []; // usernames picked to compare with (kept while the page is open)
let comparePeople = []; // everyone you follow, for the picker

async function openCompare() {
  showTab("compare");
  try {
    comparePeople = await api("/api/following");
    // forget anyone you no longer follow
    compareSel = compareSel.filter((n) =>
      comparePeople.some((u) => u.username === n)
    );
    renderComparePicker();
  } catch (err) {
    $("comparePicker").innerHTML =
      `<p class="error">Couldn't load your friends: ${esc(err.message)}</p>`;
  }
  loadCompare();
}

function renderComparePicker() {
  const picker = $("comparePicker");
  if (!comparePeople.length) {
    picker.innerHTML =
      '<p class="hint">Follow some people on the Following tab first, then pick them here to compare.</p>';
    return;
  }
  const full = compareSel.length >= MAX_COMPARE;
  picker.innerHTML = comparePeople
    .map((u) => {
      const on = compareSel.includes(u.username);
      return `
      <button type="button" class="cmp-pick" data-compare="${esc(u.username)}" aria-pressed="${on}" ${full && !on ? "disabled" : ""}>
        <span class="avatar" aria-hidden="true">${initial(u.username)}</span>
        <span>${esc(u.username)}</span>
      </button>`;
    })
    .join("");
}

$("comparePicker").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-compare]");
  if (!btn || btn.disabled) return;
  const name = btn.dataset.compare;
  compareSel = compareSel.includes(name)
    ? compareSel.filter((n) => n !== name)
    : [...compareSel, name].slice(0, MAX_COMPARE);
  renderComparePicker();
  // the buttons were redrawn, so give keyboard focus back to the one that was used
  [...$("comparePicker").querySelectorAll("[data-compare]")]
    .find((x) => x.dataset.compare === name)
    ?.focus();
  loadCompare();
});

async function loadCompare() {
  const box = $("compareBody");
  const key = compareSel.join(",");
  try {
    const rows = await api(`/api/compare?users=${encodeURIComponent(key)}`);
    if (key !== compareSel.join(",")) return; // the picks changed while loading
    box.innerHTML = renderCompare(rows);
  } catch (err) {
    box.innerHTML = `<p class="error">Couldn't load comparison: ${esc(err.message)}</p>`;
  }
}

function renderCompare(rows) {
  const pct = (v) => (v === null ? "—" : `${+v.toFixed(1)}%`);

  // the best value in a row gets highlighted, but only when the values actually differ
  const best = (key) => {
    const vals = rows.map((r) => r[key]).filter((v) => v !== null);
    return new Set(vals).size > 1 ? Math.max(...vals) : null;
  };
  const top = {
    reputation: best("reputation"),
    accuracy: best("accuracy"),
    achievement_score: best("achievement_score")
  };

  const row = (label, show, key) => `
    <tr>
      <th scope="row">${label}</th>
      ${rows
        .map(
          (r) =>
            `<td class="${r.is_me ? "me-col" : ""} ${key && top[key] !== null && r[key] === top[key] ? "best" : ""}">${show(r)}</td>`
        )
        .join("")}
    </tr>`;

  const winLoss = (r) =>
    r.settled
      ? `<div class="wl" aria-hidden="true">
           <span class="wl-win" style="width:${Number(r.win_pct)}%"></span>
           <span class="wl-loss" style="width:${Number(r.loss_pct)}%"></span>
         </div>
         ${pct(r.win_pct)} W · ${pct(r.loss_pct)} L`
      : "—";

  const head = rows
    .map(
      (r) =>
        `<th scope="col" class="${r.is_me ? "me-col" : ""}">
           <div class="cmp-user">
             <span class="avatar" aria-hidden="true">${initial(r.username)}</span>
             ${r.is_me ? "You" + badgeRow(r.badges) : userLink(r.username, r.badges)}
           </div>
         </th>`
    )
    .join("");

  return `
    <div class="cmp-wrap">
      <table class="cmp">
        <thead><tr><th scope="col" class="cmp-corner">Stats</th>${head}</tr></thead>
        <tbody>
          ${row("Reputation", (r) => esc(r.reputation), "reputation")}
          ${row(
            "Accuracy",
            (r) =>
              `${pct(r.accuracy)}<span class="sub">${r.correct} of ${r.settled} settled correct</span>`,
            "accuracy"
          )}
          ${row("Win / loss %", winLoss)}
          ${row("Record (W–L)", (r) => `${r.correct}–${r.incorrect}`)}
          ${row("Pending", (r) => esc(r.pending))}
          ${row("Total predictions", (r) => esc(r.total))}
          ${row("Rep won / lost", (r) => `+${r.rep_gained} / −${r.rep_lost}`)}
                    ${row("Achievement score", (r) => fmtNum(r.achievement_score ?? 0), "achievement_score")}
        </tbody>
      </table>
    </div>
    ${rows.length === 1 ? '<p class="hint">Pick friends above to see them side by side with you.</p>' : ""}`;
}

const SUMMARY_EVERY_MS = 20000;
let summaryTimer = null;
let lastUnreadMessages = 0;

function setCounts(notifs, msgs) {
  const n = $("notifCount");
  n.textContent = notifs > 99 ? "99+" : String(notifs || 0);
  n.hidden = !notifs;
  $("notifBtn").setAttribute(
    "aria-label",
    notifs ? `Notifications, ${notifs} unread` : "Notifications"
  );
  const m = $("msgCount");
  m.textContent = msgs > 99 ? "99+" : String(msgs || 0);
  m.hidden = !msgs;
  if (msgs > lastUnreadMessages && !$("messages").hidden) loadConversations();
  lastUnreadMessages = msgs || 0;
}

async function pollSummary() {
  if (!me || document.visibilityState !== "visible") return; // don't poll from a hidden tab
  try {
    const s = await api("/api/notifications/summary");
    setCounts(s.unread_notifications, s.unread_messages);
  } catch {
    /* a missed poll is fine; the next one will catch up */
  }
}

function startSummaryPolling() {
  if (!summaryTimer) summaryTimer = setInterval(pollSummary, SUMMARY_EVERY_MS);
}
function stopSummaryPolling() {
  clearInterval(summaryTimer);
  summaryTimer = null;
}
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") pollSummary();
});

function closeNotifPanel() {
  $("notifPanel").hidden = true;
  $("notifBtn").setAttribute("aria-expanded", "false");
}

async function openNotifPanel() {
  const panel = $("notifPanel");
  panel.hidden = false;
  $("notifBtn").setAttribute("aria-expanded", "true");
  $("notifList").innerHTML = '<p class="hint">Loading…</p>';
  try {
    const data = await api("/api/notifications");
    renderNotifications(data.notifications);
    setCounts(data.unread, lastUnreadMessages);
  } catch (err) {
    $("notifList").innerHTML =
      `<p class="error">Couldn't load notifications: ${esc(err.message)}</p>`;
  }
}

// "3 min ago", "2 h ago", or a date for anything older than a week
function ago(d) {
  const s = Math.max(0, (Date.now() - new Date(d).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 604800) return `${Math.floor(s / 86400)} d ago`;
  return when(d);
}

function renderNotifications(items) {
  $("notifList").innerHTML = items.length
    ? items
        .map(
          (n) => `
      <button type="button" class="notif ${n.read ? "" : "unread"}" data-notif="${n.id}" data-link="${esc(n.link || "")}">
        <span class="notif-icon">${n.code ? badgeSvg(n.code, 34, n.kind === "achievement_progress") : ""}</span>
        <span class="notif-text">
          <span class="notif-title">${esc(n.title)}</span>
          <span class="notif-body">${esc(n.body)}</span>
          <span class="notif-time">${ago(n.created_at)}</span>
        </span>
      </button>`
        )
        .join("")
    : '<p class="hint notif-empty">Nothing yet. Progress toward achievements and new unlocks show up here.</p>';
}

$("notifBtn").addEventListener("click", (e) => {
  e.stopPropagation();
  $("notifPanel").hidden ? openNotifPanel() : closeNotifPanel();
});
// clicking anywhere else, or pressing Escape, closes the panel
document.addEventListener("click", (e) => {
  if (!$("notifPanel").hidden && !e.target.closest("#notifPanel"))
    closeNotifPanel();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !$("notifPanel").hidden) {
    closeNotifPanel();
    $("notifBtn").focus();
  }
});

$("notifReadAll").addEventListener("click", async () => {
  try {
    await api("/api/notifications/read", "POST", {});
    document
      .querySelectorAll(".notif.unread")
      .forEach((n) => n.classList.remove("unread"));
    setCounts(0, lastUnreadMessages);
  } catch (err) {
    alert(err.message);
  }
});

$("notifList").addEventListener("click", async (e) => {
  const item = e.target.closest("[data-notif]");
  if (!item) return;
  closeNotifPanel();
  if (item.classList.contains("unread")) {
    api("/api/notifications/read", "POST", {
      ids: [Number(item.dataset.notif)]
    })
      .then(pollSummary)
      .catch(() => {});
  }
  if (item.dataset.link === "achievements") openProfile(null, "achievements");
});

const CHAT_EVERY_MS = 4000;
const MESSAGE_MAX = 1000;
let chatWith = null; // username of the open conversation
let chatLastId = 0;
let chatFirstId = null; // id of the oldest message shown ("Load earlier messages")
let chatTimer = null;
let chatConversations = [];

async function openMessages(username) {
  showTab("messages");
  await loadConversations();
  if (username) openChat(username);
  else if (!chatWith) renderChatEmpty();
}

async function loadConversations() {
  try {
    chatConversations = await api("/api/messages");
    renderConversations();
  } catch (err) {
    $("chatList").innerHTML =
      `<p class="error">Couldn't load conversations: ${esc(err.message)}</p>`;
  }
}

function renderConversations() {
  const box = $("chatList");
  if (!chatConversations.length) {
    box.innerHTML = `<p class="hint chat-none">No friends to message yet. You can message people who follow you back: find people on the Following tab.</p>`;
    return;
  }
  box.innerHTML = chatConversations
    .map((c) => {
      const preview = c.last_body
        ? `${c.last_from_me ? "You: " : ""}${esc(c.last_body)}`
        : '<span class="hint">Say hello</span>';
      return `
      <button type="button" class="convo ${c.username === chatWith ? "active" : ""} ${c.unread ? "has-unread" : ""}" data-chat="${esc(c.username)}">
        <span class="avatar" aria-hidden="true">${initial(c.username)}</span>
        <span class="convo-text">
          <span class="convo-name">${esc(c.username)}${badgeRow(c.badges, 14)}${c.is_friend ? "" : ' <span class="convo-tag">not friends</span>'}</span>
          <span class="convo-preview">${preview}</span>
        </span>
        <span class="convo-side">
          ${c.last_at ? `<span class="convo-time">${ago(c.last_at)}</span>` : ""}
          ${c.unread ? `<span class="convo-unread" aria-label="${c.unread} unread">${c.unread}</span>` : ""}
        </span>
      </button>`;
    })
    .join("");
}

function renderChatEmpty() {
  $("chat").classList.remove("open");
  $("chatMain").innerHTML =
    `<div class="chat-empty"><p>Pick a friend to start chatting.</p><p class="hint">Friends are people who follow you and whom you follow back.</p></div>`;
}

$("chatList").addEventListener("click", (e) => {
  const b = e.target.closest("[data-chat]");
  if (b) openChat(b.dataset.chat);
});

// any "Message" button (on a friend's profile) opens that conversation
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-message]");
  if (b) openMessages(b.dataset.message);
});

function messageHtml(m) {
  const t = new Date(m.created_at);
  return `
    <div class="msg ${m.from_me ? "mine" : "theirs"}" data-id="${m.id}">
      <div class="msg-bubble">${esc(m.body)}</div>
      <div class="msg-time" title="${esc(t.toLocaleString())}">${t.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</div>
    </div>`;
}

async function openChat(username) {
  chatWith = username;
  chatLastId = 0;
  chatFirstId = null;
  stopChatPolling();
  $("chat").classList.add("open"); // on phones: show the conversation instead of the list
  renderConversations();
  const main = $("chatMain");
  main.innerHTML = '<p class="hint chat-loading">Loading…</p>';
  try {
    const data = await api(`/api/messages/${encodeURIComponent(username)}`);
    if (chatWith !== username) return; // another conversation was opened meanwhile
    main.innerHTML = `
      <div class="chat-head">
        <button type="button" class="btn btn-link chat-back" id="chatBack" aria-label="Back to conversations">‹ Back</button>
        <span class="avatar" aria-hidden="true">${initial(username)}</span>
        ${userLink(username)}
      </div>
      <div class="chat-msgs" id="chatMsgs" aria-live="polite">
        ${data.has_more ? '<button type="button" class="btn btn-link chat-more" id="chatMore">Load earlier messages</button>' : ""}
        ${data.messages.length ? data.messages.map(messageHtml).join("") : '<p class="hint chat-start">No messages yet. Say hello!</p>'}
      </div>
      ${
        data.can_send
          ? `<form class="chat-form" id="chatForm">
               <textarea id="chatInput" rows="1" maxlength="${MESSAGE_MAX}" placeholder="Message ${esc(username)}" aria-label="Message"></textarea>
               <button class="btn" id="chatSend">Send</button>
               <span class="chat-count" id="chatCount" hidden></span>
             </form>
             <p class="error chat-error" id="chatError" role="alert" hidden></p>`
          : `<p class="hint chat-locked">You can message each other again when you both follow each other.</p>`
      }`;
    if (data.messages.length) {
      chatFirstId = data.messages[0].id;
      chatLastId = data.messages[data.messages.length - 1].id;
    }
    scrollChatToEnd();
    $("chatInput")?.focus();
    startChatPolling();
    pollSummary();
    loadConversations();
  } catch (err) {
    main.innerHTML = `<p class="error">${esc(err.message)}</p>`;
  }
}

function scrollChatToEnd() {
  const box = $("chatMsgs");
  if (box) box.scrollTop = box.scrollHeight;
}

function appendMessages(list) {
  const box = $("chatMsgs");
  if (!box || !list.length) return;
  box.querySelector(".chat-start")?.remove();
  const atEnd = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
  for (const m of list) {
    if (box.querySelector(`[data-id="${m.id}"]`)) continue; // already shown
    box.insertAdjacentHTML("beforeend", messageHtml(m));
    chatLastId = Math.max(chatLastId, m.id);
    if (chatFirstId === null) chatFirstId = m.id;
  }
  if (atEnd || list.some((m) => m.from_me)) scrollChatToEnd();
}

async function pollChat() {
  if (!chatWith || document.visibilityState !== "visible") return;
  const who = chatWith;
  try {
    const data = await api(
      `/api/messages/${encodeURIComponent(who)}?after=${chatLastId}`
    );
    if (who === chatWith && data.messages.length) {
      appendMessages(data.messages);
      loadConversations();
    }
  } catch {
    /* try again next time */
  }
}

function startChatPolling() {
  stopChatPolling();
  chatTimer = setInterval(pollChat, CHAT_EVERY_MS);
}
function stopChatPolling() {
  clearInterval(chatTimer);
  chatTimer = null;
}

async function sendChat() {
  const input = $("chatInput");
  const body = input.value.trim();
  if (!body) return;
  const err = $("chatError");
  err.hidden = true;
  $("chatSend").disabled = true;
  try {
    const res = await api(
      `/api/messages/${encodeURIComponent(chatWith)}`,
      "POST",
      { body }
    );
    input.value = "";
    autosize(input);
    updateChatCount();
    appendMessages([res.sent]);
    loadConversations();
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  } finally {
    $("chatSend").disabled = false;
    input.focus();
  }
}

// the message box grows with its text up to a few lines
function autosize(t) {
  t.style.height = "auto";
  t.style.height = Math.min(t.scrollHeight, 140) + "px";
}
function updateChatCount() {
  const left = MESSAGE_MAX - $("chatInput").value.length;
  const c = $("chatCount");
  c.hidden = left > 100;
  c.textContent = `${left} left`;
}

$("chatMain").addEventListener("submit", (e) => {
  e.preventDefault();
  sendChat();
});
// enter sends, Shift+Enter starts a new line
$("chatMain").addEventListener("keydown", (e) => {
  if (e.target.id === "chatInput" && e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendChat();
  }
});
$("chatMain").addEventListener("input", (e) => {
  if (e.target.id !== "chatInput") return;
  autosize(e.target);
  updateChatCount();
});
$("chatMain").addEventListener("click", async (e) => {
  if (e.target.closest("#chatBack")) {
    chatWith = null;
    stopChatPolling();
    renderConversations();
    renderChatEmpty();
    return;
  }
  if (e.target.closest("#chatMore") && chatFirstId) {
    const box = $("chatMsgs");
    const before = box.scrollHeight;
    try {
      const data = await api(
        `/api/messages/${encodeURIComponent(chatWith)}?before=${chatFirstId}`
      );
      $("chatMore").remove();
      const html = data.messages.map(messageHtml).join("");
      box.insertAdjacentHTML(
        "afterbegin",
        (data.has_more
          ? '<button type="button" class="btn btn-link chat-more" id="chatMore">Load earlier messages</button>'
          : "") + html
      );
      if (data.messages.length) chatFirstId = data.messages[0].id;
      box.scrollTop = box.scrollHeight - before; // keep the reader's place
    } catch (err) {
      alert(err.message);
    }
  }
});
loadCatalog().finally(refresh);
