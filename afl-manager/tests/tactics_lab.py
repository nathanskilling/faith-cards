"""Tactics balance check: play the same fixture many times, changing one
setting at a time for one side, and report the swing in win rate and margin.
No option should be a free lunch.   python tests/tactics_lab.py [games]"""
import random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aflm import generator, constants as C
from aflm.match_engine import simulate_match
from aflm.ratings import strength_ranking

def trial(g, a, b, tactics, n, rng, wet=None):
    g.clubs[a].tactics = dict(tactics); g.clubs[b].tactics = dict(C.DEFAULT_TACTICS)
    wins = margin = pts = 0
    for i in range(n):
        home, away = (a, b) if i % 2 == 0 else (b, a)
        r = simulate_match(g, home, away, g.clubs[home].ground, rng=rng, wet=wet)
        d = r["hs"][2] - r["as"][2] if home == a else r["as"][2] - r["hs"][2]
        wins += (d > 0) + 0.5 * (d == 0); margin += d; pts += r["hs"][2] + r["as"][2]
    return wins / n, margin / n, pts / n

def main(n=1500):
    g = generator.new_game(seed=12); rng = random.Random(1)
    rank = strength_ranking(g)
    for label, (a, b) in {"even sides": (rank[8], rank[9]), "underdog": (rank[14], rank[4])}.items():
        base = trial(g, a, b, C.DEFAULT_TACTICS, n, rng)
        print(f"\n{label}: {a} v {b}  baseline win {base[0]:.3f} margin {base[1]:+.1f} total {base[2]:.0f}")
        for key, opts in C.TACTIC_OPTIONS.items():
            for opt in opts:
                if opt == C.DEFAULT_TACTICS[key]: continue
                w, m, p = trial(g, a, b, {**C.DEFAULT_TACTICS, key: opt}, n, rng)
                print(f"  {key:<9}{opt:<10} win {w - base[0]:+.3f}  margin {m - base[1]:+5.1f}  total pts {p - base[2]:+5.1f}")
        for name, t in C.PHILOSOPHIES.items():
            w, m, p = trial(g, a, b, t, n, rng)
            print(f"  preset {name:<19} win {w - base[0]:+.3f}  margin {m - base[1]:+5.1f}")
        w, m, p = trial(g, a, b, C.DEFAULT_TACTICS, n, rng, wet=True)
        for key, opt in (("forward", "small"), ("style", "contested"), ("style", "outside"), ("forward", "tall")):
            w2, m2, _ = trial(g, a, b, {**C.DEFAULT_TACTICS, key: opt}, n, rng, wet=True)
            print(f"  WET {key}={opt:<10} win {w2 - w:+.3f}  margin {m2 - m:+5.1f}")

if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1500)
