"""Player ratings, team selection and list-strength helpers.

A player's rating in a role is a weighted average of the attributes that
matter there (constants.POS_WEIGHTS), scaled down if he is playing out of
position.  "Overall" (OVR, 0-100) is simply the 1-20 rating in his primary
position multiplied by five.
"""
from __future__ import annotations

from . import constants as C
from .models import Game, Player


# -- individual ratings ------------------------------------------------------
def raw_rating(attrs: dict, pos_type: str) -> float:
    """Weighted attribute average (1-20) for a position type."""
    return sum(attrs[a] * w for a, w in C.POS_WEIGHTS[pos_type].items())


def familiarity(player: Player, pos_type: str) -> float:
    """1.0 in his own position, sliding down the further out of position he is."""
    if pos_type == player.positions[0]:
        return 1.0
    if pos_type in player.positions:
        return 0.97
    mine = {C.POS_GROUP[p] for p in player.positions}
    grp = C.POS_GROUP[pos_type]
    if grp in mine:
        return 0.94
    if any(frozenset((grp, m)) in C.RELATED_GROUPS for m in mine):
        return 0.88
    return 0.78


def slot_rating(player: Player, pos_type: str) -> float:
    return raw_rating(player.attrs, pos_type) * familiarity(player, pos_type)


def overall(player: Player) -> float:
    """Current ability, 0-100."""
    return raw_rating(player.attrs, player.positions[0]) * 5.0


def ovr(player: Player) -> int:
    return int(round(overall(player)))


def shown_potential(game: Game, player: Player) -> int:
    """Potential as the user sees it: exact for his own list, fuzzy otherwise."""
    cur = overall(player)
    if player.club is not None and player.club == game.meta.get("user_club"):
        return int(round(max(cur, player.potential)))
    return int(round(max(cur, min(99, player.potential + player.scout_noise * scout_error(game)))))


def scout_error(game: Game, club_id: str | None = None) -> float:
    """How wrong a club's recruiters tend to be: 0.4 (elite) to 1.6 (poor)."""
    club = game.clubs.get(club_id or game.meta.get("user_club"))
    return 1.0 + (1.0 - club.recruit) * 4.0 if club else 1.0


def form_value(player: Player) -> float:
    """Average of the last five match ratings (6.0 = par)."""
    return sum(player.form) / len(player.form) if player.form else 6.0


def condition_mult(player: Player) -> float:
    """How fitness and form scale a player's output on match day."""
    fit = 0.86 + 0.14 * (player.fitness / 100.0)
    frm = 1.0 + (form_value(player) - 6.0) * 0.008
    return fit * frm


def available(player: Player) -> bool:
    return player.injury is None and player.status == "listed"


# -- selection ---------------------------------------------------------------
def auto_select(game: Game, club_id: str, youth_bias: float = 0.0) -> dict:
    """Pick the best available 23.

    Greedy assignment: rate every available player in every field slot, then
    repeatedly lock in the highest-rated (player, slot) pair still open.
    Players are naturally steered to their best role, and tired or out-of-form
    players slip behind fresher teammates.  ``youth_bias`` (rating points)
    is used by rebuilding AI clubs to get games into kids.
    """
    squad = [p for p in game.squad(club_id) if available(p)]
    pairs = []
    for p in squad:
        cm = condition_mult(p)
        bias = youth_bias * max(0, 23 - p.age) / 5.0 if youth_bias else 0.0
        for slot, pt in C.FIELD_SLOTS.items():
            pairs.append((slot_rating(p, pt) * cm + bias, slot, p.id))
    pairs.sort(reverse=True)
    lineup, used = {}, set()
    for _, slot, pid in pairs:
        if slot in lineup or pid in used:
            continue
        lineup[slot] = pid
        used.add(pid)
        if len(lineup) == len(C.FIELD_SLOTS):
            break
    # Interchange: best of the rest, favouring runners who can rotate anywhere.
    rest = []
    for p in squad:
        if p.id in used:
            continue
        util = 0.4 if C.POS_GROUP[p.pos] in ("MD", "WG", "GD", "GF") else 0.0
        bias = youth_bias * max(0, 23 - p.age) / 5.0 if youth_bias else 0.0
        rest.append((raw_rating(p.attrs, p.pos) * condition_mult(p) + util + bias, p.id))
    rest.sort(reverse=True)
    for slot, (_, pid) in zip(C.BENCH_SLOTS, rest):
        lineup[slot] = pid
    return lineup


def lineup_problems(game: Game, club_id: str) -> list[str]:
    """Human-readable reasons the current lineup can't take the field."""
    club = game.clubs[club_id]
    out, seen = [], set()
    for slot in C.ALL_SLOTS:
        pid = club.lineup.get(slot)
        p = game.players.get(pid) if pid is not None else None
        if p is None or p.club != club_id or p.status != "listed":
            out.append(f"{slot}: empty")
        elif p.injury:
            out.append(f"{slot}: {p.name} is injured ({p.injury['type']}, {p.injury['weeks']}w)")
        elif pid in seen:
            out.append(f"{slot}: {p.name} is named twice")
        seen.add(pid)
    return out


def repair_lineup(game: Game, club_id: str) -> list[str]:
    """Fill holes (injured / departed players) with the best available cover."""
    club = game.clubs[club_id]
    changes, used = [], set()
    for slot in C.ALL_SLOTS:               # keep every valid selection
        pid = club.lineup.get(slot)
        p = game.players.get(pid) if pid is not None else None
        if p and p.club == club_id and available(p) and pid not in used:
            used.add(pid)
        else:
            club.lineup.pop(slot, None)
    pool = [p for p in game.squad(club_id) if available(p) and p.id not in used]
    for slot in C.ALL_SLOTS:
        if slot in club.lineup or not pool:
            continue
        pt = C.FIELD_SLOTS.get(slot)
        key = (lambda p: slot_rating(p, pt) * condition_mult(p)) if pt else \
              (lambda p: raw_rating(p.attrs, p.pos) * condition_mult(p))
        best = max(pool, key=key)
        pool.remove(best)
        club.lineup[slot] = best.id
        changes.append(f"{best.name} comes in at {slot}")
    return changes


# -- list strength -----------------------------------------------------------
def best22_rating(game: Game, club_id: str) -> float:
    """Average OVR of the best 22 on the list, ignoring injuries (list quality)."""
    ovrs = sorted((overall(p) for p in game.squad(club_id)), reverse=True)[:22]
    return sum(ovrs) / max(1, len(ovrs))


def strength_ranking(game: Game) -> list[str]:
    """Club ids from strongest list to weakest."""
    return sorted(game.clubs, key=lambda c: best22_rating(game, c), reverse=True)


def line_ratings(game: Game, club_id: str) -> dict:
    """Average slot rating (0-100) of the selected defence, midfield and attack."""
    club = game.clubs[club_id]
    lines = {"D": [], "M": [], "F": []}
    for slot, pt in C.FIELD_SLOTS.items():
        p = game.players.get(club.lineup.get(slot))
        if p:
            lines[C.LINE_OF[pt]].append(slot_rating(p, pt) * 5)
    return {k: (sum(v) / len(v) if v else 0.0) for k, v in lines.items()}
