"""The assistant coach: reads the state of the club and points out what
deserves the coach's attention this week.

Every tip is ``{"level": "warn" | "info" | "good", "text": ..., "go": screen}``
where ``go`` names the app screen that deals with it.  The heuristics mirror
how the match engine actually works, so the advice is worth following.
"""
from __future__ import annotations

from . import constants as C
from . import offseason, season, views
from .models import Game
from .ratings import (overall, ovr, available, lineup_problems, auto_select, raw_rating,
                      shown_potential, form_value)


def _avg(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def _field(game: Game, cid: str):
    club = game.clubs[cid]
    return {s: game.players[pid] for s, pid in club.lineup.items()
            if s in C.FIELD_SLOTS and pid in game.players}


def matchup_notes(game: Game, cid: str, opp_id: str) -> list[dict]:
    """Tactical reads on the next opponent."""
    me, opp = game.clubs[cid], game.clubs[opp_id]
    mine, theirs = _field(game, cid), _field(game, opp_id)
    if len(mine) < 18 or len(theirs) < 18:
        return []
    tips = []
    skill = _avg(0.6 * p.attrs["kicking"] + 0.4 * p.attrs["decision"] for p in mine.values())
    their_backs = [theirs[s] for s in ("BPL", "FB", "BPR", "HBL", "CHB", "HBR")]
    zoneq = _avg(0.5 * p.attrs["intercept"] + 0.5 * p.attrs["decision"] for p in their_backs)
    if opp.tactics["defence"] == "zone":
        if skill >= zoneq + 0.4:
            tips.append({"level": "good", "go": "plan", "text":
                         f"{opp.name} zone off, but your ball use is good enough to pick it apart. "
                         f"An outside style or fast tempo should find targets."})
        elif skill <= zoneq - 0.4:
            tips.append({"level": "warn", "go": "plan", "text":
                         f"{opp.name}'s zone will feast on loose kicks. Go contested and bring the ball "
                         f"to ground - a small forward line helps."})
    r_me = raw_rating(mine["RUCK"].attrs, "RUCK") * 5
    r_opp = raw_rating(theirs["RUCK"].attrs, "RUCK") * 5
    if r_me - r_opp >= 7:
        tips.append({"level": "good", "go": "plan", "text":
                     f"{mine['RUCK'].short} should dominate the ruck ({r_me:.0f} v {r_opp:.0f}). "
                     f"A contested, stoppage-heavy game cashes that in."})
    elif r_opp - r_me >= 7:
        tips.append({"level": "warn", "go": "plan", "text":
                     f"You will lose the hit-outs ({theirs['RUCK'].short} {r_opp:.0f} v {r_me:.0f}). "
                     f"Keep it moving: an outside style means fewer stoppages decide the game."})
    my_talls = _avg(raw_rating(mine[s].attrs, C.FIELD_SLOTS[s]) for s in ("FB", "CHB")) * 5
    their_talls = _avg(raw_rating(theirs[s].attrs, C.FIELD_SLOTS[s]) for s in ("FF", "CHF")) * 5
    if their_talls - my_talls >= 6 and me.tactics["defence"] == "man":
        tips.append({"level": "warn", "go": "plan", "text":
                     f"Their key forwards ({their_talls:.0f}) have your key backs ({my_talls:.0f}) covered "
                     f"one-on-one. A zone or a loose man would give them help."})
    my_mid = views.line_ratings(game, cid)["M"]
    their_mid = views.line_ratings(game, opp_id)["M"]
    if their_mid - my_mid >= 5 and me.tactics["defence"] != "loose":
        tips.append({"level": "info", "go": "plan", "text":
                     f"Their midfield ({their_mid:.0f}) is well on top of yours ({my_mid:.0f}) on paper. "
                     f"Expect to defend a lot of entries - a loose man behind the ball limits the damage."})
    if opp.tactics["pressure"] == "high" and me.tactics["style"] == "outside" and skill < 14.5:
        tips.append({"level": "warn", "go": "plan", "text":
                     f"{opp.name} bring manic pressure and your outside game needs clean hands you "
                     f"don't quite have. Consider a balanced or contested style this week."})
    return tips[:3]


def advice(game: Game) -> list[dict]:
    club = game.user
    if not club:
        return []
    cid = club.id
    tips = []
    squad = game.squad(cid)
    ph = game.phase
    manual = game.meta.get("selection", "auto") == "manual"

    if ph in ("season", "finals"):
        for prob in lineup_problems(game, cid)[:2]:
            tips.append({"level": "warn", "go": "team", "text": f"Team sheet: {prob}."})
        named = {pid for pid in club.lineup.values()}
        picked = [game.players[pid] for pid in named if pid in game.players]
        if manual and picked:
            floor = min(overall(p) for p in picked)
            knock = sorted((p for p in squad if p.id not in named and available(p)
                            and overall(p) >= floor + 3), key=overall, reverse=True)[:3]
            if knock:
                tips.append({"level": "info", "go": "team", "text":
                             "Banging the door down: " + ", ".join(f"{p.short} ({p.pos} {ovr(p)})" for p in knock)
                             + ". You are picking the side, so nobody is recalled unless you do it."})
        tired = [p for p in picked if p.fitness < 78]
        if len(tired) >= 3:
            tips.append({"level": "warn", "go": "plan", "text":
                         f"{len(tired)} of your 23 are under 78% fitness ("
                         + ", ".join(p.short for p in sorted(tired, key=lambda p: p.fitness)[:4])
                         + "). A light or recovery week, or a rest for the worst of them, will help."})
        avg_fit = _avg(p.fitness for p in picked)
        if avg_fit < 86 and (club.tactics["pressure"] == "high" or club.training.get("intensity") == "heavy"):
            tips.append({"level": "warn", "go": "plan", "text":
                         f"The list is running on fumes (average fitness {avg_fit:.0f}%). "
                         f"High pressure and heavy training together are costing you late in games."})
        m = season.next_match(game, cid)
        if m:
            opp_id = m["away"] if m["home"] == cid else m["home"]
            if opp_id != cid:
                game.clubs[opp_id].lineup = auto_select(
                    game, opp_id, 0.25 if game.clubs[opp_id].strategy == "rebuild" else 0.0)
            tips += matchup_notes(game, cid, opp_id)
        kids = sorted((p for p in squad if p.id not in named and p.age <= 21 and available(p)
                       and p.reserves >= 7.3 and shown_potential(game, p) >= 80),
                      key=lambda p: -p.reserves)[:2]
        for p in kids:
            tips.append({"level": "info", "go": f"player/{p.id}", "text":
                         f"{p.name} ({p.age}, potential {shown_potential(game, p)}) rated {p.reserves} in the "
                         f"reserves. Senior games would speed up his development."})
        hot = [p for p in picked if len(p.form) >= 3 and form_value(p) >= 7.6]
        if hot:
            best = max(hot, key=form_value)
            tips.append({"level": "good", "go": f"player/{best.id}", "text":
                         f"{best.name} is in career-best touch: averaging {form_value(best):.1f} over his last "
                         f"{len(best.form)}."})

    ooc = sorted(offseason.out_of_contract(game, cid), key=overall, reverse=True)
    key_ooc = [p for p in ooc if overall(p) >= 72 or shown_potential(game, p) >= 80]
    if ph == "contracts" and ooc:
        tips.append({"level": "warn", "go": "contracts", "text":
                     f"{len(ooc)} player(s) are unsigned and will walk when the signing period ends"
                     + (": " + ", ".join(f"{p.short} ({ovr(p)})" for p in key_ooc[:4]) if key_ooc else "") + "."})
    elif ph == "season" and game.meta["round"] >= 12 and key_ooc:
        tips.append({"level": "info", "go": "contracts", "text":
                     "Out of contract this year: " + ", ".join(f"{p.short} ({ovr(p)})" for p in key_ooc[:4])
                     + ". You can re-sign them now."})
    room = offseason.cap_space(game, cid)
    if room < 0:
        tips.append({"level": "warn", "go": "contracts", "text":
                     f"You are {views.money(-room)} over the salary cap."})
    elif ph in ("trades", "draft") and room > game.cap * 0.06:
        tips.append({"level": "info", "go": "agents", "text":
                     f"You have {views.money(room)} of cap room to use on free agents or a trade."})
    if ph == "draft":
        slot = offseason.draft_on_clock(game)
        if slot and slot["owner"] == cid:
            tips.append({"level": "warn", "go": "draft", "text":
                         f"You are on the clock with pick {slot['n']}."})
    if ph in ("trades", "draft"):
        senior, rookies = offseason.list_counts(game, cid)
        if senior + rookies >= C.LIST_MAX:
            tips.append({"level": "info", "go": "contracts", "text":
                         "Your list is full (44). You cannot draft or sign anyone until you delist or trade."})
    inj = [p for p in squad if p.injury]
    if len(inj) >= 5:
        tips.append({"level": "info", "go": "squad", "text":
                     f"{len(inj)} players are on the injury list. Lighter training lowers the risk of more."})
    conf = club.board["confidence"]
    if conf < 30:
        tips.append({"level": "warn", "go": "club", "text":
                     f"The board is close to making a change (confidence {conf:.0f}/100). Wins are the only cure."})
    return tips[:7]
