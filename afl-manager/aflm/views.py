"""Read-only "view models": plain rows of data for the UIs to display.

Both front ends (the text commands and the Streamlit app) build their tables
from these functions, so they always agree with each other.
"""
from __future__ import annotations

from . import constants as C
from . import finance, offseason, season
from .models import Game, Player
from .ratings import ovr, overall, shown_potential, form_value, best22_rating, line_ratings


def money(k: float) -> str:
    """$k -> '$1.25M' / '$450k'."""
    return f"${k / 1000:.2f}M" if abs(k) >= 1000 else f"${int(k)}k"


def record(game: Game, cid: str) -> dict:
    return next(r for r in season.ladder(game) if r["club"] == cid)


def slot_of(game: Game, p: Player) -> str:
    if not p.club:
        return ""
    return next((s for s, pid in game.clubs[p.club].lineup.items() if pid == p.id), "")


def status_text(p: Player) -> str:
    if p.injury:
        return f"INJ {p.injury['type']} ({p.injury['weeks']}w)"
    return "Rookie" if p.rookie else ""


def player_row(game: Game, p: Player) -> dict:
    s = p.stats.get(str(game.year), {})
    gm = s.get("gm", 0)
    form = f"{form_value(p):.1f}" if p.form else (f"r{p.reserves:.1f}" if p.reserves else "-")
    return {
        "ID": p.id, "Name": p.name, "Pos": "/".join(p.positions), "Age": p.age, "Ht": p.height,
        "OVR": ovr(p), "POT": shown_potential(game, p), "Fit": int(round(p.fitness)), "Form": form,
        "Sel": slot_of(game, p), "Status": status_text(p), "Gm": gm, "Gls": s.get("g", 0),
        "Disp": round((s.get("k", 0) + s.get("hb", 0)) / gm, 1) if gm else 0.0,
        "Rtg": round(s.get("rt", 0) / gm, 2) if gm else 0.0,
        "Wage": p.wage, "Until": p.contract_end,
        "Value": int(round(offseason.player_value(game, p))),
    }


SQUAD_SORTS = {
    "pos": lambda r: (list(C.POS_GROUP.values()).index(C.POS_GROUP[r["Pos"].split("/")[0]]), -r["OVR"]),
    "ovr": lambda r: -r["OVR"], "pot": lambda r: -r["POT"], "age": lambda r: r["Age"],
    # senior form first, then players judged on reserves form, then the unsighted
    "form": lambda r: (r["Form"] == "-" or r["Form"].startswith("r") * 0.5,
                       -(float(r["Form"].lstrip("r")) if r["Form"] != "-" else 0)),
    "fit": lambda r: r["Fit"], "wage": lambda r: -r["Wage"], "value": lambda r: -r["Value"],
    "contract": lambda r: (r["Until"], -r["OVR"]), "goals": lambda r: -r["Gls"],
    "disp": lambda r: -r["Disp"], "rating": lambda r: -r["Rtg"], "name": lambda r: r["Name"].split()[-1],
}


def squad_rows(game: Game, cid: str, sort: str = "pos") -> list[dict]:
    rows = [player_row(game, p) for p in game.squad(cid)]
    rows.sort(key=SQUAD_SORTS.get(sort, SQUAD_SORTS["pos"]))
    return rows


def grade(x: float) -> str:
    """Club program quality (0.85-1.15) as a school report."""
    return "A" if x >= 1.08 else "B" if x >= 1.03 else "C" if x >= 0.97 else "D" if x >= 0.92 else "E"


def club_rows(game: Game) -> list[dict]:
    """The club-selection table: who is strong, who is old, who has cap room."""
    ranking = sorted(game.clubs, key=lambda c: best22_rating(game, c), reverse=True)
    rows = []
    for i, cid in enumerate(ranking):
        club, squad = game.clubs[cid], game.squad(cid)
        kids = sorted((p for p in squad if p.age <= 21), key=lambda p: p.potential, reverse=True)[:5]
        rows.append({
            "Rank": i + 1, "ID": cid, "Club": club.full_name, "Best 22": round(best22_rating(game, cid), 1),
            "Avg age": round(sum(p.age for p in squad) / len(squad), 1),
            "Young talent": round(sum(p.potential for p in kids) / max(1, len(kids)), 1),
            "Stars (85+)": sum(1 for p in squad if overall(p) >= 85),
            "Cap room": game.cap - game.payroll(cid), "Bank": club.balance,
            "Members (k)": club.supporters, "Dev": grade(club.dev), "Scout": grade(club.recruit),
            "Game plan": club.philosophy,
            "Board expects": club.board["label"],
        })
    return rows


def ladder_rows(game: Game) -> list[dict]:
    return [{"Pos": r["pos"], "Club": game.clubs[r["club"]].name, "ID": r["club"], "P": r["P"],
             "W": r["W"], "L": r["L"], "D": r["D"], "PF": r["PF"], "PA": r["PA"],
             "%": round(r["pct"], 1), "Pts": r["pts"]} for r in season.ladder(game)]


def result_text(game: Game, m: dict, perspective: str | None = None) -> str:
    h, a = game.clubs[m["home"]].name, game.clubs[m["away"]].name
    if not m["played"]:
        return f"{h} v {a} ({m['venue']})"
    hs, as_ = m["hs"], m["as"]
    return (f"{h} {hs[0]}.{hs[1]} ({hs[2]}) {'def' if hs[2] > as_[2] else 'drew' if hs[2] == as_[2] else 'lost to'} "
            f"{a} {as_[0]}.{as_[1]} ({as_[2]})")


def fixture_rows(game: Game, cid: str) -> list[dict]:
    rows = []
    for m in season.club_matches(game, cid):
        home = m["home"] == cid
        opp = m["away"] if home else m["home"]
        row = {"Rd": m["rnd"], "": "H" if home else "A", "Opponent": game.clubs[opp].name,
               "Venue": m["venue"], "Result": "", "Score": "", "ID": m["id"]}
        if m["played"]:
            us, them = (m["hs"], m["as"]) if home else (m["as"], m["hs"])
            row["Result"] = "W" if us[2] > them[2] else "L" if us[2] < them[2] else "D"
            row["Score"] = f"{us[0]}.{us[1]} ({us[2]}) - {them[0]}.{them[1]} ({them[2]})"
        rows.append(row)
    return rows


LEADER_KEYS = {"goals": ("g", "Goals", 1), "disposals": ("disp", "Disposals/game", 5),
               "rating": ("rt", "Avg rating", 5), "votes": ("v", "Brownlow votes", 1),
               "marks": ("m", "Marks/game", 5), "tackles": ("t", "Tackles/game", 5),
               "hitouts": ("ho", "Hit-outs/game", 5), "clearances": ("cl", "Clearances/game", 5)}


def leader_rows(game: Game, what: str = "goals", n: int = 15, club: str | None = None) -> list[dict]:
    key, label, min_default = LEADER_KEYS[what]
    played = max((r["P"] for r in season.ladder(game)), default=0)
    min_games = 1 if min_default == 1 else max(1, int(played * 0.5))
    rows = []
    for i, (val, p) in enumerate(season.leaders(game, key, n, min_games, club)):
        s = p.stats[str(game.year)]
        rows.append({"#": i + 1, "Player": p.name, "Club": p.club or "-", "Pos": p.pos, "Age": p.age,
                     "Gm": s["gm"], label: round(val, 2) if isinstance(val, float) else val})
    return rows


def contract_rows(game: Game, cid: str) -> list[dict]:
    rows = []
    for p in sorted(game.squad(cid), key=lambda p: (p.contract_end, -overall(p))):
        d = offseason.contract_demand(game, p)
        rows.append({"ID": p.id, "Name": p.name, "Pos": p.pos, "Age": p.age, "OVR": ovr(p),
                     "POT": shown_potential(game, p), "List": "Rookie" if p.rookie else "Senior",
                     "Wage": p.wage, "Until": p.contract_end,
                     "Out of contract": "YES" if p.contract_end <= game.year else "",
                     "Asking": d["wage"], "Years": f"{d['min_years']}-{d['max_years']}"})
    return rows


def free_agent_rows(game: Game) -> list[dict]:
    rows = []
    for pid in game.free_agents:
        p = game.players[pid]
        d = offseason.contract_demand(game, p)
        rows.append({"ID": p.id, "Name": p.name, "Pos": "/".join(p.positions), "Age": p.age,
                     "OVR": ovr(p), "POT": shown_potential(game, p),
                     "Asking": int(round(d["wage"] * 1.08 / 5) * 5), "Years": f"{d['min_years']}-{d['max_years']}"})
    rows.sort(key=lambda r: -r["OVR"])
    return rows


def pick_rows(game: Game, cid: str) -> list[dict]:
    return [{"Pick": offseason.pick_label(p), "Code": f"{p['year']}R{p['round']}:{p['orig']}",
             "Est. position": int(round(offseason.pick_number(game, p))),
             "Value": int(round(offseason.pick_value(game, p)))} for p in offseason.club_picks(game, cid)]


def prospect_rows(game: Game, n: int = 40) -> list[dict]:
    rows = []
    for i, p in enumerate(offseason.draft_board(game)[:n]):
        pot = shown_potential(game, p)
        rows.append({"Rank": i + 1, "ID": p.id, "Name": p.name, "Pos": "/".join(p.positions),
                     "Age": p.age, "Ht": p.height, "OVR": ovr(p),
                     "Potential": f"{max(ovr(p), pot - 4)}-{min(99, pot + 4)}"})
    return rows


def finance_rows(game: Game, cid: str) -> list[dict]:
    club = game.clubs[cid]
    order = ["membership", "sponsorship", "afl_distribution", "gate", "prize_money",
             "player_payments", "football_dept", "operations", "contract_payouts"]
    keys = [k for k in order if k in club.ledger] + [k for k in club.ledger if k not in order]
    return [{"Line": k.replace("_", " ").title(), "Last round": club.last_ledger.get(k, 0),
             "Season": club.ledger[k]} for k in keys]


def team_summary(game: Game, cid: str) -> dict:
    """Headline numbers for a club's selected side."""
    club = game.clubs[cid]
    lines = line_ratings(game, cid)
    picked = [game.players[pid] for pid in club.lineup.values() if pid in game.players]
    return {"def": round(lines["D"], 1), "mid": round(lines["M"], 1), "fwd": round(lines["F"], 1),
            "avg_age": round(sum(p.age for p in picked) / max(1, len(picked)), 1),
            "avg_fit": round(sum(p.fitness for p in picked) / max(1, len(picked))),
            "injured": [p for p in game.squad(cid) if p.injury]}


def win_chance(game: Game, m: dict, cid: str) -> float:
    p = finance.win_probability(game, m["home"], m["away"])
    return p if m["home"] == cid else 1 - p
