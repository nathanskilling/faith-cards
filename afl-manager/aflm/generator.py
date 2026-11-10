"""World generation: clubs, playing lists, draft prospects and draft picks.

All players are fictional.  Each new world shuffles which clubs are loaded
with talent and which are rebuilding, so every career starts differently;
club stature (supporter base, finances) follows the real competition.
"""
from __future__ import annotations

import random

from . import constants as C
from .models import Game, Player, Club
from .names import FIRST_NAMES, LAST_NAMES
from .ratings import raw_rating, overall, best22_rating

# Fraction of his ceiling a player has typically reached at each age.
AGE_CURVE = {18: .72, 19: .77, 20: .82, 21: .865, 22: .905, 23: .94, 24: .97, 25: .99,
             26: 1.0, 27: 1.0, 28: 1.0, 29: .99, 30: .975, 31: .955, 32: .93, 33: .90,
             34: .87, 35: .84, 36: .80}
AGE_WEIGHTS = {18: 3.0, 19: 3.2, 20: 3.2, 21: 3.2, 22: 3.2, 23: 3.2, 24: 3.1, 25: 3.0,
               26: 2.9, 27: 2.7, 28: 2.5, 29: 2.2, 30: 1.9, 31: 1.4, 32: 1.0, 33: 0.6, 34: 0.3}
# A 42-man list: 4 rucks, 5 key defenders, 7 general defenders, 4 wings,
# 10 midfielders, 7 general forwards and 5 key forwards.
LIST_TEMPLATE = (["RUCK"] * 4 + ["FB"] * 2 + ["CHB"] * 3 + ["BP"] * 3 + ["HBF"] * 4 + ["W"] * 4
                 + ["C"] * 4 + ["RR"] * 3 + ["ROV"] * 3 + ["HFF"] * 4 + ["CHF"] * 3 + ["FP"] * 3
                 + ["FF"] * 2)
# Talent offsets (OVR points) dealt out at random to the 18 clubs.
STRENGTH_TIERS = [2.6, 2.1, 1.7, 1.3, 1.0, 0.7, 0.4, 0.2, 0.0, -0.2, -0.4, -0.7, -1.0,
                  -1.3, -1.7, -2.1, -2.5, -3.0]
SECONDARY = {
    "FB": [("CHB", .6)], "CHB": [("FB", .4), ("CHF", .15)], "BP": [("HBF", .5)],
    "HBF": [("BP", .3), ("W", .3), ("C", .1)], "W": [("HBF", .3), ("C", .25), ("HFF", .25)],
    "C": [("RR", .4), ("ROV", .3), ("W", .2)], "RR": [("C", .6)],
    "ROV": [("C", .4), ("FP", .3), ("HFF", .2)], "RUCK": [("FF", .25), ("CHF", .1)],
    "HFF": [("FP", .4), ("W", .25), ("ROV", .2)], "CHF": [("FF", .6), ("CHB", .1)],
    "FP": [("HFF", .4), ("ROV", .3)], "FF": [("CHF", .6), ("RUCK", .1)],
}
HEIGHTS = {"RUCK": (200, 211), "FB": (191, 200), "CHB": (191, 200), "CHF": (192, 201),
           "FF": (192, 203), "W": (180, 191), "HBF": (180, 191), "HFF": (180, 191),
           "C": (180, 192), "RR": (183, 193), "BP": (174, 186), "FP": (172, 184), "ROV": (173, 185)}
PROSPECT_POS_WEIGHTS = {"RUCK": 4, "FB": 4, "CHB": 6, "BP": 6, "HBF": 9, "W": 9, "C": 11,
                        "RR": 8, "ROV": 9, "HFF": 9, "CHF": 6, "FP": 8, "FF": 5}


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def curve(age: int) -> float:
    return AGE_CURVE.get(age, 0.78 if age > 36 else 0.72)


def gen_attrs(rng, pos: str, target_ovr: float, age: int) -> dict:
    """Build an attribute set whose rating in ``pos`` equals ``target_ovr``."""
    t = target_ovr / 5.0
    w = C.POS_WEIGHTS[pos]
    tall = C.POS_GROUP[pos] in ("KD", "KF", "RK")
    a = {}
    for k in C.SKILL_ATTRS:
        if k in w:      # the more a role leans on an attribute, the better he is at it
            a[k] = t + rng.gauss(0.2 + 3.0 * (w[k] - 0.14), 1.3)
        else:
            a[k] = t - 3.2 + rng.gauss(0, 1.9)
    if pos != "RUCK":
        a["ruck"] = rng.gauss(8.0 if tall else 4.0, 1.5)
    # Kids are skilled but under-done physically; veterans lose their legs
    if age <= 21:
        a["strength"] -= 1.2; a["endurance"] -= 0.8; a["decision"] -= 0.8
    elif age >= 30:
        a["speed"] -= 1.2; a["decision"] += 0.8; a["endurance"] -= 0.4
    for _ in range(5):  # shift the role-relevant attributes until the rating lands on target
        for k in a:
            a[k] = _clamp(a[k], 1.0, 20.0)
        diff = t - raw_rating(a, pos)
        if abs(diff) < 0.01:
            break
        for k in w:
            a[k] += diff
    for k in a:
        a[k] = _clamp(a[k], 1.0, 20.0)
    a["leadership"] = _clamp(rng.gauss(6.0 + (age - 18) * 0.55, 2.6), 1, 20)
    a["consistency"] = _clamp(rng.gauss(11.0 + (age - 18) * 0.2, 2.6), 3, 20)
    a["injury_prone"] = _clamp(rng.gauss(8.0, 3.2), 1, 19)
    return a


def market_wage(ovr: float, age: int, pot: float | None = None, scale: float = 1.0) -> int:
    """What a player of this quality is worth per season, in $k."""
    w = 100 + 12 * max(0.0, ovr - 55) + 1.4 * max(0.0, ovr - 65) ** 2
    if pot is not None and age <= 23:
        w += max(0.0, pot - ovr) * 4          # paying for upside
    if age >= 31:
        w *= 0.85
    if age >= 33:
        w *= 0.85
    return int(round(max(C.MIN_WAGE, w * scale) / 5.0) * 5)


def _name(rng, used: set) -> tuple[str, str]:
    for _ in range(50):
        n = (rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES))
        if n not in used:
            used.add(n)
            return n
    return n


def make_player(rng, game: Game, pos: str, age: int, pa: float, ca: float, used: set,
                club: str | None = None) -> Player:
    first, last = _name(rng, used)
    positions = [pos]
    for sec, prob in SECONDARY[pos]:
        if rng.random() < prob and sec not in positions:
            positions.append(sec)
            break
    lo, hi = HEIGHTS[pos]
    p = Player(
        id=game.new_player_id(), first=first, last=last, age=age,
        height=rng.randint(lo, hi), club=club, positions=positions,
        attrs=gen_attrs(rng, pos, ca, age), potential=pa,
        scout_noise=rng.gauss(0, 2.5), dev_rate=_clamp(rng.gauss(1.0, 0.18), 0.55, 1.45),
    )
    return p


def make_prospect(rng, game: Game, used: set) -> Player:
    """A draft hopeful: mostly 18-year-olds with a sprinkling of mature-agers."""
    pos = rng.choices(list(PROSPECT_POS_WEIGHTS), weights=list(PROSPECT_POS_WEIGHTS.values()))[0]
    if rng.random() < 0.85:
        age, pa = 18, _clamp(rng.gauss(70.5, 8.5), 56, 95)
    else:
        age, pa = rng.choice([19, 20, 21, 22]), _clamp(rng.gauss(68.0, 5.0), 58, 84)
    ca = _clamp(pa * curve(age) + rng.gauss(0, 2.5), 40, pa - 1)
    p = make_player(rng, game, pos, age, pa, ca, used)
    p.status = "prospect"
    p.scout_noise = rng.gauss(0, 5.5)          # nobody really knows with kids
    return p


def generate_draft_pool(game: Game, rng=None) -> None:
    rng = rng or random
    used = {(p.first, p.last) for p in game.players.values()}
    pool = []
    for _ in range(C.DRAFT_POOL_SIZE):
        p = make_prospect(rng, game, used)
        game.players[p.id] = p
        pool.append(p.id)
    game.draft["pool"] = pool
    game.draft["pool_year"] = game.year
    game.draft["live"] = None


def add_draft_picks(game: Game, year: int) -> None:
    for cid in game.clubs:
        for rnd in range(1, C.DRAFT_ROUNDS + 1):
            game.draft["picks"].append({"year": year, "round": rnd, "orig": cid, "owner": cid})


def _build_list(rng, game: Game, club: Club, strength: float, used: set) -> None:
    age_shift = rng.gauss(strength * 0.3, 0.5)
    ages = list(AGE_WEIGHTS)
    weights = [AGE_WEIGHTS[a] * (1.0 + 0.09 * age_shift * (a - 24)) for a in ages]
    weights = [max(0.05, w) for w in weights]
    for pos in LIST_TEMPLATE:
        age = rng.choices(ages, weights=weights)[0]
        pa = rng.gauss(73.5 + strength, 6.3)
        if age >= 24:                       # survivors: older players are there on merit
            pa += (min(age, 30) - 23) * 0.4
        pa = _clamp(pa, 58, 94)
        ca = pa * curve(age) + rng.gauss(0, 1.5)
        floor = 67 if age >= 29 else 64 if age >= 26 else 60 if age >= 23 else 0
        if ca < floor:
            ca = floor + rng.uniform(0, 4)
        if age >= 28:
            pa = ca + rng.uniform(0, 1)     # what you see is what you get
        else:
            pa = max(pa, ca + 1)
        p = make_player(rng, game, pos, age, _clamp(pa, 40, 97), ca, used, club=club.id)
        # a plausible back-story: games and goals before the career starts
        per_year = _clamp((ca - 56) * 0.95, 0, 21) * rng.uniform(0.55, 1.0)
        p.career["games"] = int(max(0, age - 18) * per_year)
        rate = {"KF": 1.6, "GF": 1.0, "MD": 0.45, "WG": 0.35, "RK": 0.3, "GD": 0.12, "KD": 0.04}[C.POS_GROUP[pos]]
        p.career["goals"] = int(p.career["games"] * rate * rng.uniform(0.7, 1.3))
        game.players[p.id] = p


def _set_contracts(rng, game: Game, club: Club) -> None:
    squad = game.squad(club.id)
    # the five rawest kids go on the rookie list
    kids = sorted((p for p in squad if p.age <= 23), key=overall)[:5]
    for p in squad:
        o = overall(p)
        if p in kids:
            p.rookie, p.wage = True, C.ROOKIE_WAGE
            p.contract_end = game.year + rng.choice([0, 1, 1])
            continue
        p.wage = market_wage(o, p.age, p.potential)
        years = rng.choices([0, 1, 2, 3, 4], weights=[28, 30, 22, 13, 7])[0]
        if o >= 80:
            years = min(5, years + 1)
        if p.age <= 19:
            years = max(1, years)
        if p.age >= 32:
            years = min(1, years)
        p.contract_end = game.year + years
    # Squeeze or stretch senior wages so the club sits somewhere under the cap.
    target = game.cap * rng.uniform(0.93, 0.995)
    seniors = [p for p in squad if not p.rookie]
    fixed = sum(p.wage for p in squad if p.rookie)
    k = (target - fixed) / max(1, sum(p.wage for p in seniors))
    for p in seniors:
        p.wage = int(round(max(C.MIN_WAGE, p.wage * k) / 5.0) * 5)
    return k


def new_game(seed: int | None = None, save_name: str = "career") -> Game:
    """Create a fresh world.  The user picks a club afterwards (see choose_club)."""
    from . import season, finance              # local imports avoid cycles

    if seed is None:
        seed = random.randrange(1, 10 ** 6)
    rng = random.Random(seed)
    g = Game()
    g.meta = {"version": C.SAVE_VERSION, "save_name": save_name, "seed": seed,
              "year": C.START_YEAR, "phase": "season", "round": 1, "user_club": None,
              "manager": "", "hired": C.START_YEAR, "selection": "auto", "cap": C.SALARY_CAP, "wage_scale": 1.0, "next_pid": 0,
              "next_mid": 0}
    g.draft = {"picks": [], "pool": [], "pool_year": C.START_YEAR, "live": None}

    tiers = STRENGTH_TIERS[:]
    rng.shuffle(tiers)
    philosophies = [n for n in C.PHILOSOPHIES]
    used, scales = set(), []
    for (cid, name, nick, ground, state, colours, sup), strength in zip(C.CLUBS, tiers):
        club = Club(id=cid, name=name, nickname=nick, ground=ground, state=state,
                    colours=colours, supporters=float(sup))
        club.balance = int(1500 + sup * 60 + rng.uniform(-800, 800))
        club.dev = round(_clamp(rng.gauss(1.0, 0.07), 0.85, 1.15), 2)
        club.recruit = round(_clamp(rng.gauss(1.0, 0.07), 0.85, 1.15), 2)
        club.philosophy = rng.choice(philosophies)
        club.tactics = dict(C.PHILOSOPHIES[club.philosophy])
        g.clubs[cid] = club
        _build_list(rng, g, club, strength, used)
        scales.append(_set_contracts(rng, g, club))
    g.meta["wage_scale"] = round(sum(scales) / len(scales), 3)

    ranking = sorted(g.clubs, key=lambda c: best22_rating(g, c), reverse=True)
    for i, cid in enumerate(ranking):
        club = g.clubs[cid]
        club.strategy = "contend" if i < 6 else "rebuild" if i >= 12 else "balanced"
        pick_captain(g, club)
    for year in (g.year, g.year + 1):
        add_draft_picks(g, year)
    generate_draft_pool(g, rng)
    season.start_season(g, rng)
    finance.set_board_expectations(g)
    from .ratings import auto_select
    for cid, club in g.clubs.items():
        club.lineup = auto_select(g, cid)
    g.add_news(f"Welcome to the {g.year} season. Eighteen clubs, one flag.", "league", "Pre-season")
    return g


def pick_captain(game: Game, club: Club) -> None:
    """Captain = best leader among the senior core."""
    core = sorted(game.squad(club.id), key=overall, reverse=True)[:26]
    if core:
        club.captain = max(core, key=lambda p: p.attrs["leadership"] + (p.age >= 24) * 1.0).id
