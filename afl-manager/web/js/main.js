// App shell: start-up, club selection, navigation, the Continue button and settings.
import * as E from "./engine.js";
import { esc, money, ordinal, club, plural, badge, icon, posTags, ovr, toast, dialog, closeDialog, busy, nextFrame,
         applyClubTheme, setSort, panel, seg, table } from "./ui.js";
import { SCREENS, ACTIONS, S } from "./screens.js";
import "./match.js";

const app = document.getElementById("app");
const NAV = [
  ["", [["home", "Home"], ["inbox", "Inbox"]]],
  ["Team", [["squad", "Squad"], ["team", "Team sheet"], ["plan", "Game plan"]]],
  ["Match", [["match", "Match centre"], ["fixtures", "Fixtures & results"]]],
  ["Competition", [["ladder", "Ladder"], ["stats", "Player stats"], ["clubs", "Clubs"]]],
  ["List", [["contracts", "Contracts"], ["trade", "Trades"], ["draft", "Draft"], ["agents", "Free agents"]]],
  ["Club", [["club", "Board & finances"], ["settings", "Settings"]]],
];
const TABS = [["home", "Home"], ["squad", "Squad"], ["team", "Team"], ["match", "Match"]];
let route = { name: "home", arg: null }, data = null, cleanup = null, engineVersion = "";

// ---- theme ---------------------------------------------------------------------------
function getPref(key, fallback) { try { return localStorage.getItem(key) || fallback; } catch { return fallback; } }
function setPref(key, value) { try { localStorage.setItem(key, value); } catch { /* private window */ } }
function applyTheme() {
  const t = getPref("aflm-theme", "system");
  if (t === "system") delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = t;
  applyClubTheme(E.header && E.header.club);
}
matchMedia("(prefers-color-scheme: light)").addEventListener("change", applyTheme);

// ---- start-up ------------------------------------------------------------------------
function splash(text, pct) {
  app.innerHTML = `<div class="splash"><div class="splash-card"><div class="wordmark">AFL Manager<small>Coach · List · Legacy</small></div>
    <div class="loadbar"><i style="width:${pct}%"></i></div><div class="muted">${esc(text)}</div></div></div>`;
}

async function boot() {
  applyTheme();
  splash("Warming up the engine", 8);
  try {
    engineVersion = await E.startEngine(splash);
  } catch (e) {
    console.error(e);
    app.innerHTML = `<div class="splash"><div class="splash-card"><div class="wordmark">AFL Manager</div>
      <p class="bad" style="margin-top:24px"><b>The game engine could not start.</b></p>
      <p class="muted">${esc(e.message || e)}<br>The first launch needs an internet connection to download the Python runtime (roughly 6 MB). Check your connection and reload.</p>
      <button class="btn primary" onclick="location.reload()">Try again</button></div></div>`;
    return;
  }
  const saved = await E.store.get("career");
  if (saved) {
    try { E.call("load", { bundle: saved }); } catch (e) { console.error(e); toast("Your saved career could not be opened: " + e.message, "err"); }
  }
  enter();
}

function enter() {
  const h = E.header;
  applyTheme();
  if (!h) return startScreen();
  if (!h.has_club || h.sacked) return chooseScreen();
  buildShell();
  if (!location.hash || location.hash === "#") location.replace("#home");
  onRoute();
}

function startScreen() {
  app.innerHTML = `<div class="splash"><div class="splash-card"><div class="wordmark">AFL Manager<small>Coach · List · Legacy</small></div>
    <p class="muted" style="margin-top:22px">Take charge of one of eighteen clubs. Pick the side, set the game plan, work the trade table and the draft, and chase a flag over as many seasons as you like.</p>
    <div class="start-actions"><button class="btn primary" data-act="newCareer">${icon("play")} Start a new career</button>
      <button class="btn" data-act="importSave">Load a save file</button>
      <label class="muted" style="font-size:12.5px">World seed (optional: the same number always builds the same competition)
        <input type="text" id="seed" inputmode="numeric" placeholder="random" style="width:110px;margin-left:8px" aria-label="World seed"></label></div>
    <p class="faint" style="margin-top:22px">Unofficial fan project. Every player is fictional and each new world deals the talent differently.<br>Your career is saved in this browser.</p></div></div>`;
}

async function newCareer() {
  const seedBox = document.getElementById("seed");
  const seed = seedBox ? parseInt(seedBox.value, 10) || null : null;
  busy("Building the competition");
  await nextFrame();
  try { E.call("new", { seed }); } catch (e) { busy(); return toast(e.message, "err"); }
  busy();
  E.scheduleSave(0);
  S.choose.club = null;
  chooseScreen();
}

function chooseScreen() {
  const d = E.call("clubs"), offers = d.offers;
  const rows = d.clubs.filter(r => !offers || offers.includes(r.ID));
  const sel = S.choose.club;
  const card = r => { const c = club(r.ID); return `<button class="clubcard ${sel === r.ID ? "on" : ""}" data-act="chooseClub" data-v="${r.ID}">
      <div class="row">${badge(r.ID, 46)}<div class="grow"><h3>${esc(c.full)}</h3><span class="muted">${esc(c.ground)} · ${c.state}</span></div><span class="tag" title="List strength rank">#${r.Rank}</span></div>
      <div class="stats"><div><small>Best 22</small><b>${r["Best 22"]}</b></div><div><small>Avg age</small><b>${r["Avg age"]}</b></div><div><small>Kids</small><b>${r["Young talent"]}</b></div>
        <div><small>Cap room</small><b>${money(r["Cap room"])}</b></div><div><small>Members</small><b>${r["Members (k)"]}k</b></div><div><small>Dev / Scout</small><b>${r.Dev} / ${r.Scout}</b></div></div>
      <div class="muted">Board expects: ${esc(r["Board expects"])}<br>Plays: ${esc(r["Game plan"])}</div></button>`; };
  app.innerHTML = `<div class="page"><div class="wordmark" style="font-size:44px">${offers ? "Find a new club" : "Choose your club"}</div>
    <p class="muted" style="max-width:70ch">${offers ? "The board has moved you on. These clubs are prepared to give you another go."
      : "Clubs are ranked by list strength. Take a contender and chase the flag now, or take a battler with good kids and build it through the draft. Kids = average potential of the five best players 21 and under."}</p>
    <div class="clubgrid">${rows.map(card).join("")}</div></div>
    <div class="sticky-cta"><input type="text" id="coach-name" placeholder="Your name (optional)" value="${esc((E.header && E.header.manager) || "")}" aria-label="Your name" style="width:min(260px,60vw)">
      <button class="btn primary" data-act="takeJob" ${sel ? "" : "disabled"}>${sel ? `Coach ${esc(club(sel).name)}` : "Pick a club"}</button></div>`;
  applyClubTheme(sel);
}
ACTIONS.newCareer = () => newCareer();
ACTIONS.chooseClub = el => { S.choose.club = el.dataset.v; const y = scrollY; chooseScreen(); scrollTo(0, y); };
ACTIONS.takeJob = () => {
  const name = (document.getElementById("coach-name").value || "").trim();
  try { E.call("choose", { club: S.choose.club, name }); } catch (e) { return toast(e.message, "err"); }
  E.scheduleSave(0);
  location.hash = "#home";
  enter();
};

// ---- shell -----------------------------------------------------------------------------
function buildShell() {
  app.innerHTML = `<div class="shell"><aside class="rail" id="rail"></aside>
    <div class="main"><header class="top" id="top"></header><main class="view" id="view" tabindex="-1"></main></div>
    <nav class="tabbar" id="tabbar"></nav></div>`;
}

function paintChrome() {
  const h = E.header, c = club(h.club), def = SCREENS[route.name] || SCREENS.home;
  applyClubTheme(h.club);
  document.title = `${c.name} · AFL Manager`;
  const pips = { contracts: h.phase === "contracts" ? h.unsigned : 0, draft: h.on_clock ? "!" : 0 };
  document.getElementById("rail").innerHTML = `<div class="rail-club">${badge(h.club, 44)}<div><b>${esc(c.full)}</b><span>${esc(h.manager || "Senior coach")}</span></div></div>
    <nav class="nav">${NAV.map(([group, items]) => `${group ? `<h4>${group}</h4>` : ""}${items.map(([r, label]) =>
      `<a data-nav="${r}" class="${route.name === r ? "on" : ""}">${icon(r)}<span>${label}</span>${pips[r] ? `<span class="pip">${pips[r]}</span>` : ""}</a>`).join("")}`).join("")}</nav>`;
  const active = document.activeElement && document.activeElement.id === "q";
  const top = document.getElementById("top");
  const crumb = `${h.year} · ${esc(h.phase_label)}`;
  if (!top.firstChild) {
    top.innerHTML = `<div><h1 id="title"></h1><div class="crumb" id="crumb"></div></div>
      <div class="search">${icon("search")}<input id="q" type="text" placeholder="Search players and clubs" autocomplete="off" aria-label="Search"><div class="search-results" id="results" hidden></div></div>
      <div class="kpis" id="kpis"></div><div class="continue" id="cont"></div>`;
  }
  top.querySelector("#title").textContent = route.name === "player" && data ? data.p.name : def.title;
  top.querySelector("#crumb").innerHTML = crumb;
  top.querySelector("#kpis").innerHTML = `<div class="kpi"><small>Ladder</small><b>${ordinal(h.pos)} <span class="muted" style="font-size:14px">${h.record}</span></b></div>
    <div class="kpi"><small>Cap room</small><b>${money(h.cap - h.payroll)}</b></div>
    <div class="kpi"><small>Board</small><b class="${h.confidence < 30 ? "bad" : ""}">${h.confidence}</b></div>`;
  const multi = h.phase === "season";
  top.querySelector("#cont").className = "continue" + (multi ? "" : " solo");
  top.querySelector("#cont").innerHTML = `<button class="btn primary" data-act="continue">${icon("play")} ${esc(h.cont)}</button>
    ${multi ? `<button class="btn primary" data-act="contMenu" aria-label="More ways to advance">${icon("down")}</button>` : ""}`;
  document.getElementById("tabbar").innerHTML = TABS.map(([r, label]) => `<a data-nav="${r}" class="${route.name === r ? "on" : ""}">${icon(r)}${label}</a>`).join("")
    + `<a data-act="openRail">${icon("more")}More</a>`;
  if (active) document.getElementById("q").focus();
}

// ---- routing ---------------------------------------------------------------------------
const ctx = {
  get data() { return data; }, get route() { return route; },
  go(r) { if (location.hash === "#" + r) onRoute(); else location.hash = "#" + r; },
  repaint() { paint(true); },
  refresh() { load(); paint(true); },
  // run an engine request; mutate=true also autosaves
  call(op, args = {}, mutate = false) { const r = E.call(op, args); if (mutate) E.scheduleSave(); return r; },
  // run a text command through the rules; returns true (or its text) on success, false on error
  act(cmd, msg, wantText) {
    try {
      const r = E.call("act", { cmd });
      E.scheduleSave();
      const first = r.text.split("\n")[0].replace(/^=+\s*|\s*=+$/g, "");
      const note = msg === null ? "" : msg || (first.length < 170 ? first : "Done.");
      if (note) toast(note);
      if (document.getElementById("view")) ctx.refresh();
      return wantText ? r.text : true;
    } catch (e) { toast(e.message, "err"); return false; }
  },
};

function load() {
  const def = SCREENS[route.name] || SCREENS.home;
  try { data = def.load ? def.load(route.arg) : {}; }
  catch (e) { console.error(e); data = null; toast(e.message, "err"); }
}

function paint(keepScroll = false) {
  const view = document.getElementById("view");
  if (!view) return;
  const def = SCREENS[route.name] || SCREENS.home, y = view.scrollTop;
  if (cleanup) { cleanup(); cleanup = null; }
  paintChrome();
  try { view.innerHTML = data ? def.view(data, route.arg) : `<p class="muted">That screen could not be opened. <a data-nav="home">Back to home</a></p>`; }
  catch (e) { console.error(e); view.innerHTML = `<p class="bad">Something went wrong drawing this screen.</p><p class="muted">${esc(e.message)}</p>`; }
  if (def.after && data) cleanup = def.after(view, data);
  view.scrollTop = keepScroll ? y : 0;
}

function onRoute() {
  if (!document.getElementById("view")) return;
  const [name, ...rest] = (location.hash.replace(/^#\/?/, "") || "home").split("/");
  route = { name: SCREENS[name] ? name : "home", arg: rest.join("/") || null };
  document.getElementById("rail").classList.remove("open");
  closeMenus();
  load();
  paint();
}
addEventListener("hashchange", onRoute);

// ---- continue: the heartbeat of the game ---------------------------------------------------
async function advance(confirm = false) {
  const h = E.header;
  if (h.sacked) return enter();
  if (h.phase === "draft" && h.on_clock && !confirm) {
    return dialog({ title: "You are on the clock", body: `<p>Start the season now and your recruiters make the rest of your picks, or go back and choose yourself.</p>`,
      actions: [{ label: "Go to the draft", run: () => ctx.go("draft") }, { label: "Auto-draft and start the season", primary: true, run: () => { advance(true); } }] });
  }
  busy(h.phase === "draft" ? "Rolling into the new season" : h.cont);
  await nextFrame();
  let step;
  try { step = E.call("advance", { confirm }); } catch (e) { busy(); return toast(e.message, "err"); }
  busy();
  E.scheduleSave(0);
  if (E.header.sacked) {
    dialog({ title: "The board has spoken", body: `<p>After a season well short of expectations, the board has terminated your contract.</p>`, actions: [{ label: "Look for a new club", primary: true, run: () => enter() }] });
  }
  switch (step.kind) {
    case "round": case "finals":
      S.match.wrap = step; S.match.tab = "summary";
      if (step.notes.length) toast("Late changes: " + step.notes.join("; "), "info");
      if (step.match) { S.match.live = step.match; ctx.go("match/" + step.match); }
      else { S.fix.tab = step.kind === "finals" ? "finals" : "round"; S.fix.round = null; ctx.go("fixtures"); toast(`${step.label} played.`); }
      if (step.finals_set) toast("The home-and-away season is over. The top eight is set.", "info");
      break;
    case "contracts_open": toast("Contract talks are open."); ctx.go("contracts"); break;
    case "unsigned":
      dialog({ title: "Unsigned players will leave", body: `<p>These players are out of contract. End the signing period now and they walk:</p>
        ${step.players.map(p => `<div class="row" style="padding:4px 0">${posTags(p.pos.slice(0, 1))}<span class="grow">${esc(p.name)} <span class="faint">${p.age}</span></span>${ovr(p.ovr)}</div>`).join("")}`,
        actions: [{ label: "Back to contracts", run: () => ctx.go("contracts") }, { label: "Let them go", danger: true, run: () => { advance(true); } }] });
      break;
    case "trades_open": toast(step.lost.length ? `Gone: ${step.lost.join(", ")}. The trade period is open.` : "The trade period is open."); ctx.go("trade"); break;
    case "draft_open":
      ctx.go("draft");
      if (step.trades.length) dialog({ title: "Trade period wrap", body: step.trades.map(t => `<p>${esc(t.replace(/^TRADE: /, ""))}</p>`).join("") });
      break;
    case "new_season":
      ctx.go("home");
      dialog({ title: `Welcome to ${step.year}`, body: `${step.draftees.length ? `<p><b>Your draftees:</b> ${step.draftees.map(x => `#${x.n} ${esc(x.name)} (${x.pos})`).join(", ")}</p>` : ""}
        ${step.filled.length ? `<p><b>Signed to fill the list:</b> ${step.filled.map(esc).join(", ")}</p>` : ""}
        ${step.notes.length ? `<p><b>Pre-season whispers</b></p>${step.notes.map(n => `<p class="muted" style="margin:4px 0">${esc(n)}</p>`).join("")}` : `<p class="muted">A quiet summer on the track.</p>`}`,
        actions: [{ label: "Let's go", primary: true }] });
      break;
  }
}

async function simMany(target) {
  closeMenus();
  let played = 0, w = 0, l = 0;
  const start = E.header.round, me = E.header.club;
  while (E.header.phase === "season" && (target === "finals" || played < target)) {
    busy(`Playing Round ${E.header.round}`);
    await nextFrame();
    let step;
    try { step = E.call("advance", {}); } catch (e) { busy(); return toast(e.message, "err"); }
    const m = step.matches.find(x => x.home === me || x.away === me);
    if (m) { const mine = m.home === me ? m.hs[2] : m.as[2], theirs = m.home === me ? m.as[2] : m.hs[2]; if (mine > theirs) w++; else if (mine < theirs) l++; }
    played++;
  }
  busy();
  E.scheduleSave(0);
  toast(`Rounds ${start}-${start + played - 1} played: ${w} won, ${l} lost.`, "info");
  S.fix.tab = "club";
  ctx.go("fixtures");
}

function closeMenus() { document.querySelectorAll(".menu").forEach(m => m.remove()); }
ACTIONS.continue = () => advance();
ACTIONS.contMenu = () => {
  if (document.querySelector(".menu")) return closeMenus();
  const m = document.createElement("div");
  m.className = "menu";
  m.innerHTML = `<button data-act="sim" data-v="3">Play the next 3 rounds</button><button data-act="sim" data-v="5">Play the next 5 rounds</button><button data-act="sim" data-v="finals">Play to the end of the home-and-away season</button>`;
  document.querySelector(".main").appendChild(m);
};
ACTIONS.sim = el => simMany(el.dataset.v === "finals" ? "finals" : +el.dataset.v);
ACTIONS.openRail = () => document.getElementById("rail").classList.toggle("open");

// ---- settings ----------------------------------------------------------------------------
SCREENS.settings = {
  title: "Settings",
  load: () => ({}),
  view() {
    const h = E.header, at = E.lastSavedAt();
    return `<div class="grid">
      ${panel("Appearance", `<div class="col"><div class="row wrap"><span class="grow">Theme</span>${seg("theme", [["system", "System"], ["dark", "Dark"], ["light", "Light"]], getPref("aflm-theme", "system"))}</div>
        <p class="muted" style="margin:0">The accent colour follows the club you coach.</p></div>`, { cls: "s6" })}
      ${panel("Selection", `<div class="col"><div class="row wrap"><span class="grow">Who names the team each week?</span>${seg("selMode", [["auto", "Assistant"], ["manual", "Me"]], h.selection)}</div>
        <p class="muted" style="margin:0">With the assistant, the best fit 23 is named every week. Naming a player yourself switches this to you.</p></div>`, { cls: "s6" })}
      ${panel("Your career", `<dl class="kv"><dt>Coach</dt><dd>${esc(h.manager || "-")}</dd><dt>Club</dt><dd>${esc(club(h.club).full)}</dd><dt>Season</dt><dd>${h.year}</dd><dt>World seed</dt><dd>${h.seed}</dd>
          <dt>Saved in this browser</dt><dd>${at ? at.toLocaleTimeString() : "after your next move"}</dd></dl>
        <div class="row wrap" style="margin-top:14px"><button class="btn" data-act="exportSave">Download save file</button><button class="btn" data-act="importSave">Load a save file</button>
          <button class="btn danger right" data-act="resetCareer">Start a new career</button></div>
        <p class="muted" style="margin:12px 0 0">Careers live in this browser's storage. Download a save file now and then: it is your backup and the way to move a career to another device.</p>`, { cls: "s12" })}
      ${panel("About", `<p style="margin-top:0">AFL Manager is an unofficial fan project. Club names are used for flavour only; every player is fictional.</p>
        <p class="muted" style="margin:0">Engine build ${esc(engineVersion)} · the simulation runs entirely on your device.</p>`, { cls: "s12" })}
    </div>`;
  },
};
ACTIONS.theme = (el, c) => { setPref("aflm-theme", el.dataset.v); applyTheme(); c.repaint(); };
ACTIONS.exportSave = () => {
  const h = E.header, blob = new Blob([E.saveString()], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `afl-manager-${h.club || "career"}-${h.year}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  toast("Save file downloaded.");
};
ACTIONS.importSave = () => {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".json,application/json";
  input.onchange = async () => {
    const file = input.files[0];
    if (!file) return;
    try { E.call("load", { bundle: await file.text() }); } catch (e) { return toast(e.message, "err"); }
    await E.saveNow();
    toast("Career loaded.");
    location.hash = "#home";
    enter();
  };
  input.click();
};
ACTIONS.resetCareer = () => dialog({
  title: "Start a new career?", body: `<p>This replaces the career saved in this browser. Download a save file first if you want to keep it.</p>`,
  actions: [{ label: "Cancel" }, { label: "Download save first", run: () => { ACTIONS.exportSave(); return false; } }, { label: "Start again", danger: true, run: () => { newCareer(); } }],
});

// ---- search ------------------------------------------------------------------------------
let searchTimer = null;
function runSearch(q) {
  const box = document.getElementById("results");
  if (!box) return;
  if (q.trim().length < 2) { box.hidden = true; return; }
  let r;
  try { r = E.call("search", { q }); } catch { return; }
  box.hidden = false;
  box.innerHTML = r.clubs.map(id => `<a data-nav="squad/${id}">${badge(id, 22)} <b>${esc(club(id).full)}</b></a>`).join("")
    + r.players.map(p => `<a data-nav="player/${p.id}">${posTags(p.pos.slice(0, 1))}<span class="grow">${esc(p.name)} <span class="faint">${p.age}</span></span><span class="faint">${p.club || (p.status === "prospect" ? "draft" : "free")}</span>${ovr(p.ovr)}</a>`).join("")
    || `<div class="muted" style="padding:8px">No one by that name.</div>`;
}

// ---- event delegation ----------------------------------------------------------------------
document.addEventListener("click", e => {
  const sortEl = e.target.closest("[data-sort]");
  if (sortEl) { const [id, key] = sortEl.dataset.sort.split(":"); setSort(id, key); return ctx.repaint(); }
  const actEl = e.target.closest("[data-act]");
  if (actEl && !actEl.disabled) {
    e.preventDefault();
    e.stopPropagation();
    const fn = ACTIONS[actEl.dataset.act];
    if (fn) fn(actEl, ctx);
    if (!actEl.closest(".menu") && actEl.dataset.act !== "contMenu") closeMenus();
    return;
  }
  const navEl = e.target.closest("[data-nav]");
  if (navEl) {
    e.preventDefault();
    closeDialog();
    const box = document.getElementById("results");
    if (box) { box.hidden = true; const q = document.getElementById("q"); if (q && navEl.closest(".search-results")) q.value = ""; }
    return ctx.go(navEl.dataset.nav);
  }
  if (!e.target.closest(".search")) { const box = document.getElementById("results"); if (box) box.hidden = true; }
  if (!e.target.closest(".menu")) closeMenus();
  if (!e.target.closest(".rail") && !e.target.closest("[data-act=openRail]")) { const r = document.getElementById("rail"); if (r) r.classList.remove("open"); }
});
document.addEventListener("change", e => {
  const el = e.target.closest("[data-change]");
  if (el && ACTIONS[el.dataset.change]) ACTIONS[el.dataset.change](el, ctx);
});
document.addEventListener("input", e => {
  if (e.target.id !== "q") return;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => runSearch(e.target.value), 140);
});
document.addEventListener("keydown", e => { if (e.key === "Escape") { closeDialog(); closeMenus(); const b = document.getElementById("results"); if (b) b.hidden = true; } });

boot();
