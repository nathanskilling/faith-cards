// Match centre: the preview of the next game, and the match report with a
// live replay (scoreboard, score worm and running commentary).
import * as E from "./engine.js";
import { esc, ordinal, club, badge, icon, posTags, ovr, dots, form, table, panel, seg, meter, plural } from "./ui.js";
import { SCREENS, ACTIONS, S, compare, matchRow, ovalView } from "./screens.js";

S.match = { tab: "summary", side: 0, live: null, wrap: null };
const TACTIC_WORDS = { style: "style", tempo: "tempo", pressure: "pressure", forward: "forward line", defence: "defence" };

// ---- preview ----------------------------------------------------------------------------
function previewView(d) {
  const m = d.match, me = d.teams[d.me], opp = d.teams[d.opp];
  const [hid, aid] = [m.home, m.away], [ht, at] = [d.teams[hid], d.teams[aid]];
  const side = (id, t, away) => `<div class="side ${away ? "away" : ""}">${badge(id, 60)}<div><b>${esc(club(id).name)}</b>
    <span class="muted">${ordinal(t.pos)} · ${t.rec} · ${t.pct}%</span><div>${dots(t.last5)}</div></div></div>`;
  const stars = (id, t) => panel(`${esc(club(id).name)} key players`, t.stars.map(p => `<a class="row" data-nav="player/${p.id}" style="padding:5px 0;color:var(--text);cursor:pointer">
      ${posTags(p.pos.slice(0, 1))}<span class="grow">${esc(p.name)}</span>${form(p)} ${ovr(p.ovr)}</a>`).join("")
    + (t.out.length ? `<div class="upper" style="margin-top:10px">Unavailable</div><p class="muted" style="margin:4px 0 0">${t.out.map(p => `${esc(p.short)} (${p.ovr}, ${esc(p.inj[0])})`).join(", ")}</p>` : ""), { cls: "s6" });
  const plan = opp.tactics;
  return `<section class="panel"><header><h2>${esc(m.label)}</h2><span class="right muted">${esc(m.venue)}${d.roof ? " · roof closed" : ""}</span></header>
      <div class="hero">
        <div class="versus">${side(hid, ht)}<div class="mid"><b>V</b></div>${side(aid, at, true)}</div>
        ${compare(["DEF", "MID", "FWD", "RUCK"], [...ht.lines, ht.ruck], [...at.lines, at.ruck])}
        <div class="chance"><span class="upper">Your win chance</span>${meter(d.win, "club")}<b class="num" style="font-size:20px">${d.win}%</b></div>
        ${d.travel ? `<p class="muted" style="margin:0">${esc(d.travel)}</p>` : ""}
        <div class="row wrap"><button class="btn primary" data-act="continue">${icon("play")} ${esc(E.header.cont)}</button>
          <button class="btn" data-nav="team">Team sheet</button><button class="btn" data-nav="plan">Game plan</button>
          ${S.match.hasLast ? `<button class="btn right" data-act="matchLast">Last match report</button>` : ""}</div>
      </div></section>
    <div class="grid" style="margin-top:14px">
      ${panel("Scouting report", `<p style="margin-top:0">${esc(club(d.opp).name)} play <b>${esc(opp.philosophy)}</b>: ${Object.entries(plan).map(([k, v]) => `${esc(v)} ${TACTIC_WORDS[k]}`).join(", ")}.</p>
        ${d.notes.length ? d.notes.map(n => `<div class="tip ${n.level}" data-nav="${n.go}" style="padding:8px 0"><i></i><span>${esc(n.text)}</span></div>`).join("") : `<p class="muted" style="margin:0">No obvious mismatch either way. Back your structure.</p>`}`, { cls: "s12" })}
      ${stars(d.me, me)}${stars(d.opp, opp)}
      ${panel(`${esc(club(d.opp).name)} likely side`, ovalView(d.their_slots, false, null), { cls: "s12" })}
    </div>`;
}

// ---- report -------------------------------------------------------------------------------
const absT = (q, min) => (q - 1) * 30 + min;

function wormSvg(m, upto = Infinity) {
  const W = 1000, H = 150, nq = m.qs.length, total = nq * 30;
  let margin = 0, peak = 24, biggest = 0;
  const pts = [[0, 0]];
  for (const [q, min, side, kind] of m.timeline) {
    margin += (side === 0 ? 1 : -1) * (kind === "G" ? 6 : 1);
    peak = Math.max(peak, Math.abs(margin));
    if (Math.abs(margin) > Math.abs(biggest)) biggest = margin;
    pts.push([absT(q, min), margin]);
  }
  const x = t => (t / total * W).toFixed(1), y = v => (H / 2 - v / peak * (H / 2 - 12)).toFixed(1);
  let d = `M0 ${y(0)}`, last = 0, lastM = 0;
  for (const [t, v] of pts.slice(1)) {
    if (t > upto) break;
    d += ` H${x(t)} V${y(v)}`;
    last = t; lastM = v;
  }
  const end = Math.min(upto, total);
  d += ` H${x(end)}`;
  const grid = Array.from({ length: nq - 1 }, (_, i) => `<line x1="${x((i + 1) * 30)}" x2="${x((i + 1) * 30)}" y1="0" y2="${H}" stroke="var(--line2)" stroke-dasharray="3 5"/>`).join("");
  const note = upto < total
    ? (lastM ? `${lastM > 0 ? m.home : m.away} by ${Math.abs(lastM)}` : "Scores level")
    : `Biggest lead: ${biggest ? `${biggest > 0 ? m.home : m.away} by ${Math.abs(biggest)}` : "none"}`;
  return `<div class="wormbox"><svg class="worm" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Score worm: margin through the game">
    ${grid}<line x1="0" x2="${W}" y1="${H / 2}" y2="${H / 2}" stroke="var(--line2)" vector-effect="non-scaling-stroke"/>
    <path d="${d}" fill="none" stroke="var(--club-text)" stroke-width="2.5" stroke-linejoin="round" vector-effect="non-scaling-stroke"/></svg>
    <span class="tl">${m.home} ahead</span><span class="bl">${m.away} ahead</span><span class="tr">${note}</span></div>`;
}

function scoreAt(m, upto) {
  const s = [[0, 0], [0, 0]];
  for (const [q, min, side, kind] of m.timeline) {
    if (absT(q, min) > upto) break;
    s[side][kind === "G" ? 0 : 1]++;
  }
  return s;
}

const qLabel = q => q === 1 ? "Quarter time" : q === 2 ? "Half time" : q === 3 ? "Three-quarter time" : q === 4 ? "Full time" : "End of extra time";
function feedItems(m, upto = Infinity) {
  // merge scores, highlights and quarter breaks into one running order
  const items = [];
  const hi = new Map(m.feed.map(([q, min, text]) => [`${q}:${min}`, text]));
  let run = [[0, 0], [0, 0]];
  const gb = s => `${s[0]}.${s[1]} (${s[0] * 6 + s[1]})`;
  let curQ = 1;
  const closeQ = q => items.push({ t: q * 30 + .5, cls: "q", when: "", text: `${qLabel(q)}: ${esc(club(m.home).name)} ${gb(run[0])} - ${esc(club(m.away).name)} ${gb(run[1])}` });
  for (const [q, min, side, kind, name] of m.timeline) {
    while (curQ < q) closeQ(curQ++);
    run[side][kind === "G" ? 0 : 1]++;
    const cid = side === 0 ? m.home : m.away, when = q <= 4 ? `Q${q} ${min}'` : "ET";
    const key = `${q}:${min}`;
    if (kind === "G") {
      const note = hi.get(key);
      hi.delete(key);
      items.push({ t: absT(q, min), cls: "goal", when, text: `<b>GOAL ${cid}</b> ${esc(name)}${note ? `<br><span class="muted">${esc(note)}</span>` : ""}` });
    } else items.push({ t: absT(q, min), cls: "", when, text: `<span class="muted">Behind ${cid}${kind === "R" ? " (rushed)" : ` · ${esc(name)}`}</span>` });
  }
  for (const [key, text] of hi) {                       // marks and moments that were not goals
    const [q, min] = key.split(":").map(Number);
    items.push({ t: absT(q, min) - .1, cls: "", when: q <= 4 ? `Q${q} ${min}'` : "ET", text: esc(text) });
  }
  while (curQ <= m.qs.length) closeQ(curQ++);
  return items.sort((a, b) => a.t - b.t).filter(i => i.t <= upto);
}
const feedHtml = items => [...items].reverse().map(i => `<div class="ev ${i.cls}"><span class="t">${i.when}</span><span>${i.text}</span></div>`).join("");

function boardHtml(m, s, clock, live) {
  const pts = x => x[0] * 6 + x[1], lead = pts(s[0]) - pts(s[1]);
  const side = (id, sc, away) => `<div class="side ${away ? "away" : ""}">${badge(id, 54)}<div><b>${esc(club(id).name)}</b><span class="gb">${sc[0]}.${sc[1]}</span></div></div>`;
  return `${side(m.home, s[0], false)}<div class="mid"><span class="pts ${lead > 0 ? "lead" : ""}">${pts(s[0])}</span>
    <div class="clock"><b>${clock}</b><span class="muted">${live ? "LIVE" : m.et ? "extra time" : "final"}</span></div>
    <span class="pts ${lead < 0 ? "lead" : ""}">${pts(s[1])}</span></div>${side(m.away, s[1], true)}`;
}

function quarterTable(m) {
  const row = (id, gi, bi) => `<tr><td>${esc(club(id).name)}</td>${m.qs.map(q => `<td>${q[gi]}.${q[bi]}</td>`).join("")}<td><b>${m.qs[m.qs.length - 1][gi] * 6 + m.qs[m.qs.length - 1][bi]}</b></td></tr>`;
  return `<table class="qtable"><tr><th></th>${m.qs.map((_, i) => `<th>${i < 4 ? "Q" + (i + 1) : "ET"}</th>`).join("")}<th>TOTAL</th></tr>${row(m.home, 0, 1)}${row(m.away, 2, 3)}</table>`;
}

function statBars(m) {
  const rows = [["Inside 50s", m.team[0].i50, m.team[1].i50], ["Clearances", m.team[0].cl, m.team[1].cl], ["Hit-outs", m.team[0].ho, m.team[1].ho]];
  if (m.players) {
    const sum = (side, f) => m.players.filter(p => p.side === side).reduce((t, p) => t + f(p), 0);
    rows.unshift(["Disposals", sum(0, p => p.k + p.hb), sum(1, p => p.k + p.hb)]);
    rows.push(["Marks", sum(0, p => p.m), sum(1, p => p.m)], ["Tackles", sum(0, p => p.t), sum(1, p => p.t)]);
    rows.push(["Scoring shots", m.hs[0] + m.hs[1], m.as[0] + m.as[1]]);
  }
  return rows.map(([l, a, b]) => `<div class="statbar"><b>${a}</b><div class="bar l ${a >= b ? "win" : ""}"><i style="width:${a / Math.max(a, b, 1) * 100}%"></i></div>
    <span class="lbl">${l}</span><div class="bar r ${b > a ? "win" : ""}"><i style="width:${b / Math.max(a, b, 1) * 100}%"></i></div><b>${b}</b></div>`).join("");
}

function reportBody(m) {
  const st = S.match, sideId = [m.home, m.away];
  const tabs = [["summary", "Summary"]];
  if (m.players) tabs.push(["players", "Player stats"], ["feed", "Play by play"]);
  if (!tabs.some(t => t[0] === st.tab)) st.tab = "summary";
  let body;
  if (st.tab === "players") {
    const rows = m.players.filter(p => p.side === st.side);
    const n = k => ({ k, t: k.toUpperCase(), n: 1 });
    body = `<div class="toolbar">${seg("matchSide", [[0, club(m.home).name], [1, club(m.away).name]].map(([v, l]) => [String(v), l]), String(st.side))}</div>
      ${panel(`${esc(club(sideId[st.side]).name)} player stats`, table("match-players", [
        { k: "slot", t: "Pos" }, { k: "name", t: "Player", c: "name", f: r => esc(r.name) }, { ...n("k"), t: "K" }, { k: "hb", t: "H", n: 1 },
        { k: "d", t: "D", n: 1, s: r => r.k + r.hb, f: r => `<b>${r.k + r.hb}</b>` }, { ...n("m"), t: "M" }, { ...n("t"), t: "T" },
        { ...n("g"), t: "G", f: r => r.g ? `<b class="good">${r.g}</b>` : 0 }, { ...n("b"), t: "B" }, { k: "ho", t: "HO", n: 1 }, { k: "cl", t: "CL", n: 1 }, { k: "i50", t: "I50", n: 1 },
        { k: "rt", t: "Rating", n: 1, f: r => `<span class="frm ${r.rt >= 7.5 ? "hot" : r.rt < 5 ? "cold" : ""}">${r.rt.toFixed(1)}</span>` }],
        rows, { sort: { k: "rt", dir: -1 }, row: r => `data-nav="player/${r.id}"` }), { flush: true, right: "tap a column to sort" })}`;
  } else if (st.tab === "feed") {
    body = panel("Play by play", `<div class="feed">${feedHtml(feedItems(m))}</div>`, { flush: true });
  } else {
    const wrap = st.wrap && st.wrap.match === m.id ? st.wrap : null;
    body = `<div class="grid">
      ${m.timeline ? panel("Score worm", wormSvg(m), { cls: "s12" }) : ""}
      ${panel("Scores", quarterTable(m) + `<dl class="kv" style="margin-top:12px"><dt>Goals ${m.home}</dt><dd style="text-align:left">${esc(m.gk[0] || "-")}</dd><dt>Goals ${m.away}</dt><dd style="text-align:left">${esc(m.gk[1] || "-")}</dd>
        <dt>Crowd</dt><dd style="text-align:left">${m.att.toLocaleString()} at ${esc(m.venue)} · ${m.wet ? "wet" : "dry"}</dd>
        ${m.inj.length ? `<dt>Injuries</dt><dd style="text-align:left">${m.inj.map(([n, c, typ, wk]) => `${esc(n)} (${c}) ${esc(typ)}, ${plural(wk, "week")}`).join("; ")}</dd>` : ""}</dl>`, { cls: "s6" })}
      ${panel("Team stats", statBars(m), { cls: "s6", right: `${m.home} · ${m.away}` })}
      ${panel("Best on ground", m.best.map(([name, cid, rt, line], i) => `<div class="row" style="padding:6px 0"><b class="num" style="width:20px;font-size:18px">${3 - i}</b>${badge(cid, 24)}<span class="grow"><b>${esc(name)}</b><br><span class="muted">${esc(line)}</span></span><span class="frm hot">${rt}</span></div>`).join(""), { cls: "s6", right: "votes" })}
      ${wrap ? panel("Around the grounds", wrap.matches.filter(x => x.id !== m.id).map(x => matchRow(x, E.header.club)).join("") || `<p class="muted" style="padding:14px;margin:0">No other games.</p>`, { cls: "s6", flush: true, right: `<a data-nav="ladder">Ladder</a>` }) : ""}
    </div>`;
  }
  return `<div class="toolbar" style="margin-top:14px">${seg("matchTab", tabs, st.tab)}
      <span class="right row"><button class="btn" data-act="matchReplay" ${m.timeline ? "" : "hidden"}>${icon("play")} Watch replay</button>
      <button class="btn" data-nav="fixtures">Results</button></span></div>${body}`;
}

SCREENS.match = {
  title: "Match centre",
  load(arg) {
    const st = S.match;
    st.hasLast = false;
    if (!arg) {
      const pre = E.call("preview");
      const last = E.call("match");
      st.hasLast = !!last.match;
      st.lastId = last.match ? last.match.id : null;
      if (pre.match) return { preview: pre };
      return last.match ? last : { none: true };
    }
    return E.call("match", { id: +arg });
  },
  view(d) {
    if (d.none) return `<p class="muted">No game to preview and none played yet this season.</p>`;
    if (d.preview) return previewView(d.preview);
    const m = d.match, live = S.match.live === m.id && !!m.timeline;
    if (!m.played) return `<p class="muted">${esc(club(m.home).name)} v ${esc(club(m.away).name)} at ${esc(m.venue)} has not been played yet.</p>`;
    const final = [[m.hs[0], m.hs[1]], [m.as[0], m.as[1]]];
    return `<section class="panel"><header><h2>${esc(m.label)}</h2><span class="right muted">${esc(m.venue)} · ${m.att.toLocaleString()}</span></header>
        <div class="board" id="board">${boardHtml(m, live ? [[0, 0], [0, 0]] : final, live ? "Q1" : "FT", live)}</div>
        <div id="livebox" ${live ? "" : "hidden"}>
          <div style="padding:0 14px" id="liveworm">${m.timeline ? wormSvg(m, 0) : ""}</div>
          <div class="row" style="padding:10px 14px;border-top:1px solid var(--line)"><span class="upper">Replay</span>
            ${seg("liveSpeed", [["1", "Normal"], ["3", "Fast"]], "1")}<button class="btn right" data-act="liveSkip">Skip to full time</button></div>
          <div class="feed" id="livefeed"></div>
        </div></section>
      <div id="report" ${live ? "hidden" : ""}>${reportBody(m)}</div>`;
  },
  after(root, d) {
    if (!d.match || !d.match.played || S.match.live !== d.match.id || !d.match.timeline) return null;
    return runLive(root, d.match);
  },
};

// Live replay: the result is already decided; this just reveals it over ~15 seconds.
let liveCtl = null;
function runLive(root, m) {
  const total = m.qs.length * 30, items = feedItems(m);
  const board = root.querySelector("#board"), worm = root.querySelector("#liveworm"), feed = root.querySelector("#livefeed");
  let t = 0, shown = 0, timer = null, pause = 0;
  const ctl = liveCtl = { speed: 1, finish };
  function paint() {
    const q = Math.min(m.qs.length, Math.floor(Math.max(0, t - .01) / 30) + 1), min = Math.max(1, Math.ceil(t - (q - 1) * 30));
    board.innerHTML = boardHtml(m, scoreAt(m, t), t >= total ? "FT" : q <= 4 ? `Q${q} ${min}'` : "ET", t < total);
    worm.innerHTML = wormSvg(m, t);
    const upto = items.filter(i => i.t <= t).length;
    if (upto !== shown) { shown = upto; feed.innerHTML = feedHtml(items.slice(0, upto)); }
  }
  function tick() {
    if (pause > 0) { pause--; return; }
    const before = Math.floor(t / 30);
    t = Math.min(total, t + .5 * ctl.speed);
    if (Math.floor(t / 30) > before && t < total) { t = Math.floor(t / 30) * 30; pause = Math.round(9 / ctl.speed); }   // hold at each break
    paint();
    if (t >= total) finish();
  }
  function finish() {
    clearInterval(timer);
    timer = null;
    liveCtl = null;
    S.match.live = null;
    t = total;
    paint();
    root.querySelector("#livebox").hidden = true;
    root.querySelector("#report").hidden = false;
  }
  paint();
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) { finish(); return null; }
  timer = setInterval(tick, 55);
  return () => { clearInterval(timer); liveCtl = null; S.match.live = null; };
}

ACTIONS.liveSpeed = el => {
  if (liveCtl) liveCtl.speed = +el.dataset.v;
  el.parentElement.querySelectorAll("button").forEach(b => b.classList.toggle("on", b === el));
};
ACTIONS.liveSkip = () => liveCtl && liveCtl.finish();
ACTIONS.matchTab = (el, ctx) => { S.match.tab = el.dataset.v; ctx.repaint(); };
ACTIONS.matchSide = (el, ctx) => { S.match.side = +el.dataset.v; ctx.repaint(); };
ACTIONS.matchReplay = (el, ctx) => { S.match.live = ctx.data.match.id; ctx.repaint(); };
ACTIONS.matchLast = (el, ctx) => ctx.go("match/" + S.match.lastId);
