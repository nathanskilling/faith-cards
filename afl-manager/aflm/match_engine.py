"""The match engine.

``simulate_match`` is a pure function of the two selected sides, their game
plans, the venue and a random source.  It never mutates the Game: applying
the result (stats, fitness, injuries, ladder) is season.py's job, which keeps
the engine easy to test and to swap out later.

How a game is played
--------------------
A match is ~105 "passages" of play.  Every passage ends with one side going
inside 50, so the engine is really answering two footy questions over and over:

1. WHO GOES FORWARD?
   * From a centre bounce or stoppage: ruck contest -> clearance -> entry.
     Hit-outs come from the ruckman, clearances from the on-ball brigade.
   * In general play: a contest between the two sides' "territory" ratings
     (midfield, run and spread, ball use, rebound) shaped by style, pressure
     and fatigue, plus momentum from the previous passage (a rebound from an
     intercept mark is the best launching pad in the game).

2. WHAT HAPPENS INSIDE 50?
   * Long shot from outside the arc, or
   * a kick to a target: forward v his defender -> mark and set shot,
     intercept mark (rebound!), or a spoil that brings it to ground, or
   * ground ball: crumbers v small defenders -> snap, rushed behind or clearance.

Every one of those contests uses the attributes of the individual players
involved, scaled by fitness, form, familiarity with the role, home ground
advantage and a per-game "day" roll that depends on Consistency.

Disposals, marks and tackles that happen between the arcs are handed out in
bulk at the end, weighted by role and quality.
"""
from __future__ import annotations

import math
import random

from . import constants as C
from .models import Game
from .ratings import raw_rating, familiarity, condition_mult

# ---- tuning knobs (see tests/calibrate.py) -----------------------------------
PASSAGES_PER_QTR = 26.4     # ~53 inside 50s a side
K_TERRITORY = 0.24          # how sharply territory rating gaps turn into entries
K_RUCK = 0.28
K_CLEAR = 0.22
BASE_REF = 14.5             # attribute level of a typical senior player in his role
REF_RATING = 15.0           # ...and the average role rating the knobs were tuned at

# Role weights for bulk stats
DISP_W = {"C": 1.75, "RR": 1.65, "ROV": 1.6, "W": 1.5, "HBF": 1.5, "RUCK": 1.05,
          "HFF": 1.2, "CHB": 1.1, "BP": 1.05, "FB": 0.9, "CHF": 1.0, "FP": 0.95, "FF": 0.75}
KICK_SHARE = {"C": .50, "RR": .43, "ROV": .50, "W": .62, "HBF": .66, "RUCK": .38,
              "HFF": .60, "CHB": .62, "BP": .60, "FB": .64, "CHF": .62, "FP": .58, "FF": .72}
MARK_W = {"C": .8, "RR": .6, "ROV": .7, "W": 1.3, "HBF": 1.4, "RUCK": .8, "HFF": 1.1,
          "CHB": 1.5, "BP": 1.0, "FB": 1.1, "CHF": 1.2, "FP": .7, "FF": .9}
TACKLE_W = {"C": 1.5, "RR": 1.7, "ROV": 1.4, "W": .8, "HBF": .8, "RUCK": .7, "HFF": .9,
            "CHB": .5, "BP": .9, "FB": .5, "CHF": .6, "FP": 1.2, "FF": .5}
DELIVER_W = {"C": 2.0, "RR": 1.5, "ROV": 1.8, "W": 2.0, "HBF": 1.2, "HFF": 1.5, "RUCK": .5,
             "CHF": .7, "CHB": .3, "BP": .2, "FB": .1, "FP": .4, "FF": .1}
TARGET_W = {"FF": 3.2, "CHF": 2.4, "HFL": 0.9, "HFR": 0.9, "FPL": 0.8, "FPR": 0.8, "RUCK": 0.5}
CRUMB_W = {"FPL": 2.0, "FPR": 2.0, "HFL": 1.3, "HFR": 1.3, "ROV": 1.5, "C": 1.3, "RR": 1.1,
           "WL": 0.9, "WR": 0.9, "FF": 0.8, "CHF": 0.8, "HBL": 0.3, "HBR": 0.3}
LONG_W = {"C": 2.0, "RR": 1.6, "ROV": 1.8, "WL": 1.8, "WR": 1.8, "HFL": 1.4, "HFR": 1.4,
          "HBL": 1.0, "HBR": 1.0, "CHF": 0.6, "FPL": 0.4, "FPR": 0.4, "RUCK": 0.3}
# Expected "impact score" for an average player in each role over a full game.
# Measured with tests/calibrate.py; used to turn raw output into a 1-10 rating.
EXPECTED = {"C": 127, "RR": 113, "ROV": 111, "W": 100, "HBF": 97, "RUCK": 103, "HFF": 95,
            "CHB": 77, "BP": 60, "FB": 68, "CHF": 86, "FP": 70, "FF": 71}
# ...and how much that score typically varies game to game (one standard deviation),
# so a key forward's bag and a midfielder's 38 touches are judged on the same scale.
SPREAD = {"C": 27, "RR": 25, "ROV": 25, "W": 22, "HBF": 21, "RUCK": 26, "HFF": 25,
          "CHB": 18, "BP": 16, "FB": 18, "CHF": 27, "FP": 21, "FF": 26}
BENCH_EXPECTED = 0.44       # interchange players see less of it
TOG_FIELD, TOG_BENCH = 0.88, 0.55


def _sig(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


class PlayerDay:
    """One player's afternoon: his match-day multiplier and stat line."""
    __slots__ = ("p", "slot", "pt", "tog", "m", "rating", "st", "conceded")

    def __init__(self, p, slot, rng, team_mult):
        self.p, self.slot = p, slot
        bench = slot not in C.FIELD_SLOTS
        self.pt = p.pos if bench else C.FIELD_SLOTS[slot]
        self.tog = TOG_BENCH if bench else TOG_FIELD
        sigma = 0.085 - 0.0035 * p.attrs["consistency"]          # steady players vary less
        day = _clamp(1.0 + rng.gauss(0, sigma), 0.82, 1.18)
        self.m = condition_mult(p) * day * team_mult * familiarity(p, self.pt)
        self.rating = raw_rating(p.attrs, self.pt) * self.m
        self.st = {"k": 0, "hb": 0, "m": 0, "t": 0, "g": 0, "b": 0, "ho": 0,
                   "cl": 0, "i50": 0, "int": 0, "sp": 0}
        self.conceded = 0

    def a(self, attr: str) -> float:
        return self.p.attrs[attr] * self.m

    def mix(self, weights: dict) -> float:
        return sum(self.p.attrs[k] * w for k, w in weights.items()) * self.m


class Side:
    """A selected 23 with its game plan and the team ratings derived from it."""

    def __init__(self, game: Game, club_id: str, team_mult: float, rng, wet: bool, REF: float = BASE_REF):
        club = game.clubs[club_id]
        self.cid, self.name, self.tac, self.rng = club_id, club.name, club.tactics, rng
        leaders = sorted((game.players[pid].attrs["leadership"] for pid in club.lineup.values()),
                         reverse=True)[:3]
        cap = game.players.get(club.captain)
        if cap and cap.id in club.lineup.values():
            leaders.append(cap.attrs["leadership"])               # the skipper counts twice
        team_mult *= 1.0 + (sum(leaders) / len(leaders) - 13.0) * 0.002
        self.e = {slot: PlayerDay(game.players[pid], slot, rng, team_mult)
                  for slot, pid in club.lineup.items()}
        self.field = [self.e[s] for s in C.FIELD_SLOTS]
        self.bench = [self.e[s] for s in C.BENCH_SLOTS if s in self.e]
        self.everyone = self.field + self.bench
        e = self.e

        def grp(slots, w):
            return sum(e[s].mix(w) for s in slots) / len(slots)

        def line(code):
            xs = [d.rating for d in self.field if C.LINE_OF[d.pt] == code]
            return sum(xs) / len(xs)

        self.ruck = e["RUCK"].mix({"ruck": .7, "strength": .2, "marking": .1})
        self.clr = grp(["C", "RR", "ROV"], {"toughness": .28, "handballing": .24, "strength": .18,
                                             "decision": .16, "tackling": .14})
        self.spread = grp(["WL", "WR", "HBL", "HBR", "C", "ROV"],
                          {"endurance": .3, "speed": .25, "kicking": .25, "decision": .2})
        n = len(self.field)
        self.skill = sum(d.mix({"kicking": .6, "decision": .4}) for d in self.field) / n
        self.press = sum(d.mix({"tackling": .45, "endurance": .3, "toughness": .25}) for d in self.field) / n
        self.stam = sum(d.a("endurance") for d in self.field) / n
        self.mid_r, self.def_r, self.fwd_r = line("M"), line("D"), line("F")
        backs = ["BPL", "FB", "BPR", "HBL", "CHB", "HBR"]
        self.zoneq = grp(backs, {"intercept": .5, "decision": .5})
        self.def_air = grp(backs, {"intercept": .5, "strength": .25, "marking": .25})
        self.fground = grp(["FPL", "FPR", "HFL", "HFR", "ROV"], {"speed": .35, "goal_sense": .35, "tackling": .3})
        self.dground = grp(["BPL", "BPR", "HBL", "HBR"], {"speed": .35, "intercept": .35, "tackling": .3})
        self.depth = (sum(d.rating for d in self.bench) / len(self.bench)) if self.bench else 11.0

        t = self.tac
        # How quickly the side tires: manic pressure and all-out run cost legs.
        load = 1.0 + {"low": -.3, "medium": 0, "high": .5}[t["pressure"]] \
                   + {"slow": -.15, "balanced": 0, "fast": .25}[t["tempo"]]
        self.fade = load * max(0.3, 16.5 - self.stam) * 0.028 - 0.02 * (self.depth - REF)
        self.fade = max(0.0, self.fade)

        # Territory: the general-play arm wrestle.
        terr = (0.38 * self.mid_r + 0.22 * self.spread + 0.14 * self.skill
                + 0.14 * self.def_r + 0.12 * self.fwd_r)
        if t["style"] == "outside":
            terr += 0.07 * (self.skill - REF) + (-0.15 if wet else 0.0)
        elif t["style"] == "contested":
            terr += 0.03 * (self.clr - REF) + (0.15 if wet else 0.0)
        if t["pressure"] == "high":
            terr += 0.20 + 0.06 * (self.press - REF)
        elif t["pressure"] == "low":
            terr -= 0.20
        if t["defence"] == "loose":
            terr -= 0.20
        terr += 0.08 * (self.depth - REF)
        self.terr = terr
        self.clr_eff = self.clr * {"contested": 1.04, "balanced": 1.0, "outside": 0.97}[t["style"]] \
            + (0.2 if wet and t["style"] == "contested" else 0.0)

        # Pre-computed weighted pickers
        self._deliver = self._weights(self.field, lambda d: DELIVER_W[d.pt] * (d.mix({"kicking": .5, "endurance": .5}) / REF) ** 1.2)
        tallf = {"tall": 1.25, "balanced": 1.0, "small": 0.75}[t["forward"]]
        tw = []
        for s, w in TARGET_W.items():
            d = e[s]
            if s in ("FF", "CHF"):
                w *= tallf
            tw.append(w * (d.a("marking") / REF) ** 0.8)
        self._targets = ([e[s] for s in TARGET_W], self._cum(tw))
        self._crumb = ([e[s] for s in CRUMB_W],
                       self._cum([w * e[s].a("goal_sense") / REF for s, w in CRUMB_W.items()]))
        self._long = ([e[s] for s in LONG_W],
                      self._cum([w * e[s].a("kicking") / REF for s, w in LONG_W.items()]))
        # Clearances: the on-ball trio lead, but everyone at the coalface gets a few.
        clr_w = {"C": 2.2, "RR": 2.4, "ROV": 2.0, "RUCK": 1.2, "W": 0.9, "HFF": 0.7, "HBF": 0.6, "CHF": 0.3}
        self._mids = self._weights(
            [d for d in self.everyone if d.pt in clr_w],
            lambda d: clr_w[d.pt] * (0.55 if d in self.bench else 1.0)
            * (d.mix({"toughness": .4, "handballing": .3, "strength": .3}) / REF) ** 2)
        self._backs = [e[s] for s in backs]

    @staticmethod
    def _cum(ws):
        out, tot = [], 0.0
        for w in ws:
            tot += w
            out.append(tot)
        return out

    def _weights(self, pop, fn):
        return (pop, self._cum([fn(d) for d in pop]))

    def pick(self, table):
        return self.rng.choices(table[0], cum_weights=table[1])[0]


def home_advantage(game: Game, home_id: str, away_id: str, venue: str) -> tuple[float, float]:
    """Match-day multipliers (home, away).  Interstate trips hurt the most."""
    h, a = game.clubs[home_id], game.clubs[away_id]
    vstate = C.VENUES[venue][0]
    hm = am = 1.0
    if h.state == vstate and a.state != vstate:
        hm, am = 1.012, 0.988                     # the long flight
    elif a.state == vstate and h.state != vstate:
        hm, am = 0.988, 1.012                     # e.g. a Grand Final at the MCG
    elif h.ground == venue and a.ground != venue:
        hm = 1.012 if venue == "GMHBA Stadium" else 1.007
    elif a.ground == venue and h.ground != venue:
        am = 1.007
    else:
        hm = 1.003                                # shared ground: just the crowd split
    return hm, am


def simulate_match(game: Game, home_id: str, away_id: str, venue: str, *,
                   is_final: bool = False, rng=None, wet: bool | None = None) -> dict:
    rng = rng or random
    if wet is None:
        wet = rng.random() < C.VENUES[venue][3]
    hm, am = home_advantage(game, home_id, away_id, venue)
    # Skill-dependent odds (accuracy, entry quality...) are measured against the
    # standard of the two sides on the day, so scoring stays realistic even if
    # the whole league gets better or worse over a long career.
    levels = [raw_rating(game.players[pid].attrs, pt)
              for cid in (home_id, away_id)
              for slot, pt in C.FIELD_SLOTS.items()
              if (pid := game.clubs[cid].lineup.get(slot)) in game.players]
    REF = BASE_REF + 0.7 * (sum(levels) / len(levels) - REF_RATING)
    sides = (Side(game, home_id, hm, rng, wet, REF), Side(game, away_id, am, rng, wet, REF))
    score = [[0, 0], [0, 0]]                      # [goals, behinds] per side
    timeline = []                                 # every score: [quarter, minute, side, G|B|R, player id]
    tstat = [{"i50": 0, "cl": 0, "ho": 0}, {"i50": 0, "cl": 0, "ho": 0}]
    events, quarters = [], []

    def pts(i):
        return score[i][0] * 6 + score[i][1]

    tempo = sum({"slow": -0.04, "balanced": 0, "fast": 0.04}[s.tac["tempo"]] for s in sides)
    base_n = PASSAGES_PER_QTR * (1 + tempo) * (0.95 if wet else 1.0)

    def stoppage(q, count_extra=True):
        """Ruck contest then clearance.  Returns the index of the side that wins it."""
        A, B = sides
        ho = 0 if rng.random() < _sig(K_RUCK * (A.ruck - B.ruck)) else 1
        if rng.random() < 0.9:
            sides[ho].e["RUCK"].st["ho"] += 1
            tstat[ho]["ho"] += 1
        if count_extra and rng.random() < 0.25:   # repeat ball-up
            ho2 = 0 if rng.random() < _sig(K_RUCK * (A.ruck - B.ruck)) else 1
            sides[ho2].e["RUCK"].st["ho"] += 1
            tstat[ho2]["ho"] += 1
        edge = K_CLEAR * ((A.clr_eff - A.fade * (q - 1)) - (B.clr_eff - B.fade * (q - 1)))
        edge += 0.22 if ho == 0 else -0.22
        w = 0 if rng.random() < _sig(edge) else 1
        sides[w].pick(sides[w]._mids).st["cl"] += 1
        tstat[w]["cl"] += 1
        return w

    def shot(i, shooter, kind, q, minute, base, wet_pen):
        """Resolve a scoring shot.  Returns 'goal' | 'behind' | 'miss'."""
        skill = 0.65 * shooter.a("goal_sense") + 0.35 * shooter.a("kicking")
        p_goal = _clamp(base + 0.015 * (skill - REF) - (wet_pen if wet else 0), 0.2, 0.85)
        shooter.st["k"] += 1
        r = rng.random()
        if r < p_goal:
            lead_before = pts(i) - pts(1 - i)
            shooter.st["g"] += 1
            score[i][0] += 1
            timeline.append([q, minute, i, "G", shooter.p.id])
            events.append((q, minute, "goal", i, shooter, kind, lead_before))
            return "goal"
        if r < p_goal + (1 - p_goal) * (0.70 if kind == "set" else 0.62):
            shooter.st["b"] += 1
            score[i][1] += 1
            timeline.append([q, minute, i, "B", shooter.p.id])
            return "behind"
        return "miss"

    def entry(i, q, minute):
        """Side i goes inside 50.  Returns (next_state, advantage_side, advantage_size)."""
        att, dfn = sides[i], sides[1 - i]
        tstat[i]["i50"] += 1
        kicker = att.pick(att._deliver)
        kicker.st["i50"] += 1
        kicker.st["k"] += 1
        at, dt = att.tac, dfn.tac
        eq = (kicker.mix({"kicking": .6, "decision": .4}) - REF) / 10.0
        eq -= {"low": -0.03, "medium": 0.0, "high": 0.035}[dt["pressure"]] + (dfn.press - REF) * 0.008
        eq += {"outside": 0.03, "balanced": 0.0, "contested": -0.02}[at["style"]]
        fast, slow = at["tempo"] == "fast", at["tempo"] == "slow"
        reb = 0.45 * (1.45 if fast else 0.75 if slow else 1.0) * (0.85 if at["forward"] == "small" else 1.0)
        loose_cost = at["defence"] == "loose"      # attacking side is a forward short

        # -- long shot from outside 50 / running goal --------------------------
        if rng.random() < (0.125 if fast else 0.10):
            res = shot(i, att.pick(att._long), "long", q, minute, 0.36, 0.06)
            if res == "goal":
                return "bounce", None, 0
            return "open", 1 - i, 0.12 if res == "behind" else 0.2

        target_p = 0.60 + {"tall": .10, "balanced": 0, "small": -.10}[at["forward"]] + 0.25 * eq
        target_p -= (0.10 if wet else 0) + (0.05 if at["style"] == "contested" else 0)
        ground = True
        if rng.random() < target_p:
            fwd = att.pick(att._targets)
            if fwd.slot in C.MATCHUP and rng.random() < (0.8 if dt["defence"] == "man" else 0.5):
                opp = dfn.e[C.MATCHUP[fwd.slot]]
            else:
                opp = rng.choice(dfn._backs)
            tall = fwd.pt in ("FF", "CHF", "RUCK")
            if tall:
                fs = fwd.mix({"marking": .5, "strength": .3, "speed": .2})
                ds = opp.mix({"intercept": .5, "strength": .3, "marking": .2})
            else:
                fs = fwd.mix({"marking": .5, "speed": .35, "strength": .15})
                ds = opp.mix({"intercept": .5, "speed": .35, "strength": .15})
            if dt["defence"] != "man":
                ds = 0.5 * ds + 0.5 * dfn.def_air           # team defence shares the load
            diff = fs - ds
            p_mark = 0.30 + 0.022 * diff + 0.20 * eq
            p_int = 0.19 - 0.018 * diff - 0.14 * eq
            if dt["defence"] == "loose":
                p_mark -= 0.05
                p_int += 0.04
            elif dt["defence"] == "zone":
                z = _clamp(dfn.zoneq - att.skill, -3, 3)     # good users slice a zone
                p_mark -= 0.01 + 0.014 * z - (0.02 if fast else 0)
                p_int += 0.02 + 0.016 * z
            if fast:
                p_mark += 0.02
            elif slow:
                p_mark -= 0.01
            if loose_cost:
                p_mark -= 0.03
            if wet:
                p_mark -= 0.07
                p_int -= 0.05
            p_mark, p_int = _clamp(p_mark, 0.06, 0.62), _clamp(p_int, 0.04, 0.45)
            r = rng.random()
            if r < p_mark:
                fwd.st["m"] += 1
                if p_mark < 0.24 and tall and rng.random() < 0.5:
                    events.append((q, minute, "screamer", i, fwd, opp, 0))
                res = shot(i, fwd, "set", q, minute, 0.61, 0.05)
                if res == "goal":
                    opp.conceded += 1
                    return "bounce", None, 0
                return "open", 1 - i, 0.12 if res == "behind" else 0.2
            if r < p_mark + p_int:
                opp.st["m"] += 1
                opp.st["int"] += 1
                return "open", 1 - i, reb
            opp.st["sp"] += 1                                # spoiled: ball hits the deck

        if ground:
            p_fwd = 0.36 + 0.025 * (att.fground - dfn.dground)
            p_fwd += {"tall": -.04, "balanced": 0, "small": .05}[at["forward"]]
            p_fwd += (-0.05 if dt["defence"] == "loose" else 0) + (-0.04 if loose_cost else 0)
            p_fwd += (0.02 if wet else 0) + (0.02 if at["style"] == "contested" else 0)
            if rng.random() < _clamp(p_fwd, 0.15, 0.70):
                res = shot(i, att.pick(att._crumb), "snap", q, minute, 0.41 + (0.02 if fast else 0), 0.03)
                if res == "goal":
                    return "bounce", None, 0
                if res == "behind":
                    return "open", 1 - i, 0.12
                return "stoppage", None, 0
            if rng.random() < 0.3:
                rng.choice(dfn._backs).st["t"] += 1
            r = rng.random()
            if r < 0.08:                                     # rushed through
                score[i][1] += 1
                timeline.append([q, minute, i, "R", 0])
                return "open", 1 - i, 0.12
            if r < 0.55:
                return "open", 1 - i, reb * 0.55
            return "stoppage", None, 0
        return "open", None, 0

    def play(q, n):
        state, adv, adv_size = "bounce", None, 0.0
        for k in range(n):
            minute = int(k / n * 30) + 1
            if state == "open" and rng.random() < 0.22:
                state = "stoppage"
            if state in ("bounce", "stoppage"):
                w = stoppage(q)
                A = sides[w]
                keep = 0.64 + 0.01 * (A.skill - sides[1 - w].press)
                i = w if rng.random() < _clamp(keep, 0.5, 0.78) else 1 - w
            else:
                A, B = sides
                edge = K_TERRITORY * ((A.terr - A.fade * (q - 1)) - (B.terr - B.fade * (q - 1)))
                if adv is not None:
                    edge += adv_size if adv == 0 else -adv_size
                i = 0 if rng.random() < _sig(edge) else 1
                if rng.random() < 0.25:                      # an around-the-ground stoppage on the way
                    stoppage(q, count_extra=False)
            state, adv, adv_size = entry(i, q, minute)

    for q in (1, 2, 3, 4):
        play(q, max(18, int(round(rng.gauss(base_n, 1.8)))))
        quarters.append([score[0][0], score[0][1], score[1][0], score[1][1]])
    extra_time = False
    while is_final and pts(0) == pts(1):                     # finals can't be drawn
        extra_time = True
        play(5, 6)
        quarters.append([score[0][0], score[0][1], score[1][0], score[1][1]])

    # -- between-the-arcs stats ------------------------------------------------
    tot_i50 = tstat[0]["i50"] + tstat[1]["i50"]
    for i, s in enumerate(sides):
        share = tstat[i]["i50"] / max(1, tot_i50)
        t = s.tac
        f_disp = {"slow": 1.06, "balanced": 1.0, "fast": 0.97}[t["tempo"]] * \
                 {"outside": 1.03, "balanced": 1.0, "contested": 0.97}[t["style"]]
        n_disp = int(rng.gauss(295, 16) * f_disp * (0.86 + 0.28 * share) * (0.94 if wet else 1))
        w = [DISP_W[d.pt] * d.tog * (d.rating / REF) ** 0.9 for d in s.everyone]
        hb_bias = 0.04 if t["style"] == "contested" else -0.02 if t["style"] == "outside" else 0
        for d in rng.choices(s.everyone, weights=w, k=n_disp):
            if rng.random() < KICK_SHARE[d.pt] - hb_bias - (0.03 if wet else 0):
                d.st["k"] += 1
            else:
                d.st["hb"] += 1
        f_mark = {"slow": 1.10, "balanced": 1.0, "fast": 0.95}[t["tempo"]] * \
                 {"outside": 1.06, "balanced": 1.0, "contested": 0.92}[t["style"]]
        n_mark = int(rng.gauss(76, 8) * f_mark * (0.75 if wet else 1))
        w = [MARK_W[d.pt] * d.tog * (d.a("marking") / REF) ** 1.5 for d in s.everyone]
        for d in rng.choices(s.everyone, weights=w, k=n_mark):
            d.st["m"] += 1
        f_tack = {"low": 0.9, "medium": 1.0, "high": 1.12}[t["pressure"]] * (1.15 if wet else 1)
        n_tack = int(rng.gauss(51, 6) * f_tack * (1.14 - 0.28 * share))
        w = [TACKLE_W[d.pt] * d.tog * (d.a("tackling") / REF) ** 1.8 for d in s.everyone]
        for d in rng.choices(s.everyone, weights=w, k=n_tack):
            d.st["t"] += 1

    # -- player ratings and votes ----------------------------------------------
    margin = pts(0) - pts(1)
    players, ranked = {}, []
    for i, s in enumerate(sides):
        won = (margin > 0) if i == 0 else (margin < 0)
        for d in s.everyone:
            st = d.st
            impact = (3 * st["k"] + 2 * st["hb"] + 3 * st["m"] + 4 * st["t"] + 6 * st["g"] + st["b"]
                      + st["ho"] + 2 * st["cl"] + 3 * st["int"] + 2.5 * st["sp"] + st["i50"]
                      - 3 * d.conceded)
            on = d.slot in C.FIELD_SLOTS
            exp = EXPECTED[d.pt] * (1.0 if on else BENCH_EXPECTED)
            sd = SPREAD[d.pt] * (1.0 if on else 0.6)
            rating = _clamp(6.0 + 1.15 * (impact - exp) / sd + (0.2 if won else 0), 1.0, 10.0)
            players[d.p.id] = {"side": i, "slot": d.slot, **st, "rt": round(rating, 1)}
            # Brownlow votes: umpires notice ball-winners and winners
            eye = {"MD": 0.6, "WG": 0.2, "RK": 0.2, "GD": 0.1, "KD": -0.3}.get(C.POS_GROUP[d.pt], 0.0)
            ranked.append((rating + impact / 85.0 + eye + (0.3 if won else 0), d.p.id))
    ranked.sort(reverse=True)

    comm, feed = _commentary(sides, events, quarters, extra_time, wet)
    return {
        "home": home_id, "away": away_id, "venue": venue, "wet": wet, "final": is_final,
        "hs": [score[0][0], score[0][1], pts(0)], "as": [score[1][0], score[1][1], pts(1)],
        "qs": quarters, "et": extra_time,
        "team": tstat, "players": players, "votes": [pid for _, pid in ranked[:3]],
        "comm": comm, "feed": feed, "timeline": timeline,
        "tactics": [dict(sides[0].tac), dict(sides[1].tac)],
    }


def score_str(g: int, b: int) -> str:
    return f"{g}.{b} ({g * 6 + b})"


def _commentary(sides, events, quarters, extra_time, wet) -> tuple[list[str], list]:
    """Turn the event log into a short highlights reel.  Returns the text reel
    (for reports) and the same moments as [quarter, minute, text] (for live views)."""
    names = [s.name for s in sides]
    out, feed = [], []
    if wet:
        out.append("Conditions: wet and slippery - a day for the in-and-under types.")
    goals_by, streak_side, streak, shown_streak = {}, None, 0, False
    first, screamers = True, 0
    last_q = quarters and len(quarters)
    qlabel = {1: "QT", 2: "HT", 3: "3QT"}
    cur_q = 1

    def qline(q):
        hg, hb, ag, ab = quarters[q - 1]
        return f"{qlabel[q]}: {names[0]} {score_str(hg, hb)} - {names[1]} {score_str(ag, ab)}"

    def say(q, minute, tag, text):
        out.append(f"{tag}  {text}")
        feed.append([q, minute, text])

    for q, minute, kind, i, pl, extra, lead_before in events:
        while cur_q < q and cur_q <= 3:
            out.append(qline(cur_q))
            cur_q += 1
        tag = f"Q{q} {minute:>2}'" if q <= 4 else "ET"
        if kind == "screamer":
            if screamers < 2:
                screamers += 1
                say(q, minute, tag, f"SCREAMER! {pl.p.name} climbs over {extra.p.name} and pulls it down.")
            continue
        n = goals_by[pl.p.id] = goals_by.get(pl.p.id, 0) + 1
        if streak_side == i:
            streak += 1
        else:
            streak_side, streak, shown_streak = i, 1, False
        how = {"set": "goes back and slots the set shot", "snap": "snaps truly from the pocket",
               "long": "launches from outside 50 - it's home"}[extra]
        if first:
            say(q, minute, tag, f"{pl.p.name} {how} for the first of the day ({names[i]}).")
            first = False
        elif n in (4, 6, 8) or n == 5:
            word = {4: "fourth", 5: "FIFTH", 6: "sixth", 8: "eighth"}[n]
            say(q, minute, tag, f"{pl.p.name} has his {word}! He's having a day out for {names[i]}.")
        elif streak >= 4 and not shown_streak:
            shown_streak = True
            say(q, minute, tag, f"{names[i]} have kicked {streak} on the trot - {pl.p.name} with the latest.")
        elif q >= 4 and lead_before <= 0 and lead_before + 6 > 0:
            say(q, minute, tag, f"{pl.p.name} {how} and {names[i]} hit the front!")
        elif q >= 4 and minute >= 24 and 0 < lead_before <= 11:
            say(q, minute, tag, f"{pl.p.name} {how} - that might be the sealer for {names[i]}.")
    while cur_q <= 3:
        out.append(qline(cur_q))
        cur_q += 1
    hg, hb, ag, ab = quarters[-1]
    if extra_time:
        out.append("Scores level at the final siren - we go to extra time!")
    out.append(f"FT: {names[0]} {score_str(hg, hb)} - {names[1]} {score_str(ag, ab)}")
    # keep the reel tight: always keep quarter lines and the last few moments
    if len(out) > 16:
        keep = [l for l in out if l[:2] in ("QT", "HT", "3Q", "FT", "Co", "Sc")]
        other = [l for l in out if l not in keep]
        chosen = set(other[:3] + other[-(13 - len(keep)):]) if len(keep) < 13 else set(other[:3])
        out = [l for l in out if l in keep or l in chosen]
    return out, feed
