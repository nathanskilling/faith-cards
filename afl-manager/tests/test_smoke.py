"""End-to-end tests: build a world, play three full years through every
off-season phase and check the invariants that keep a career sane.

Run with:  python -m pytest tests -q      (or simply: python tests/test_smoke.py)
"""
import os
import random
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("AFLM_SAVES", tempfile.mkdtemp(prefix="aflm_test_"))

from aflm import constants as C, generator, offseason, season, storage  # noqa: E402
from aflm.commands import execute  # noqa: E402
from aflm.ratings import lineup_problems, overall  # noqa: E402


def new(seed=3, club="CAR"):
    g = generator.new_game(seed=seed, save_name=f"test{seed}")
    out = execute(g, f"choose {club} Test Coach")
    assert "senior coach" in out, out
    return g


def check_world(g):
    for cid in g.clubs:
        squad = g.squad(cid)
        assert C.LIST_MIN <= len(squad) <= C.LIST_MAX, (cid, len(squad))
        assert g.payroll(cid) <= g.cap, (cid, g.payroll(cid), g.cap)
        senior, rookies = offseason.list_counts(g, cid)
        assert senior <= C.SENIOR_MAX + 2 and rookies <= C.ROOKIE_MAX + 2, (cid, senior, rookies)
    for p in g.players.values():
        assert all(1.0 <= v <= 20.0 for v in p.attrs.values()), p.name
        assert 17 <= p.age <= 40
        if p.status == "listed":
            assert p.club in g.clubs


def test_fixture_is_fair():
    g = new()
    home, games, meets = {}, {}, {}
    for rd in g.season["rounds"]:
        assert len(rd) == 9
        teams = [t for m in rd for t in (m["home"], m["away"])]
        assert len(set(teams)) == 18                      # everyone plays every round
        for m in rd:
            home[m["home"]] = home.get(m["home"], 0) + 1
            for t in (m["home"], m["away"]):
                games[t] = games.get(t, 0) + 1
            key = frozenset((m["home"], m["away"]))
            meets[key] = meets.get(key, 0) + 1
    assert set(games.values()) == {23}
    assert all(11 <= h <= 12 for h in home.values()), home
    assert len(meets) == 153 and set(meets.values()) == {1, 2}
    assert all(meets[frozenset(r)] == 2 for r in C.RIVALRIES)


def test_new_world_is_sane():
    g = new()
    assert len(g.clubs) == 18 and g.user.id == "CAR"
    check_world(g)
    assert len(g.draft["pool"]) == C.DRAFT_POOL_SIZE
    assert len(g.draft["picks"]) == 18 * C.DRAFT_ROUNDS * 2
    assert not lineup_problems(g, "CAR")


def test_commands_do_not_crash():
    g = new()
    rng = random.Random(1)
    squad = sorted(g.squad("CAR"), key=overall, reverse=True)
    star, fringe = squad[0], squad[-1]
    for cmd in ["help", "clubs", "status", "squad", "squad ovr", "squad GEE value", f"player #{star.id}",
                f"player {star.name}", "lineup", "pick auto", f"pick IC5 #{squad[25].id}",
                f"swap #{squad[0].id}, #{squad[1].id}", f"captain #{star.id}", "tactics",
                "tactics style=contested pressure=high", "tactics fast zone", "tactics preset Run and Gun",
                "training", "training skills heavy", "preview", "ladder", "fixture", "fixture GEE",
                "finances", "board", "contracts", "picks", "freeagents", "draft", "news", "history",
                "show squad", "simulate next match", "match", "match all", "results", "stats goals",
                "stats disposals", "stats rating CAR", "stats votes",
                f"trade check GEE give {g.year}R1 for {g.year}R2", f"offer #{fringe.id} 1"]:
        out = execute(g, cmd, rng)
        assert out and "Traceback" not in out, cmd
        assert not out.startswith("Unknown command"), (cmd, out)
    assert execute(g, "player zzzzqqq").startswith("!")
    assert execute(g, "trade GEE give nothing for nothing").startswith("!")   # not trade period
    assert g.meta["round"] == 2


def test_three_full_seasons_and_save_roundtrip():
    g = new(seed=5, club="STK")
    rng = random.Random(5)
    for year in range(3):
        start_year = g.year
        guard = 0
        while g.phase in ("season", "finals"):
            out = execute(g, "sim", rng)
            assert not out.startswith("!"), out
            guard += 1
            assert guard < 40
        assert g.phase == "review" and g.season["premier"]
        lad = season.ladder(g)
        assert sum(r["W"] for r in lad) == sum(r["L"] for r in lad)
        assert all(r["P"] == 23 for r in lad)
        assert 60 < sum(r["PF"] for r in lad) / (18 * 23) < 110          # sane scoring
        if g.meta.get("sacked"):
            assert not execute(g, f"choose {offseason.job_offers(g)[0]}").startswith("!")
        assert "review" in execute(g, "review").lower()
        execute(g, "advance", rng)                                       # -> contracts
        assert g.phase == "contracts"
        assert "WILL LEAVE" in execute(g, "advance", rng) or not offseason.out_of_contract(g, g.user.id)
        execute(g, "offer all", rng)
        execute(g, "advance confirm", rng)                               # -> trades
        assert g.phase == "trades"
        # try a real trade: our second-rounder for the best player an AI club will give up for it
        mine = [p for p in offseason.club_picks(g, g.user.id) if p["year"] == g.year]
        if mine:
            code = f"{mine[0]['year']}R{mine[0]['round']}:{mine[0]['orig']}"
            for target in sorted(g.squad("GEE"), key=overall):
                if not execute(g, f"trade check GEE give {code} for #{target.id}", rng).startswith("[trade check] Geelong accept"):
                    continue
                out = execute(g, f"trade GEE give {code} for #{target.id}", rng)
                assert out.startswith("DONE") or out.startswith("Geelong") or "list limit" in out or "cap" in out, out
                break
        fa = g.free_agents[:1]
        if fa:
            execute(g, f"sign #{fa[0]} 1", rng)
        execute(g, "advance", rng)                                       # -> draft
        assert g.phase == "draft"
        slot = offseason.draft_on_clock(g)
        if slot and slot["owner"] == g.user.id:
            out = execute(g, "draft auto", rng)
            assert not out.startswith("!"), out
        out = execute(g, "advance", rng)                                 # -> new season
        assert not out.startswith("!"), out
        assert g.year == start_year + 1 and g.phase == "season" and g.meta["round"] == 1
        check_world(g)
        assert not lineup_problems(g, g.user.id)
        assert len(g.history) == year + 1
    # save / load must round-trip exactly
    storage.save_game(g, "roundtrip")
    g2 = storage.load_game("roundtrip")
    assert g2.meta == g.meta and len(g2.players) == len(g.players)
    assert {k: v.to_dict() for k, v in g2.players.items()} == {k: v.to_dict() for k, v in g.players.items()}
    assert {k: v.to_dict() for k, v in g2.clubs.items()} == {k: v.to_dict() for k, v in g.clubs.items()}
    assert g2.season == g.season
    assert not execute(g2, "sim", rng).startswith("!")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
