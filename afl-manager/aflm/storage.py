"""Save / load a career as a folder of JSON files.

    saves/<name>/meta.json      year, phase, round, user club, cap ...
    saves/<name>/clubs.json     18 clubs (tactics, lineup, board, finances)
    saves/<name>/players.json   every player, one per line (diff friendly)
    saves/<name>/season.json    this year's fixture and results
    saves/<name>/draft.json     pick ownership, prospect pool, live draft state
    saves/<name>/history.json   past seasons, free agents and the news feed

JSON was chosen over SQLite so saves are human readable, easy to hand-edit
and merge nicely in git.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .models import Game, Player, Club
from . import constants as C

SAVE_ROOT = Path(os.environ.get("AFLM_SAVES", Path(__file__).resolve().parent.parent / "saves"))
POINTER = "current.txt"     # remembers which save the CLI is working on


def save_dir(name: str) -> Path:
    return SAVE_ROOT / name


def _write(path: Path, obj, one_per_line: bool = False) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        if one_per_line:
            f.write("[\n" + ",\n".join(json.dumps(o, separators=(",", ":")) for o in obj) + "\n]\n")
        else:
            json.dump(obj, f, indent=1)
    tmp.replace(path)       # atomic: a crash never leaves a half-written file


def to_bundle(game: Game) -> dict:
    """The whole career as one JSON-ready object (same sections as the save folder)."""
    game.meta["version"] = C.SAVE_VERSION
    return {"meta": game.meta, "clubs": [c.to_dict() for c in game.clubs.values()],
            "players": [p.to_dict() for p in game.players.values()], "season": game.season,
            "draft": game.draft,
            "history": {"history": game.history, "free_agents": game.free_agents, "news": game.news}}


def from_bundle(b: dict) -> Game:
    g = Game()
    g.meta = b["meta"]
    g.clubs = {c["id"]: Club.from_dict(c) for c in b["clubs"]}
    g.players = {p["id"]: Player.from_dict(p) for p in b["players"]}
    g.season, g.draft = b["season"], b["draft"]
    h = b["history"]
    g.history, g.free_agents, g.news = h["history"], h["free_agents"], h["news"]
    return g


def save_game(game: Game, name: str | None = None) -> Path:
    name = name or game.meta.get("save_name", "career")
    game.meta["save_name"] = name
    b = to_bundle(game)
    d = save_dir(name)
    d.mkdir(parents=True, exist_ok=True)
    for section in ("meta", "clubs", "season", "draft", "history"):
        _write(d / f"{section}.json", b[section])
    _write(d / "players.json", b["players"], one_per_line=True)
    (SAVE_ROOT / POINTER).write_text(name)
    return d


def load_game(name: str | None = None) -> Game:
    name = name or current_save()
    if not name:
        raise FileNotFoundError("No save found. Start one with: python play.py new")
    d = save_dir(name)
    if not (d / "meta.json").exists():
        raise FileNotFoundError(f"No save called '{name}' in {SAVE_ROOT}")

    def read(fn):
        with open(d / fn, encoding="utf-8") as f:
            return json.load(f)

    return from_bundle({s: read(f"{s}.json") for s in
                        ("meta", "clubs", "players", "season", "draft", "history")})


def current_save() -> str | None:
    p = SAVE_ROOT / POINTER
    if p.exists():
        name = p.read_text().strip()
        if (save_dir(name) / "meta.json").exists():
            return name
    saves = list_saves()
    return saves[0] if saves else None


def list_saves() -> list[str]:
    if not SAVE_ROOT.exists():
        return []
    return sorted(p.name for p in SAVE_ROOT.iterdir() if (p / "meta.json").exists())
