"""Engine calibration report: run whole seasons and print the numbers that
should look like real footy.  Usage: python tests/calibrate.py [seasons]"""
import random, statistics as st, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aflm import generator, season, constants as C
from aflm.ratings import best22_rating, overall

def run(n_seasons=3, seed=1):
    scores, margins, wins_by_rank, gb = [], [], {}, [0, 0]
    slot_impact, top_goals, top_disp, hga, team = {}, [], [], [0, 0], {"i50": [], "cl": [], "ho": []}
    disp_t, marks_t, tack_t, ratings, bench_r = [], [], [], [], []
    t0 = time.time()
    for s in range(n_seasons):
        g = generator.new_game(seed=seed + s)
        rng = random.Random(seed + s)
        g.meta["keep_all_detail"] = True
        rank = {c: i for i, c in enumerate(sorted(g.clubs, key=lambda c: best22_rating(g, c), reverse=True))}
        if s == 0:
            b = sorted(best22_rating(g, c) for c in g.clubs)
            print("best22 OVR range: %.1f .. %.1f" % (b[0], b[-1]))
            ov = sorted(overall(p) for p in g.players.values() if p.status == "listed")
            print("league OVR pctiles 10/50/90/99: %.0f %.0f %.0f %.0f  max %.0f" % (ov[len(ov)//10], ov[len(ov)//2], ov[len(ov)*9//10], ov[len(ov)*99//100], ov[-1]))
            pay = sorted(g.payroll(c) for c in g.clubs); print("payroll range", pay[0], pay[-1], "scale", g.meta["wage_scale"])
        for r in range(C.HA_ROUNDS):
            rep = season.play_round(g, rng)
            for m in rep["matches"]:
                scores += [m["hs"][2], m["as"][2]]; margins.append(abs(m["hs"][2] - m["as"][2]))
                gb[0] += m["hs"][0] + m["as"][0]; gb[1] += m["hs"][1] + m["as"][1]
                hga[0] += m["hs"][2] > m["as"][2]; hga[1] += 1
                for k in team: team[k] += [m["team"][0][k], m["team"][1][k]]
                if "detail" in m:
                    for side in (0, 1):
                        ps = [x for x in m["detail"]["players"].values() if x["side"] == side]
                        disp_t.append(sum(x["k"] + x["hb"] for x in ps)); marks_t.append(sum(x["m"] for x in ps)); tack_t.append(sum(x["t"] for x in ps))
                    for x in m["detail"]["players"].values():
                        ratings.append(x["rt"])
                        if x["slot"] not in C.FIELD_SLOTS: bench_r.append(x["rt"])
                        if x["slot"] in C.FIELD_SLOTS:
                            imp = 3*x["k"]+2*x["hb"]+3*x["m"]+4*x["t"]+6*x["g"]+x["b"]+x["ho"]+2*x["cl"]+3*x["int"]+2.5*x["sp"]+x["i50"]
                            slot_impact.setdefault(C.FIELD_SLOTS[x["slot"]], []).append(imp)
        lad = season.ladder(g)
        for row in lad: wins_by_rank.setdefault(rank[row["club"]], []).append(row["W"])
        top_goals.append(season.leaders(g, "g", 1)[0][0]); top_disp.append(season.leaders(g, "disp", 1, min_games=15)[0][0])
        if s == 0:
            print("ladder W:", [r["W"] for r in lad], " pct top/bot: %.0f/%.0f" % (lad[0]["pct"], lad[-1]["pct"]))
            print("injured now:", sum(1 for p in g.players.values() if p.injury) / 18.0, "per club; avg fitness %.0f" % st.mean(p.fitness for p in g.players.values() if p.status == "listed"))
            import collections
            gp = collections.Counter()
            for p in g.players.values():
                if p.stats.get(str(g.year)): gp[C.POS_GROUP[p.pos]] += p.stats[str(g.year)]["g"]
            tot = sum(gp.values()); print("goal share by group:", {k: round(v / tot, 2) for k, v in gp.items()})
            print("top goals:", [(int(v), p.name, p.pos) for v, p in season.leaders(g, "g", 5)])
            print("top disp:", [(round(v, 1), p.pos) for v, p in season.leaders(g, "disp", 5, min_games=15)])
            print("top votes:", [(int(v), p.pos) for v, p in season.leaders(g, "v", 6)])
            print("top rating:", [(round(v, 2), p.pos, round(overall(p))) for v, p in season.leaders(g, "rt", 8, min_games=15)])
    print("%d seasons in %.1fs" % (n_seasons, time.time() - t0))
    print("avg score %.1f  sd %.1f | avg margin %.1f | goals/behinds per team %.1f / %.1f | home win %.3f" % (st.mean(scores), st.pstdev(scores), st.mean(margins), gb[0]/len(scores), gb[1]/len(scores), hga[0]/hga[1]))
    print("team i50 %.1f cl %.1f ho %.1f | disp %.0f marks %.0f tackles %.0f | rating mean %.2f sd %.2f" % (st.mean(team["i50"]), st.mean(team["cl"]), st.mean(team["ho"]), st.mean(disp_t), st.mean(marks_t), st.mean(tack_t), st.mean(ratings), st.pstdev(ratings)))
    print("bench rating mean %.2f" % st.mean(bench_r))
    print("wins by list rank:", [round(st.mean(wins_by_rank[i]), 1) for i in range(18)])
    print("coleman", [int(x) for x in top_goals], " top disp avg", [round(x, 1) for x in top_disp])
    print("mean impact by role:", {k: round(st.mean(v)) for k, v in sorted(slot_impact.items())})
    print("sd impact by role:", {k: round(st.pstdev(v)) for k, v in sorted(slot_impact.items())})
    print("margins >60: %.3f  <12: %.3f" % (sum(m > 60 for m in margins)/len(margins), sum(m < 12 for m in margins)/len(margins)))

if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 3)
