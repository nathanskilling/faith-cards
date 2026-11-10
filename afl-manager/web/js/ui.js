// Small view helpers shared by every screen.  Screens build HTML strings; clicks
// are handled by delegation on data-nav / data-act attributes (see main.js).
import { statics } from "./engine.js";

export const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const money = k => (k < 0 ? "-" : "") + (Math.abs(k) >= 1000 ? `$${(Math.abs(k) / 1000).toFixed(2)}M` : `$${Math.round(Math.abs(k))}k`);
export const ordinal = n => n + (n % 100 >= 11 && n % 100 <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] || "th");
export const club = id => statics.clubs[id] || { id, name: id, full: id, c: ["#444", "#888", "#ccc"] };
export const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

function luminance(hex) {
  const n = parseInt(hex.slice(1), 16);
  const [r, g, b] = [n >> 16, (n >> 8) & 255, n & 255].map(v => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; });
  return .2126 * r + .7152 * g + .0722 * b;
}
export const inkOn = hex => luminance(hex) > .42 ? "#111111" : "#ffffff";

// Club colours drive the accent.  On a dark page use the club's bright colour,
// on a light page the darkest of its colours so text stays readable.
export function applyClubTheme(id) {
  const root = document.documentElement;
  const light = root.dataset.theme === "light" ||
    (root.dataset.theme !== "dark" && matchMedia("(prefers-color-scheme: light)").matches);
  const c = id ? club(id).c : ["#1d5a3c", "#ffffff", "#f2a900"];
  let fill = c[2], text = c[2];
  if (light) {
    const dark = [c[0], c[1], c[2]].filter(x => luminance(x) < .22).sort((a, b) => luminance(b) - luminance(a));
    fill = text = dark[0] || "#1d5a3c";
    if (luminance(fill) < .02) { fill = "#1b1f1d"; text = "#1b1f1d"; }
  }
  root.style.setProperty("--club", fill);
  root.style.setProperty("--club-ink", inkOn(fill));
  root.style.setProperty("--club-text", text);
}

export function badge(id, size = 34) {
  const c = club(id);
  return `<span class="badge" style="--sz:${size}px;--c1:${c.c[0]};--c2:${c.c[1]};--ct:${inkOn(c.c[0])}" title="${esc(c.full)}"><span>${esc(id)}</span></span>`;
}

const ICONS = {
  home: "M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
  inbox: "M3 13l3-8h12l3 8v6H3zM3 13h5l1 3h6l1-3h5",
  squad: "M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM2 20c0-3 3-5 6-5s6 2 6 5M17 11a2.5 2.5 0 1 0 0-5M16 15c3 0 6 1.6 6 5",
  team: "M12 3c4.4 0 8 4 8 9s-3.6 9-8 9-8-4-8-9 3.600-9 8-9zM4 12h16M12 3v18",
  plan: "M4 20V4M4 5h11l-2 3.500 2 3.500H4M14 19l4-4M18 19l-4-4",
  match: "M12 3c5 0 9 4 9 9s-4 9-9 9-9-4-9-9 4-9 9-9zM7 7l10 10M9.500 5.500l9 9M5.500 9.500l9 9",
  fixtures: "M4 6h16v14H4zM4 10h16M8 3v4M16 3v4",
  ladder: "M4 6h16M4 12h16M4 18h10",
  stats: "M5 20V10M12 20V4M19 20v-7",
  clubs: "M12 3l8 3v6c0 4.500-3.300 8-8 9-4.700-1-8-4.500-8-9V6z",
  contracts: "M6 3h9l4 4v14H6zM14 3v5h5M9 13h7M9 17h5",
  trade: "M4 8h14l-3-3M20 16H6l3 3",
  draft: "M12 3l2.700 5.600 6.100.900-4.400 4.300 1 6.100L12 17l-5.400 2.900 1-6.100L3.200 9.500l6.100-.900z",
  agents: "M10 11a3.500 3.500 0 1 0 0-7 3.500 3.500 0 0 0 0 7zM3 20c0-3.300 3.200-5.500 7-5.500 1.300 0 2.500.300 3.600.700M18 14v6M15 17h6",
  club: "M4 20V9l8-5 8 5v11M9 20v-6h6v6",
  settings: "M12 15.500a3.500 3.500 0 1 0 0-7 3.500 3.500 0 0 0 0 7zM19 12a7 7 0 0 0-.100-1.300l2-1.500-2-3.400-2.300.900a7 7 0 0 0-2.300-1.300L14 3h-4l-.300 2.400a7 7 0 0 0-2.300 1.300l-2.300-.900-2 3.400 2 1.500a7 7 0 0 0 0 2.600l-2 1.500 2 3.400 2.300-.900a7 7 0 0 0 2.300 1.300L10 21h4l.300-2.400a7 7 0 0 0 2.300-1.300l2.300.900 2-3.400-2-1.500c.100-.400.100-.900.100-1.300z",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4",
  play: "M7 4l13 8-13 8z", more: "M5 12h.010M12 12h.010M19 12h.010", down: "M6 9l6 6 6-6", back: "M15 5l-7 7 7 7",
};
export const icon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${ICONS[name] || ICONS.more}"/></svg>`;

// ---- small data marks ------------------------------------------------------------
const LINE = { KD: "D", GD: "D", WG: "M", MD: "M", RK: "R", GF: "F", KF: "F" };
export const posLine = pos => LINE[statics.pos_group[pos]] || "M";
export const posTags = list => list.map((p, i) => `<span class="pos ${posLine(p)}${i ? " alt" : ""}" title="${esc(statics.pos_name[p])}">${p}</span>`).join(" ");
export const tier = v => v >= 85 ? 5 : v >= 78 ? 4 : v >= 70 ? 3 : v >= 62 ? 2 : 1;
export const ovr = (v, big) => `<span class="ovr t${tier(v)}${big ? " big" : ""}">${v}</span>`;
export const attrClass = v => "a" + (v >= 17 ? 5 : v >= 14 ? 4 : v >= 11 ? 3 : v >= 8 ? 2 : 1);
const fitClass = v => v < 72 ? "low" : v < 86 ? "mid" : "";
export const fit = v => `<span class="fit"><span class="meter"><i class="${fitClass(v)}" style="width:${v}%"></i></span>${v}</span>`;
export const meter = (pct, cls = "") => `<div class="meter"><i class="${cls}" style="width:${Math.max(0, Math.min(100, pct))}%"></i></div>`;
export const dots = arr => `<span class="dots">${(arr || []).map(r => `<i class="${r}">${r}</i>`).join("")}</span>`;

export function form(p) {
  if (p.form != null) return `<span class="frm ${p.form >= 7 ? "hot" : p.form < 5.2 ? "cold" : ""}">${p.form.toFixed(1)}</span>`;
  if (p.res) return `<span class="frm res" title="Last reserves game">r${p.res.toFixed(1)}</span>`;
  return `<span class="faint">-</span>`;
}
export function spark(forms) {
  if (!forms || !forms.length) return "";
  return `<span class="spark">${forms.map(v => `<i class="${v >= 7 ? "hi" : v < 5.2 ? "lo" : ""}" style="height:${Math.max(3, (v - 2) / 8 * 18)}px" title="${v}"></i>`).join("")}</span>`;
}
export function nameCell(p, opts = {}) {
  const tags = [];
  if (opts.captain === p.id) tags.push(`<span class="tag cap" title="Captain">C</span>`);
  if (p.inj) tags.push(`<span class="tag inj" title="${esc(p.inj[0])}">${esc(p.inj[0])} ${p.inj[1]}w</span>`);
  if (p.rookie) tags.push(`<span class="tag rk" title="Rookie list">R</span>`);
  return `${esc(p.name)} ${tags.join(" ")}`;
}
export const score = s => `${s[0]}.${s[1]} <b>${s[2]}</b>`;

// ---- sortable tables --------------------------------------------------------------
// cols: { k: key, t: title, n: numeric, f: row => html, s: row => sort value, c: class, tip }
const sortState = {};
export function setSort(id, key) {
  const cur = sortState[id];
  sortState[id] = cur && cur.k === key ? { k: key, dir: -cur.dir } : { k: key, dir: 0 };
}
export function table(id, cols, rows, opts = {}) {
  const st = sortState[id] || opts.sort;
  let sorted = rows;
  if (st) {
    const col = cols.find(c => c.k === st.k);
    if (col) {
      const val = col.s || (r => r[col.k]);
      const dir = st.dir || (col.n ? -1 : 1);
      sorted = [...rows].sort((a, b) => {
        const x = val(a), y = val(b);
        if (x == null && y == null) return 0;
        if (x == null) return 1;
        if (y == null) return -1;
        return (x < y ? -1 : x > y ? 1 : 0) * dir;
      });
    }
  }
  const head = cols.map(c => `<th class="${c.c || (c.n ? "r" : "")}${st && st.k === c.k ? " sorted" : ""}"${c.k ? ` data-sort="${id}:${c.k}"` : ""}${c.tip ? ` title="${esc(c.tip)}"` : ""}>${c.t}</th>`).join("");
  const body = sorted.map((r, i) => `<tr ${opts.row ? opts.row(r, i) : ""}>${cols.map(c => `<td class="${c.c || (c.n ? "r" : "")}">${c.f ? c.f(r, i) : (r[c.k] ?? "")}</td>`).join("")}</tr>`).join("");
  return `<div class="tblwrap"><table class="tbl"><thead><tr>${head}</tr></thead><tbody>${body || `<tr><td colspan="${cols.length}" class="muted">Nothing to show.</td></tr>`}</tbody></table></div>`;
}

export const panel = (title, body, opts = {}) =>
  `<section class="panel ${opts.cls || ""}"><header><h2>${title}</h2>${opts.right ? `<span class="right muted">${opts.right}</span>` : ""}</header><div class="body${opts.flush ? " flush" : ""}">${body}</div></section>`;
export const seg = (act, options, value, attrs = "") =>
  `<div class="seg">${options.map(o => { const [v, label] = Array.isArray(o) ? o : [o, o]; return `<button class="${v === value ? "on" : ""}" data-act="${act}" data-v="${esc(v)}" ${attrs}>${esc(label)}</button>`; }).join("")}</div>`;
export const chips = (act, options, value) =>
  `<div class="chips">${options.map(o => { const [v, label] = Array.isArray(o) ? o : [o, o]; return `<button class="chip ${v === value ? "on" : ""}" data-act="${act}" data-v="${esc(v)}">${esc(label)}</button>`; }).join("")}</div>`;

// ---- toasts and dialogs -------------------------------------------------------------
export function toast(msg, kind = "") {
  let box = document.querySelector(".toasts");
  if (!box) { box = document.createElement("div"); box.className = "toasts"; document.body.appendChild(box); }
  const el = document.createElement("div");
  el.className = "toast " + kind;
  el.textContent = msg;
  box.appendChild(el);
  while (box.children.length > 2) box.firstChild.remove();      // never bury the screen in notes
  setTimeout(() => el.remove(), kind === "err" ? 6500 : 3400);
}

// dialog({title, body, actions: [{label, primary, danger, run}]}) -> closes on any action
export function dialog({ title, body, actions = [{ label: "Close" }] }) {
  closeDialog();
  const scrim = document.createElement("div");
  scrim.className = "scrim";
  scrim.innerHTML = `<div class="dialog" role="dialog" aria-modal="true"><header><h2>${title}</h2></header><div class="body">${body}</div>
    <footer>${actions.map((a, i) => `<button class="btn ${a.primary ? "primary" : ""} ${a.danger ? "danger" : ""}" data-i="${i}">${esc(a.label)}</button>`).join("")}</footer></div>`;
  scrim.addEventListener("click", e => {
    const b = e.target.closest("button[data-i]");
    if (b) {
      const a = actions[+b.dataset.i];
      const keep = a.run && a.run(scrim) === false;
      if (!keep) closeDialog();
    } else if (e.target === scrim) closeDialog();
  });
  document.body.appendChild(scrim);
  return scrim;
}
export const closeDialog = () => document.querySelectorAll(".scrim").forEach(el => el.remove());
export function busy(text) {
  let el = document.querySelector(".busy");
  if (!text) { if (el) el.remove(); return; }
  if (!el) { el = document.createElement("div"); el.className = "busy"; el.innerHTML = "<div></div>"; document.body.appendChild(el); }
  el.firstChild.textContent = text;
}
export const nextFrame = () => new Promise(r => requestAnimationFrame(() => setTimeout(r, 0)));
