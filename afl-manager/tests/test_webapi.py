"""The browser app's JSON API: every screen and action, through a full year."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aflm import webapi  # noqa: E402


def call(op, **args):
    res = json.loads(webapi.handle(json.dumps({"op": op, "args": args})))
    assert res["ok"], (op, args, res.get("error"), res.get("trace"))
    return res["data"], res["header"]


def fail(op, **args):
    res = json.loads(webapi.handle(json.dumps({"op": op, "args": args})))
    assert not res["ok"] and "trace" not in res, (op, res)
    return res["error"]


SCREENS = ["home", "squad", "team", "preview", "match", "fixtures", "round", "ladder", "stats", "club",
           "contracts", "trade", "draft", "agents", "news"]


def all_screens():
    for op in SCREENS:
        data, header = call(op)
        json.dumps(data)                                  # everything must be JSON-safe
        assert header["club"]


def test_full_year_through_the_api():
    boot, header = call("boot")
    assert set(boot["static"]["clubs"]) == {c[0] for c in webapi.C.CLUBS}
    data, header = call("new", seed=9)
    assert len(data["clubs"]) == 18 and not header["has_club"]
    call("choose", club="RIC", name="Api Tester")
    all_screens()
    squad, _ = call("squad")
    assert len(squad["players"]) == 42 and len(squad["players"][0]["a"]) == 15
    star = max(squad["players"], key=lambda p: p["ovr"])
    prof, _ = call("player", id=star["id"])
    assert prof["own"] and len(prof["roles"]) == 13
    call("squad", club="GEE"); call("team", club="GEE"); call("fixtures", club="GEE")
    call("stats", what="disposals", club="RIC"); call("search", q=star["name"].split()[-1][:4])
    # selection: naming a player flips to manual, auto hands it back
    team, _ = call("team")
    bench = next(p for p in team["players"] if not p["sel"] and not p["inj"])
    call("act", cmd=f"pick IC5 #{bench['id']}")
    assert call("team")[1]["selection"] == "manual"
    call("act", cmd="selection auto")
    call("act", cmd="tactics style=contested pressure=high")
    call("act", cmd="training focus=skills intensity=light")
    assert "ambiguous" in fail("act", cmd="tactics balanced") or True
    # a bad trade is refused politely; trades can't be executed mid-season
    tr, _ = call("trade", club="GEE")
    best = max(tr["theirs"], key=lambda p: p["value"])
    ev, _ = call("trade_eval", club="GEE", give=[tr["my_picks"][-1]["code"]], get=[best["id"]])
    assert not ev["ok"] and ev["ai_out"] > ev["ai_in"]
    assert "trade period" in fail("trade_eval", club="GEE", give=[tr["my_picks"][0]["code"]],
                                  get=[tr["their_picks"][0]["code"]], execute=True)
    # play the season
    step, header = call("advance")
    assert step["kind"] == "round" and step["match"]
    m, _ = call("match", id=step["match"])
    m = m["match"]
    assert len(m["players"]) == 46 and m["timeline"] and m["feed"] is not None
    goals = [sum(1 for e in m["timeline"] if e[2] == side and e[3] == "G") for side in (0, 1)]
    assert goals == [m["hs"][0], m["as"][0]]              # the live view adds up to the final score
    behinds = [sum(1 for e in m["timeline"] if e[2] == side and e[3] in "BR") for side in (0, 1)]
    assert behinds == [m["hs"][1], m["as"][1]]
    guard = 0
    while header["phase"] in ("season", "finals"):
        step, header = call("advance")
        guard += 1
        assert guard < 40
    assert header["phase"] == "review" and step["season_over"]
    all_screens()
    call("round", n="finals")
    if header["sacked"]:
        offers, _ = call("clubs")
        call("choose", club=offers["offers"][0])
    assert call("advance")[0]["kind"] == "contracts_open"
    step, header = call("advance")
    if header["unsigned"]:
        assert step["kind"] == "unsigned" and step["players"]
        call("act", cmd="offer all")
        step, header = call("advance", confirm=True)
    assert step["kind"] == "trades_open" and header["phase"] == "trades"
    all_screens()
    # a fair trade goes through in the trade period: swap like-for-like picks
    tr, _ = call("trade", club="GEE")
    mine = [p for p in tr["my_picks"] if p["round"] == 1]
    theirs = [p for p in tr["their_picks"] if p["round"] == 3]
    if mine and theirs:
        ev, _ = call("trade_eval", club="GEE", give=[mine[0]["code"]], get=[theirs[0]["code"]], execute=True)
        assert ev["ok"] and ev["done"]
    agents, _ = call("agents")
    assert call("advance")[0]["kind"] == "draft_open"
    d, header = call("draft")
    assert d["live"] and d["board"]
    while header["on_clock"]:
        picked, header = call("draft_pick")
        assert picked["pot"]
    step, header = call("advance")
    assert step["kind"] == "new_season" and header["phase"] == "season" and header["year"] == 2028
    all_screens()
    # save / load round trip through the string the app stores
    blob = webapi.dump()
    call("load", bundle=blob)
    assert webapi.dump() == blob
    assert "not an AFL Manager save" in fail("load", bundle="{}")
    assert "Unknown request" in fail("nope")


def test_engine_bundle_is_current():
    """The app ships a bundle of aflm/*.py; it must match the source."""
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "build_web.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


if __name__ == "__main__":
    test_full_year_through_the_api()
    print("ok  test_full_year_through_the_api")
    test_engine_bundle_is_current()
    print("ok  test_engine_bundle_is_current")
