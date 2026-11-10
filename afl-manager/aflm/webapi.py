"""JSON API for the browser app.

The app runs this package inside the browser (Pyodide) and talks to it through
one function::

    handle('{"op": "squad", "args": {"club": "GEE"}}')  ->  '{"ok": true, "data": ..., "header": ...}'

Views return plain data for the UI to draw; actions go through the same rule
code the text commands use, so the two front ends can never disagree.  Keeping
the UI behind this narrow interface also means the engine could later move to a
server, or be rewritten, without touching the screens.
"""
from __future__ import annotations

import json
import random
import traceback

from . import assistant, constants as C, finance, generator, offseason, season, storage, views
from . import commands
from .commands import CmdError
from .models import Game, Player
from .ratings import (ovr, overall, shown_potential, form_value, slot_rating, raw_rating,
                      auto_select, lineup_problems, available, best22_rating)

_game: Game | None = None
_rng = random.Random()


def G() -> Game:
    if _game is None:
        raise CmdError("No career loaded.")
    return _game


# -- shared row builders -------------------------------------------------------
def _prow(g: Game, p: Player) -> dict:
    s = p.stats.get(str(g.year), {})
    gm = s.get("gm", 0)
    return {
        "id": p.id, "name": p.name, "short": p.short, "pos": p.positions, "grp": C.POS_GROUP[p.pos],
        "age": p.age, "ht": p.height, "ovr": ovr(p), "pot": shown_potential(g, p),
        "fit": int(round(p.fitness)), "form": round(form_value(p), 1) if p.form else None,
        "forms": p.form, "res": p.reserves or None, "sel": views.slot_of(g, p),
        "inj": [p.injury["type"], p.injury["weeks"]] if p.injury else None,
        "rookie": p.rookie, "club": p.club, "status": p.status,
        "gm": gm, "g": s.get("g", 0),
        "disp": round((s.get("k", 0) + s.get("hb", 0)) / gm, 1) if gm else None,
        "rt": round(s.get("rt", 0) / gm, 2) if gm else None, "v": s.get("v", 0),
        "wage": p.wage, "until": p.contract_end, "value": int(round(offseason.player_value(g, p))),
        "a": [int(round(p.attrs[k])) for k in C.ATTRS],
    }


def _mrow(g: Game, m: dict) -> dict:
    out = {k: m.get(k) for k in ("id", "rnd", "home", "away", "venue", "played")}
    out["label"] = _round_label(m["rnd"])
    if m["played"]:
        out.update(hs=m["hs"], **{"as": m["as"]}, best=m["best"], gk=m["gk"], att=m["att"],
                   wet=m["wet"], detail="detail" in m)
    return out


def _round_label(rnd) -> str:
    if isinstance(rnd, int):
        return f"Round {rnd}"
    return {"QF": "Qualifying Final", "EF": "Elimination Final", "SF": "Semi Final",
            "PF": "Preliminary Final", "GF": "Grand Final"}[rnd[:2]]


def _last5(g: Game) -> dict:
    """club -> list of recent results ('W' / 'L' / 'D'), oldest first."""
    out = {cid: [] for cid in g.clubs}
    for rd in g.season["rounds"]:
        for m in rd:
            if m["played"]:
                hp, ap = m["hs"][2], m["as"][2]
                out[m["home"]].append("W" if hp > ap else "L" if hp < ap else "D")
                out[m["away"]].append("W" if ap > hp else "L" if ap < hp else "D")
    return {cid: r[-5:] for cid, r in out.items()}


def _continue_label(g: Game) -> str:
    ph = g.phase
    if g.meta.get("sacked"):
        return "Find a new club"
    if ph == "season":
        return f"Play Round {g.meta['round']}"
    if ph == "finals":
        return "Play " + g.season["finals"][-1]["name"]
    return {"review": "Open contract talks", "contracts": "End signing period",
            "trades": "Go to the draft", "draft": "Start next season"}[ph]


def header() -> dict | None:
    g = _game
    if g is None:
        return None
    h = {"year": g.year, "phase": g.phase, "has_club": bool(g.user), "sacked": bool(g.meta.get("sacked")),
         "selection": g.meta.get("selection", "auto"), "manager": g.meta.get("manager", ""),
         "save_name": g.meta.get("save_name", "career"), "seed": g.meta.get("seed"),
         "round": g.meta.get("round"), "cap": g.cap}
    club = g.user
    if club:
        rec = views.record(g, club.id)
        h.update(club=club.id, phase_label=commands.phase_label(g), cont=_continue_label(g),
                 pos=rec["pos"], record=f"{rec['W']}-{rec['L']}-{rec['D']}", pct=round(rec["pct"], 1),
                 confidence=round(club.board["confidence"]), payroll=g.payroll(club.id),
                 balance=club.balance, unsigned=len(offseason.out_of_contract(g, club.id)),
                 injured=sum(1 for p in g.squad(club.id) if p.injury))
        slot = offseason.draft_on_clock(g) if g.phase == "draft" else None
        h["on_clock"] = bool(slot and slot["owner"] == club.id)
    return h


# -- career management ---------------------------------------------------------
def op_boot() -> dict:
    return {"has_game": _game is not None, "static": _static()}


def _static() -> dict:
    """Things that never change: positions, tactics text, club identity."""
    clubs = {}
    for cid, name, nick, ground, state, colours, _sup in C.CLUBS:
        full = name if nick in name else f"{name} {nick}"
        clubs[cid] = {"id": cid, "name": name, "nick": nick, "full": full, "ground": ground,
                      "state": state, "colours": colours, "c": list(C.CLUB_COLOURS[cid])}
    return {"clubs": clubs, "attrs": C.ATTRS, "attr_label": C.ATTR_LABEL, "attr_short": C.ATTR_SHORT,
            "pos_name": C.POS_NAME, "pos_group": C.POS_GROUP, "group_name": C.GROUP_NAME,
            "pos_types": C.POS_TYPES, "field_slots": C.FIELD_SLOTS, "bench_slots": C.BENCH_SLOTS,
            "tactics": C.TACTIC_OPTIONS, "presets": C.PHILOSOPHIES,
            "focus": {k: v[0] for k, v in C.TRAINING_FOCUS.items()},
            "intensity": {"light": "Fresh legs, slower development.", "normal": "A standard week.",
                          "heavy": "Faster development, slower recovery, more soft-tissue injuries."},
            "limits": {"senior": C.SENIOR_MAX, "rookie": C.ROOKIE_MAX, "list": C.LIST_MAX,
                       "rounds": C.HA_ROUNDS}}


def op_new(seed=None) -> dict:
    global _game
    _game = generator.new_game(seed=int(seed) if seed else None)
    return {"clubs": views.club_rows(_game)}


def op_load(bundle: str) -> dict:
    global _game
    data = json.loads(bundle) if isinstance(bundle, str) else bundle
    if not isinstance(data, dict) or "meta" not in data or "players" not in data:
        raise CmdError("That file is not an AFL Manager save.")
    _game = storage.from_bundle(data)
    return {}


def dump() -> str:
    """The whole career as a JSON string (called by the app to autosave)."""
    return json.dumps(storage.to_bundle(G()), separators=(",", ":"))


def op_clubs() -> dict:
    g = G()
    return {"clubs": views.club_rows(g),
            "offers": offseason.job_offers(g) if g.meta.get("sacked") else None}


def op_choose(club: str, name: str = "") -> dict:
    out = commands.cmd_choose(G(), [club] + (name.split() if name else []))
    return {"text": out}


# -- screens -------------------------------------------------------------------
def op_home() -> dict:
    g = G()
    club = g.user
    cid = club.id
    commands.refresh_auto_lineup(g)
    lad = season.ladder(g)
    last5 = _last5(g)
    pos = next(r["pos"] for r in lad if r["club"] == cid)
    lo = max(0, min(len(lad) - 7, pos - 4))
    rows = [{**r, "pct": round(r["pct"], 1), "form": last5[r["club"]]} for r in lad[lo:lo + 7]]
    nxt = season.next_match(g, cid)
    nxt_view = None
    if nxt:
        opp = nxt["away"] if nxt["home"] == cid else nxt["home"]
        orec = next(r for r in lad if r["club"] == opp)
        mine, theirs = views.team_summary(g, cid), None
        g.clubs[opp].lineup = auto_select(g, opp, 0.25 if g.clubs[opp].strategy == "rebuild" else 0.0)
        theirs = views.team_summary(g, opp)
        nxt_view = {"id": nxt["id"], "label": _round_label(nxt["rnd"]), "opp": opp, "home": nxt["home"] == cid,
                    "venue": nxt["venue"], "win": round(views.win_chance(g, nxt, cid) * 100),
                    "opp_pos": orec["pos"], "opp_rec": f"{orec['W']}-{orec['L']}", "opp_form": last5[opp],
                    "lines": {"me": [mine["def"], mine["mid"], mine["fwd"]],
                              "opp": [theirs["def"], theirs["mid"], theirs["fwd"]]},
                    "opp_plan": g.clubs[opp].philosophy}
    played = [m for m in season.club_matches(g, cid) if m["played"]]
    squad = g.squad(cid)
    in_form = sorted((p for p in squad if len(p.form) >= 2), key=form_value, reverse=True)[:5]
    y = str(g.year)
    goals = sorted((p for p in squad if p.stats.get(y, {}).get("g")), key=lambda p: -p.stats[y]["g"])[:5]
    senior, rookies = offseason.list_counts(g, cid)
    return {
        "next": nxt_view, "last": _mrow(g, played[-1]) if played else None,
        "ladder": rows, "form": last5[cid], "advice": assistant.advice(g),
        "news": list(reversed(g.news[-9:])),
        "injuries": [_prow(g, p) for p in sorted(squad, key=lambda p: -overall(p)) if p.injury],
        "in_form": [_prow(g, p) for p in in_form], "goals": [_prow(g, p) for p in goals],
        "board": club.board, "profit": finance.profit(club),
        "list": {"senior": senior, "rookie": rookies, "room": offseason.cap_space(g, cid)},
        "training": club.training, "tactics": club.tactics, "philosophy": club.philosophy,
        "review": g.meta.get("review") if g.phase != "season" and g.season.get("premier") else None,
        "premier": g.season.get("premier"), "awards": g.season.get("awards"),
        "finals": [{"name": wk["name"], "matches": [_mrow(g, m) for m in wk["matches"]]}
                   for wk in g.season["finals"]],
    }


def op_squad(club: str | None = None) -> dict:
    g = G()
    cid = club or g.user.id
    c = g.clubs[cid]
    senior, rookies = offseason.list_counts(g, cid)
    return {"club": cid, "own": cid == g.meta.get("user_club"), "captain": c.captain,
            "players": [_prow(g, p) for p in g.squad(cid)],
            "senior": senior, "rookie": rookies, "payroll": g.payroll(cid), "cap": g.cap,
            "best22": round(best22_rating(g, cid), 1), "strategy": c.strategy, "philosophy": c.philosophy,
            "tactics": c.tactics, "dev": views.grade(c.dev), "recruit": views.grade(c.recruit),
            "board": c.board["label"], "members": c.supporters}


def op_player(id: int) -> dict:
    g = G()
    p = g.players.get(int(id))
    if not p:
        raise CmdError("That player is no longer in the game.")
    own = p.club is not None and p.club == g.meta.get("user_club")
    roles = sorted(((round(slot_rating(p, pt) * 5), pt) for pt in C.POS_TYPES), reverse=True)
    seasons = []
    for y in sorted(p.stats):
        s = p.stats[y]
        gm = max(1, s["gm"])
        seasons.append({"year": y, "gm": s["gm"], "g": s["g"], "b": s["b"],
                        "disp": round((s["k"] + s["hb"]) / gm, 1), "m": round(s["m"] / gm, 1),
                        "t": round(s["t"] / gm, 1), "ho": round(s["ho"] / gm, 1),
                        "cl": round(s["cl"] / gm, 1), "rt": round(s["rt"] / gm, 2), "v": s["v"]})
    demand = None
    if own or p.status == "free_agent":
        d = offseason.contract_demand(g, p)
        demand = {"wage": int(round(d["wage"] * (1.0 if own else 1.08) / 5) * 5),
                  "min": d["min_years"], "max": d["max_years"]}
    club = g.clubs.get(p.club)
    return {"p": _prow(g, p), "attrs": {k: round(p.attrs[k], 1) for k in C.ATTRS},
            "roles": [[pt, r] for r, pt in roles], "seasons": seasons, "career": p.career,
            "own": own, "demand": demand, "drafted": p.drafted, "exact_pot": own,
            "captain": bool(club and club.captain == p.id),
            "can_offer": (own and p.contract_end <= g.year + 1) or p.status == "free_agent",
            "offseason": g.phase not in ("season", "finals"),
            "prospect": p.status == "prospect"}


def _lineup(g: Game, cid: str) -> dict:
    club = g.clubs[cid]
    slots = {}
    for slot in C.ALL_SLOTS:
        p = g.players.get(club.lineup.get(slot))
        if not p:
            slots[slot] = None
            continue
        pt = C.FIELD_SLOTS.get(slot)
        slots[slot] = {"id": p.id, "short": p.short, "name": p.name, "pos": p.pos,
                       "r": int(round(slot_rating(p, pt) * 5 if pt else overall(p))),
                       "oop": bool(pt and pt not in p.positions), "inj": bool(p.injury),
                       "fit": int(round(p.fitness)), "form": round(form_value(p), 1) if p.form else None,
                       "cap": club.captain == p.id}
    return slots


def op_team(club: str | None = None) -> dict:
    g = G()
    cid = club or g.user.id
    own = cid == g.meta.get("user_club")
    if own:
        commands.refresh_auto_lineup(g)
    players = []
    for p in g.squad(cid):
        row = _prow(g, p)
        row["r"] = {pt: int(round(slot_rating(p, pt) * 5)) for pt in C.POS_TYPES}
        players.append(row)
    c = g.clubs[cid]
    return {"club": cid, "own": own, "mode": g.meta.get("selection", "auto") if own else "auto",
            "slots": _lineup(g, cid), "summary": {k: v for k, v in views.team_summary(g, cid).items()
                                                  if k != "injured"},
            "problems": lineup_problems(g, cid), "players": players, "captain": c.captain,
            "tactics": c.tactics, "philosophy": c.philosophy, "training": c.training,
            "playing": g.phase in ("season", "finals")}


def op_preview() -> dict:
    g = G()
    cid = g.user.id
    m = season.next_match(g, cid)
    if not m:
        return {"match": None}
    commands.refresh_auto_lineup(g)
    opp = m["away"] if m["home"] == cid else m["home"]
    g.clubs[opp].lineup = auto_select(g, opp, 0.25 if g.clubs[opp].strategy == "rebuild" else 0.0)
    lad = {r["club"]: r for r in season.ladder(g)}
    last5 = _last5(g)
    teams = {}
    for c in (cid, opp):
        club, s, r = g.clubs[c], views.team_summary(g, c), lad[c]
        stars = sorted((g.players[pid] for pid in club.lineup.values()), key=overall, reverse=True)[:5]
        ruck = g.players.get(club.lineup.get("RUCK"))
        teams[c] = {"pos": r["pos"], "rec": f"{r['W']}-{r['L']}-{r['D']}", "pct": round(r["pct"], 1),
                    "last5": last5[c], "lines": [s["def"], s["mid"], s["fwd"]], "age": s["avg_age"],
                    "fit": s["avg_fit"], "out": [_prow(g, p) for p in s["injured"]][:8],
                    "tactics": club.tactics, "philosophy": club.philosophy,
                    "stars": [_prow(g, p) for p in stars],
                    "ruck": int(round(raw_rating(ruck.attrs, "RUCK") * 5)) if ruck else 0}
    vstate = C.VENUES[m["venue"]][0]
    travel = ("You travel interstate for this one - expect it to cost you." if g.user.state != vstate else
              "They have to travel interstate - worth a couple of goals to you."
              if g.clubs[opp].state != vstate else "")
    return {"match": _mrow(g, m), "me": cid, "opp": opp, "teams": teams, "travel": travel,
            "win": round(views.win_chance(g, m, cid) * 100), "their_slots": _lineup(g, opp),
            "notes": assistant.matchup_notes(g, cid, opp), "roof": C.VENUES[m["venue"]][2]}


def op_match(id: int | None = None) -> dict:
    g = G()
    if id is None:
        played = [m for m in season.club_matches(g, g.user.id) if m["played"]]
        if not played:
            return {"match": None}
        m = played[-1]
    else:
        m = season.find_match(g, int(id))
        if not m:
            raise CmdError("That match is not in this season's records.")
    out = _mrow(g, m)
    if not m["played"]:
        return {"match": out}
    out.update(qs=m["qs"], et=m.get("et", False), team=m["team"], inj=m["inj"])
    d = m.get("detail")
    if d:
        names = d.get("names", {})

        def nm(pid):
            p = g.players.get(int(pid))
            return p.short if p else names.get(str(pid), f"#{pid}")
        out["players"] = [{"id": int(pid), "name": nm(pid), **st} for pid, st in d["players"].items()]
        out["feed"] = d.get("feed", [])
        out["timeline"] = [[q, mn, side, kind, nm(pid) if pid else ""]
                           for q, mn, side, kind, pid in d.get("timeline", [])]
        out["tactics"] = d.get("tactics")
        out["comm"] = d.get("comm", [])
    return {"match": out, "mine": g.user.id if g.user and g.user.id in (m["home"], m["away"]) else None}


def op_fixtures(club: str | None = None) -> dict:
    g = G()
    cid = club or g.user.id
    rows = []
    for m in season.club_matches(g, cid):
        r = _mrow(g, m)
        r["opp"] = m["away"] if m["home"] == cid else m["home"]
        r["at_home"] = m["home"] == cid
        if m["played"]:
            us, them = (m["hs"], m["as"]) if r["at_home"] else (m["as"], m["hs"])
            r["res"] = "W" if us[2] > them[2] else "L" if us[2] < them[2] else "D"
            r["us"], r["them"] = us, them
        rows.append(r)
    return {"club": cid, "rows": rows}


def op_round(n=None) -> dict:
    g = G()
    if n == "finals":
        return {"finals": True,
                "weeks": [{"name": wk["name"], "matches": [_mrow(g, m) for m in wk["matches"]]}
                          for wk in g.season["finals"]]}
    last = g.meta["round"] - 1 if g.phase == "season" else C.HA_ROUNDS
    n = max(1, min(C.HA_ROUNDS, int(n) if n else max(1, last)))
    return {"round": n, "matches": [_mrow(g, m) for m in g.season["rounds"][n - 1]],
            "has_finals": bool(g.season["finals"])}


def op_ladder() -> dict:
    g = G()
    last5 = _last5(g)
    return {"rows": [{**r, "pct": round(r["pct"], 1), "form": last5[r["club"]]} for r in season.ladder(g)],
            "seeds": g.season.get("seeds"), "premier": g.season.get("premier")}


def op_stats(what: str = "goals", club: str | None = None) -> dict:
    g = G()
    if what not in views.LEADER_KEYS:
        raise CmdError("Unknown stat.")
    key, label, min_default = views.LEADER_KEYS[what]
    played = max((r["P"] for r in season.ladder(g)), default=0)
    min_games = 1 if min_default == 1 else max(1, int(played * 0.5))
    rows = []
    for val, p in season.leaders(g, key, 30, min_games, club or None):
        row = _prow(g, p)
        row["val"] = round(val, 2) if isinstance(val, float) else val
        rows.append(row)
    return {"what": what, "label": label, "rows": rows, "keys": {k: v[1] for k, v in views.LEADER_KEYS.items()}}


def op_club() -> dict:
    g = G()
    club = g.user
    lines = views.finance_rows(g, club.id)
    return {"board": club.board, "finance": lines, "profit": finance.profit(club), "balance": club.balance,
            "payroll": g.payroll(club.id), "cap": g.cap, "floor": int(g.cap * C.CAP_FLOOR_PCT),
            "members": club.supporters, "dev": views.grade(club.dev), "recruit": views.grade(club.recruit),
            "history": g.history, "review": g.meta.get("review") if g.season.get("premier") else None,
            "hired": g.meta.get("hired"), "pos": views.record(g, club.id)["pos"]}


def op_contracts() -> dict:
    g = G()
    cid = g.user.id
    rows = []
    for p in g.squad(cid):
        d = offseason.contract_demand(g, p)
        row = _prow(g, p)
        row.update(ooc=p.contract_end <= g.year, ask=d["wage"], ymin=d["min_years"], ymax=d["max_years"],
                   can_offer=p.contract_end <= g.year + 1)
        rows.append(row)
    senior, rookies = offseason.list_counts(g, cid)
    return {"rows": rows, "senior": senior, "rookie": rookies, "payroll": g.payroll(cid), "cap": g.cap,
            "floor": int(g.cap * C.CAP_FLOOR_PCT), "offseason": g.phase not in ("season", "finals"),
            "phase": g.phase}


def _pick_rows(g: Game, cid: str) -> list[dict]:
    return [{"code": f"{p['year']}R{p['round']}:{p['orig']}", "label": offseason.pick_label(p),
             "year": p["year"], "round": p["round"], "orig": p["orig"],
             "est": int(round(offseason.pick_number(g, p))), "value": int(round(offseason.pick_value(g, p)))}
            for p in offseason.club_picks(g, cid)]


def op_trade(club: str | None = None) -> dict:
    g = G()
    me = g.user.id
    other = club if club and club != me else next(c for c in g.clubs if c != me)
    return {"me": me, "other": other, "open": g.phase in ("trades", "draft"),
            "mine": [_prow(g, p) for p in g.squad(me)], "theirs": [_prow(g, p) for p in g.squad(other)],
            "my_picks": _pick_rows(g, me), "their_picks": _pick_rows(g, other),
            "room": {"me": offseason.cap_space(g, me), "other": offseason.cap_space(g, other)},
            "size": {"me": len(g.squad(me)), "other": len(g.squad(other))},
            "strategy": g.clubs[other].strategy}


def _items(g: Game, codes: list, owner: str) -> list:
    out = []
    for code in codes:
        if isinstance(code, int) or str(code).isdigit():
            p = g.players.get(int(code))
            if not p or p.club != owner:
                raise CmdError("One of those players has moved on.")
            out.append(p)
        else:
            head, orig = str(code).split(":")
            year, rnd = head.split("R")
            pick = next((x for x in g.draft["picks"] if x["owner"] == owner and x["orig"] == orig
                         and x["year"] == int(year) and x["round"] == int(rnd)), None)
            if not pick:
                raise CmdError("One of those picks has already been traded.")
            out.append(pick)
    return out


def op_trade_eval(club: str, give: list, get: list, execute: bool = False) -> dict:
    g = G()
    me = g.user.id
    give_items, get_items = _items(g, give, me), _items(g, get, club)
    res = offseason.evaluate_trade(g, club, give_items, get_items)
    done = False
    if execute:
        if g.phase not in ("trades", "draft"):
            raise CmdError("Trades can only be completed in the trade period, after the season.")
        if res["ok"]:
            offseason.execute_trade(g, me, club, give_items, get_items)
            from .ratings import repair_lineup
            repair_lineup(g, me)
            done = True
    return {**res, "done": done}


def op_draft() -> dict:
    g = G()
    cid = g.user.id
    live = g.draft.get("live")
    slot = offseason.draft_on_clock(g) if live else None
    board = []
    for i, p in enumerate(offseason.draft_board(g)[:70]):
        row = _prow(g, p)
        row["rank"] = i + 1
        row["lo"], row["hi"] = max(row["ovr"], row["pot"] - 4), min(99, row["pot"] + 4)
        board.append(row)
    upcoming = live["order"][live["idx"]:live["idx"] + 12] if live else []
    return {"live": bool(live) and g.phase == "draft", "on_clock": slot,
            "my_turn": bool(slot and slot["owner"] == cid), "board": board,
            "log": live["log"] if live else [], "upcoming": upcoming, "picks": _pick_rows(g, cid),
            "year": g.draft.get("pool_year"), "size": len(g.squad(cid)), "phase": g.phase}


def op_draft_pick(id: int | None = None) -> dict:
    g = G()
    if g.phase != "draft":
        raise CmdError("The draft is held after the trade period.")
    p = g.players.get(int(id)) if id else offseason.draft_board(g)[0]
    ok, msg = offseason.user_draft_pick(g, p)
    if not ok:
        raise CmdError(msg)
    offseason.run_draft(g, stop_for_user=True)
    return {"text": msg, "pot": round(p.potential), "id": p.id}


def op_agents() -> dict:
    g = G()
    rows = []
    for pid in g.free_agents:
        p = g.players[pid]
        d = offseason.contract_demand(g, p)
        row = _prow(g, p)
        row.update(ask=int(round(d["wage"] * 1.08 / 5) * 5), ymin=d["min_years"], ymax=d["max_years"])
        rows.append(row)
    senior, rookies = offseason.list_counts(g, g.user.id)
    return {"rows": rows, "room": offseason.cap_space(g, g.user.id), "size": senior + rookies}


def op_news() -> dict:
    return {"news": list(reversed(G().news[-150:]))}


def op_search(q: str) -> dict:
    g = G()
    t = q.strip().lower()
    if len(t) < 2:
        return {"players": [], "clubs": []}
    hits = [p for p in g.players.values() if t in p.name.lower()]
    hits.sort(key=lambda p: (not p.last.lower().startswith(t), -overall(p)))
    clubs = [cid for cid, c in g.clubs.items() if t in c.full_name.lower() or t == cid.lower()]
    return {"players": [_prow(g, p) for p in hits[:12]], "clubs": clubs}


def op_act(cmd: str) -> dict:
    """Run a text command (the rules live there).  Errors come back as errors."""
    out = commands.execute(G(), cmd, _rng)
    if out.startswith("! "):
        raise CmdError(out[2:])
    return {"text": out}


def op_advance(confirm: bool = False) -> dict:
    g = G()
    step = commands.advance_step(g, _rng, confirm)
    kind = step["kind"]
    out = {"kind": kind}
    if kind in ("round", "finals"):
        rep = step["rep"]
        um = rep.get("user_match")
        out.update(label=rep["label"], notes=rep.get("notes", []), match=um["id"] if um else None,
                   matches=[_mrow(g, m) for m in rep["matches"]], finals_set=bool(rep.get("finals_set")),
                   season_over=bool(step.get("season_over")), premier=rep.get("premier"))
        if um is None and rep["matches"] and rep["matches"][0]["rnd"] == "GF":
            out["match"] = rep["matches"][0]["id"]
    elif kind == "unsigned":
        out["players"] = [_prow(g, p) for p in step["players"]]
    elif kind == "trades_open":
        out["lost"] = step["lost"]
    elif kind == "draft_open":
        out["trades"] = [n["text"] for n in g.news[-40:] if n["tag"] == "trade" and n["year"] == g.year][-10:]
    elif kind == "new_season":
        rep = step["rep"]
        cid = g.user.id
        out.update(year=rep["year"], filled=rep["filled"], notes=rep["notes"],
                   draftees=[{"n": n, "id": pid, "name": name, "pos": pos, "age": age}
                             for n, c, pid, name, pos, age in rep["draft_log"] if c == cid])
    return out


OPS = {name[3:]: fn for name, fn in list(globals().items()) if name.startswith("op_")}


def handle(request: str) -> str:
    """Single entry point: JSON in, JSON out.  Never raises."""
    try:
        req = json.loads(request)
        fn = OPS.get(req.get("op"))
        if fn is None:
            raise CmdError(f"Unknown request '{req.get('op')}'.")
        out = {"ok": True, "data": fn(**(req.get("args") or {}))}
    except CmdError as e:
        out = {"ok": False, "error": str(e)}
    except Exception as e:                       # a bug: report it rather than freeze the UI
        out = {"ok": False, "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()}
    try:
        out["header"] = header()
    except Exception:
        out["header"] = None
    return json.dumps(out)
