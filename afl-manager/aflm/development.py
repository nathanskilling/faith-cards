"""Everything that changes a player over time: match wear, weekly training,
injuries, reserves form, and the yearly cycle of growth, decline and retirement.

Growth model
------------
A player has a hidden ceiling (``potential``, OVR scale) and a hidden
``dev_rate``.  He closes the gap to that ceiling in two ways:

* weekly, during the season - faster if young, if the gap is big, if the club
  trains harder and if he is actually playing senior footy;
* one pre-season block each summer, with a big random swing, which is where
  breakouts (and the kid who never comes on) come from.

Gains are expressed in OVR points and then spread across the attributes that
matter for his position, tilted towards the club's training focus.
From 29 on the legs go first: speed and endurance fall away, footy IQ holds.
"""
from __future__ import annotations

import random

from . import constants as C
from .models import Game, Player
from .ratings import overall

WEEKLY_AGE_FACTOR = {18: 1.0, 19: 1.0, 20: 1.0, 21: .9, 22: .8, 23: .65, 24: .5, 25: .35, 26: .2, 27: .1}
SUMMER_SHARE = {19: .18, 20: .20, 21: .22, 22: .24, 23: .26, 24: .28, 25: .30, 26: .30, 27: .30}
BASE_INJURY = 0.026


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def roll_injury(rng, minor: bool = False) -> dict:
    table = [i for i in C.INJURIES if not minor or i[2] <= 4]
    name, lo, hi, _ = rng.choices(table, weights=[i[3] for i in table])[0]
    return {"type": name, "weeks": rng.randint(lo, hi), "new": True}


def match_wear(game: Game, p: Player, tactics: dict, on_field: bool, rng) -> dict | None:
    """Fitness cost of a game and the chance of getting hurt in it."""
    tog = 1.0 if on_field else 0.6
    cost = (17.0 - 0.45 * p.attrs["endurance"]) * tog
    cost += {"low": -2.0, "medium": 0.0, "high": 3.5}[tactics["pressure"]]
    cost += {"slow": -1.0, "balanced": 0.0, "fast": 1.5}[tactics["tempo"]]
    if p.age >= 31:
        cost += 1.5
    risk = BASE_INJURY * tog * (0.5 + p.attrs["injury_prone"] / 10.0) * (1.0 + (100 - p.fitness) / 50.0)
    if p.age >= 31:
        risk *= 1.25
    p.fitness = _clamp(p.fitness - max(3.0, cost), 35.0, 100.0)
    if rng.random() < risk:
        p.injury = roll_injury(rng)
        return p.injury
    return None


def add_growth(p: Player, gain: float, focus_w: dict | None = None) -> None:
    """Raise OVR by ``gain`` points, spread over his position's attributes."""
    if gain <= 0:
        return
    w = C.POS_WEIGHTS[p.pos]
    focus_w = focus_w or {}
    norm = sum(wk * focus_w.get(k, 1.0) for k, wk in w.items())
    for k in w:
        p.attrs[k] = _clamp(p.attrs[k] + (gain / 5.0) * focus_w.get(k, 1.0) / norm, 1.0, 20.0)
    for k in C.SKILL_ATTRS:            # everything else creeps up a little too
        if k not in w and k != "ruck":
            p.attrs[k] = _clamp(p.attrs[k] + gain / 5.0 * 0.3 * focus_w.get(k, 1.0), 1.0, 20.0)


def weekly_tick(game: Game, rng, played: set | None = None) -> None:
    """One week of training, recovery and healing for every listed player."""
    played = played or set()
    for cid, club in game.clubs.items():
        focus = club.training.get("focus", "balanced")
        dev_mult, recover, risk_mult = C.TRAINING_INTENSITY[club.training.get("intensity", "normal")]
        focus_w = C.TRAINING_FOCUS[focus][1]
        if focus == "recovery":
            dev_mult, recover, risk_mult = 0.0, recover + 7.0, 0.3
        for p in game.squad(cid):
            if p.injury:
                if p.injury.pop("new", None):
                    pass                              # hurt this week: clock starts next week
                else:
                    p.injury["weeks"] -= 1
                    if p.injury["weeks"] <= 0:
                        p.injury = None
                        p.fitness = min(p.fitness, 88.0)   # short of a gallop on return
                        if cid == game.meta.get("user_club"):
                            game.add_news(f"{p.name} is fit again and available for selection.", "injury")
                p.fitness = _clamp(p.fitness + recover * 0.8, 35.0, 100.0)
                continue
            p.fitness = _clamp(p.fitness + recover, 35.0, 100.0)
            if p.id not in played:                    # a run in the twos
                p.reserves = round(_clamp(rng.gauss(5.6 + (overall(p) - 64.0) / 7.0, 1.1), 2.0, 10.0), 1)
                if rng.random() < 0.0035 * risk_mult * (0.5 + p.attrs["injury_prone"] / 10.0):
                    p.injury = roll_injury(rng, minor=True)
                    p.injury.pop("new")
                    if cid == game.meta.get("user_club"):
                        game.add_news(f"{p.name} hurt at training ({p.injury['type']}, "
                                      f"{p.injury['weeks']}w).", "injury")
            age_f = WEEKLY_AGE_FACTOR.get(p.age, 0.0)
            if age_f and dev_mult:
                gap = _clamp((p.potential - overall(p)) / 8.0, 0.0, 1.25)
                gain = 0.085 * p.dev_rate * club.dev * age_f * gap * dev_mult * rng.uniform(0.5, 1.5)
                if p.id in played:
                    gain *= 1.25                      # nothing develops a kid like senior footy
                add_growth(p, gain, focus_w)


# -- the yearly cycle ----------------------------------------------------------
def retirement_chance(p: Player) -> float:
    if p.age < 30:
        return 0.0
    o = overall(p)
    ch = 0.06 + 0.11 * (p.age - 30) + (0.25 if o < 68 else 0.0) - (0.10 if o >= 80 else 0.0)
    if p.injury and p.injury["weeks"] >= 20:
        ch += 0.25
    if p.age >= 36:
        ch = max(ch, 0.9)
    return _clamp(ch, 0.0, 0.97)


def process_retirements(game: Game, rng) -> list[Player]:
    gone = []
    for p in list(game.players.values()):
        if p.status == "listed" and rng.random() < retirement_chance(p):
            gone.append(p)
            games = p.career["games"]
            if overall(p) >= 78 or p.club == game.meta.get("user_club"):
                game.add_news(f"{p.name} ({p.club}, {p.age}) has announced his retirement"
                              + (f" after {games} games." if games else "."), "league")
            remove_player(game, p)
    return gone


def remove_player(game: Game, p: Player) -> None:
    """Take a player out of the game entirely (retired / never drafted)."""
    if p.club:
        club = game.clubs[p.club]
        club.lineup = {s: pid for s, pid in club.lineup.items() if pid != p.id}
        if club.captain == p.id:
            club.captain = None
    if p.id in game.free_agents:
        game.free_agents.remove(p.id)
    game.players.pop(p.id, None)


def new_year_progression(game: Game, rng) -> list[str]:
    """Birthday, pre-season growth and age-related decline.  Returns headlines
    about the user's players (breakouts and fades)."""
    notes = []
    user = game.meta.get("user_club")
    for p in game.players.values():
        if p.status == "prospect":
            continue
        before = overall(p)
        p.age += 1
        share = SUMMER_SHARE.get(p.age, 0.0)
        if share:
            swing = rng.choice([0.2, 0.6, 0.9, 1.0, 1.1, 1.4, 2.0])     # breakout or stall
            prog = game.clubs[p.club].dev if p.club else 1.0
            add_growth(p, min(max(0.0, p.potential - before),
                              max(0.0, p.potential - before) * share * p.dev_rate * prog * swing))
        if p.age >= 29:
            k = 1.0 if p.age <= 30 else 1.6 if p.age <= 32 else 2.3
            p.attrs["speed"] -= rng.uniform(0.1, 0.5) * k
            p.attrs["endurance"] -= rng.uniform(0.0, 0.4) * k
            for a in ("kicking", "marking", "handballing", "strength", "tackling", "goal_sense",
                      "intercept", "toughness", "ruck"):
                p.attrs[a] -= rng.uniform(0.0, 0.2) * k
            if p.age <= 31:
                p.attrs["decision"] += 0.15
        if p.age <= 30:
            p.attrs["leadership"] = _clamp(p.attrs["leadership"] + rng.uniform(0.2, 0.8), 1, 20)
            p.attrs["consistency"] = _clamp(p.attrs["consistency"] + rng.uniform(0.0, 0.4), 1, 20)
        for a in C.SKILL_ATTRS:
            p.attrs[a] = _clamp(p.attrs[a], 1.0, 20.0)
        after = overall(p)
        if p.age >= 28:
            p.potential = after
        else:
            p.potential = max(p.potential, after)
        # a summer off heals most things
        if p.injury:
            p.injury["weeks"] -= 22
            p.injury.pop("new", None)
            if p.injury["weeks"] <= 0:
                p.injury = None
        p.fitness, p.form, p.reserves = 100.0, [], 0.0
        # keep saves lean: only the last three seasons of stat lines
        for key in sorted(p.stats)[:-3]:
            del p.stats[key]
        if p.club == user and p.status == "listed":
            if after - before >= 3.5:
                notes.append(f"{p.name} ({p.age}) has had a huge pre-season: {before:.0f} -> {after:.0f}.")
            elif after - before <= -2.0:
                notes.append(f"{p.name} ({p.age}) is slowing down: {before:.0f} -> {after:.0f}.")
    return notes
