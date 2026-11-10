"""Club finances and the board.

Deliberately simple for now: a round-by-round ledger of the big income and
expense lines (all in $k), gate receipts driven by crowds, and a board whose
confidence in you moves with results measured against what they expected.
"""
from __future__ import annotations

import math

from . import constants as C
from .models import Game, Club
from .ratings import best22_rating

PRIZE_MONEY = {"Premier": 1200, "Runner-up": 660, "Preliminary final": 300,
               "Semi final": 150, "Elimination final": 75}


def _add(club: Club, key: str, amount: float) -> None:
    amount = int(round(amount))
    club.ledger[key] = club.ledger.get(key, 0) + amount
    club.last_ledger[key] = club.last_ledger.get(key, 0) + amount
    club.balance += amount


def match_day(game: Game, m: dict, rng) -> int:
    """Work out the crowd and bank the gate for the home club."""
    from .season import ladder
    home, away = game.clubs[m["home"]], game.clubs[m["away"]]
    vstate, capacity = C.VENUES[m["venue"]][0], C.VENUES[m["venue"]][1]
    final = not isinstance(m["rnd"], int)
    crowd = home.supporters * (0.40 if home.state == vstate else 0.10)
    crowd += away.supporters * (0.22 if away.state == vstate else 0.03)
    pos = {r["club"]: r["pos"] for r in ladder(game)}
    for cid in (home.id, away.id):
        crowd *= 1.10 if pos[cid] <= 4 else 0.92 if pos[cid] >= 15 else 1.0
    if m.get("wet"):
        crowd *= 0.9
    crowd *= 1000 * rng.uniform(0.85, 1.15)
    if final:
        crowd = capacity * (1.0 if m["rnd"] == "GF" else rng.uniform(0.8, 1.0))
    att = int(min(capacity, crowd))
    home.last_ledger = {}
    away.last_ledger = {}
    # finals gates go to the league; clubs get prize money instead
    if not final:
        _add(home, "gate", att * 0.014)
    return att


def weekly(game: Game) -> None:
    """Per-round share of the season-long income and expense lines."""
    n = C.HA_ROUNDS
    scale = game.cap / C.SALARY_CAP              # everything inflates with the cap
    for cid, club in game.clubs.items():
        s = club.supporters
        _add(club, "membership", s * 190 / n * scale)
        _add(club, "sponsorship", (9000 + s * 90) / n * scale)
        _add(club, "afl_distribution", (13500 + max(0.0, 80 - s) * 170) / n * scale)
        _add(club, "player_payments", -game.payroll(cid) / n)
        _add(club, "football_dept", -9000 / n * scale)
        _add(club, "operations", -(7000 + s * 215) / n * scale)


def profit(club: Club) -> int:
    return sum(club.ledger.values())


# -- the board -----------------------------------------------------------------
def set_board_expectations(game: Game) -> None:
    """Expectations follow list quality: the better the list, the higher the bar."""
    ranking = sorted(game.clubs, key=lambda c: best22_rating(game, c), reverse=True)
    for i, cid in enumerate(ranking):
        rank = i + 1
        target = 4 if rank <= 3 else 8 if rank <= 7 else 12 if rank <= 12 else 16
        label = next(lbl for pos, lbl in C.BOARD_TIERS if target <= pos)
        b = game.clubs[cid].board
        b["target"], b["label"], b["list_rank"] = target, label, rank
        # a new season softens the mood either way, but the board has a memory
        b["confidence"] = round(min(85.0, max(15.0, 0.65 * b.get("confidence", 60.0) + 0.35 * 55.0)), 1)


def win_probability(game: Game, home_id: str, away_id: str) -> float:
    """Rough pre-game expectation, used by the board and the match preview."""
    diff = best22_rating(game, home_id) - best22_rating(game, away_id)
    return 1.0 / (1.0 + math.exp(-(0.30 * diff + 0.15)))


def board_after_match(game: Game, m: dict) -> None:
    user = game.meta.get("user_club")
    if user not in (m["home"], m["away"]):
        return
    p_home = win_probability(game, m["home"], m["away"])
    hp, ap = m["hs"][2], m["as"][2]
    res_home = 1.0 if hp > ap else 0.5 if hp == ap else 0.0
    exp, res = (p_home, res_home) if user == m["home"] else (1 - p_home, 1 - res_home)
    final = not isinstance(m["rnd"], int)
    b = game.clubs[user].board
    b["confidence"] = round(max(0.0, min(100.0, b["confidence"] + 4.5 * (res - exp) * (1.6 if final else 1.0))), 1)


def season_review(game: Game) -> dict:
    """End-of-year verdict for the user plus prize money for everyone."""
    from .season import finals_finish
    finish = finals_finish(game)
    for cid, stage in finish.items():
        _add(game.clubs[cid], "prize_money", PRIZE_MONEY.get(stage, 0))
    club = game.user
    if not club:
        return {}
    pos = game.season["final_ladder"].index(club.id) + 1
    b = club.board
    delta = 0.0
    if pos <= b["target"]:
        delta += 6.0 + (b["target"] - pos) * 1.0
    else:
        delta -= min(35.0, 4.0 * (pos - b["target"]))
    stage = finish.get(club.id)
    delta += {"Premier": 30, "Runner-up": 14, "Preliminary final": 8, "Semi final": 4}.get(stage, 0)
    pl = profit(club)
    delta += 3.0 if pl > 1500 else -4.0 if pl < -2500 else 0.0
    b["confidence"] = round(max(0.0, min(100.0, b["confidence"] + delta)), 1)
    verdict = ("delighted" if delta >= 20 else "pleased" if delta >= 8 else "satisfied" if delta >= 0
               else "disappointed" if delta > -15 else "furious")
    # no board sacks a coach after one season; after that, lose them and you're gone
    sacked = b["confidence"] < 12.0 and game.year > game.meta.get("hired", game.year)
    return {"position": pos, "target": b["target"], "label": b["label"], "finish": stage,
            "profit": pl, "delta": round(delta, 1), "confidence": b["confidence"],
            "verdict": verdict, "sacked": sacked}
