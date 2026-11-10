"""Long-run health check: play N seasons with a hands-off user and print how the
league evolves (talent levels, list sizes, payroll, parity).  python tests/longrun.py [seasons] [seed]"""
import os, random, statistics as st, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("AFLM_SAVES", tempfile.mkdtemp(prefix="aflm_long_"))
from aflm import generator, offseason, season
from aflm.commands import execute
from aflm.ratings import overall, best22_rating

def main(n=8, seed=21, club="ESS"):
    g = generator.new_game(seed=seed); execute(g, f"choose {club} Bot"); rng = random.Random(seed)
    def snap(tag):
        ov = sorted(overall(p) for p in g.players.values() if p.status == "listed")
        b = sorted(best22_rating(g, c) for c in g.clubs)
        ages = [p.age for p in g.players.values() if p.status == "listed"]
        sizes = [len(g.squad(c)) for c in g.clubs]; pay = [g.payroll(c) / g.cap for c in g.clubs]
        print(f"{tag}: ovr p10/50/90/max {ov[len(ov)//10]:.0f}/{ov[len(ov)//2]:.0f}/{ov[len(ov)*9//10]:.0f}/{ov[-1]:.0f} "
              f"best22 {b[0]:.1f}..{b[-1]:.1f} age {st.mean(ages):.1f} lists {min(sizes)}-{max(sizes)} "
              f"pay {min(pay):.2f}-{max(pay):.2f} 85+:{sum(o >= 85 for o in ov)} 90+:{sum(o >= 90 for o in ov)}")
    snap("start")
    for _ in range(n):
        while g.phase in ("season", "finals"):
            out = execute(g, "sim", rng); assert not out.startswith("!"), out
        lad = season.ladder(g); h = g.history[-1]; u = h["user"]
        tag = (f"{g.year} prem {h['premier']} wins {lad[0]['W']}..{lad[-1]['W']} coleman {h['awards']['coleman'][2]} "
               f"user {u['club']} {u['pos']} ({u['w']}-{u['l']}) conf {g.user.board['confidence']:.0f}")
        if g.meta.get("sacked"):
            tag += " SACKED"; execute(g, f"choose {offseason.job_offers(g)[0]}")
        for cmd in ("advance", "offer all", "advance confirm", "advance"):
            execute(g, cmd, rng)
        while (s := offseason.draft_on_clock(g)) and s["owner"] == g.user.id:
            execute(g, "draft auto", rng)
        out = execute(g, "advance", rng); assert not out.startswith("!"), out
        snap(tag)

if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8, int(sys.argv[2]) if len(sys.argv) > 2 else 21)
