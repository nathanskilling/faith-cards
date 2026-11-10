"""List management and the off-season: contracts, delistings, free agency,
trades, the national draft and rolling the world into a new year.

Valuation
---------
Trades are judged with one common currency, "trade points":

* a player is worth roughly ``(effective_rating - 50) ^ 2.2 / 10`` where the
  effective rating blends in his (perceived) potential while he is young, and
  the total is discounted as he ages past 26;
* a draft pick is worth ``300 / (1 + 0.115 * (pick - 1)) ^ 1.25`` - pick 1 is
  a touch more than an established star, pick 18 about a good ordinary
  player, a fourth-rounder very little.  (A simplified take on the AFL's
  Draft Value Index; swapping in the real points table is a one-function job.)

AI clubs then bend those numbers by list strategy: rebuilders pay over the
odds for picks and kids, contenders for ready-made 24-30 year olds.
"""
from __future__ import annotations

import random

from . import constants as C
from . import development, finance, season
from .generator import market_wage, generate_draft_pool, add_draft_picks, pick_captain
from .models import Game, Player, Club
from .ratings import overall, auto_select, repair_lineup, best22_rating, shown_potential, scout_error

AI_LIST_TARGET = 42


# -- list bookkeeping ----------------------------------------------------------
def list_counts(game: Game, cid: str) -> tuple[int, int]:
    squad = game.squad(cid)
    rookies = sum(1 for p in squad if p.rookie)
    return len(squad) - rookies, rookies


def cap_space(game: Game, cid: str) -> int:
    return game.cap - game.payroll(cid)


def out_of_contract(game: Game, cid: str) -> list[Player]:
    return [p for p in game.squad(cid) if p.contract_end <= game.year]


def release_player(game: Game, p: Player) -> None:
    """Delist: he goes into the free-agent pool."""
    club = game.clubs.get(p.club)
    if club:
        club.lineup = {s: pid for s, pid in club.lineup.items() if pid != p.id}
        if club.captain == p.id:
            club.captain = None
    p.club, p.status, p.rookie = None, "free_agent", False
    if p.id not in game.free_agents:
        game.free_agents.append(p.id)


def sign_player(game: Game, p: Player, cid: str, wage: int, years: int, rookie: bool = False) -> None:
    if p.id in game.free_agents:
        game.free_agents.remove(p.id)
    if p.id in game.draft.get("pool", []):
        game.draft["pool"].remove(p.id)
    p.club, p.status, p.rookie = cid, "listed", rookie
    p.wage = C.ROOKIE_WAGE if rookie else int(wage)
    p.contract_end = game.year + years
    if cid == game.meta.get("user_club"):
        p.scout_noise = 0.0


# -- contracts -----------------------------------------------------------------
def contract_demand(game: Game, p: Player) -> dict:
    """What it takes to sign him: wage and acceptable contract lengths."""
    o = overall(p)
    wage = market_wage(o, p.age, p.potential, game.meta["wage_scale"])
    wage = int(round(wage * (1.0 + ((p.id * 7) % 9 - 4) * 0.012) / 5.0) * 5)   # some drive a harder bargain
    if p.age <= 23:
        lo, hi = 2, 4
    elif p.age <= 28:
        lo, hi = 2, 5
    elif p.age <= 30:
        lo, hi = 1, 3
    else:
        lo, hi = 1, 2
    if o < 66:
        lo, hi = 1, min(hi, 2)
    return {"wage": max(C.MIN_WAGE, wage), "min_years": lo, "max_years": hi}


def offer_contract(game: Game, p: Player, years: int, wage: int | None = None) -> tuple[bool, str]:
    """User offers a new deal to one of his own players or a free agent."""
    cid = game.meta["user_club"]
    d = contract_demand(game, p)
    own = p.club == cid
    if not own and p.status != "free_agent":
        return False, f"{p.name} is not available to sign."
    if own and p.contract_end > game.year + 1:
        return False, f"{p.name} is contracted to {p.contract_end} - no need to talk yet."
    if p.rookie and own and wage is None:
        # rookies simply roll over on the rookie list
        p.contract_end = game.year + 1
        return True, f"{p.name} stays on the rookie list for {game.year + 1} (${C.ROOKIE_WAGE}k)."
    wage = d["wage"] if wage is None else int(wage)
    if not d["min_years"] <= years <= d["max_years"]:
        return False, (f"{p.name} wants a {d['min_years']}-{d['max_years']} year deal, "
                       f"not {years} year{'s' if years != 1 else ''}.")
    ask = d["wage"] * (1.08 if not own else 1.0)
    if own and game.history and game.history[-1].get("user", {}).get("pos", 18) <= 4:
        ask *= 0.95                              # players take a little less to stay at a contender
    if wage < ask * 0.985:
        return False, f"{p.name} turns it down - he wants about ${int(round(ask / 5) * 5)}k a season."
    current = p.wage if own else 0
    if game.payroll(cid) - current + wage > game.cap:
        return False, (f"That deal would put you ${game.payroll(cid) - current + wage - game.cap}k over "
                       f"the ${game.cap}k salary cap.")
    if not own:
        senior, rookies = list_counts(game, cid)
        if senior + rookies >= C.LIST_MAX:
            return False, "Your list is full (44). Delist or trade someone first."
        rookie = senior >= C.SENIOR_MAX
        sign_player(game, p, cid, wage, years, rookie)
        game.add_news(f"{p.name} signs with {game.clubs[cid].name} as a free agent.", "list")
        return True, f"{p.name} signs for {years} year{'s' if years != 1 else ''} at ${p.wage}k."
    if p.rookie:
        senior, _ = list_counts(game, cid)
        if senior >= C.SENIOR_MAX:
            return False, "No room on the senior list (38) to upgrade him."
        p.rookie = False
    p.wage = wage
    p.contract_end = max(game.year, p.contract_end) + years
    return True, f"{p.name} re-signs to the end of {p.contract_end} at ${wage}k a season."


def delist(game: Game, p: Player) -> tuple[bool, str]:
    if game.phase in ("season", "finals"):
        return False, "Players can only be delisted in the off-season."
    if p.club != game.meta["user_club"]:
        return False, f"{p.name} is not on your list."
    payout = 0
    if p.contract_end > game.year:               # contracted players are paid out half of what's left
        payout = int(p.wage * (p.contract_end - game.year) * 0.5)
        finance._add(game.clubs[p.club], "contract_payouts", -payout)
    release_player(game, p)
    game.add_news(f"{game.user.name} delist {p.name}.", "list")
    return True, f"{p.name} has been delisted" + (f" (payout ${payout}k)." if payout else ".")


def _ai_contracts(game: Game, cid: str, rng) -> None:
    """Re-sign who is worth keeping, turn over the bottom of the list."""
    club = game.clubs[cid]
    squad = sorted(game.squad(cid), key=lambda p: player_value(game, p, perceived=False))
    ooc = [p for p in squad if p.contract_end <= game.year]
    cuts_needed = max(0, len(squad) - (AI_LIST_TARGET - 3)) + rng.choice([0, 0, 1, 1, 2])
    # Only the bottom of the list is ever at risk; out-of-contract players go first.
    fringe = sorted(squad[:cuts_needed + 5], key=lambda p: p.contract_end > game.year)
    cuts = {p.id for p in fringe[:cuts_needed]}
    for p in squad:
        if p.id in cuts:
            release_player(game, p)
    for p in ooc:
        if p.id in cuts:
            continue
        d = contract_demand(game, p)
        p.wage = C.ROOKIE_WAGE if p.rookie else d["wage"]
        p.contract_end = game.year + (1 if p.rookie else rng.randint(d["min_years"], d["max_years"]))
    # cap squeeze: shed the worst value-for-money contracts
    while game.payroll(cid) > game.cap * 0.985:
        squad = [p for p in game.squad(cid) if not p.rookie]
        if not squad:
            break
        worst = min(squad, key=lambda p: player_value(game, p, perceived=False) / max(1, p.wage))
        release_player(game, worst)
        if overall(worst) >= 76:
            game.add_news(f"Cap casualty: {club.name} part ways with {worst.name}.", "list")


# -- valuation -----------------------------------------------------------------
def player_value(game: Game, p: Player, perceived: bool = True) -> float:
    o = overall(p)
    pot = p.potential + (p.scout_noise if perceived else 0.0)
    youth = {18: .7, 19: .7, 20: .7, 21: .6, 22: .5, 23: .35, 24: .2}.get(p.age, 0.0)
    eff = o + max(0.0, pot - o) * youth
    v = max(0.0, eff - 50.0) ** 2.2 / 10.0
    if p.age > 26:
        v *= {27: .92, 28: .82, 29: .70, 30: .55, 31: .40, 32: .28}.get(p.age, .15)
    if p.injury and p.injury["weeks"] > 20:
        v *= 0.75
    return v


def pick_number(game: Game, pick: dict) -> float:
    """Best guess at where a pick will fall in the draft (1 = first)."""
    live = game.draft.get("live")
    if live and pick["year"] == game.draft.get("pool_year"):
        for o in live["order"]:
            if (o["round"], o["orig"]) == (pick["round"], pick["orig"]):
                return o["n"]
    if game.season.get("final_ladder") and pick["year"] == game.year:
        order = draft_order(game)
    elif pick["year"] == game.year and game.meta.get("round", 1) > 6 and game.phase == "season":
        order = [r["club"] for r in reversed(season.ladder(game))]
    else:
        order = sorted(game.clubs, key=lambda c: best22_rating(game, c))
    idx = order.index(pick["orig"])
    if pick["year"] > game.year:
        idx = 0.5 * idx + 0.5 * 8.5               # next year is anyone's guess
    return (pick["round"] - 1) * len(game.clubs) + idx + 1


def pick_value(game: Game, pick: dict) -> float:
    n = pick_number(game, pick)
    v = 300.0 / (1.0 + 0.115 * (n - 1)) ** 1.25
    return v * (0.85 if pick["year"] > game.year else 1.0)


def pick_label(pick: dict) -> str:
    lbl = f"{pick['year']} R{pick['round']}"
    return lbl + (f" ({pick['orig']})" if pick["orig"] != pick["owner"] else "")


def club_picks(game: Game, cid: str) -> list[dict]:
    return sorted((p for p in game.draft["picks"] if p["owner"] == cid),
                  key=lambda p: (p["year"], p["round"], p["orig"]))


def _ai_value(game: Game, club: Club, item, outgoing: bool) -> float:
    """How an AI club values a player or pick, given its list strategy."""
    if isinstance(item, dict):
        return pick_value(game, item) * {"rebuild": 1.15, "contend": 0.9}.get(club.strategy, 1.0)
    v = player_value(game, item)
    if club.strategy == "rebuild":
        v *= 1.15 if item.age <= 22 else 0.7 if item.age >= 28 else 1.0
    elif club.strategy == "contend":
        v *= 1.1 if 24 <= item.age <= 30 else 1.0
    if outgoing:
        squad = sorted(game.squad(club.id), key=overall, reverse=True)
        if item in squad[:3] and item.age < 29:
            v *= 1.35                             # franchise players cost extra
        elif item.age <= 21 and item.potential + item.scout_noise >= 84:
            v *= 1.2                              # so do the prized kids
    return v


def evaluate_trade(game: Game, ai_id: str, give: list, get: list) -> dict:
    """The user offers ``give`` to an AI club for ``get``.  Items are Player
    objects or pick dicts.  Returns the AI's verdict without changing anything."""
    user_id = game.meta["user_club"]
    ai = game.clubs[ai_id]
    for it in give:
        owner = it["owner"] if isinstance(it, dict) else it.club
        if owner != user_id:
            return {"ok": False, "msg": "You can only offer your own players and picks."}
    for it in get:
        owner = it["owner"] if isinstance(it, dict) else it.club
        if owner != ai_id:
            return {"ok": False, "msg": f"Everything you ask for must belong to {ai.name}."}
    if not give and not get:
        return {"ok": False, "msg": "Nothing to trade."}
    ai_in = sum(_ai_value(game, ai, it, False) for it in give)
    ai_out = sum(_ai_value(game, ai, it, True) for it in get)
    res = {"ai_in": round(ai_in), "ai_out": round(ai_out), "ok": False}
    gp = [x for x in give if isinstance(x, Player)]
    rp = [x for x in get if isinstance(x, Player)]
    for cid, incoming, outgoing in ((user_id, rp, gp), (ai_id, gp, rp)):
        name = game.clubs[cid].name
        if len(game.squad(cid)) + len(incoming) - len(outgoing) > C.LIST_MAX:
            res["msg"] = f"{name} would be over the list limit of {C.LIST_MAX}."
            return res
        pay = game.payroll(cid) + sum(p.wage for p in incoming) - sum(p.wage for p in outgoing)
        if pay > game.cap:
            res["msg"] = f"{name} can't fit the wages under the cap (would be ${pay - game.cap}k over)."
            return res
    if not get:
        res["msg"] = f"{ai.name} are happy to take a gift, but ask for something in return."
        return res
    need = ai_out * 1.08
    if ai_in >= need:
        res.update(ok=True, msg=f"{ai.name} accept. (They rate what they get at {ai_in:.0f} points "
                                f"and what they give up at {ai_out:.0f}.)")
    else:
        res["msg"] = (f"{ai.name} say no. They rate your offer at {ai_in:.0f} points and what you're "
                      f"asking for at {ai_out:.0f} - you need roughly {need - ai_in:.0f} more.")
    return res


def execute_trade(game: Game, a_id: str, b_id: str, a_gives: list, b_gives: list) -> None:
    for src, dst, items in ((a_id, b_id, a_gives), (b_id, a_id, b_gives)):
        for it in items:
            if isinstance(it, dict):
                it["owner"] = dst
            else:
                club = game.clubs[src]
                club.lineup = {s: pid for s, pid in club.lineup.items() if pid != it.id}
                if club.captain == it.id:
                    club.captain = None
                it.club = dst
                it.scout_noise = 0.0 if dst == game.meta.get("user_club") else it.scout_noise

    def desc(items):
        return ", ".join(pick_label(i) if isinstance(i, dict) else i.name for i in items) or "nothing"

    game.add_news(f"TRADE: {game.clubs[a_id].name} send {desc(a_gives)} to {game.clubs[b_id].name} "
                  f"for {desc(b_gives)}.", "trade")
    for cid in (a_id, b_id):
        if game.clubs[cid].captain is None:
            pick_captain(game, game.clubs[cid])


def _ai_trades(game: Game, rng) -> None:
    """Contenders shop picks to rebuilders for ready-made senior players."""
    user = game.meta.get("user_club")
    buyers = [c for c in game.clubs.values() if c.strategy != "rebuild" and c.id != user]
    sellers = [c for c in game.clubs.values() if c.strategy != "contend" and c.id != user]
    rng.shuffle(buyers)
    done = 0
    for buyer in buyers:
        if done >= 7:
            break
        picks = [p for p in club_picks(game, buyer.id) if p["year"] == game.year and p["round"] <= 3]
        if not picks:
            continue
        rng.shuffle(sellers)
        for seller in sellers[:6]:
            if seller.id == buyer.id:
                continue
            targets = [p for p in game.squad(seller.id) if 26 <= p.age <= 31 and overall(p) >= 75]
            rng.shuffle(targets)
            deal = None
            for t in targets[:4]:
                if game.payroll(buyer.id) + t.wage > game.cap or len(game.squad(buyer.id)) >= C.LIST_MAX:
                    continue
                for pk in picks:
                    gain_b = _ai_value(game, buyer, t, False) - _ai_value(game, buyer, pk, True)
                    gain_s = _ai_value(game, seller, pk, False) - _ai_value(game, seller, t, True)
                    if gain_b > 0 and gain_s > 0:
                        deal = (t, pk)
                        break
                if deal:
                    break
            if deal:
                execute_trade(game, buyer.id, seller.id, [deal[1]], [deal[0]])
                done += 1
                break


def _ai_free_agents(game: Game, rng) -> None:
    user = game.meta.get("user_club")
    clubs = [c for c in game.clubs.values() if c.id != user]
    rng.shuffle(clubs)
    for club in clubs:
        if len(game.squad(club.id)) >= AI_LIST_TARGET - 3:
            continue
        pool = sorted((game.players[pid] for pid in game.free_agents),
                      key=lambda p: player_value(game, p), reverse=True)
        for p in pool[:3]:
            d = contract_demand(game, p)
            if overall(p) >= 68 and game.payroll(club.id) + d["wage"] <= game.cap * 0.97:
                sign_player(game, p, club.id, d["wage"], d["min_years"])
                if overall(p) >= 74:
                    game.add_news(f"{club.name} snap up free agent {p.name}.", "list")
                break


# -- the draft -----------------------------------------------------------------
def draft_order(game: Game) -> list[str]:
    """Reverse finishing order: wooden-spooners first, premiers last."""
    lad = game.season.get("final_ladder") or [r["club"] for r in season.ladder(game)]
    finish = season.finals_finish(game)
    stage_rank = {"Elimination final": 0, "Semi final": 1, "Preliminary final": 2,
                  "Runner-up": 3, "Premier": 4}
    missed = [c for c in reversed(lad) if c not in finish]
    made = sorted((c for c in lad if c in finish),
                  key=lambda c: (stage_rank[finish[c]], -lad.index(c)))
    return missed + made


def prospect_score(game: Game, p: Player, viewer: str | None = None) -> float:
    """Consensus draft-board rating: mostly upside, some readiness.  AI clubs
    each see a slightly different player, so boards differ club to club."""
    pot = p.potential + p.scout_noise * scout_error(game, viewer)
    if viewer and viewer != game.meta.get("user_club"):
        pot += ((p.id * 31 + sum(map(ord, viewer))) % 9 - 4) * 0.8
    return 0.65 * min(99.0, pot) + 0.35 * overall(p)


def draft_board(game: Game) -> list[Player]:
    pool = [game.players[pid] for pid in game.draft["pool"] if pid in game.players]
    return sorted(pool, key=lambda p: prospect_score(game, p), reverse=True)


def open_draft(game: Game) -> None:
    order, n = [], 0
    base = draft_order(game)
    owners = {(p["round"], p["orig"]): p["owner"] for p in game.draft["picks"] if p["year"] == game.year}
    for rnd in range(1, C.DRAFT_ROUNDS + 1):
        for orig in base:
            n += 1
            order.append({"n": n, "round": rnd, "orig": orig, "owner": owners.get((rnd, orig), orig)})
    game.draft["live"] = {"order": order, "idx": 0, "log": []}


def _draft_select(game: Game, slot: dict, p: Player) -> None:
    cid = slot["owner"]
    senior, _ = list_counts(game, cid)
    rookie = senior >= C.SENIOR_MAX
    wage = max(C.MIN_WAGE, int(round(market_wage(overall(p), p.age, p.potential, game.meta["wage_scale"]) * 0.8 / 5) * 5))
    sign_player(game, p, cid, wage, 2, rookie)
    p.drafted = f"{game.year} pick {slot['n']} ({cid})"
    game.draft["live"]["log"].append([slot["n"], cid, p.id, p.name, p.pos, p.age])
    if slot["n"] <= 10 or cid == game.meta.get("user_club"):
        game.add_news(f"Draft pick {slot['n']}: {game.clubs[cid].name} select {p.name} ({p.pos}, {p.age}).", "draft")


def _ai_draft_choice(game: Game, cid: str) -> Player | None:
    board = [game.players[pid] for pid in game.draft["pool"]]
    if not board:
        return None
    club = game.clubs[cid]
    groups = {}
    for q in game.squad(cid):
        groups[C.POS_GROUP[q.pos]] = groups.get(C.POS_GROUP[q.pos], 0) + 1
    ideal = {"RK": 4, "KD": 5, "GD": 7, "WG": 4, "MD": 10, "GF": 7, "KF": 5}

    def score(p):
        s = prospect_score(game, p, cid)
        s += 0.8 * max(0, ideal[C.POS_GROUP[p.pos]] - groups.get(C.POS_GROUP[p.pos], 0))   # list need
        if club.strategy == "contend":
            s += 0.12 * (overall(p) - 55)          # contenders like the ready-made
        return s
    return max(board, key=score)


def draft_on_clock(game: Game) -> dict | None:
    live = game.draft.get("live")
    if not live or live["idx"] >= len(live["order"]):
        return None
    return live["order"][live["idx"]]


def run_draft(game: Game, stop_for_user: bool = True) -> list:
    """Make picks until it is the user's turn (or to the end).  Returns the new log lines."""
    live = game.draft["live"]
    user = game.meta.get("user_club")
    start = len(live["log"])
    while live["idx"] < len(live["order"]):
        slot = live["order"][live["idx"]]
        cid = slot["owner"]
        size = len(game.squad(cid))
        full = size >= C.LIST_MAX or not game.draft["pool"]
        if cid == user:
            if not full and stop_for_user:
                break
            if not full:                            # auto-pick for the user: best on the board
                board = draft_board(game)
                _draft_select(game, slot, board[0])
        elif not full and (size < AI_LIST_TARGET or slot["round"] == 1):
            p = _ai_draft_choice(game, cid)
            if p:
                _draft_select(game, slot, p)
        live["idx"] += 1
    return live["log"][start:]


def user_draft_pick(game: Game, p: Player) -> tuple[bool, str]:
    slot = draft_on_clock(game)
    if not slot or slot["owner"] != game.meta["user_club"]:
        return False, "You are not on the clock."
    if p.id not in game.draft["pool"]:
        return False, f"{p.name} is not in the draft pool."
    if len(game.squad(slot["owner"])) >= C.LIST_MAX:
        return False, "Your list is full - delist someone or pass."
    _draft_select(game, slot, p)
    game.draft["live"]["idx"] += 1
    return True, f"With pick {slot['n']}, {game.user.name} select {p.name}."


# -- phase transitions ---------------------------------------------------------
def season_review(game: Game, rng) -> dict:
    """Called once, straight after the Grand Final."""
    user = game.user
    review = finance.season_review(game)
    lad = game.season["final_ladder"]
    rows = {r["club"]: r for r in season.ladder(game)}
    finish = season.finals_finish(game)
    entry = {"year": game.year, "premier": game.season["premier"], "runner_up": game.season["runner_up"],
             "ladder": lad, "awards": game.season["awards"]}
    if user:
        r = rows[user.id]
        bnf = season.best_and_fairest(game, user.id, 3)
        entry["user"] = {"club": user.id, "pos": lad.index(user.id) + 1, "w": r["W"], "l": r["L"],
                         "d": r["D"], "finish": finish.get(user.id, ""),
                         "bnf": [[p.name, v] for v, p in bnf]}
        review["bnf"] = entry["user"]["bnf"]
    game.history.append(entry)
    retired = development.process_retirements(game, rng)
    review["retired"] = [[p.name, p.club, p.age, p.career["games"]] for p in retired
                         if user and p.club == user.id]
    review["retired_count"] = len(retired)
    if review.get("sacked"):
        game.meta["sacked"] = True
        game.add_news(f"The {user.name} board has sacked {game.meta.get('manager') or 'the coach'}.", "board")
    return review


def job_offers(game: Game) -> list[str]:
    """Clubs willing to hire a sacked coach: the bottom six that aren't his old one."""
    lad = game.season.get("final_ladder") or [r["club"] for r in season.ladder(game)]
    return [c for c in lad[-7:] if c != game.meta.get("user_club")][-6:]


def open_contracts(game: Game) -> None:
    game.meta["phase"] = "contracts"


def close_contracts(game: Game, rng) -> list[str]:
    """Deadline day: unsigned players walk, AI clubs sort their lists out."""
    user = game.meta.get("user_club")
    lost = []
    for p in out_of_contract(game, user) if user else []:
        lost.append(p.name)
        release_player(game, p)
    if lost:
        game.add_news(f"Out of contract and gone from {game.user.name}: {', '.join(lost)}.", "list")
    for cid in game.clubs:
        if cid != user:
            _ai_contracts(game, cid, rng)
    # the oldest and weakest of the unwanted hang the boots up
    for pid in list(game.free_agents):
        p = game.players[pid]
        if p.age >= 31 or (p.age >= 27 and overall(p) < 64):
            development.remove_player(game, p)
    game.meta["phase"] = "trades"
    return lost


def close_trades(game: Game, rng) -> None:
    _ai_trades(game, rng)
    _ai_free_agents(game, rng)
    game.meta["phase"] = "draft"
    open_draft(game)
    run_draft(game, stop_for_user=True)


def finish_draft_and_roll_over(game: Game, rng) -> dict:
    """Complete the draft, top lists up, then tick the world over to next year."""
    run_draft(game, stop_for_user=False)
    user = game.meta.get("user_club")
    filled = []
    # undrafted kids and leftover free agents fill any list short of the minimum
    spare = sorted((game.players[pid] for pid in game.draft["pool"] + game.free_agents),
                   key=lambda p: prospect_score(game, p), reverse=True)
    for cid in game.clubs:
        while len(game.squad(cid)) < C.LIST_MIN and spare:
            p = spare.pop(0)
            senior, rookies = list_counts(game, cid)
            rookie = rookies < C.ROOKIE_MAX
            sign_player(game, p, cid, C.MIN_WAGE, 1, rookie)
            if cid == user:
                filled.append(p.name)
    # cap floor: clubs under 95% front-load their best players' deals
    for cid in game.clubs:
        short = int(game.cap * C.CAP_FLOOR_PCT) - game.payroll(cid)
        if short > 0:
            best = sorted((p for p in game.squad(cid) if not p.rookie), key=overall, reverse=True)[:8]
            for p in best:
                p.wage += int(round(short / len(best) / 5.0) * 5)
            if cid == user and short >= 50:
                game.add_news(f"To reach the salary floor, ${short}k was front-loaded into your "
                              f"leading players' contracts.", "list")
    draft_log = game.draft["live"]["log"]
    old_year = game.year
    new_cap = int(round(game.cap * C.CAP_GROWTH / 10.0) * 10)
    for cid in game.clubs:                          # AI clubs restructure deals to stay legal
        pay = game.payroll(cid)
        if cid != user and pay > new_cap:
            k = new_cap * 0.995 / pay
            for p in game.squad(cid):
                if not p.rookie:
                    p.wage = max(C.MIN_WAGE, int(p.wage * k / 5.0) * 5)
    for pid in list(game.draft["pool"]):            # the undrafted go back to state leagues
        development.remove_player(game, game.players[pid])
    keep = sorted((game.players[pid] for pid in game.free_agents),
                  key=lambda p: player_value(game, p), reverse=True)[:25]
    for pid in list(game.free_agents):
        if game.players[pid] not in keep:
            development.remove_player(game, game.players[pid])

    notes = development.new_year_progression(game, rng)
    game.meta["year"] = old_year + 1
    game.meta["cap"] = new_cap
    game.meta["wage_scale"] = round(game.meta["wage_scale"] * C.CAP_GROWTH, 3)
    game.draft["picks"] = [p for p in game.draft["picks"] if p["year"] > old_year]
    add_draft_picks(game, game.year + 1)
    lad = game.season["final_ladder"]
    premier = game.season["premier"]
    ranking = sorted(game.clubs, key=lambda c: best22_rating(game, c), reverse=True)
    for cid, club in game.clubs.items():
        pos = lad.index(cid) + 1
        club.supporters = round(club.supporters * (1.0 + 0.04 * (9.5 - pos) / 8.5 + (0.03 if cid == premier else 0)), 1)
        i = ranking.index(cid)
        club.strategy = "contend" if i < 6 else "rebuild" if i >= 12 else "balanced"
        if club.captain not in {p.id for p in game.squad(cid)}:
            pick_captain(game, club)
    generate_draft_pool(game, rng)
    season.start_season(game, rng)
    finance.set_board_expectations(game)
    for cid, club in game.clubs.items():
        if cid == user and game.meta.get("selection") == "manual":
            repair_lineup(game, cid)
        else:
            club.lineup = auto_select(game, cid)
    game.add_news(f"The {game.year} season is here. Salary cap: ${game.cap}k.", "league", "Pre-season")
    return {"draft_log": draft_log, "filled": filled, "notes": notes, "year": game.year}
