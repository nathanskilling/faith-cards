"""Text commands: the "chat" way to play.

``execute(game, "squad ovr")`` runs one command against a Game and returns the
text to show.  play.py wraps this in a CLI / REPL and saves after each command.
Every command here is a thin layer over the engine modules, so the Streamlit
app can call the same functions.
"""
from __future__ import annotations

import random
import re

from . import constants as C
from . import finance, offseason, season, views
from .generator import pick_captain
from .match_engine import score_str
from .models import Game, Player
from .ratings import (ovr, overall, shown_potential, form_value, slot_rating, auto_select,
                      lineup_problems, repair_lineup, available, best22_rating)
from .views import money


class CmdError(Exception):
    """A user-facing problem with a command (bad name, illegal move...)."""


# -- formatting helpers --------------------------------------------------------
def table(rows: list[dict], cols: list[str] | None = None, money_cols: tuple = ()) -> str:
    if not rows:
        return "  (none)"
    cols = cols or list(rows[0])
    cells = [[(money(r[c]) if c in money_cols else str(r.get(c, ""))) for c in cols] for r in rows]
    numeric = [all(isinstance(r.get(c), (int, float)) for r in rows) for c in cols]
    widths = [max(len(c), *(len(row[i]) for row in cells)) for i, c in enumerate(cols)]
    def fmt(vals):
        return "  ".join(v.rjust(w) if numeric[i] else v.ljust(w)
                         for i, (v, w) in enumerate(zip(vals, widths))).rstrip()
    return "\n".join([fmt(cols), fmt(["-" * w for w in widths])] + [fmt(r) for r in cells])


def heading(text: str) -> str:
    return f"\n=== {text} ==="


def find_club(game: Game, text: str) -> str:
    t = text.strip().lower()
    for cid, c in game.clubs.items():
        if t in (cid.lower(), c.name.lower(), c.nickname.lower(), c.full_name.lower()):
            return cid
    hits = [cid for cid, c in game.clubs.items() if t and t in c.full_name.lower()]
    if len(hits) == 1:
        return hits[0]
    raise CmdError(f"Unknown club '{text}'. Use a code such as: {', '.join(game.clubs)}")


def find_player(game: Game, text: str, pool: list | None = None, prefer: str | None = None) -> Player:
    """Look a player up by #id, full name, surname or any unique part of the name."""
    t = text.strip().lstrip("#").lower()
    if not t:
        raise CmdError("Which player?")
    if t.isdigit():
        p = game.players.get(int(t))
        if p and (pool is None or p in pool):
            return p
        raise CmdError(f"No player with id {t} here.")
    pool = pool if pool is not None else list(game.players.values())
    for test in (lambda p: p.name.lower() == t, lambda p: p.last.lower() == t,
                 lambda p: t in p.name.lower()):
        hits = [p for p in pool if test(p)]
        if prefer and len(hits) > 1:
            mine = [p for p in hits if p.club == prefer]
            hits = mine or hits
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            opts = ", ".join(f"{p.name} #{p.id} ({p.club or p.status})" for p in hits[:8])
            raise CmdError(f"'{text}' matches several players - use the #id: {opts}")
    raise CmdError(f"No player matches '{text}'.")


def _need_user(game: Game):
    if not game.user:
        raise CmdError("Pick a club first: 'clubs' to compare them, then 'choose <CLUB>'.")
    return game.user


# -- club selection ------------------------------------------------------------
def cmd_clubs(game: Game, args) -> str:
    rows = views.club_rows(game)
    out = [heading(f"The {game.year} competition - ranked by list strength"),
           table(rows, ["Rank", "ID", "Club", "Best 22", "Avg age", "Young talent", "Stars (85+)",
                        "Cap room", "Members (k)", "Dev", "Scout", "Game plan", "Board expects"],
                 money_cols=("Cap room",)),
           "Best 22 = average rating of the best 22 on the list. Young talent = average potential of the "
           "five best kids (21 and under).\nDev / Scout = quality of the club's development and "
           "recruiting programs (A-E)."]
    if not game.user:
        out.append("\nChoose with:  choose <ID>   e.g.  choose " + rows[8]["ID"])
    return "\n".join(out)


def cmd_choose(game: Game, args) -> str:
    if game.user and not game.meta.get("sacked"):
        raise CmdError(f"You are already in charge of {game.user.name}.")
    if not args:
        raise CmdError("Usage: choose <CLUB> [your name]")
    cid = find_club(game, args[0])
    if game.meta.get("sacked"):
        offers = offseason.job_offers(game)
        if cid not in offers:
            raise CmdError(f"No offer from {game.clubs[cid].name}. Clubs interested: {', '.join(offers)}")
        game.meta["sacked"] = False
        game.clubs[cid].board["confidence"] = 55.0
    game.meta["user_club"] = cid
    game.meta["hired"] = game.year + (1 if game.phase not in ("season", "finals") else 0)
    if len(args) > 1:
        game.meta["manager"] = " ".join(args[1:])
    club = game.clubs[cid]
    for p in game.squad(cid):
        p.scout_noise = 0.0
    game.add_news(f"{game.meta.get('manager') or 'A new coach'} takes the reins at {club.full_name}.", "board")
    return (f"You are now senior coach and list boss of the {club.full_name}.\n"
            f"Home ground: {club.ground}.  The board expects: {club.board['label']}.\n"
            f"You inherit a '{club.philosophy}' game plan - change it any time with 'tactics'.\n"
            + cmd_status(game, []))


# -- overview ------------------------------------------------------------------
def cmd_status(game: Game, args) -> str:
    club = _need_user(game)
    cid = club.id
    rec = views.record(game, cid)
    senior, rookies = offseason.list_counts(game, cid)
    out = [heading(f"{club.full_name} - {game.year} - {phase_label(game)}")]
    if game.meta.get("manager"):
        out.append(f"Coach: {game.meta['manager']}")
    out.append(f"Ladder: {_ordinal(rec['pos'])}  ({rec['W']}-{rec['L']}-{rec['D']}, {rec['pct']:.1f}%)   "
               f"Board: {club.board['label']} - confidence {club.board['confidence']:.0f}/100")
    out.append(f"Cap: {money(game.payroll(cid))} of {money(game.cap)} ({money(offseason.cap_space(game, cid))} room)   "
               f"List: {senior} senior + {rookies} rookie   Bank: {money(club.balance)}")
    inj = [p for p in game.squad(cid) if p.injury]
    if inj:
        out.append("Injured: " + ", ".join(f"{p.short} ({p.injury['type']}, {p.injury['weeks']}w)" for p in inj))
    if game.phase in ("season", "finals"):
        m = season.next_match(game, cid)
        if m:
            opp = m["away"] if m["home"] == cid else m["home"]
            orec = views.record(game, opp)
            rd = f"Round {m['rnd']}" if isinstance(m["rnd"], int) else m["rnd"]
            out.append(f"Next: {rd} v {game.clubs[opp].name} ({'H' if m['home'] == cid else 'A'}) at {m['venue']} - "
                       f"they are {_ordinal(orec['pos'])}; win chance about {views.win_chance(game, m, cid) * 100:.0f}%")
        elif game.phase == "finals":
            out.append("Your season is over - 'sim' to follow the finals.")
        probs = lineup_problems(game, cid)
        if probs:
            out.append("TEAM SHEET NEEDS ATTENTION: " + "; ".join(probs[:4])
                       + ("  ('pick auto' fixes it, or it is patched automatically at the bounce)"))
        tired = [p for p in (game.players[pid] for pid in club.lineup.values()) if p.fitness < 75]
        if tired:
            out.append("Tired legs in the 23: " + ", ".join(f"{p.short} {p.fitness:.0f}%" for p in tired))
        if game.meta.get("selection", "auto") == "manual":
            named = set(club.lineup.values())
            floor = min((overall(game.players[pid]) for pid in named), default=0)
            knock = sorted((p for p in game.squad(cid) if p.id not in named and available(p)
                            and overall(p) >= floor + 3), key=overall, reverse=True)[:4]
            out.append("Selection: MANUAL - your team sheet stays as you set it."
                       + (" Banging the door down: " + ", ".join(f"{p.short} ({p.pos} {ovr(p)})" for p in knock)
                          if knock else ""))
        else:
            out.append("Selection: AUTO - your assistant picks the best fit 23 each week "
                       "('pick'/'swap' to take over).")
    out.append(_phase_hint(game))
    news = [n for n in game.news[-6:]]
    if news:
        out.append("\nLatest:")
        out += [f"  [{n['when']}] {n['text']}" for n in news[-5:]]
    return "\n".join(out)


def phase_label(game: Game) -> str:
    ph = game.phase
    if ph == "season":
        return f"Round {game.meta['round']} of {C.HA_ROUNDS}"
    if ph == "finals":
        return game.season["finals"][-1]["name"]
    return {"review": "Season review", "contracts": "Off-season: contracts",
            "trades": "Off-season: trade period", "draft": "Off-season: national draft"}[ph]


def _phase_hint(game: Game) -> str:
    ph = game.phase
    if game.meta.get("sacked"):
        return ("\nYou have been sacked. Clubs willing to hire you: "
                + ", ".join(offseason.job_offers(game)) + "  ->  choose <CLUB>")
    return "\nNext step: " + {
        "season": "'lineup' / 'tactics' / 'training' to prepare, then 'sim' to play the round.",
        "finals": "'sim' to play this week of the finals.",
        "review": "'review' to re-read the season wrap, 'advance' to open contract talks.",
        "contracts": "'contracts' lists who is out of contract; 'offer <player> <years>' re-signs, "
                     "'delist <player>' cuts. 'advance' ends the signing period.",
        "trades": "'trade <CLUB> give <items> for <items>', 'freeagents', 'sign <player> <years>'. "
                  "'advance' moves to the draft.",
        "draft": "'draft' shows the board; 'draft pick <player>' when on the clock; "
                 "'advance' auto-drafts the rest and starts the new season.",
    }[ph]


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


# -- squad and players ---------------------------------------------------------
def cmd_squad(game: Game, args) -> str:
    cid, sort = (game.user.id if game.user else None), "pos"
    for a in args:
        if a.lower() in views.SQUAD_SORTS:
            sort = a.lower()
        else:
            cid = find_club(game, a)
    if not cid:
        raise CmdError("Usage: squad [CLUB] [sort]   sorts: " + ", ".join(views.SQUAD_SORTS))
    club = game.clubs[cid]
    rows = views.squad_rows(game, cid, sort)
    senior, rookies = offseason.list_counts(game, cid)
    out = [heading(f"{club.full_name} list - {senior} senior + {rookies} rookie, payroll "
                   f"{money(game.payroll(cid))} / {money(game.cap)}"),
           table(rows, ["ID", "Name", "Pos", "Age", "OVR", "POT", "Fit", "Form", "Sel", "Gm", "Gls",
                        "Disp", "Rtg", "Wage", "Until", "Value", "Status"]),
           "Form = avg of last 5 senior ratings (r = last reserves game). Sel = spot in the 23. "
           "Wage in $k. Value = trade points."]
    if cid != game.meta.get("user_club"):
        out.append("POT for other clubs' players is your recruiters' estimate, not gospel.")
    return "\n".join(out)


def cmd_player(game: Game, args) -> str:
    p = find_player(game, " ".join(args), prefer=game.meta.get("user_club"))
    club = game.clubs[p.club].full_name if p.club else p.status.replace("_", " ").title()
    out = [heading(f"{p.name}  #{p.id}"),
           f"{club} | {' / '.join(C.POS_NAME[x] for x in p.positions)} | {p.age} yo | {p.height} cm",
           f"Overall {ovr(p)}   Potential {shown_potential(game, p)}"
           + ("" if p.club == game.meta.get("user_club") else " (estimate)")
           + f"   Fitness {p.fitness:.0f}%   Form {form_value(p):.1f}"
           + (f"   Last five: {' '.join(str(x) for x in p.form)}" if p.form else "")]
    if p.injury:
        out.append(f"INJURED: {p.injury['type']} - {p.injury['weeks']} week(s)")
    if p.status == "listed":
        out.append(f"Contract: ${p.wage}k a season to the end of {p.contract_end}"
                   + ("  (rookie list)" if p.rookie else "")
                   + (f"   Drafted: {p.drafted}" if p.drafted else ""))
    names = [(C.ATTR_LABEL[a], p.attrs[a]) for a in C.ATTRS]
    out.append("")
    for i in range(0, len(names), 3):
        out.append("   ".join(f"{n:<17}{round(v):>3}" for n, v in names[i:i + 3]))
    rates = sorted(((slot_rating(p, pt) * 5, pt) for pt in C.POS_TYPES), reverse=True)[:5]
    out.append("\nBest roles: " + ", ".join(f"{C.POS_NAME[pt]} {r:.0f}" for r, pt in rates))
    if p.stats:
        rows = []
        for y in sorted(p.stats):
            s = p.stats[y]
            g = max(1, s["gm"])
            rows.append({"Season": y, "Gm": s["gm"], "Goals": s["g"], "Disp": round((s["k"] + s["hb"]) / g, 1),
                         "Marks": round(s["m"] / g, 1), "Tackles": round(s["t"] / g, 1),
                         "Hit-outs": round(s["ho"] / g, 1), "Clear": round(s["cl"] / g, 1),
                         "Rating": round(s["rt"] / g, 2), "Votes": s["v"]})
        out += ["", table(rows)]
    out.append(f"Career: {p.career['games']} games, {p.career['goals']} goals")
    return "\n".join(out)


# -- selection -----------------------------------------------------------------
SLOT_ALIASES = {"RK": "RUCK", "R": "RUCK", "ROVER": "ROV", "CENTRE": "C", "CENTER": "C",
                "RUCKROVER": "RR", "INT1": "IC1", "INT2": "IC2", "INT3": "IC3", "INT4": "IC4",
                "INT5": "IC5"}


def lineup_text(game: Game, cid: str) -> str:
    club = game.clubs[cid]
    out = []
    for label, slots in C.TEAM_SHEET_ROWS:
        cells = []
        for s in slots:
            p = game.players.get(club.lineup.get(s))
            if not p:
                cells.append(f"{s}: ---")
                continue
            pt = C.FIELD_SLOTS.get(s)
            r = slot_rating(p, pt) * 5 if pt else overall(p)
            flag = "!" if p.injury else "*" if pt and pt not in p.positions else ""
            cells.append(f"{s}: {p.short} {r:.0f}{flag}")
        if label == "I/C":
            out.append(f"{label:<5}" + "   ".join(cells))
        else:
            out.append(f"{label:<5}" + "".join(c.ljust(26) for c in cells).rstrip())
    return "\n".join(out)


def cmd_lineup(game: Game, args) -> str:
    cid = find_club(game, args[0]) if args else _need_user(game).id
    club = game.clubs[cid]
    s = views.team_summary(game, cid)
    cap = game.players.get(club.captain)
    out = [heading(f"{club.name} team sheet"), lineup_text(game, cid),
           f"\nDefence {s['def']}  Midfield {s['mid']}  Attack {s['fwd']}  |  avg age {s['avg_age']}  "
           f"avg fitness {s['avg_fit']}%  |  Captain: {cap.name if cap else '-'}",
           "(number = rating in that role; * = out of position; ! = injured)"]
    probs = lineup_problems(game, cid)
    if probs:
        out.append("PROBLEMS: " + "; ".join(probs))
    if cid == game.meta.get("user_club"):
        named = set(club.lineup.values())
        emerg = sorted((p for p in game.squad(cid) if p.id not in named and available(p)),
                       key=overall, reverse=True)[:6]
        out.append("Next in line: " + ", ".join(f"{p.short} ({p.pos} {ovr(p)}"
                                               + (f", r{p.reserves:.1f}" if p.reserves else "") + ")" for p in emerg))
        out.append("Change it: 'pick auto'  |  'pick <SLOT> <player>'  |  'swap <player> <player>'")
    return "\n".join(out)


def cmd_pick(game: Game, args) -> str:
    club = _need_user(game)
    if not args:
        raise CmdError("Usage: pick auto | pick <SLOT> <player>   slots: " + " ".join(C.ALL_SLOTS))
    if args[0].lower() == "auto":
        club.lineup = auto_select(game, club.id)
        return "Best available 23 selected.\n" + cmd_lineup(game, [])
    took_over = _go_manual(game)
    slot = SLOT_ALIASES.get(args[0].upper(), args[0].upper())
    if slot not in C.ALL_SLOTS:
        raise CmdError(f"Unknown slot '{args[0]}'. Slots: " + " ".join(C.ALL_SLOTS))
    p = find_player(game, " ".join(args[1:]), pool=game.squad(club.id))
    if p.injury:
        raise CmdError(f"{p.name} is injured ({p.injury['type']}, {p.injury['weeks']}w).")
    old_slot = next((s for s, pid in club.lineup.items() if pid == p.id), None)
    displaced = club.lineup.get(slot)
    club.lineup[slot] = p.id
    if old_slot and old_slot != slot:
        if displaced is not None:
            club.lineup[old_slot] = displaced          # straight swap
        else:
            del club.lineup[old_slot]
    msg = f"{p.name} named at {slot}."
    if displaced and not old_slot:
        msg += f" {game.players[displaced].name} is omitted."
    return took_over + msg + "\n" + cmd_lineup(game, [])


def _go_manual(game: Game) -> str:
    if game.meta.get("selection", "auto") == "manual":
        return ""
    game.meta["selection"] = "manual"
    return ("You've taken over selection (MANUAL): the side now stays exactly as you set it, apart from "
            "replacing injured players. 'selection auto' hands it back to your assistant.\n")


def cmd_selection(game: Game, args) -> str:
    club = _need_user(game)
    if args and args[0].lower() in ("auto", "manual"):
        game.meta["selection"] = args[0].lower()
        if args[0].lower() == "auto":
            club.lineup = auto_select(game, club.id)
    mode = game.meta.get("selection", "auto")
    return (f"Selection is {mode.upper()}. " +
            ("Your assistant coach picks the best fit 23 before every game."
             if mode == "auto" else
             "Your team sheet stays as you set it; injured players are replaced automatically, "
             "but nobody is recalled or rested unless you do it.")
            + "  Change with: selection auto | selection manual")


def cmd_swap(game: Game, args) -> str:
    club = _need_user(game)
    text = " ".join(args)
    parts = [x.strip() for x in re.split(r",| with | and | for ", text) if x.strip()]
    if len(parts) != 2:
        parts = args if len(args) == 2 else parts
    if len(parts) != 2:
        raise CmdError("Usage: swap <player> <player>   (use #ids or separate names with a comma)")
    a, b = (find_player(game, x, pool=game.squad(club.id)) for x in parts)
    sa = next((s for s, pid in club.lineup.items() if pid == a.id), None)
    sb = next((s for s, pid in club.lineup.items() if pid == b.id), None)
    if not sa and not sb:
        raise CmdError("Neither of those players is in the 23.")
    for incoming, slot in ((b, sa), (a, sb)):
        if slot and incoming.injury:
            raise CmdError(f"{incoming.name} is injured.")
    for incoming, slot in ((b, sa), (a, sb)):
        if slot:
            club.lineup[slot] = incoming.id
    return _go_manual(game) + f"Swapped {a.name} and {b.name}.\n" + cmd_lineup(game, [])


def cmd_captain(game: Game, args) -> str:
    club = _need_user(game)
    p = find_player(game, " ".join(args), pool=game.squad(club.id))
    club.captain = p.id
    return f"{p.name} is the new captain (leadership {round(p.attrs['leadership'])})."


# -- game plan -----------------------------------------------------------------
def _set_options(target: dict, options: dict, args, what: str) -> list[str]:
    changed = []
    for a in args:
        if "=" in a:
            k, v = (x.strip().lower() for x in a.split("=", 1))
        else:
            v = a.lower()
            keys = [k for k, opts in options.items() if v in opts]
            if len(keys) != 1:
                raise CmdError(f"'{a}' is ambiguous or unknown - use key=value, e.g. "
                               + " ".join(f"{k}={next(iter(o))}" for k, o in options.items()))
            k = keys[0]
        if k not in options or v not in options[k]:
            raise CmdError(f"Bad {what} setting '{a}'. Options: "
                           + "; ".join(f"{k}: {'/'.join(o)}" for k, o in options.items()))
        target[k] = v
        changed.append(f"{k} -> {v}")
    return changed


def cmd_tactics(game: Game, args) -> str:
    club = _need_user(game)
    msg = ""
    if args and args[0].lower() == "preset":
        name = " ".join(args[1:]).lower()
        match = next((n for n in C.PHILOSOPHIES if n.lower() == name), None)
        if not match:
            raise CmdError("Presets: " + ", ".join(C.PHILOSOPHIES))
        club.tactics = dict(C.PHILOSOPHIES[match])
        club.philosophy = match
        msg = f"Game plan set to '{match}'.\n"
    elif args:
        msg = "Changed: " + ", ".join(_set_options(club.tactics, C.TACTIC_OPTIONS, args, "tactics")) + "\n"
        club.philosophy = next((n for n, t in C.PHILOSOPHIES.items() if t == club.tactics), "Custom")
    out = [msg + heading(f"{club.name} game plan ({club.philosophy})")]
    for key, opts in C.TACTIC_OPTIONS.items():
        cur = club.tactics[key]
        out.append(f"{key:<9}{cur:<10}{opts[cur]}")
        out.append(" " * 9 + "other options: " + ", ".join(o for o in opts if o != cur))
    out.append("\nSet with e.g.  tactics style=contested pressure=high   or   tactics preset Run and Gun")
    return "\n".join(out)


def cmd_training(game: Game, args) -> str:
    club = _need_user(game)
    opts = {"focus": {k: v[0] for k, v in C.TRAINING_FOCUS.items()},
            "intensity": {"light": "Fresh legs, slower development.",
                          "normal": "Standard week.",
                          "heavy": "Faster development, slower recovery, more soft-tissue risk."}}
    msg = ""
    if args:
        msg = "Changed: " + ", ".join(_set_options(club.training, opts, args, "training")) + "\n"
    out = [msg + heading(f"{club.name} training")]
    for key in ("focus", "intensity"):
        cur = club.training[key]
        out.append(f"{key:<10}{cur:<10}{opts[key][cur]}")
        out.append(" " * 10 + "other options: " + ", ".join(o for o in opts[key] if o != cur))
    return "\n".join(out)


# -- competition ---------------------------------------------------------------
def cmd_ladder(game: Game, args) -> str:
    rows = views.ladder_rows(game)
    user = game.meta.get("user_club")
    lines = table(rows, ["Pos", "Club", "P", "W", "L", "D", "PF", "PA", "%", "Pts"]).split("\n")
    for i, r in enumerate(rows):
        if r["ID"] == user:
            lines[i + 2] += "   <- you"
        if i == 7:
            lines[i + 2] += "\n" + "-" * 8 + " top eight " + "-" * 8
    return heading(f"{game.year} ladder") + "\n" + "\n".join(lines)


def cmd_fixture(game: Game, args) -> str:
    cid = find_club(game, args[0]) if args else _need_user(game).id
    return heading(f"{game.clubs[cid].name} {game.year} fixture") + "\n" + \
        table(views.fixture_rows(game, cid), ["Rd", "", "Opponent", "Venue", "Result", "Score", "ID"])


def cmd_results(game: Game, args) -> str:
    if args and args[0].lower().startswith("f"):
        blocks = [(wk["name"], wk["matches"]) for wk in game.season["finals"]]
    else:
        last = game.meta["round"] - 1 if game.phase == "season" else C.HA_ROUNDS
        rnd = int(args[0]) if args and args[0].isdigit() else max(1, last)
        if not 1 <= rnd <= C.HA_ROUNDS:
            raise CmdError(f"Round must be 1-{C.HA_ROUNDS}.")
        blocks = [(f"Round {rnd}", game.season["rounds"][rnd - 1])]
    out = []
    for name, ms in blocks:
        out.append(heading(name))
        out += [f"  {views.result_text(game, m)}   [match {m['id']}]" for m in ms]
    return "\n".join(out)


def match_report(game: Game, m: dict, both: bool = False) -> str:
    if not m["played"]:
        return views.result_text(game, m) + " - not played yet."
    h, a = game.clubs[m["home"]], game.clubs[m["away"]]
    rd = f"Round {m['rnd']}" if isinstance(m["rnd"], int) else \
        {"QF": "Qualifying Final", "EF": "Elimination Final", "SF": "Semi Final",
         "PF": "Preliminary Final", "GF": "GRAND FINAL"}[m["rnd"][:2]]
    out = [heading(f"{rd}: {h.name} v {a.name}"),
           f"{m['venue']} | crowd {m['att']:,} | {'wet' if m['wet'] else 'dry'}"
           + (" | after extra time" if m.get("et") else "")]
    w = max(len(h.name), len(a.name))
    for name, gi, bi in ((h.name, 0, 1), (a.name, 2, 3)):
        qs = "  ".join(f"{q[gi]}.{q[bi]}".rjust(6) for q in m["qs"])
        out.append(f"{name:<{w}}  {qs}  ({m['qs'][-1][gi] * 6 + m['qs'][-1][bi]})")
    out.append(f"Goals  {h.id}: {m['gk'][0] or '-'}")
    out.append(f"       {a.id}: {m['gk'][1] or '-'}")
    out.append("Best:  " + "; ".join(f"{n} ({c}) {rt} - {line}" for n, c, rt, line in m["best"]))
    t = m["team"]
    out.append(f"Stats  Inside 50s {t[0]['i50']}-{t[1]['i50']} | Clearances {t[0]['cl']}-{t[1]['cl']} | "
               f"Hit-outs {t[0]['ho']}-{t[1]['ho']}")
    if m["inj"]:
        out.append("Injuries: " + ", ".join(f"{n} ({c}) {typ} {wk}w" for n, c, typ, wk in m["inj"]))
    d = m.get("detail")
    if d:
        out.append("\nHighlights:")
        out += ["  " + line for line in d["comm"]]
        user = game.meta.get("user_club")
        sides = [0, 1] if both else [0 if m["home"] == user else 1] if user in (m["home"], m["away"]) else [0, 1]
        for side in sides:
            rows = []
            for pid, st in d["players"].items():
                if st["side"] != side:
                    continue
                p = game.players.get(int(pid))
                rows.append({"Slot": st["slot"],
                             "Player": p.short if p else d.get("names", {}).get(pid, f"#{pid}"), "K": st["k"],
                             "H": st["hb"], "D": st["k"] + st["hb"], "M": st["m"], "T": st["t"],
                             "G": st["g"], "B": st["b"], "HO": st["ho"], "CL": st["cl"], "I50": st["i50"],
                             "Rtg": st["rt"]})
            rows.sort(key=lambda r: -r["Rtg"])
            out.append(f"\n{(h, a)[side].name} player stats:")
            out.append(table(rows))
    return "\n".join(out)


def cmd_match(game: Game, args) -> str:
    both = "all" in [a.lower() for a in args]
    ids = [a for a in args if a.isdigit()]
    if ids:
        m = season.find_match(game, int(ids[0]))
        if not m:
            raise CmdError(f"No match {ids[0]} this season.")
    else:
        played = [x for x in season.club_matches(game, _need_user(game).id) if x["played"]]
        if not played:
            raise CmdError("You haven't played a game yet.")
        m = played[-1]
    return match_report(game, m, both)


def cmd_preview(game: Game, args) -> str:
    club = _need_user(game)
    m = season.next_match(game, club.id)
    if not m:
        raise CmdError("No game coming up.")
    opp_id = m["away"] if m["home"] == club.id else m["home"]
    opp = game.clubs[opp_id]
    if opp_id != game.meta["user_club"]:
        opp.lineup = auto_select(game, opp_id, 0.25 if opp.strategy == "rebuild" else 0.0)
    out = [heading(f"Preview: {game.clubs[m['home']].name} v {game.clubs[m['away']].name} at {m['venue']}")]
    for c in (club, opp):
        rec, s = views.record(game, c.id), views.team_summary(game, c.id)
        last5 = "".join(r["Result"] for r in views.fixture_rows(game, c.id) if r["Result"])[-5:] or "-"
        out.append(f"{c.name:<17} {_ordinal(rec['pos']):>4} ({rec['W']}-{rec['L']})  last five {last5:<5}  "
                   f"DEF {s['def']}  MID {s['mid']}  FWD {s['fwd']}  out: {len(s['injured'])}")
    t = opp.tactics
    out.append(f"\n{opp.name} play '{opp.philosophy}': {t['style']} style, {t['tempo']} tempo, {t['pressure']} "
               f"pressure, {t['forward']} forward line, {t['defence']} defence.")
    stars = sorted((game.players[pid] for pid in opp.lineup.values()), key=overall, reverse=True)[:5]
    out.append("Their best: " + ", ".join(f"{p.short} ({p.pos} {ovr(p)}, form {form_value(p):.1f})" for p in stars))
    vstate = C.VENUES[m["venue"]][0]
    if club.state != vstate:
        out.append("You are travelling interstate - expect it to cost you.")
    elif opp.state != vstate:
        out.append("They have to travel interstate - that's worth a couple of goals to you.")
    out.append(f"Win chance (on list quality and venue): about {views.win_chance(game, m, club.id) * 100:.0f}%")
    out.append("\n" + opp.name + " likely side:\n" + lineup_text(game, opp_id))
    return "\n".join(out)


def cmd_stats(game: Game, args) -> str:
    what = (args[0].lower() if args else "goals")
    what = {"disp": "disposals", "brownlow": "votes", "ratings": "rating", "goal": "goals"}.get(what, what)
    if what not in views.LEADER_KEYS:
        raise CmdError("Usage: stats " + "|".join(views.LEADER_KEYS) + " [CLUB]")
    club = find_club(game, args[1]) if len(args) > 1 else None
    rows = views.leader_rows(game, what, 15, club)
    return heading(f"{game.year} leaders: {views.LEADER_KEYS[what][1]}") + "\n" + table(rows)


def cmd_news(game: Game, args) -> str:
    n = int(args[0]) if args and args[0].isdigit() else 15
    return heading("News") + "\n" + "\n".join(f"  [{x['year']} {x['when']}] {x['text']}" for x in game.news[-n:])


def cmd_history(game: Game, args) -> str:
    if not game.history:
        return "No completed seasons yet."
    rows = []
    for h in game.history:
        u = h.get("user", {})
        rows.append({"Year": h["year"], "Premier": game.clubs[h["premier"]].name,
                     "Runner-up": game.clubs[h["runner_up"]].name,
                     "Brownlow": f"{h['awards']['brownlow'][0]} ({h['awards']['brownlow'][1]})",
                     "Coleman": f"{h['awards']['coleman'][0]} {h['awards']['coleman'][2]}",
                     "You": f"{u.get('club', '')} {_ordinal(u['pos'])} ({u['w']}-{u['l']}) {u.get('finish', '')}" if u else ""})
    return heading("Honour roll") + "\n" + table(rows)


# -- club business -------------------------------------------------------------
def cmd_finances(game: Game, args) -> str:
    club = _need_user(game)
    rows = views.finance_rows(game, club.id)
    out = [heading(f"{club.name} finances ($k)"), table(rows),
           f"\nSeason result so far: {money(finance.profit(club))}   Bank: {money(club.balance)}",
           f"Player payments: {money(game.payroll(club.id))} of the {money(game.cap)} cap "
           f"(floor {money(game.cap * C.CAP_FLOOR_PCT)})"]
    return "\n".join(out)


def cmd_board(game: Game, args) -> str:
    club = _need_user(game)
    b = club.board
    rec = views.record(game, club.id)
    mood = ("right behind you" if b["confidence"] >= 70 else "comfortable" if b["confidence"] >= 50
            else "getting nervous" if b["confidence"] >= 30 else "close to making a change")
    return "\n".join([heading(f"{club.name} board"),
                      f"Expectation: {b['label']} (your list is rated {_ordinal(b.get('list_rank', 9))} in the league)",
                      f"Currently:   {_ordinal(rec['pos'])} on the ladder",
                      f"Confidence:  {b['confidence']:.0f}/100 - the board is {mood}.",
                      f"Finances:    {money(finance.profit(club))} this season, {money(club.balance)} in the bank."])


def cmd_contracts(game: Game, args) -> str:
    club = _need_user(game)
    rows = views.contract_rows(game, club.id)
    ooc = [r for r in rows if r["Out of contract"]]
    out = [heading(f"{club.name} contracts - cap room {money(offseason.cap_space(game, club.id))}"),
           table(rows, ["ID", "Name", "Pos", "Age", "OVR", "POT", "List", "Wage", "Until",
                        "Out of contract", "Asking", "Years"]),
           f"\n{len(ooc)} player(s) come out of contract at the end of {game.year}. "
           f"Asking = wage ($k) he wants on a new deal.",
           "offer <player> <years> [wage]  |  offer all  |  delist <player>  |  promote <rookie>"]
    return "\n".join(out)


def cmd_offer(game: Game, args) -> str:
    club = _need_user(game)
    if args and args[0].lower() == "all":
        out = []
        for p in sorted(offseason.out_of_contract(game, club.id), key=overall, reverse=True):
            d = offseason.contract_demand(game, p)
            ok, msg = offseason.offer_contract(game, p, 1 if p.rookie else d["min_years"])
            out.append(("  OK  " if ok else "  NO  ") + msg)
        return "\n".join(out) or "Nobody is out of contract."
    nums = [a for a in args if a.isdigit()]
    words = [a for a in args if not a.isdigit()]
    # a leading #id or bare id is the player; trailing numbers are years then wage
    if not words and nums:
        target, nums = nums[0], nums[1:]
    else:
        target = " ".join(words)
    if not nums:
        raise CmdError("Usage: offer <player> <years> [wage in $k]")
    p = find_player(game, target, pool=game.squad(club.id) + [game.players[i] for i in game.free_agents],
                    prefer=club.id)
    ok, msg = offseason.offer_contract(game, p, int(nums[0]), int(nums[1]) if len(nums) > 1 else None)
    return msg


def cmd_delist(game: Game, args) -> str:
    club = _need_user(game)
    p = find_player(game, " ".join(args), pool=game.squad(club.id))
    return offseason.delist(game, p)[1]


def cmd_promote(game: Game, args) -> str:
    club = _need_user(game)
    p = find_player(game, " ".join(args), pool=game.squad(club.id))
    if not p.rookie:
        raise CmdError(f"{p.name} is already on the senior list.")
    senior, _ = offseason.list_counts(game, club.id)
    if senior >= C.SENIOR_MAX:
        raise CmdError("The senior list is full (38).")
    d = offseason.contract_demand(game, p)
    if game.payroll(club.id) - p.wage + d["wage"] > game.cap:
        raise CmdError("Not enough cap room to upgrade him.")
    p.rookie, p.wage = False, d["wage"]
    p.contract_end = max(p.contract_end, game.year + 1)
    return f"{p.name} is promoted to the senior list on ${p.wage}k to {p.contract_end}."


def cmd_freeagents(game: Game, args) -> str:
    rows = views.free_agent_rows(game)
    return heading("Free agents") + "\n" + table(rows[:40]) + \
        "\nsign <player> <years> [wage]   (asking wage shown in $k)"


def cmd_picks(game: Game, args) -> str:
    cid = find_club(game, args[0]) if args else _need_user(game).id
    return heading(f"{game.clubs[cid].name} draft picks") + "\n" + table(views.pick_rows(game, cid)) + \
        "\nUse the Code in trades, e.g. 2027R1:COL (the club is who the pick originally belonged to)."


def _parse_items(game: Game, text: str, owner: str) -> list:
    items = []
    for raw in [x.strip() for x in re.split(r",|\+| and ", text) if x.strip()]:
        mt = re.fullmatch(r"(\d{4})\s*r(\d)(?:\s*[:(]\s*(\w+)\s*\)?)?", raw.lower())
        if mt:
            year, rnd = int(mt.group(1)), int(mt.group(2))
            orig = find_club(game, mt.group(3)) if mt.group(3) else None
            cands = [p for p in game.draft["picks"] if p["owner"] == owner and p["year"] == year
                     and p["round"] == rnd and (orig is None or p["orig"] == orig)]
            if not cands:
                raise CmdError(f"{game.clubs[owner].name} don't hold a {year} round {rnd} pick"
                               + (f" from {orig}" if orig else "") + ".")
            if len(cands) > 1:
                raise CmdError(f"{game.clubs[owner].name} hold more than one {year} R{rnd} pick - "
                               f"say which, e.g. {year}R{rnd}:{cands[0]['orig']}")
            items.append(cands[0])
        elif raw.lower() not in ("nothing", "none", "-"):
            items.append(find_player(game, raw, pool=game.squad(owner)))
    return items


def cmd_trade(game: Game, args) -> str:
    club = _need_user(game)
    check = bool(args) and args[0].lower() == "check"
    if check:
        args = args[1:]
    elif game.phase not in ("trades", "draft"):
        raise CmdError("Trades can only be completed in the trade period (after the season). "
                       "You can test the market any time with 'trade check ...'.")
    text = " ".join(args)
    mt = re.match(r"(?:with\s+)?(\S+)\s+give\s+(.*?)\s+(?:for|get)\s+(.*)$", text, re.I)
    if not mt:
        raise CmdError("Usage: trade [check] <CLUB> give <players/picks> for <players/picks>\n"
                       "   e.g. trade check GEE give 2027R1, Tom Smith for Jack Brown\n"
                       "   Items are separated by commas; picks look like 2027R2 or 2027R2:GEE.")
    ai_id = find_club(game, mt.group(1))
    if ai_id == club.id:
        raise CmdError("You can't trade with yourself.")
    give = _parse_items(game, mt.group(2), club.id)
    get = _parse_items(game, mt.group(3), ai_id)
    res = offseason.evaluate_trade(game, ai_id, give, get)
    if check or not res["ok"]:
        return ("[trade check] " if check else "") + res["msg"]
    offseason.execute_trade(game, club.id, ai_id, give, get)
    repair_lineup(game, club.id)
    return "DONE. " + res["msg"]


def draft_screen(game: Game) -> str:
    club = _need_user(game)
    out = [heading(f"{game.draft['pool_year']} national draft")]
    live = game.draft.get("live")
    if live:
        slot = offseason.draft_on_clock(game)
        if live["log"]:
            out.append("Picks so far:")
            out += [f"  {n:>2}. {cid}  {name} ({pos}, {age})" for n, cid, pid, name, pos, age in live["log"][-12:]]
        if slot:
            mine = [o["n"] for o in live["order"][live["idx"]:] if o["owner"] == club.id]
            out.append(f"\nON THE CLOCK: pick {slot['n']} - {game.clubs[slot['owner']].name}"
                       + ("  <- that's you!" if slot["owner"] == club.id else ""))
            out.append("Your remaining picks: " + (", ".join(map(str, mine)) or "none"))
        else:
            out.append("\nThe draft is complete.")
    else:
        out.append("Draft order is set after the Grand Final. Your picks: "
                   + ", ".join(r["Pick"] + f" (~#{r['Est. position']})" for r in views.pick_rows(game, club.id)
                               if r["Pick"].startswith(str(game.year))))
    out.append("\nDraft board (your recruiters' ranking - potential is a range, not a promise):")
    out.append(table(views.prospect_rows(game, 30)))
    out.append("draft pick <player>  |  draft auto (take the top-ranked player)  |  player <name> for a closer look")
    return "\n".join(out)


def cmd_draft(game: Game, args) -> str:
    club = _need_user(game)
    if not args:
        return draft_screen(game)
    sub = args[0].lower()
    if game.phase != "draft":
        raise CmdError("The draft is held after the trade period. 'draft' on its own shows the board.")
    pool = [game.players[pid] for pid in game.draft["pool"]]
    if sub == "auto":
        p = offseason.draft_board(game)[0]
    elif sub == "pick":
        p = find_player(game, " ".join(args[1:]), pool=pool)
    else:
        p = find_player(game, " ".join(args), pool=pool)
    ok, msg = offseason.user_draft_pick(game, p)
    if not ok:
        raise CmdError(msg)
    offseason.run_draft(game, stop_for_user=True)
    return msg + f"  ({p.pos}, {p.age}, OVR {ovr(p)}, true potential {round(p.potential)})\n" + draft_screen(game)


# -- moving time forward -------------------------------------------------------
def review_text(game: Game) -> str:
    r = game.meta.get("review") or {}
    s = game.season
    aw = s["awards"]
    out = [heading(f"{game.year} season review"),
           f"Premiers: {game.clubs[s['premier']].full_name}   Runners-up: {game.clubs[s['runner_up']].name}",
           f"Brownlow: {aw['brownlow'][0]} ({aw['brownlow'][1]}) {aw['brownlow'][2]} votes   "
           f"Coleman: {aw['coleman'][0]} ({aw['coleman'][1]}) {aw['coleman'][2]} goals"
           + (f"   Rising Star: {aw['rising_star'][0]} ({aw['rising_star'][1]})" if aw.get("rising_star") else "")]
    if r:
        club = game.user
        out.append(f"\n{club.name}: finished {_ordinal(r['position'])}"
                   + (f" - {r['finish']}" if r.get("finish") else "")
                   + f". The board wanted: {r['label']}.")
        out.append(f"The board is {r['verdict']} (confidence {r['confidence']:.0f}/100, {r['delta']:+.0f}). "
                   f"Season result: {money(r['profit'])}.")
        if r.get("bnf"):
            out.append("Best and fairest: " + ", ".join(f"{n} ({v:+.0f})" for n, v in r["bnf"]))
        if r.get("retired"):
            out.append("Retiring: " + ", ".join(f"{n} ({age}, {gm} games)" for n, _, age, gm in r["retired"]))
        if r.get("sacked"):
            out.append("\n*** The board has run out of patience. You have been SACKED. ***")
    return "\n".join(out)


def round_report(game: Game, rep: dict, brief: bool = False) -> str:
    out = [heading(rep["label"])]
    um = rep.get("user_match")
    if rep.get("notes"):
        out.append("Late changes: " + "; ".join(rep["notes"]))
    if um:
        out.append(views.result_text(game, um) if brief else match_report(game, um))
    elif rep["matches"][0]["rnd"] == "GF":
        um = rep["matches"][0]                     # everyone watches the Grand Final
        out.append(match_report(game, um, both=True))
    others = [m for m in rep["matches"] if m is not um]
    if not brief and others:
        out.append("\nAround the grounds:" if rep.get("user_match") else "\nResults:")
        out += [f"  {m['rnd']}: " * (rep["kind"] == "finals") + f"  {views.result_text(game, m)}".lstrip()
                if rep["kind"] == "finals" else f"  {views.result_text(game, m)}" for m in others]
        if rep["kind"] == "round":
            out.append(cmd_ladder(game, []))
    if rep.get("finals_set"):
        out.append("\nThe home-and-away season is over. Finals week one:")
        out += [f"  {m['rnd']}: {views.result_text(game, m)}" for m in game.season["finals"][0]["matches"]]
    return "\n".join(out)


def advance_step(game: Game, rng=None, confirm: bool = False) -> dict:
    """Move the game on by one step, whatever phase it is in, and report what
    happened as data.  Both front ends build on this."""
    rng = rng or random
    club = _need_user(game)
    if game.meta.get("sacked"):
        raise CmdError(_phase_hint(game).strip())
    ph = game.phase
    if ph == "season":
        return {"kind": "round", "rep": season.play_round(game, rng)}
    if ph == "finals":
        rep = season.play_finals_week(game, rng)
        if game.phase == "review":
            game.meta["review"] = offseason.season_review(game, rng)
        return {"kind": "finals", "rep": rep, "season_over": game.phase == "review"}
    if ph == "review":
        offseason.open_contracts(game)
        return {"kind": "contracts_open"}
    if ph == "contracts":
        ooc = offseason.out_of_contract(game, club.id)
        if ooc and not confirm:
            return {"kind": "unsigned", "players": ooc}
        return {"kind": "trades_open", "lost": offseason.close_contracts(game, rng)}
    if ph == "trades":
        offseason.close_trades(game, rng)
        return {"kind": "draft_open"}
    if ph == "draft":
        if game.payroll(club.id) > game.cap * 1.04:      # a little over can be restructured away
            raise CmdError(f"You are well over next season's cap ({money(game.payroll(club.id))} v {money(game.cap)}). "
                           f"Delist or trade before the season can start.")
        return {"kind": "new_season", "rep": offseason.finish_draft_and_roll_over(game, rng)}
    raise CmdError(f"Unknown phase {ph}")


def advance(game: Game, rng=None, confirm: bool = False, brief: bool = False) -> str:
    """Text version of advance_step."""
    step = advance_step(game, rng, confirm)
    kind, club = step["kind"], game.user
    if kind == "round":
        return round_report(game, step["rep"], brief)
    if kind == "finals":
        out = round_report(game, step["rep"], brief)
        if step["season_over"]:
            return out + "\n" + review_text(game) + "\n" + _phase_hint(game)
        nxt = game.season["finals"][-1]
        return out + f"\n\nNext: {nxt['name']}\n" + "\n".join(
            f"  {m['rnd']}: {views.result_text(game, m)}" for m in nxt["matches"])
    if kind == "contracts_open":
        return "Contract talks are open.\n" + cmd_contracts(game, [])
    if kind == "unsigned":
        return ("These players are still unsigned and WILL LEAVE if you advance:\n  "
                + ", ".join(f"{p.name} ({p.pos} {ovr(p)}, {p.age})" for p in step["players"])
                + "\nRe-sign with 'offer <player> <years>' / 'offer all', or run 'advance confirm' to let them go.")
    if kind == "trades_open":
        lost = step["lost"]
        return ((f"Gone: {', '.join(lost)}.\n" if lost else "")
                + "The trade period is open.\n" + cmd_picks(game, []) + "\n" + _phase_hint(game))
    if kind == "draft_open":
        trades = [n["text"] for n in game.news[-40:] if n["tag"] == "trade" and n["year"] == game.year]
        return ("Trade period closed.\n" + "\n".join("  " + t for t in trades[-10:]) + "\n" + draft_screen(game))
    rep = step["rep"]
    out = [heading(f"Welcome to {rep['year']}")]
    mine = [x for x in rep["draft_log"] if x[1] == club.id]
    if mine:
        out.append("Your draftees: " + ", ".join(f"#{n} {name} ({pos})" for n, _, _, name, pos, _ in mine))
    if rep["filled"]:
        out.append("Signed to fill the list: " + ", ".join(rep["filled"]))
    if rep["notes"]:
        out.append("Pre-season whispers:")
        out += ["  " + n for n in rep["notes"]]
    out.append(cmd_status(game, []))
    return "\n".join(out)


def cmd_sim(game: Game, args, rng=None) -> str:
    confirm = any(a.lower() == "confirm" for a in args)
    n = next((int(a) for a in args if a.isdigit()), 1)
    if n <= 1:
        return advance(game, rng, confirm)
    out = []
    for i in range(n):
        if game.phase not in ("season", "finals") or game.meta.get("sacked"):
            out.append(_phase_hint(game))
            break
        out.append(advance(game, rng, confirm, brief=(i < n - 1 and game.phase == "season")))
    return "\n".join(out)


def cmd_review(game: Game, args) -> str:
    if not game.season.get("premier"):
        raise CmdError("The season isn't over yet.")
    return review_text(game)


HELP = """AFL MANAGER - commands
 Getting started   clubs | choose <CLUB> [your name] | status | help
 Your list         squad [sort] | squad <CLUB> | player <name or #id>
 Selection         lineup | pick auto | pick <SLOT> <player> | swap <p1>, <p2> | captain <player>
                   selection auto|manual   (auto = assistant coach picks the best 23 every week)
 Game plan         tactics [key=value ...] | tactics preset <name> | training [focus] [intensity]
 Match day         preview | sim [n] (play the next round/s) | match [id] [all] | results [round|finals]
 Competition       ladder | fixture [CLUB] | stats goals|disposals|rating|votes|marks|tackles|hitouts|clearances
 Club              finances | board | news [n] | history | review
 List management   contracts | offer <player> <years> [wage] | offer all | delist <player> | promote <rookie>
                   freeagents | sign <player> <years> [wage] | picks [CLUB]
                   trade [check] <CLUB> give <items> for <items>      e.g. give 2027R1, Smith for Jones
                   draft | draft pick <player> | draft auto
 Time              advance (same as sim) - also steps through the off-season
 Sorts for squad:  pos ovr pot age form fit wage value contract goals disp rating name
 Slots: BPL FB BPR / HBL CHB HBR / WL C WR / HFL CHF HFR / FPL FF FPR / RUCK RR ROV / IC1-IC5"""

COMMANDS = {
    "help": lambda g, a: HELP, "clubs": cmd_clubs, "choose": cmd_choose, "takejob": cmd_choose,
    "status": cmd_status, "home": cmd_status, "squad": cmd_squad, "list": cmd_squad, "club": cmd_squad,
    "player": cmd_player, "lineup": cmd_lineup, "team": cmd_lineup, "pick": cmd_pick,
    "select": cmd_pick, "swap": cmd_swap, "captain": cmd_captain, "tactics": cmd_tactics,
    "selection": cmd_selection,
    "training": cmd_training, "ladder": cmd_ladder, "fixture": cmd_fixture, "fixtures": cmd_fixture,
    "results": cmd_results, "match": cmd_match, "preview": cmd_preview, "stats": cmd_stats,
    "leaders": cmd_stats, "news": cmd_news, "history": cmd_history, "finances": cmd_finances,
    "finance": cmd_finances, "board": cmd_board, "contracts": cmd_contracts, "offer": cmd_offer,
    "resign": cmd_offer, "sign": cmd_offer, "delist": cmd_delist, "promote": cmd_promote,
    "freeagents": cmd_freeagents, "picks": cmd_picks, "trade": cmd_trade, "draft": cmd_draft,
    "review": cmd_review, "sim": cmd_sim, "advance": cmd_sim, "next": cmd_sim, "play": cmd_sim,
}
# Plain-English phrasings people actually type.
PHRASES = [
    (r"^(show|view|see|open|my|the)\s+", ""), (r"^simulate( the)?( next)?( match| round| game)?", "sim"),
    (r"^play( the)?( next)?( match| round| game)", "sim"), (r"^next (match|round|game)", "sim"),
    (r"^set (the )?(team|lineup|side).*", "pick auto"), (r"^auto ?(pick|select).*", "pick auto"),
    (r"^run (the )?draft", "draft auto"), (r"^table", "ladder"), (r"^free agents", "freeagents"),
    (r"^(team sheet|selected side)", "lineup"), (r"^roster", "squad"),
]


def refresh_auto_lineup(game: Game) -> None:
    """In AUTO selection, keep the stored team sheet equal to what will run out."""
    club = game.user
    if club and game.meta.get("selection", "auto") == "auto" and game.phase in ("season", "finals"):
        club.lineup = auto_select(game, club.id)


def execute(game: Game, line: str, rng=None) -> str:
    """Run one command line and return its output (never raises for user errors)."""
    line = line.strip()
    if not line:
        return ""
    low = line.lower()
    for pat, repl in PHRASES:
        new = re.sub(pat, repl, low, count=1)
        if new != low:
            line = low = new.strip()
    parts = line.split()
    if not parts:
        return cmd_status(game, [])
    cmd, args = parts[0].lower(), parts[1:]
    fn = COMMANDS.get(cmd)
    refresh_auto_lineup(game)
    if not fn:
        return f"Unknown command '{cmd}'. Type 'help' for the list."
    try:
        if fn is cmd_sim:
            return cmd_sim(game, args, rng)
        return fn(game, args)
    except CmdError as e:
        return f"! {e}"
