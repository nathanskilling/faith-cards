// Bridge to the game engine.
//
// The engine is the Python package in ../../aflm, run unchanged in the browser
// by Pyodide (CPython compiled to WebAssembly).  The app only ever talks to it
// through call(op, args), which returns plain JSON - see aflm/webapi.py.
// Careers are kept in the browser's IndexedDB and can be exported to a file.

const PYODIDE_VERSION = "0.28.3";
const PYODIDE_BASE = window.AFLM_PYODIDE_BASE || `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

let handle = null;      // aflm.webapi.handle
let dump = null;        // aflm.webapi.dump
export let header = null;   // latest header returned by the engine (club, phase, ladder spot ...)
export let statics = null;  // clubs, positions, tactic descriptions: never change

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = src;
    s.onload = resolve;
    s.onerror = () => reject(new Error("Could not load " + src));
    document.head.appendChild(s);
  });
}

export async function startEngine(progress = () => {}) {
  progress("Warming up the engine", 15);
  await loadScript(PYODIDE_BASE + "pyodide.js");
  const py = await window.loadPyodide({ indexURL: PYODIDE_BASE });
  progress("Loading the rule book", 70);
  const res = await fetch("web/engine.json", { cache: "no-cache" });
  if (!res.ok) throw new Error("Could not load the game engine (web/engine.json).");
  const bundle = await res.json();
  py.FS.mkdirTree("/app/aflm");
  for (const [name, src] of Object.entries(bundle.files)) py.FS.writeFile("/app/aflm/" + name, src);
  py.runPython("import sys\nsys.path.insert(0, '/app')\nimport aflm.webapi as _aflm_api");
  const api = py.globals.get("_aflm_api");
  handle = api.handle;
  dump = api.dump;
  progress("Ready", 100);
  statics = call("boot").static;
  return bundle.version;
}

export class EngineError extends Error {}

// Run one engine request.  Throws EngineError with a message fit to show the user.
export function call(op, args = {}) {
  const res = JSON.parse(handle(JSON.stringify({ op, args })));
  if (res.header !== undefined) header = res.header;
  if (!res.ok) {
    if (res.trace) console.error(res.trace);
    throw new EngineError(res.error || "Something went wrong.");
  }
  return res.data;
}

export const saveString = () => dump();

// ---- storage: IndexedDB with a tiny promise wrapper --------------------------
const DB = "afl-manager", STORE = "saves";

function db() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function tx(mode, fn) {
  const d = await db();
  return new Promise((resolve, reject) => {
    const t = d.transaction(STORE, mode);
    const req = fn(t.objectStore(STORE));
    t.oncomplete = () => resolve(req && req.result);
    t.onerror = () => reject(t.error);
  });
}

export const store = {
  async get(key) { try { return await tx("readonly", s => s.get(key)); } catch { return null; } },
  async set(key, value) { try { await tx("readwrite", s => s.put(value, key)); return true; } catch { return false; } },
  async del(key) { try { await tx("readwrite", s => s.delete(key)); } catch { /* nothing to delete */ } },
};

// Autosave: writes are coalesced so a burst of changes costs one serialisation.
let saveTimer = null, saving = false, lastSaved = null;
const listeners = new Set();
export const onSaved = fn => listeners.add(fn);

export function scheduleSave(delay = 900) {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveNow, delay);
}

export async function saveNow() {
  clearTimeout(saveTimer);
  saveTimer = null;
  if (!handle || !header || saving) return;
  saving = true;
  try {
    const ok = await store.set("career", saveString());
    lastSaved = ok ? new Date() : null;
    listeners.forEach(fn => fn(ok));
  } finally { saving = false; }
}

export const lastSavedAt = () => lastSaved;
document.addEventListener("visibilitychange", () => { if (document.hidden && saveTimer) saveNow(); });
window.addEventListener("pagehide", () => { if (saveTimer) saveNow(); });
