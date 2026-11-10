"""Season structure: fixture, ladder, playing rounds, finals and awards.

Phases of a year (``game.meta["phase"]``):

    season -> finals -> review -> contracts -> trades -> draft -> (next) season

``advance`` in offseason.py / commands.py walks through them; this module
owns everything up to the final siren of the Grand Final.
"""
from __future__ import annotations

import random

from . import constants as C
from . import development, finance
from .match_engine import simulate_match, score_str
from .models import Game
from .ratings import auto_select, repair_lineup, lineup_problems, overall

FINALS_WEEKS = ["Finals Week 1", "Semi Finals", "Preliminary Finals", "Grand Final"]


# -- fixture -------------------------------------------------------------------
def make_fixture(rng) -> list[list[list[str]]]:
    """23 rounds x 9 games.  Everyone meets once (17 rounds, circle method),
    then six return rounds; the nine traditional rivalries always meet twice."""
    n = len(C.CLUBS)
    arr = [None] * n
    pairs = C.RIVALRIES[:]
    rng.shuffle(pairs)
    for i, (a, b) in enumerate(pairs):       # seed the circle so round 0 = rivalry round
        if rng.random() < 0.5:
            a, b = b, a
        arr[i], arr[n - 1 - i] = a, b
    rounds, cur = [], arr[:]
    for r in range(n - 1):
        rd = []
        for i in range(n // 2):
            a, b = cur[i], cur[n - 1 - i]
            if (r + i) % 2:
                a, b = b, a
            rd.append([a, b])
        rounds.append(rd)
        cur = [cur[0], cur[-1]] + cur[1:-1]
    rivalry, others = rounds[0], rounds[1:]
    doubles = [rivalry] + rng.sample(others, 5)
    twice = {frozenset(m) for rd in doubles for m in rd}
    first = rounds[:]
    rng.shuffle(first)
    returns = [[[b, a] for a, b in rd] for rd in doubles]
    rng.shuffle(returns)
    fixture = first + returns
    # even out home games (11 or 12 each) by flipping one-off meetings
    home = {c[0]: 0 for c in C.CLUBS}
    for rd in fixture:
        for h, _ in rd:
            home[h] += 1
    for _ in range(40):
        flipped = False
        for rd in fixture:
            for m in rd:
                if frozenset(m) in twice:
                    continue
                if home[m[0]] - home[m[1]] >= 2:
                    home[m[0]] -= 1
                    home[m[1]] += 1
                    m[0], m[1] = m[1], m[0]
                    flipped = True
        if not flipped:
            break
    return fixture


def _new_match(game: Game, rnd, home: str, away: str, venue: str | None = None) -> dict:
    game.meta["next_mid"] += 1
    return {"id": game.meta["next_mid"], "rnd": rnd, "home": home, "away": away,
            "venue": venue or game.clubs[home].ground, "played": False}


def start_season(game: Game, rng=None) -> None:
    rng = rng or random
    fixture = make_fixture(rng)
    game.season = {
        "year": game.year,
        "rounds": [[_new_match(game, r + 1, h, a) for h, a in rd] for r, rd in enumerate(fixture)],
        "finals": [], "seeds": [], "awards": {}, "premier": None, "runner_up": None,
    }
    game.meta["phase"], game.meta["round"] = "season", 1
    for club in game.clubs.values():
        club.ledger, club.last_ledger = {}, {}


# -- ladder --------------------------------------------------------------------
def ladder(game: Game) -> list[dict]:
    rows = {cid: {"club": cid, "P": 0, "W": 0, "L": 0, "D": 0, "PF": 0, "PA": 0, "pts": 0}
            for cid in game.clubs}
    for rd in game.season["rounds"]:
        for m in rd:
            if not m["played"]:
                continue
            h, a, hp, ap = rows[m["home"]], rows[m["away"]], m["hs"][2], m["as"][2]
            h["P"] += 1; a["P"] += 1
            h["PF"] += hp; h["PA"] += ap; a["PF"] += ap; a["PA"] += hp
            if hp > ap:
                h["W"] += 1; a["L"] += 1; h["pts"] += 4
            elif ap > hp:
                a["W"] += 1; h["L"] += 1; a["pts"] += 4
            else:
                h["D"] += 1; a["D"] += 1; h["pts"] += 2; a["pts"] += 2
    out = list(rows.values())
    for r in out:
        r["pct"] = 100.0 * r["PF"] / r["PA"] if r["PA"] else 0.0
    out.sort(key=lambda r: (r["pts"], r["pct"], r["PF"]), reverse=True)
    for i, r in enumerate(out):
        r["pos"] = i + 1
    return out


def ladder_pos(game: Game, club_id: str) -> int:
    return next(r["pos"] for r in ladder(game) if r["club"] == club_id)


def club_matches(game: Game, club_id: str) -> list[dict]:
    ms = [m for rd in game.season["rounds"] for m in rd if club_id in (m["home"], m["away"])]
    ms += [m for wk in game.season["finals"] for m in wk["matches"] if club_id in (m["home"], m["away"])]
    return ms


def current_matches(game: Game) -> list[dict]:
    """The matches about to be played (this round / this week of finals)."""
    if game.phase == "season":
        return game.season["rounds"][game.meta["round"] - 1]
    if game.phase == "finals" and game.season["finals"]:
        return game.season["finals"][-1]["matches"]
    return []


def next_match(game: Game, club_id: str) -> dict | None:
    return next((m for m in current_matches(game)
                 if not m["played"] and club_id in (m["home"], m["away"])), None)


def find_match(game: Game, match_id: int) -> dict | None:
    for rd in game.season["rounds"]:
        for m in rd:
            if m["id"] == match_id:
                return m
    for wk in game.season["finals"]:
        for m in wk["matches"]:
            if m["id"] == match_id:
                return m
    return None


# -- playing matches -----------------------------------------------------------
def prepare_lineups(game: Game) -> list[str]:
    """AI clubs pick their sides.  The user's side is picked by the assistant
    coach when selection is 'auto'; in 'manual' it is only patched if invalid."""
    notes = []
    user = game.meta.get("user_club")
    for cid, club in game.clubs.items():
        if cid == user and game.meta.get("selection", "auto") == "manual":
            if lineup_problems(game, cid):
                notes = repair_lineup(game, cid)
        else:
            club.lineup = auto_select(game, cid, 0.25 if club.strategy == "rebuild" else 0.0)
    return notes


def _stat_line(st: dict) -> str:
    bits = [f"{st['k'] + st['hb']} disp"]
    if st["g"]:
        bits.append(f"{st['g']} goal{'s' if st['g'] > 1 else ''}")
    if st["m"] >= 6:
        bits.append(f"{st['m']} marks")
    if st["t"] >= 6:
        bits.append(f"{st['t']} tackles")
    if st["ho"] >= 15:
        bits.append(f"{st['ho']} hit-outs")
    if st["cl"] >= 6:
        bits.append(f"{st['cl']} clearances")
    return ", ".join(bits)


def play_match(game: Game, m: dict, rng, keep_detail: bool) -> dict:
    """Simulate one fixture and apply everything that flows from it."""
    final = not isinstance(m["rnd"], int)
    res = simulate_match(game, m["home"], m["away"], m["venue"], is_final=final, rng=rng)
    year = game.year
    m.update(played=True, hs=res["hs"], qs=res["qs"], wet=res["wet"], et=res["et"])
    m["as"] = res["as"]
    clubs = (game.clubs[m["home"]], game.clubs[m["away"]])

    # player consequences: stats, form, fitness, injuries
    injuries, gk = [], ([], [])
    for pid, st in res["players"].items():
        p = game.players[pid]
        s = p.season(year)
        s["gm"] += 1
        for k in ("k", "hb", "m", "t", "g", "b", "ho", "cl", "i50"):
            s[k] += st[k]
        s["rt"] = round(s["rt"] + st["rt"], 1)
        p.career["games"] += 1
        p.career["goals"] += st["g"]
        p.form = (p.form + [st["rt"]])[-5:]
        p.reserves = 0.0
        if st["g"]:
            gk[st["side"]].append((st["g"], p.short))
        inj = development.match_wear(game, p, clubs[st["side"]].tactics,
                                     st["slot"] in C.FIELD_SLOTS, rng)
        if inj:
            injuries.append({"pid": pid, "name": p.name, "club": p.club, **inj})
    if not final:
        for pid, v in zip(res["votes"], (3, 2, 1)):
            game.players[pid].season(year)["v"] += v
    m["best"] = [[game.players[pid].name, game.players[pid].club, res["players"][pid]["rt"],
                  _stat_line(res["players"][pid])] for pid in res["votes"]]
    m["gk"] = [", ".join(f"{n} {g}" if g > 1 else n for g, n in sorted(side, reverse=True)[:6])
               for side in gk]
    m["team"] = res["team"]
    m["inj"] = [[i["name"], i["club"], i["type"], i["weeks"]] for i in injuries]
    m["att"] = finance.match_day(game, m, rng)
    if keep_detail:
        m["detail"] = {"players": {str(pid): st for pid, st in res["players"].items()},
                       "comm": res["comm"], "tactics": res["tactics"]}
    finance.board_after_match(game, m)
    for i in injuries:
        if i["weeks"] >= 4 or i["club"] == game.meta.get("user_club"):
            game.add_news(f"{i['name']} ({i['club']}) - {i['type']}, out {i['weeks']} week"
                          f"{'s' if i['weeks'] != 1 else ''}.", "injury")
    return m


def play_round(game: Game, rng=None) -> dict:
    """Play the next home-and-away round for all 18 clubs."""
    rng = rng or random
    rnd = game.meta["round"]
    notes = prepare_lineups(game)
    user = game.meta.get("user_club")
    matches = game.season["rounds"][rnd - 1]
    for m in matches:
        play_match(game, m, rng, keep_detail=user in (m["home"], m["away"]) or game.meta.get("keep_all_detail", False))
    development.weekly_tick(game, rng, played=_who_played(matches, game))
    finance.weekly(game)
    report = {"kind": "round", "label": f"Round {rnd}", "matches": matches, "notes": notes,
              "user_match": next((m for m in matches if user in (m["home"], m["away"])), None)}
    if rnd >= C.HA_ROUNDS:
        _end_home_and_away(game)
        report["finals_set"] = True
    else:
        game.meta["round"] = rnd + 1
    return report


def _who_played(matches, game) -> set:
    played = set()
    for m in matches:
        for cid in (m["home"], m["away"]):
            played.update(game.clubs[cid].lineup.values())
    return played


# -- awards and finals ---------------------------------------------------------
def leaders(game: Game, key: str, n: int = 10, min_games: int = 1, club: str | None = None) -> list:
    """Season leaders.  key: g, disp, rt (average rating), v (votes), m, t, ho, cl."""
    y = str(game.year)
    rows = []
    for p in game.players.values():
        s = p.stats.get(y)
        if not s or s["gm"] < min_games or (club and p.club != club):
            continue
        if key == "disp":
            val = (s["k"] + s["hb"]) / s["gm"]
        elif key == "rt":
            val = s["rt"] / s["gm"]
        elif key in ("m", "t", "ho", "cl"):
            val = s[key] / s["gm"]
        else:
            val = s[key]
        rows.append((val, p))
    rows.sort(key=lambda r: r[0], reverse=True)
    return rows[:n]


def _end_home_and_away(game: Game) -> None:
    lad = ladder(game)
    s = game.season
    s["seeds"] = [r["club"] for r in lad[:8]]
    s["final_ladder"] = [r["club"] for r in lad]
    aw = s["awards"]
    v, p = leaders(game, "v", 1)[0]
    aw["brownlow"] = [p.name, p.club, int(v)]
    g, p = leaders(game, "g", 1)[0]
    aw["coleman"] = [p.name, p.club, int(g)]
    kids = [(val, pl) for val, pl in leaders(game, "rt", 400, min_games=10) if pl.age <= 21]
    if kids:
        aw["rising_star"] = [kids[0][1].name, kids[0][1].club, round(kids[0][0], 2)]
    game.add_news(f"Brownlow Medal: {aw['brownlow'][0]} ({aw['brownlow'][1]}) with {aw['brownlow'][2]} votes.", "award")
    game.add_news(f"Coleman Medal: {aw['coleman'][0]} ({aw['coleman'][1]}) with {aw['coleman'][2]} goals.", "award")
    game.add_news("Minor premiers: " + game.clubs[lad[0]['club']].full_name + ". The top eight is locked in.", "league")
    game.meta["phase"] = "finals"
    _schedule_finals_week(game)


def _schedule_finals_week(game: Game) -> None:
    s = game.season
    seeds = s["seeds"]
    rank = {c: i for i, c in enumerate(seeds)}

    def res(label):      # (winner, loser) of an earlier final
        for wk in s["finals"]:
            for m in wk["matches"]:
                if m["rnd"] == label:
                    return (m["home"], m["away"]) if m["hs"][2] > m["as"][2] else (m["away"], m["home"])

    def mk(label, a, b, venue=None):
        if rank[a] > rank[b]:
            a, b = b, a                       # higher seed hosts
        return _new_match(game, label, a, b, venue)

    week = len(s["finals"])
    if week == 0:
        ms = [mk("QF1", seeds[0], seeds[3]), mk("QF2", seeds[1], seeds[2]),
              mk("EF1", seeds[4], seeds[7]), mk("EF2", seeds[5], seeds[6])]
    elif week == 1:
        ms = [mk("SF1", res("QF1")[1], res("EF1")[0]), mk("SF2", res("QF2")[1], res("EF2")[0])]
    elif week == 2:
        ms = [mk("PF1", res("QF1")[0], res("SF2")[0]), mk("PF2", res("QF2")[0], res("SF1")[0])]
    else:
        ms = [mk("GF", res("PF1")[0], res("PF2")[0], C.GRAND_FINAL_VENUE)]
    s["finals"].append({"name": FINALS_WEEKS[week], "matches": ms})


def play_finals_week(game: Game, rng=None) -> dict:
    rng = rng or random
    notes = prepare_lineups(game)
    user = game.meta.get("user_club")
    wk = game.season["finals"][-1]
    for m in wk["matches"]:
        play_match(game, m, rng, keep_detail=True)   # every final keeps its full record
    development.weekly_tick(game, rng, played=_who_played(wk["matches"], game))
    report = {"kind": "finals", "label": wk["name"], "matches": wk["matches"], "notes": notes,
              "user_match": next((m for m in wk["matches"] if user in (m["home"], m["away"])), None)}
    if wk["matches"][0]["rnd"] == "GF":
        gf = wk["matches"][0]
        win, lose = (gf["home"], gf["away"]) if gf["hs"][2] > gf["as"][2] else (gf["away"], gf["home"])
        game.season["premier"], game.season["runner_up"] = win, lose
        game.add_news(f"{game.clubs[win].full_name} are the {game.year} premiers, beating "
                      f"{game.clubs[lose].name} {score_str(*max(gf['hs'], gf['as'], key=lambda x: x[2])[:2])} to "
                      f"{score_str(*min(gf['hs'], gf['as'], key=lambda x: x[2])[:2])}.", "league")
        game.meta["phase"] = "review"
        report["premier"] = win
    else:
        _schedule_finals_week(game)
    return report


def finals_finish(game: Game) -> dict:
    """club -> how far it went: 9+ = missed, else 'Premier', 'Runner-up', ..."""
    out = {}
    for wk in game.season["finals"]:
        for m in wk["matches"]:
            if not m["played"]:
                continue
            loser = m["away"] if m["hs"][2] > m["as"][2] else m["home"]
            stage = m["rnd"][:2]
            if stage in ("EF", "SF", "PF", "GF"):
                out[loser] = {"EF": "Elimination final", "SF": "Semi final",
                              "PF": "Preliminary final", "GF": "Runner-up"}[stage]
    if game.season.get("premier"):
        out[game.season["premier"]] = "Premier"
    return out


def best_and_fairest(game: Game, club_id: str, n: int = 5) -> list:
    """Club champion count: every game earns votes for how far above par he rated."""
    y = str(game.year)
    rows = []
    for p in game.squad(club_id):
        s = p.stats.get(y)
        if s and s["gm"]:
            rows.append((round(s["rt"] - 5.0 * s["gm"], 1), p))
    rows.sort(key=lambda r: r[0], reverse=True)
    return rows[:n]
