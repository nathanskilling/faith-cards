// Every screen except the match centre.  A screen is { title, load(arg) -> data,
// view(data, arg) -> html }.  ACTIONS are click handlers named by data-act.
import * as E from "./engine.js";
import { esc, money, ordinal, club, plural, badge, icon, posTags, posLine, ovr, attrClass, fit, meter, dots,
         form, spark, nameCell, score, table, panel, seg, chips, toast, dialog, tier } from "./ui.js";

export const S = {                       // UI state that survives re-renders
  squad: { view: "overview", grp: "ALL" }, team: { sel: null }, fix: { tab: "club", round: null },
  stats: { what: "goals", mine: false }, con: { ooc: false }, trade: { club: null, give: [], get: [], verdict: null },
  draft: { pos: "ALL" }, choose: { club: null },
};
export const SCREENS = {};
export const ACTIONS = {};
const GROUPS = ["KD", "GD", "WG", "MD", "RK", "GF", "KF"];
const LINES = [["ALL", "All"], ["D", "Defenders"], ["M", "Midfield"], ["R", "Rucks"], ["F", "Forwards"]];
const inLine = (p, line) => line === "ALL" || posLine(p.pos[0]) === line;
const pnav = r => `data-nav="player/${r.id}"`;

// ---- shared columns -----------------------------------------------------------------
const cName = (opts = {}) => ({ k: "name", t: "Player", c: "name", s: r => r.name.split(" ").slice(-1)[0], f: r => nameCell(r, opts) });
const cPos = { k: "pos", t: "Pos", s: r => GROUPS.indexOf(r.grp) * 100 - r.ovr, f: r => posTags(r.pos) };
const cAge = { k: "age", t: "Age", n: 1 };
const cOvr = { k: "ovr", t: "Ovr", n: 1, f: r => ovr(r.ovr), tip: "Current ability" };
const cPot = { k: "pot", t: "Pot", n: 1, f: r => ovr(r.pot), tip: "Potential (an estimate unless he is yours)" };
const cFit = { k: "fit", t: "Fitness", n: 1, c: " ", f: r => fit(r.fit) };
const cForm = { k: "form", t: "Form", n: 1, c: " ", s: r => r.form ?? (r.res ? r.res - 20 : null), f: r => `${form(r)} ${spark(r.forms)}`, tip: "Average of last five senior ratings (r = reserves)" };
const cWage = { k: "wage", t: "Wage", n: 1, f: r => money(r.wage) };
const cUntil = { k: "until", t: "Until", n: 1 };
const cValue = { k: "value", t: "Value", n: 1, tip: "Trade points" };
const cClub = { k: "club", t: "Club", f: r => r.club ? `<span class="row" style="gap:6px">${badge(r.club, 20)} ${esc(club(r.club).name)}</span>` : `<span class="faint">-</span>` };

function matchRow(m, mine) {
  const h = club(m.home), a = club(m.away);
  if (!m.played) {
    return `<a class="mrow" data-nav="${m.home === mine || m.away === mine ? "match" : "squad/" + (m.home === mine ? m.away : m.home)}"><span class="t">${badge(m.home, 24)} ${esc(h.name)}</span>
      <span class="sc faint">v</span><span class="t away">${badge(m.away, 24)} ${esc(a.name)}</span></a>`;
  }
  const hw = m.hs[2] > m.as[2], aw = m.as[2] > m.hs[2];
  return `<a class="mrow" data-nav="match/${m.id}"><span class="t ${aw ? "lose" : ""}">${badge(m.home, 24)} ${esc(h.name)}</span>
    <span class="sc"><span class="${aw ? "lose" : ""}">${m.hs[0]}.${m.hs[1]} (${m.hs[2]})</span> <span class="faint">-</span> <span class="${hw ? "lose" : ""}">${m.as[0]}.${m.as[1]} (${m.as[2]})</span></span>
    <span class="t away ${hw ? "lose" : ""}">${badge(m.away, 24)} ${esc(a.name)}</span></a>`;
}
export { matchRow };

// ---- home -----------------------------------------------------------------------------
function compare(labels, mine, theirs) {
  const max = Math.max(...mine, ...theirs, 1), min = Math.min(...mine, ...theirs) - 12;
  const w = v => Math.max(6, (v - min) / (max - min) * 100);
  return `<div class="cmp">${labels.map((l, i) => `
    <div class="v l">${mine[i]}<div class="bar l grow ${mine[i] >= theirs[i] ? "win" : ""}"><i style="width:${w(mine[i])}%"></i></div></div>
    <div class="lbl">${l}</div>
    <div class="v"><div class="bar r grow ${theirs[i] > mine[i] ? "win" : ""}"><i style="width:${w(theirs[i])}%"></i></div>${theirs[i]}</div>`).join("")}</div>`;
}
export { compare };

function heroNext(d, h) {
  const n = d.next, me = club(h.club), opp = club(n.opp);
  const [home, away] = n.home ? [me, opp] : [opp, me];
  return `<section class="panel s7"><header><h2>Next match</h2><span class="right muted">${esc(n.label)} · ${esc(n.venue)}</span></header>
    <div class="hero">
      <div class="versus">
        <div class="side">${badge(home.id, 56)}<div><b>${esc(home.name)}</b><span class="muted">${home.id === h.club ? `${ordinal(h.pos)} · ${h.record}` : `${ordinal(n.opp_pos)} · ${n.opp_rec}`}</span><div>${dots(home.id === h.club ? d.form : n.opp_form)}</div></div></div>
        <div class="mid"><b>V</b></div>
        <div class="side away">${badge(away.id, 56)}<div><b>${esc(away.name)}</b><span class="muted">${away.id === h.club ? `${ordinal(h.pos)} · ${h.record}` : `${ordinal(n.opp_pos)} · ${n.opp_rec}`}</span><div>${dots(away.id === h.club ? d.form : n.opp_form)}</div></div></div>
      </div>
      ${compare(["DEF", "MID", "FWD"], n.home ? n.lines.me : n.lines.opp, n.home ? n.lines.opp : n.lines.me)}
      <div class="chance"><span class="upper">Your win chance</span>${meter(n.win, "club")}<b class="num" style="font-size:20px">${n.win}%</b></div>
      <div class="row wrap"><button class="btn primary" data-act="continue">${icon("play")} ${esc(h.cont)}</button>
        <button class="btn" data-nav="match">Match preview</button><button class="btn" data-nav="team">Team sheet</button>
        <span class="muted right">They play: ${esc(n.opp_plan)}</span></div>
    </div></section>`;
}

function heroOff(d, h) {
  const order = ["review", "contracts", "trades", "draft"], names = ["Season review", "Contracts", "Trade period", "Draft"];
  const at = order.indexOf(h.phase);
  let body = "";
  if (h.phase === "finals") {
    body = `<p class="muted">Your season is over. Follow the finals from here.</p>`;
  } else if (h.phase === "review") {
    body = `<p class="muted">The season is done. Read the wrap below, then open contract talks.</p>`;
  } else if (h.phase === "contracts") {
    body = `<p>${h.unsigned ? `<b class="warn">${plural(h.unsigned, "player")} unsigned.</b> Anyone not re-signed walks when you end the signing period.` : "Everyone you want is signed."}</p>`;
  } else if (h.phase === "trades") {
    body = `<p class="muted">Clubs are open for business. Trade players and picks, and sign free agents, before the draft.</p>`;
  } else if (h.phase === "draft") {
    body = `<p>${h.on_clock ? `<b class="warn">You are on the clock.</b>` : "The draft is under way."} <span class="muted">Starting the season auto-drafts anything left.</span></p>`;
  }
  const links = { finals: [["fixtures", "Finals results"]], review: [["club", "Board review"]], contracts: [["contracts", "Contracts"]],
                  trades: [["trade", "Trades"], ["agents", "Free agents"], ["contracts", "Contracts"]], draft: [["draft", "Draft board"], ["trade", "Trades"]] }[h.phase] || [];
  return `<section class="panel s7"><header><h2>${h.phase === "finals" ? "Finals" : "Off-season"}</h2><span class="right muted">${esc(h.phase_label)}</span></header>
    <div class="hero">${h.phase === "finals" ? "" : `<div class="steps">${names.map((n, i) => `<span class="${i === at ? "on" : i < at ? "done" : ""}">${n}</span>`).join("")}<span>New season</span></div>`}
      ${body}
      ${d.finals.length && h.phase === "finals" ? `<div>${d.finals[d.finals.length - 1].matches.map(m => matchRow(m, h.club)).join("")}</div>` : ""}
      <div class="row wrap"><button class="btn primary" data-act="continue">${icon("play")} ${esc(h.cont)}</button>
        ${links.map(([r, l]) => `<button class="btn" data-nav="${r}">${l}</button>`).join("")}</div>
    </div></section>`;
}

export function reviewBlock(r, d) {
  if (!r || r.position == null) return "";
  const aw = d.awards || {};
  return `<dl class="kv" style="max-width:640px">
    <dt>Premiers</dt><dd>${d.premier ? esc(club(d.premier).full) : "-"}</dd>
    <dt>Your finish</dt><dd>${ordinal(r.position)}${r.finish ? ` · ${esc(r.finish)}` : ""}</dd>
    <dt>Board wanted</dt><dd>${esc(r.label)}</dd>
    <dt>Board verdict</dt><dd class="${r.delta >= 0 ? "good" : "bad"}">${esc(r.verdict)} (${r.delta > 0 ? "+" : ""}${Math.round(r.delta)})</dd>
    <dt>Season result</dt><dd>${money(r.profit)}</dd>
    ${r.bnf && r.bnf.length ? `<dt>Best and fairest</dt><dd>${r.bnf.map(x => esc(x[0])).join(", ")}</dd>` : ""}
    ${aw.brownlow ? `<dt>Brownlow</dt><dd>${esc(aw.brownlow[0])} (${aw.brownlow[1]}) ${aw.brownlow[2]}</dd>` : ""}
    ${aw.coleman ? `<dt>Coleman</dt><dd>${esc(aw.coleman[0])} (${aw.coleman[1]}) ${aw.coleman[2]}</dd>` : ""}
    ${r.retired && r.retired.length ? `<dt>Retiring</dt><dd>${r.retired.map(x => esc(x[0])).join(", ")}</dd>` : ""}
  </dl>`;
}

SCREENS.home = {
  title: "Home",
  load: () => E.call("home"),
  view(d) {
    const h = E.header;
    const hero = d.next ? heroNext(d, h) : heroOff(d, h);
    const tips = d.advice.length
      ? `<div class="tips">${d.advice.map(t => `<a class="tip ${t.level}" data-nav="${esc(t.go)}"><i></i><span>${esc(t.text)}</span></a>`).join("")}</div>`
      : `<p class="muted" style="padding:14px;margin:0">Nothing needs your attention. Enjoy it while it lasts.</p>`;
    const last = d.last ? `<div class="scoreline" data-nav="match/${d.last.id}" style="cursor:pointer">
        ${[["home", "hs", "as"], ["away", "as", "hs"]].map(([side, mine, other]) => `
          <div class="t ${d.last[mine][2] < d.last[other][2] ? "lose" : ""}">${badge(d.last[side], 28)} ${esc(club(d.last[side]).name)}</div>
          <div class="s ${d.last[mine][2] < d.last[other][2] ? "lose" : ""}">${d.last[mine][0]}.${d.last[mine][1]} <b>${d.last[mine][2]}</b></div>`).join("")}
      </div><p class="muted" style="margin:10px 0 0">Best: ${d.last.best.map(b => `${esc(b[0])} ${b[2]}`).join(" · ")}</p>`
      : `<p class="muted" style="margin:0">No games played yet this season.</p>`;
    const ladder = table("home-ladder", [
      { t: "", f: r => r.pos, c: "r" }, { t: "Club", f: r => `<span class="row" style="gap:7px">${badge(r.club, 20)} ${esc(club(r.club).name)}</span>` },
      { t: "W-L", f: r => `${r.W}-${r.L}`, c: "c" }, { t: "%", f: r => r.pct.toFixed(1), c: "r" }, { t: "Form", f: r => dots(r.form) },
    ], d.ladder, { row: r => `class="${r.club === h.club ? "me" : ""}${r.pos === 8 ? " cut" : ""}" data-nav="squad/${r.club}"` });
    const b = d.board;
    return `<div class="grid">
      ${hero}
      <section class="panel s5"><header><h2>Assistant coach</h2><span class="right muted">${plural(d.advice.length, "note")}</span></header><div class="body flush">${tips}</div></section>
      ${d.review ? `<section class="panel s12"><header><h2>${h.year} season review</h2></header><div class="body">${reviewBlock(d.review, d)}</div></section>` : ""}
      ${panel("Last result", last, { cls: "s4", right: d.last ? esc(d.last.label) : "" })}
      <section class="panel s4"><header><h2>Ladder</h2><a class="right" data-nav="ladder">Full ladder</a></header><div class="body flush">${ladder}</div></section>
      <section class="panel s4"><header><h2>Squad pulse</h2><a class="right" data-nav="squad">Squad</a></header><div class="body">
        <div class="upper">In form</div>${d.in_form.length ? d.in_form.map(p => `<a class="row" data-nav="player/${p.id}" style="padding:4px 0;color:var(--text);cursor:pointer">${posTags(p.pos.slice(0, 1))}<span class="grow">${esc(p.name)}</span>${spark(p.forms)} ${form(p)}</a>`).join("") : `<p class="muted" style="margin:4px 0 0">Form builds once games are played.</p>`}
        <div class="upper" style="margin-top:12px">Injury list (${d.injuries.length})</div>
        ${d.injuries.length ? d.injuries.slice(0, 6).map(p => `<a class="row" data-nav="player/${p.id}" style="padding:4px 0;color:var(--text);cursor:pointer">${posTags(p.pos.slice(0, 1))}<span class="grow">${esc(p.name)}</span><span class="tag inj">${esc(p.inj[0])} ${p.inj[1]}w</span></a>`).join("") : `<p class="muted" style="margin:4px 0 0">A clean bill of health.</p>`}
      </div></section>
      <section class="panel s7"><header><h2>Inbox</h2><a class="right" data-nav="inbox">All news</a></header><div class="body flush">
        ${d.news.map(n => `<div class="news-item"><span class="when">${esc(n.when)}</span><span>${esc(n.text)}</span></div>`).join("") || `<p class="muted" style="padding:14px;margin:0">Nothing yet.</p>`}</div></section>
      <section class="panel s5"><header><h2>Club</h2><a class="right" data-nav="club">Board &amp; finances</a></header><div class="body col">
        <div class="gauge"><div class="row"><span class="upper">Board confidence</span><b class="num right">${Math.round(b.confidence)}/100</b></div>${meter(b.confidence, b.confidence < 30 ? "low" : b.confidence < 50 ? "mid" : "")}<span class="muted">Expectation: ${esc(b.label)}</span></div>
        <div class="gauge"><div class="row"><span class="upper">Salary cap</span><b class="num right">${money(h.payroll)} / ${money(h.cap)}</b></div>${meter(h.payroll / h.cap * 100, "club")}<span class="muted">${money(d.list.room)} room · ${d.list.senior} senior + ${d.list.rookie} rookie</span></div>
        <dl class="kv"><dt>Game plan</dt><dd>${esc(d.philosophy)}</dd><dt>Training</dt><dd style="text-transform:capitalize">${esc(d.training.focus)} · ${esc(d.training.intensity)}</dd><dt>Season result</dt><dd class="${d.profit < 0 ? "bad" : ""}">${money(d.profit)}</dd></dl>
      </div></section>
    </div>`;
  },
};

SCREENS.inbox = {
  title: "Inbox",
  load: () => E.call("news"),
  view: d => panel("News", d.news.map(n => `<div class="news-item"><span class="when">${n.year} ${esc(n.when)}</span><span><span class="tag">${esc(n.tag)}</span> ${esc(n.text)}</span></div>`).join("") || `<p class="muted" style="padding:14px">Nothing yet.</p>`, { flush: true }),
};

// ---- squad ------------------------------------------------------------------------------
SCREENS.squad = {
  title: "Squad",
  load: arg => E.call("squad", { club: arg || null }),
  view(d) {
    const st = S.squad, A = E.statics;
    const rows = d.players.filter(p => inLine(p, st.grp));
    const name = cName({ captain: d.captain });
    const sel = { k: "sel", t: "Sel", s: r => r.sel ? 0 : 1, f: r => r.sel ? `<span class="tag">${r.sel}</span>` : "", tip: "Spot in the selected 23" };
    const views = {
      overview: [sel, name, cPos, cAge, cOvr, cPot, cFit, cForm, { k: "gm", t: "Gm", n: 1 }, cValue],
      attributes: [name, cPos, cOvr, ...A.attrs.map((a, i) => ({ k: "a" + i, t: A.attr_short[a], c: "a", n: 1, tip: A.attr_label[a], s: r => r.a[i], f: r => `<span class="${attrClass(a === "injury_prone" ? 21 - r.a[i] : r.a[i])}">${r.a[i]}</span>` }))],
      season: [name, cPos, { k: "gm", t: "Games", n: 1 }, { k: "g", t: "Goals", n: 1 }, { k: "disp", t: "Disp", n: 1, f: r => r.disp ?? "-" }, { k: "rt", t: "Rating", n: 1, f: r => r.rt ? r.rt.toFixed(2) : "-" }, { k: "v", t: "Votes", n: 1 }, cForm],
      contract: [name, cPos, cAge, cOvr, cPot, cWage, cUntil, cValue, { t: "List", f: r => r.rookie ? "Rookie" : "Senior" }],
    };
    const c = club(d.club);
    const avgAge = (d.players.reduce((s, p) => s + p.age, 0) / d.players.length).toFixed(1);
    return `<div class="toolbar">
        <select data-change="squadClub" aria-label="Club">${Object.values(A.clubs).map(x => `<option value="${x.id}" ${x.id === d.club ? "selected" : ""}>${esc(x.full)}</option>`).join("")}</select>
        ${chips("squadGrp", LINES, st.grp)}
        <span class="right">${seg("squadView", [["overview", "Overview"], ["attributes", "Attributes"], ["season", "Season"], ["contract", "Contracts"]], st.view)}</span>
      </div>
      <section class="panel"><header>${badge(d.club, 30)}<h2>${esc(c.full)}</h2>
        <span class="right muted">${d.senior} senior + ${d.rookie} rookie · best 22 <b>${d.best22}</b> · avg age ${avgAge} · ${money(d.payroll)} of ${money(d.cap)}${d.own ? "" : ` · ${esc(d.philosophy)} · development ${d.dev} · recruiting ${d.recruit}`}</span></header>
        <div class="body flush">${table("squad-" + st.view, views[st.view], rows, { sort: { k: "pos", dir: 1 }, row: pnav })}</div></section>
      ${d.own ? "" : `<p class="muted">Potential for other clubs' players is your recruiters' estimate. <a data-nav="team/${d.club}">Their likely team</a> · <a data-nav="trade/${d.club}">Talk trade</a></p>`}`;
  },
};
ACTIONS.squadView = (el, ctx) => { S.squad.view = el.dataset.v; ctx.repaint(); };
ACTIONS.squadGrp = (el, ctx) => { S.squad.grp = el.dataset.v; ctx.repaint(); };
ACTIONS.squadClub = (el, ctx) => ctx.go("squad/" + el.value);

// ---- player ---------------------------------------------------------------------------
const ATTR_GROUPS = [["Skills", ["kicking", "handballing", "marking", "goal_sense", "intercept", "ruck"]],
                     ["Athletic", ["speed", "endurance", "strength", "tackling", "toughness"]],
                     ["Character", ["decision", "leadership", "consistency", "injury_prone"]]];

SCREENS.player = {
  title: "Player",
  load: arg => E.call("player", { id: +arg }),
  view(d) {
    const p = d.p, A = E.statics;
    const buttons = [];
    if (d.can_offer) buttons.push(`<button class="btn primary" data-act="offer" data-id="${p.id}">${d.own ? "Offer new contract" : "Offer contract"}</button>`);
    if (d.own && !d.captain) buttons.push(`<button class="btn" data-act="captain" data-id="${p.id}">Make captain</button>`);
    if (d.own && p.rookie) buttons.push(`<button class="btn" data-act="promote" data-id="${p.id}">Promote to senior list</button>`);
    if (d.own && d.offseason) buttons.push(`<button class="btn danger" data-act="delist" data-id="${p.id}" data-name="${esc(p.name)}">Delist</button>`);
    if (d.prospect && E.header.on_clock) buttons.push(`<button class="btn primary" data-act="draftPick" data-id="${p.id}">Draft him</button>`);
    if (p.club && !d.own) buttons.push(`<button class="btn" data-nav="trade/${p.club}">Talk trade with ${esc(club(p.club).name)}</button>`);
    const attrs = ATTR_GROUPS.map(([title, keys]) => `<div><div class="upper" style="margin-bottom:4px">${title}</div>${keys.map(k => {
      const v = d.attrs[k], shown = Math.round(v), good = k === "injury_prone" ? 21 - shown : shown;
      return `<div class="attr ${attrClass(good)}"><span style="color:var(--text)">${esc(A.attr_label[k])}</span><b>${shown}</b>${meter(shown * 5)}</div>`;
    }).join("")}</div>`).join("");
    const roles = d.roles.slice(0, 7).map(([pt, r]) => `<div class="attr"><span>${esc(A.pos_name[pt])}</span><b class="${"a" + tier(r)}">${r}</b>${meter(r, p.pos.includes(pt) ? "club" : "")}</div>`).join("");
    const seasons = table("pl-seasons", [
      { t: "Season", f: r => r.year }, { t: "Gm", f: r => r.gm, c: "r" }, { t: "Goals", f: r => r.g, c: "r" }, { t: "Disp", f: r => r.disp, c: "r" },
      { t: "Marks", f: r => r.m, c: "r" }, { t: "Tackles", f: r => r.t, c: "r" }, { t: "Hit-outs", f: r => r.ho, c: "r" },
      { t: "Clearances", f: r => r.cl, c: "r" }, { t: "Rating", f: r => r.rt.toFixed(2), c: "r" }, { t: "Votes", f: r => r.v, c: "r" }], d.seasons);
    const where = p.club ? `${badge(p.club, 22)} ${esc(club(p.club).full)}` : d.prospect ? "Draft prospect" : "Free agent";
    return `<section class="panel"><div class="phead">
        <div><div class="row wrap" style="gap:8px;margin-bottom:6px">${posTags(p.pos)} ${d.captain ? `<span class="tag cap">Captain</span>` : ""} ${p.rookie ? `<span class="tag rk">Rookie list</span>` : ""} ${p.inj ? `<span class="tag inj">${esc(p.inj[0])} · ${plural(p.inj[1], "week")}</span>` : ""}</div>
          <h2>${esc(p.name)}</h2>
          <div class="row wrap muted" style="margin-top:6px">${where} · ${p.age} years · ${p.ht} cm${p.sel ? ` · named at ${p.sel}` : ""}${d.drafted ? ` · drafted ${esc(d.drafted)}` : ""}</div></div>
        <div class="boxes"><div>${ovr(p.ovr, true)}<small>OVERALL</small></div><div>${ovr(p.pot, true)}<small>${d.exact_pot ? "POTENTIAL" : "POTENTIAL (EST.)"}</small></div>
          <div><span class="ovr big t2">${p.fit}</span><small>FITNESS</small></div><div><span class="ovr big t2">${p.form != null ? p.form.toFixed(1) : "-"}</span><small>FORM</small></div></div>
      </div>
      ${buttons.length ? `<div class="row wrap" style="padding:0 18px 16px">${buttons.join("")}</div>` : ""}</section>
      <div class="grid" style="margin-top:14px">
        ${panel("Attributes", `<div class="attrs">${attrs}</div>`, { cls: "s8", right: "1-20" })}
        ${panel("Best roles", roles, { cls: "s4", right: "rating in role" })}
        ${panel("Contract", p.club ? `<dl class="kv"><dt>Wage</dt><dd>${money(p.wage)} a season</dd><dt>Runs to</dt><dd>end of ${p.until}</dd><dt>List</dt><dd>${p.rookie ? "Rookie" : "Senior"}</dd><dt>Trade value</dt><dd>${p.value} points</dd>${d.demand ? `<dt>Asking on a new deal</dt><dd>${money(d.demand.wage)} · ${d.demand.min}-${d.demand.max} years</dd>` : ""}</dl>`
          : d.demand ? `<dl class="kv"><dt>Asking</dt><dd>${money(d.demand.wage)} a season</dd><dt>Length</dt><dd>${d.demand.min}-${d.demand.max} years</dd></dl>` : `<p class="muted" style="margin:0">Not contracted. Draftees sign a standard two-year deal.</p>`, { cls: "s4" })}
        ${panel("Seasons", seasons, { cls: "s8", flush: true, right: `Career: ${d.career.games} games, ${d.career.goals} goals` })}
      </div>`;
  },
};

function offerDialog(id, ctx) {
  const d = E.call("player", { id });
  const p = d.p, dm = d.demand;
  if (!dm) return toast("He is not available to sign.", "err");
  const years = [];
  for (let y = dm.min; y <= dm.max; y++) years.push(y);
  const rookieKeep = d.own && p.rookie;
  dialog({
    title: d.own ? "New contract" : "Contract offer",
    body: `<p><b>${esc(p.name)}</b> · ${p.pos.join("/")} · ${p.age} · overall ${p.ovr}</p>
      <p class="muted">He is asking for about <b>${money(dm.wage)}</b> a season over ${dm.min}-${dm.max} years. You have ${money(E.header.cap - E.header.payroll + (d.own ? p.wage : 0))} of cap room to work with.</p>
      <div class="row wrap"><label>Years <select id="offer-years">${years.map(y => `<option>${y}</option>`).join("")}</select></label>
      <label>Wage ($k) <input id="offer-wage" type="number" step="5" min="100" value="${dm.wage}" style="width:110px"></label></div>
      ${rookieKeep ? `<p class="muted">This upgrades him to the senior list. Rookies can instead be rolled over for a year at the rookie wage.</p>` : ""}`,
    actions: [{ label: "Cancel" },
      ...(rookieKeep ? [{ label: "Keep as rookie (1 year)", run: () => { ctx.act(`offer #${id} 1`); } }] : []),
      { label: "Make the offer", primary: true, run: el => {
        const ok = ctx.act(`offer #${id} ${el.querySelector("#offer-years").value} ${el.querySelector("#offer-wage").value}`);
        return ok ? undefined : false;
      } }],
  });
}
ACTIONS.offer = (el, ctx) => offerDialog(+el.dataset.id, ctx);
ACTIONS.captain = (el, ctx) => ctx.act(`captain #${el.dataset.id}`);
ACTIONS.promote = (el, ctx) => ctx.act(`promote #${el.dataset.id}`);
ACTIONS.delist = (el, ctx) => dialog({
  title: "Delist player", body: `<p>Delist <b>${esc(el.dataset.name)}</b>? Contracted players are paid out half of what remains on their deal.</p>`,
  actions: [{ label: "Keep him" }, { label: "Delist", danger: true, run: () => { if (ctx.act(`delist #${el.dataset.id}`)) ctx.go("contracts"); } }],
});

// ---- team sheet -------------------------------------------------------------------------
const SPOTS = { FPL: [19, 9], FF: [50, 9], FPR: [81, 9], HFL: [18, 25], CHF: [50, 25], HFR: [82, 25], WL: [16, 41.5], C: [50, 41.5], WR: [84, 41.5],
                RUCK: [19, 57.5], RR: [50, 57.5], ROV: [81, 57.5], HBL: [18, 74], CHB: [50, 74], HBR: [82, 74], BPL: [19, 91], FB: [50, 91], BPR: [81, 91] };

function token(slot, s, own, selected) {
  const xy = SPOTS[slot], style = xy ? `style="left:${xy[0]}%;top:${xy[1]}%"` : "";
  const act = own ? `data-act="tok" data-slot="${slot}"` : s ? `data-nav="player/${s.id}"` : "";
  if (!s) return `<button class="tok empty" ${style} ${act}><span class="s"><span>${slot}</span></span><span class="n faint">Empty</span></button>`;
  const f = s.fit < 72 ? "low" : s.fit < 86 ? "mid" : "";
  return `<button class="tok ${selected ? "sel" : ""} ${s.inj ? "inj" : ""}" ${style} ${act} title="${esc(s.name)} · fitness ${s.fit}%${s.oop ? " · out of position" : ""}">
    <span class="s"><span>${slot}${s.cap ? " (C)" : ""}</span><span class="r ${"a" + tier(s.r)}">${s.r}${s.oop ? "*" : ""}</span></span>
    <span class="n">${esc(s.short)}</span><span class="f"><i class="${f}" style="width:${s.fit}%"></i></span></button>`;
}

export function ovalView(slots, own, sel) {
  const A = E.statics;
  return `<div class="oval"><div class="turf"><span class="arc top"></span><span class="arc bot"></span></div>${Object.keys(A.field_slots).map(s => token(s, slots[s], own, sel === s)).join("")}</div>
    <div class="bench">${A.bench_slots.map(s => token(s, slots[s], own, sel === s)).join("")}</div>`;
}

SCREENS.team = {
  title: "Team sheet",
  load: arg => E.call("team", { club: arg || null }),
  view(d) {
    const st = S.team, A = E.statics, sm = d.summary;
    if (!d.own) st.sel = null;
    const pt = st.sel ? (A.field_slots[st.sel] || null) : null;
    const rate = p => pt ? p.r[pt] : p.ovr;
    let list = d.players.filter(p => st.sel ? true : !p.sel);
    list = [...list].sort((a, b) => (a.inj ? 1 : 0) - (b.inj ? 1 : 0) || rate(b) - rate(a));
    const cols = [cName({ captain: d.captain }), cPos,
      { t: pt ? pt : "Ovr", f: r => ovr(rate(r)), c: "r" }, { t: "Fit", f: r => fit(r.fit), c: " " }, { t: "Form", f: r => form(r), c: " " },
      { t: "Now", f: r => r.sel ? `<span class="tag">${r.sel}</span>` : "" }];
    const picker = table("team-pick", cols, list, { row: r => d.own && st.sel && !r.inj ? `data-act="assign" data-id="${r.id}"` : pnav(r) });
    const title = st.sel ? `Choose for ${st.sel}${pt ? ` · ${esc(A.pos_name[pt])}` : " · interchange"}` : "Not selected";
    return `<div class="toolbar">
        ${d.own ? seg("selMode", [["auto", "Assistant picks"], ["manual", "I pick"]], d.mode) : `<button class="btn" data-nav="squad/${d.club}">${icon("back")} ${esc(club(d.club).name)} squad</button>`}
        ${d.own ? `<button class="btn" data-act="pickAuto">Pick best 23</button>` : ""}
        <span class="right muted">DEF <b>${sm.def}</b> · MID <b>${sm.mid}</b> · FWD <b>${sm.fwd}</b> · avg age ${sm.avg_age} · fitness ${sm.avg_fit}%</span>
      </div>
      ${d.problems.length ? `<p class="warn">${d.problems.map(esc).join(" · ")}</p>` : ""}
      <div class="teamgrid">
        <section class="panel"><header><h2>${esc(club(d.club).name)} 23</h2><span class="right muted">${d.own ? (st.sel ? "Tap another spot to swap, or pick from the list" : "Tap a spot to change it") : "Their likely side"}</span></header>
          <div class="body">${ovalView(d.slots, d.own, st.sel)}<p class="faint" style="margin:10px 0 0">Number = rating in that role. * out of position. Bar = fitness. Attacking up the page.</p></div></section>
        <section class="panel"><header><h2>${title}</h2>${st.sel ? `<button class="btn small right" data-act="tokClear">Done</button>` : `<span class="right muted">${plural(list.length, "player")}</span>`}</header>
          <div class="body flush picker">${picker}</div></section>
      </div>`;
  },
};
ACTIONS.tok = (el, ctx) => {
  const st = S.team, slot = el.dataset.slot, d = ctx.data;
  if (!st.sel) st.sel = slot;
  else if (st.sel === slot) st.sel = null;
  else {
    const a = d.slots[st.sel], b = d.slots[slot];
    st.sel = null;
    if (a && b) return ctx.act(`swap #${a.id}, #${b.id}`);
    if (a || b) return ctx.act(`pick ${a ? slot : st.sel} #${(a || b).id}`);
  }
  ctx.repaint();
};
ACTIONS.tokClear = (el, ctx) => { S.team.sel = null; ctx.repaint(); };
ACTIONS.assign = (el, ctx) => { const slot = S.team.sel; S.team.sel = null; ctx.act(`pick ${slot} #${el.dataset.id}`); };
ACTIONS.selMode = (el, ctx) => ctx.act(`selection ${el.dataset.v}`);
ACTIONS.pickAuto = (el, ctx) => { S.team.sel = null; ctx.act("pick auto", "Best available 23 selected."); };

// ---- game plan --------------------------------------------------------------------------
const cap = v => [v, v[0].toUpperCase() + v.slice(1)];      // option value -> [value, Label]
const TACTIC_TITLE = { style: "Game style", tempo: "Ball movement", pressure: "Pressure", forward: "Forward structure", defence: "Defensive system" };
SCREENS.plan = {
  title: "Game plan",
  load: () => E.call("team"),
  view(d) {
    const A = E.statics;
    const cards = Object.entries(A.tactics).map(([k, opts]) => panel(TACTIC_TITLE[k],
      `${seg("tac", Object.keys(opts).map(cap), d.tactics[k], `data-k="${k}"`)}<p>${esc(opts[d.tactics[k]])}</p>`)).join("");
    return `<div class="toolbar"><span class="upper">Presets</span>${chips("preset", Object.keys(A.presets), d.philosophy)}
        <span class="right muted">Current plan: <b>${esc(d.philosophy)}</b></span></div>
      <div class="plan">${cards}</div>
      <h2 style="margin:22px 0 10px;font-size:20px;text-transform:uppercase">Training week</h2>
      <div class="plan">
        ${panel("Focus", `${seg("train", Object.keys(A.focus).map(cap), d.training.focus, `data-k="focus"`)}<p>${esc(A.focus[d.training.focus])}</p>`)}
        ${panel("Intensity", `${seg("train", Object.keys(A.intensity).map(cap), d.training.intensity, `data-k="intensity"`)}<p>${esc(A.intensity[d.training.intensity])}</p>`)}
        ${panel("Squad condition", `<dl class="kv"><dt>Average fitness of the 23</dt><dd>${d.summary.avg_fit}%</dd><dt>Average age</dt><dd>${d.summary.avg_age}</dd></dl>
          <p>High pressure and fast ball movement win games but drain fitness week after week. Recovery and light weeks put it back.</p>`)}
      </div>`;
  },
};
ACTIONS.tac = (el, ctx) => ctx.act(`tactics ${el.dataset.k}=${el.dataset.v}`);
ACTIONS.preset = (el, ctx) => ctx.act(`tactics preset ${el.dataset.v}`);
ACTIONS.train = (el, ctx) => ctx.act(`training ${el.dataset.k}=${el.dataset.v}`);

// ---- fixtures, ladder, stats, clubs -----------------------------------------------------------
SCREENS.fixtures = {
  title: "Fixtures & results",
  load(arg) {
    const st = S.fix;
    return { fx: E.call("fixtures", { club: arg || null }), rd: E.call("round", { n: st.round }) };
  },
  view(d) {
    const st = S.fix, h = E.header, A = E.statics;
    let body;
    if (st.tab === "club") {
      body = panel(`${esc(club(d.fx.club).name)} ${h.year}`, table("fixtures", [
        { t: "Rd", f: r => typeof r.rnd === "number" ? r.rnd : esc(r.rnd) }, { t: "", f: r => r.at_home ? "H" : "A", c: "c" },
        { t: "Opponent", f: r => `<span class="row" style="gap:7px">${badge(r.opp, 22)} ${esc(club(r.opp).name)}</span>`, c: "name" },
        { t: "Venue", f: r => esc(r.venue) }, { t: "", f: r => r.res ? `<span class="res ${r.res}">${r.res}</span>` : "", c: "c" },
        { t: "Score", f: r => r.played ? `${score(r.us)} - ${score(r.them)}` : `<span class="faint">-</span>` },
        { t: "Best", f: r => r.played ? esc(r.best[0][0]) : "" }], d.fx.rows,
        { row: r => r.played ? `data-nav="match/${r.id}"` : "" }), { flush: true });
    } else if (st.tab === "finals") {
      const fin = E.call("round", { n: "finals" });
      body = fin.weeks.length ? fin.weeks.map(w => panel(esc(w.name), w.matches.map(m => matchRow(m, h.club)).join(""), { flush: true })).join("<div style='height:14px'></div>")
        : `<p class="muted">The finals have not started.</p>`;
    } else {
      const n = d.rd.round;
      body = `<div class="toolbar"><button class="btn" data-act="fixRound" data-v="${n - 1}" ${n <= 1 ? "disabled" : ""}>${icon("back")}</button>
        <b class="num" style="font-size:20px">ROUND ${n}</b><button class="btn" data-act="fixRound" data-v="${n + 1}" ${n >= A.limits.rounds ? "disabled" : ""} style="transform:scaleX(-1)">${icon("back")}</button></div>
        ${panel(`Round ${n}`, d.rd.matches.map(m => matchRow(m, h.club)).join(""), { flush: true })}`;
    }
    return `<div class="toolbar">${seg("fixTab", [["club", "Club fixture"], ["round", "Round by round"], ["finals", "Finals"]], st.tab)}
      ${st.tab === "club" ? `<select data-change="fixClub" class="right" aria-label="Club">${Object.values(A.clubs).map(x => `<option value="${x.id}" ${x.id === d.fx.club ? "selected" : ""}>${esc(x.full)}</option>`).join("")}</select>` : ""}</div>${body}`;
  },
};
ACTIONS.fixTab = (el, ctx) => { S.fix.tab = el.dataset.v; ctx.repaint(); };
ACTIONS.fixRound = (el, ctx) => { S.fix.round = +el.dataset.v; ctx.refresh(); };
ACTIONS.fixClub = (el, ctx) => ctx.go("fixtures/" + el.value);

SCREENS.ladder = {
  title: "Ladder",
  load: () => E.call("ladder"),
  view(d) {
    const h = E.header;
    return panel(`${h.year} premiership ladder`, table("ladder", [
      { t: "", f: r => r.pos, c: "r" }, { t: "Club", c: "name", f: r => `<span class="row" style="gap:8px">${badge(r.club, 24)} ${esc(club(r.club).full)}${d.premier === r.club ? ` <span class="tag cap">Premiers</span>` : ""}</span>` },
      { t: "P", f: r => r.P, c: "r" }, { t: "W", f: r => r.W, c: "r" }, { t: "L", f: r => r.L, c: "r" }, { t: "D", f: r => r.D, c: "r" },
      { t: "For", f: r => r.PF, c: "r" }, { t: "Agst", f: r => r.PA, c: "r" }, { t: "%", f: r => r.pct.toFixed(1), c: "r" },
      { t: "Pts", f: r => `<b>${r.pts}</b>`, c: "r" }, { t: "Last five", f: r => dots(r.form) }], d.rows,
      { row: r => `class="${r.club === h.club ? "me" : ""}${r.pos === 8 ? " cut" : ""}" data-nav="squad/${r.club}"` }),
      { flush: true, right: "Top eight play finals" });
  },
};

SCREENS.stats = {
  title: "Player stats",
  load: () => E.call("stats", { what: S.stats.what, club: S.stats.mine ? E.header.club : null }),
  view(d) {
    return `<div class="toolbar">${chips("statWhat", Object.entries(d.keys).map(([k, v]) => [k, v.replace("/game", "")]), d.what)}
        <label class="right row" style="gap:6px;cursor:pointer"><input type="checkbox" data-change="statMine" ${S.stats.mine ? "checked" : ""}> My club only</label></div>
      ${panel(esc(d.label), table("stats", [{ t: "", f: (r, i) => i + 1, c: "r" }, cName(), cClub, cPos, cAge, { t: "Gm", f: r => r.gm, c: "r" },
        { t: esc(d.label), f: r => `<b class="num" style="font-size:16px">${r.val}</b>`, c: "r" }, cOvr], d.rows, { row: pnav }), { flush: true })}`;
  },
};
ACTIONS.statWhat = (el, ctx) => { S.stats.what = el.dataset.v; ctx.refresh(); };
ACTIONS.statMine = (el, ctx) => { S.stats.mine = el.checked; ctx.refresh(); };

SCREENS.clubs = {
  title: "Clubs",
  load: () => E.call("clubs"),
  view: d => panel("The competition", table("clubs", [
    { k: "Rank", t: "List", n: 1, f: r => r.Rank, tip: "List strength rank" }, { k: "Club", t: "Club", c: "name", f: r => `<span class="row" style="gap:8px">${badge(r.ID, 24)} ${esc(r.Club)}</span>` },
    { k: "Best 22", t: "Best 22", n: 1 }, { k: "Avg age", t: "Avg age", n: 1 }, { k: "Young talent", t: "Kids", n: 1, tip: "Average potential of the five best players 21 and under" },
    { k: "Stars (85+)", t: "Stars", n: 1 }, { k: "Cap room", t: "Cap room", n: 1, f: r => money(r["Cap room"]) }, { k: "Members (k)", t: "Members", n: 1, f: r => r["Members (k)"] + "k" },
    { k: "Dev", t: "Dev", c: "c" }, { k: "Scout", t: "Scout", c: "c" }, { k: "Game plan", t: "Game plan" }], d.clubs,
    { sort: { k: "Rank", dir: 1 }, row: r => `class="${r.ID === E.header.club ? "me" : ""}" data-nav="squad/${r.ID}"` }), { flush: true }),
};

// ---- list management --------------------------------------------------------------------------
function capStrip(d) {
  const L = E.statics.limits;
  return `<div class="grid" style="margin-bottom:14px">
    <div class="panel s6"><div class="body gauge"><div class="row"><span class="upper">Salary cap</span><b class="num right">${money(d.payroll)} / ${money(d.cap)}</b></div>${meter(d.payroll / d.cap * 100, d.payroll > d.cap ? "low" : "club")}<span class="muted">${money(d.cap - d.payroll)} room · floor ${money(d.floor)}</span></div></div>
    <div class="panel s6"><div class="body gauge"><div class="row"><span class="upper">List spots</span><b class="num right">${d.senior + d.rookie} / ${L.list}</b></div>${meter((d.senior + d.rookie) / L.list * 100, "club")}<span class="muted">${d.senior} of ${L.senior} senior · ${d.rookie} of ${L.rookie} rookie</span></div></div></div>`;
}

SCREENS.contracts = {
  title: "Contracts",
  load: () => E.call("contracts"),
  view(d) {
    const rows = d.rows.filter(r => !S.con.ooc || r.ooc);
    const n = d.rows.filter(r => r.ooc).length;
    return `${capStrip(d)}<div class="toolbar">${chips("conFilter", [["all", "Whole list"], ["ooc", `Out of contract (${n})`]], S.con.ooc ? "ooc" : "all")}
        ${n ? `<button class="btn right" data-act="offerAll">Re-sign all at asking price</button>` : ""}</div>
      ${panel("Contracts", table("contracts", [cName(), cPos, cAge, cOvr, cPot, cWage,
        { k: "until", t: "Until", n: 1, f: r => r.ooc ? `<span class="tag ooc">${r.until}</span>` : r.until },
        { k: "ask", t: "Asking", n: 1, f: r => money(r.ask), tip: "Wage he wants on a new deal" }, { t: "Years", f: r => `${r.ymin}-${r.ymax}`, c: "c" }, cValue,
        { t: "", f: r => `${r.can_offer ? `<button class="btn small" data-act="offer" data-id="${r.id}">${r.ooc ? "Re-sign" : "Extend"}</button>` : ""} ${d.offseason ? `<button class="btn small danger" data-act="delist" data-id="${r.id}" data-name="${esc(r.name)}">Delist</button>` : ""}` }],
        rows, { sort: { k: "until", dir: 1 }, row: pnav }), { flush: true, right: d.offseason ? "Delisting is open" : "Delisting opens in the off-season" })}`;
  },
};
ACTIONS.conFilter = (el, ctx) => { S.con.ooc = el.dataset.v === "ooc"; ctx.repaint(); };
ACTIONS.offerAll = (el, ctx) => {
  const out = ctx.act("offer all", null, true);
  if (out) dialog({ title: "Contract round-up", body: `<pre style="white-space:pre-wrap;font:inherit;margin:0">${esc(out)}</pre>` });
};

function tradeList(side, players, picks, chosen) {
  const prow = p => `<div class="pickrow ${chosen.includes(p.id) ? "on" : ""}" data-act="tradePick" data-side="${side}" data-code="${p.id}">
    <span class="box">${chosen.includes(p.id) ? "✓" : ""}</span>${posTags(p.pos.slice(0, 1))}<span class="grow">${esc(p.name)} <span class="faint">${p.age}</span></span>${ovr(p.ovr)}<span class="muted" style="width:54px;text-align:right">${money(p.wage)}</span><b class="num" style="width:34px;text-align:right">${p.value}</b></div>`;
  const krow = k => `<div class="pickrow ${chosen.includes(k.code) ? "on" : ""}" data-act="tradePick" data-side="${side}" data-code="${k.code}">
    <span class="box">${chosen.includes(k.code) ? "✓" : ""}</span><span class="grow">${esc(k.label)} <span class="faint">about pick ${k.est}</span></span><b class="num" style="width:34px;text-align:right">${k.value}</b></div>`;
  return `<div class="scroll"><div class="upper" style="padding:8px 12px 2px">Draft picks</div>${picks.map(krow).join("")}
    <div class="upper" style="padding:10px 12px 2px">Players</div>${[...players].sort((a, b) => b.value - a.value).map(prow).join("")}</div>`;
}

SCREENS.trade = {
  title: "Trades",
  load(arg) {
    const st = S.trade, d = E.call("trade", { club: arg || st.club });
    if (st.club !== d.other) { st.club = d.other; st.give = []; st.get = []; st.verdict = null; }
    return d;
  },
  view(d) {
    const st = S.trade, A = E.statics, v = st.verdict;
    const other = club(d.other);
    const total = v ? Math.max(v.ai_in, v.ai_out, 1) : 1;
    const verdict = !st.give.length && !st.get.length ? `<p class="muted" style="margin:0">Tick what you would give and what you want. ${esc(other.name)} tell you straight away what they think.</p>`
      : v ? `<div class="statbar" style="grid-template-columns:44px 1fr 150px 1fr 44px"><b>${v.ai_in ?? 0}</b><div class="bar l ${v.ok ? "win" : ""}"><i style="width:${(v.ai_in || 0) / total * 100}%"></i></div>
          <span class="lbl">They value: yours / theirs</span><div class="bar r ${v.ok ? "" : "win"}"><i style="width:${(v.ai_out || 0) / total * 100}%"></i></div><b>${v.ai_out ?? 0}</b></div>
          <p class="${v.ok ? "good" : "warn"}" style="margin:8px 0 0"><b>${esc(v.msg)}</b></p>` : "";
    return `<div class="toolbar"><span class="upper">Trade partner</span>
        <select data-change="tradeClub" aria-label="Trade partner">${Object.values(A.clubs).filter(x => x.id !== d.me).map(x => `<option value="${x.id}" ${x.id === d.other ? "selected" : ""}>${esc(x.full)}</option>`).join("")}</select>
        <span class="muted">${esc(other.name)} are ${d.strategy === "rebuild" ? "rebuilding: they pay over the odds for picks and kids" : d.strategy === "contend" ? "contending: they want ready-made players" : "balanced buyers"}</span>
        <a class="right" data-nav="squad/${d.other}">Their squad</a></div>
      <section class="panel deal" style="margin-bottom:14px"><header><h2>The deal</h2><span class="right muted">${d.open ? "Trade period is open" : "Sounding out only: deals are done in the trade period"}</span></header>
        <div class="body">${verdict}<div class="row wrap" style="margin-top:12px">
          <button class="btn primary" data-act="tradeDo" ${d.open && v && v.ok ? "" : "disabled"}>Do the deal</button>
          <button class="btn" data-act="tradeClear" ${st.give.length || st.get.length ? "" : "disabled"}>Clear</button>
          <span class="muted right">Cap room: you ${money(d.room.me)} · them ${money(d.room.other)} · lists ${d.size.me} / ${d.size.other}</span></div></div></section>
      <div class="trade">
        ${panel(`You give (${st.give.length})`, tradeList("give", d.mine, d.my_picks, st.give), { flush: true, right: "value" })}
        ${panel(`You get (${st.get.length})`, tradeList("get", d.theirs, d.their_picks, st.get), { flush: true, right: "value" })}
      </div>`;
  },
};
function evalTrade(ctx, execute = false) {
  const st = S.trade;
  if (!st.give.length && !st.get.length) { st.verdict = null; return null; }
  try { st.verdict = ctx.call("trade_eval", { club: st.club, give: st.give, get: st.get, execute }, execute); }
  catch (e) { st.verdict = { ok: false, msg: e.message, ai_in: 0, ai_out: 0 }; }
  return st.verdict;
}
ACTIONS.tradePick = (el, ctx) => {
  const list = S.trade[el.dataset.side], raw = el.dataset.code, code = /^\d+$/.test(raw) ? +raw : raw;
  const i = list.indexOf(code);
  if (i >= 0) list.splice(i, 1); else list.push(code);
  evalTrade(ctx);
  ctx.repaint();
};
ACTIONS.tradeClear = (el, ctx) => { Object.assign(S.trade, { give: [], get: [], verdict: null }); ctx.repaint(); };
ACTIONS.tradeClub = (el, ctx) => ctx.go("trade/" + el.value);
ACTIONS.tradeDo = (el, ctx) => {
  const v = evalTrade(ctx, true);
  if (v && v.done) { toast("Trade done. " + v.msg); Object.assign(S.trade, { give: [], get: [], verdict: null }); ctx.refresh(); }
  else { toast(v ? v.msg : "Nothing to trade.", "err"); ctx.repaint(); }
};

SCREENS.draft = {
  title: "Draft",
  load: () => E.call("draft"),
  view(d) {
    const st = S.draft;
    const board = d.board.filter(p => inLine(p, st.pos));
    const banner = d.live ? (d.on_clock
      ? `<section class="panel" style="margin-bottom:14px"><div class="body row wrap">${badge(d.on_clock.owner, 40)}<div class="grow"><div class="upper">On the clock · pick ${d.on_clock.n} · round ${d.on_clock.round}</div>
          <b class="num" style="font-size:24px">${esc(club(d.on_clock.owner).full)}</b></div>
          ${d.my_turn ? `<button class="btn primary" data-act="draftPick">Take the best available</button>` : ""}</div></section>`
      : `<section class="panel" style="margin-bottom:14px"><div class="body"><b>The draft is complete.</b> <span class="muted">Start the new season when you are ready.</span></div></section>`)
      : `<p class="muted">The ${d.year} draft is held after the trade period. The order is set by the final ladder: wooden-spooners first, premiers last. Scout the board any time.</p>`;
    const cols = [{ k: "rank", t: "#", n: 1, s: r => -r.rank }, cName(), cPos, cAge, { k: "ht", t: "Ht", n: 1 }, cOvr,
      { k: "pot", t: "Potential", n: 1, f: r => `${ovr(r.lo)} <span class="faint">to</span> ${ovr(r.hi)}`, tip: "Your recruiters' range. They are sometimes wrong." },
      { t: "", f: r => d.my_turn ? `<button class="btn small primary" data-act="draftPick" data-id="${r.id}">Draft</button>` : "" }];
    return `${banner}<div class="grid">
      <section class="panel s8"><header><h2>Draft board</h2><span class="right">${chips("draftPos", LINES, st.pos)}</span></header>
        <div class="body flush" style="max-height:70vh;overflow:auto">${table("draft-board", cols, board, { sort: { k: "rank", dir: -1 }, row: pnav })}</div></section>
      <div class="s4 col">
        ${panel("Your picks", d.picks.length ? d.picks.map(k => `<div class="row" style="padding:4px 0"><span class="grow">${esc(k.label)}</span><span class="muted">about pick ${k.est}</span><b class="num" style="width:34px;text-align:right">${k.value}</b></div>`).join("") : `<p class="muted" style="margin:0">You hold no picks.</p>`, { right: `list ${d.size}/${E.statics.limits.list}` })}
        ${d.live && d.upcoming.length ? panel("Coming up", d.upcoming.map(o => `<div class="row" style="padding:3px 0"><b class="num" style="width:26px">${o.n}</b>${badge(o.owner, 20)}<span class="${o.owner === E.header.club ? "" : "muted"}">${esc(club(o.owner).name)}</span></div>`).join("")) : ""}
        ${d.log.length ? panel("Selections", `<div style="max-height:44vh;overflow:auto">${[...d.log].reverse().map(([n, cid, pid, name, pos, age]) => `<a class="row" data-nav="player/${pid}" style="padding:4px 14px;color:var(--text);cursor:pointer"><b class="num" style="width:26px">${n}</b>${badge(cid, 20)}<span class="grow">${esc(name)}</span><span class="muted">${pos} ${age}</span></a>`).join("")}</div>`, { flush: true }) : ""}
      </div></div>`;
  },
};
ACTIONS.draftPos = (el, ctx) => { S.draft.pos = el.dataset.v; ctx.repaint(); };
ACTIONS.draftPick = (el, ctx) => {
  try {
    const r = ctx.call("draft_pick", el.dataset.id ? { id: +el.dataset.id } : {}, true);
    toast(`${r.text} His true potential: ${r.pot}.`);
    if (ctx.route.name === "draft") ctx.refresh(); else ctx.go("draft");
  } catch (e) { toast(e.message, "err"); }
};

SCREENS.agents = {
  title: "Free agents",
  load: () => E.call("agents"),
  view: d => `<p class="muted">Delisted and uncontracted players. You have ${money(d.room)} of cap room and ${E.statics.limits.list - d.size} list spot(s) free.</p>
    ${panel("Available now", table("agents", [cName(), cPos, cAge, cOvr, cPot, { k: "ask", t: "Asking", n: 1, f: r => money(r.ask) }, { t: "Years", f: r => `${r.ymin}-${r.ymax}`, c: "c" }, cValue,
      { t: "", f: r => `<button class="btn small" data-act="offer" data-id="${r.id}">Sign</button>` }], d.rows, { sort: { k: "ovr", dir: -1 }, row: pnav }), { flush: true })}`,
};

// ---- club -------------------------------------------------------------------------------------
SCREENS.club = {
  title: "Board & finances",
  load: () => E.call("club"),
  view(d) {
    const b = d.board, h = E.header;
    const mood = b.confidence >= 70 ? "right behind you" : b.confidence >= 50 ? "comfortable" : b.confidence >= 30 ? "getting nervous" : "close to making a change";
    const fin = table("finance", [{ t: "", f: r => esc(r.Line), c: "name" }, { t: "Last round", f: r => money(r["Last round"]), c: "r" },
      { t: "Season", f: r => `<span class="${r.Season < 0 ? "bad" : "good"}">${money(r.Season)}</span>`, c: "r" }], d.finance);
    const hist = d.history.length ? table("history", [{ t: "Year", f: r => r.year }, { t: "Premier", f: r => `<span class="row" style="gap:7px">${badge(r.premier, 20)} ${esc(club(r.premier).name)}</span>` },
      { t: "Runner-up", f: r => esc(club(r.runner_up).name) }, { t: "Brownlow", f: r => `${esc(r.awards.brownlow[0])} (${r.awards.brownlow[1]})` },
      { t: "Coleman", f: r => `${esc(r.awards.coleman[0])} ${r.awards.coleman[2]}` },
      { t: "You", f: r => r.user ? `${r.user.club} ${ordinal(r.user.pos)} (${r.user.w}-${r.user.l}) ${esc(r.user.finish || "")}` : "" }], [...d.history].reverse())
      : `<p class="muted" style="padding:14px;margin:0">No completed seasons yet.</p>`;
    return `<div class="grid">
      ${panel("The board", `<div class="gauge"><div class="row"><span class="upper">Confidence in you</span><b class="num right" style="font-size:22px">${Math.round(b.confidence)}/100</b></div>${meter(b.confidence, b.confidence < 30 ? "low" : b.confidence < 50 ? "mid" : "")}</div>
        <dl class="kv" style="margin-top:12px"><dt>Mood</dt><dd>The board is ${mood}</dd><dt>Expectation</dt><dd>${esc(b.label)}</dd><dt>List rated</dt><dd>${ordinal(b.list_rank || 9)} in the league</dd><dt>Currently</dt><dd>${ordinal(d.pos)} on the ladder</dd>
        <dt>Members</dt><dd>${d.members}k</dd><dt>Development program</dt><dd>${d.dev}</dd><dt>Recruiting</dt><dd>${d.recruit}</dd></dl>`, { cls: "s5" })}
      ${panel("Finances", fin + `<div style="padding:12px 14px"><dl class="kv"><dt>Season result so far</dt><dd class="${d.profit < 0 ? "bad" : "good"}">${money(d.profit)}</dd><dt>In the bank</dt><dd>${money(d.balance)}</dd><dt>Player payments</dt><dd>${money(d.payroll)} of ${money(d.cap)} (floor ${money(d.floor)})</dd></dl></div>`, { cls: "s7", flush: true, right: "$ thousands" })}
      ${d.review ? panel(`${h.year} season review`, reviewBlock(d.review, { premier: d.history.length ? d.history[d.history.length - 1].premier : null, awards: d.history.length ? d.history[d.history.length - 1].awards : {} }), { cls: "s12" }) : ""}
      ${panel("Honour roll", hist, { cls: "s12", flush: true })}</div>`;
  },
};
