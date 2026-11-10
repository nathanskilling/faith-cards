"""AFL Manager - Streamlit front end.

    pip install streamlit
    streamlit run app.py

A thin skin over the same engine the text commands use: tables come from
aflm.views, every action goes through aflm.commands.execute (so the rules are
identical in both interfaces) and the career is saved after each action.
"""
import pandas as pd
import streamlit as st

from aflm import constants as C
from aflm import generator, offseason, season, storage, views
from aflm.commands import execute, lineup_text, phase_label, refresh_auto_lineup
from aflm.ratings import ovr, lineup_problems

st.set_page_config(page_title="AFL Manager", page_icon="🏉", layout="wide")


# -- plumbing ------------------------------------------------------------------
def get_game():
    if "game" not in st.session_state:
        try:
            st.session_state.game = storage.load_game()
        except FileNotFoundError:
            st.session_state.game = None
    return st.session_state.game


def run(cmd: str, show: bool = True) -> str:
    """Run a text command against the game, save, and remember the output."""
    g = st.session_state.game
    out = execute(g, cmd)
    storage.save_game(g)
    if show:
        st.session_state.flash = out
    return out


def flash():
    out = st.session_state.pop("flash", None)
    if out:
        if out.startswith("!"):
            st.error(out[2:])
        else:
            st.code(out, language=None)


def df(rows, **kw):
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", **kw)


def player_options(players):
    return {f"{p.name} ({p.pos} {ovr(p)}, {p.age}) #{p.id}": p.id for p in players}


# -- start-up screens ----------------------------------------------------------
def screen_new_game():
    st.title("🏉 AFL Manager")
    st.write("No career found. Create a new world - 18 clubs, about 760 fictional players, "
             "a different balance of power every time.")
    saves = storage.list_saves()
    if saves:
        pick = st.selectbox("Load an existing career", saves)
        if st.button("Load"):
            st.session_state.game = storage.load_game(pick)
            storage.save_game(st.session_state.game)
            st.rerun()
    with st.form("new"):
        name = st.text_input("Save name", "career")
        seed = st.number_input("World seed (0 = random)", 0, 999999, 0)
        if st.form_submit_button("Create world"):
            st.session_state.game = generator.new_game(seed=int(seed) or None, save_name=name)
            storage.save_game(st.session_state.game, name)
            st.rerun()


def screen_choose_club(g):
    st.title("🏉 Choose your club")
    st.write("Clubs are ranked by list strength. Take a contender and chase the flag, "
             "or take a battler and build it from the draft up.")
    df(views.club_rows(g))
    names = {f"{c.full_name} ({cid})": cid for cid, c in g.clubs.items()}
    if g.meta.get("sacked"):
        offers = offseason.job_offers(g)
        names = {k: v for k, v in names.items() if v in offers}
        st.warning("You were sacked. These clubs are prepared to give you another go.")
    c1, c2 = st.columns(2)
    club = c1.selectbox("Club", list(names))
    coach = c2.text_input("Your name", g.meta.get("manager", ""))
    if st.button("Take the job", type="primary"):
        run(f"choose {names[club]} {coach}".strip())
        st.rerun()


# -- pages ---------------------------------------------------------------------
def page_home(g):
    club = g.user
    rec = views.record(g, club.id)
    c = st.columns(5)
    c[0].metric(f"Ladder ({rec['W']}-{rec['L']}-{rec['D']})", f"{rec['pos']} of 18")
    c[1].metric("Percentage", f"{rec['pct']:.1f}")
    c[2].metric("Board confidence", f"{club.board['confidence']:.0f}/100")
    c[3].metric("Cap room", views.money(offseason.cap_space(g, club.id)))
    c[4].metric("Bank", views.money(club.balance))
    st.caption(f"Board expectation: {club.board['label']}")

    label = {"season": "▶ Play next round", "finals": "▶ Play finals week", "review": "Open contract talks",
             "contracts": "Close the signing period", "trades": "Close the trade period",
             "draft": "Finish draft and start next season"}[g.phase]
    b1, b2, _ = st.columns([1, 1, 3])
    if b1.button(label, type="primary"):
        run("advance")
        st.rerun()
    if g.phase == "contracts" and offseason.out_of_contract(g, club.id):
        if b2.button("Let unsigned players go"):
            run("advance confirm")
            st.rerun()
    if g.phase == "season" and b2.button("Sim 5 rounds"):
        run("sim 5")
        st.rerun()
    flash()
    st.code(execute(g, "status"), language=None)


def page_squad(g):
    c1, c2 = st.columns([2, 1])
    ids = list(g.clubs)
    cid = c1.selectbox("Club", ids, index=ids.index(g.user.id), format_func=lambda c: g.clubs[c].full_name)
    sort = c2.selectbox("Sort", list(views.SQUAD_SORTS))
    rows = views.squad_rows(g, cid, sort)
    df(rows, height=560)
    st.caption("Form = average of last five senior ratings (r = reserves). Sel = spot in the 23. "
               "Wage in $k. Value = trade points. POT is exact for your list, an estimate for others.")
    opts = player_options(sorted(g.squad(cid), key=ovr, reverse=True))
    who = st.selectbox("Player profile", list(opts))
    st.code(execute(g, f"player #{opts[who]}"), language=None)


def page_selection(g):
    club = g.user
    mode = g.meta.get("selection", "auto")
    c1, c2, c3 = st.columns([2, 1, 1])
    new_mode = c1.radio("Who picks the team?", ["auto", "manual"], index=["auto", "manual"].index(mode),
                        horizontal=True,
                        format_func=lambda m: "Assistant coach (best 23 every week)" if m == "auto" else "I do")
    if new_mode != mode:
        run(f"selection {new_mode}", show=False)
        st.rerun()
    if c2.button("Pick best 23 now"):
        run("pick auto", show=False)
        st.rerun()
    flash()
    st.code(lineup_text(g, club.id), language=None)
    s = views.team_summary(g, club.id)
    st.caption(f"Defence {s['def']} · Midfield {s['mid']} · Attack {s['fwd']} · average age {s['avg_age']} · "
               f"average fitness {s['avg_fit']}%   (* = out of position, ! = injured)")
    for prob in lineup_problems(g, club.id):
        st.warning(prob)
    st.subheader("Make a change")
    squad = sorted((p for p in g.squad(club.id) if not p.injury), key=ovr, reverse=True)
    opts = player_options(squad)
    a, b, c = st.columns([1, 3, 1])
    slot = a.selectbox("Position", C.ALL_SLOTS)
    who = b.selectbox("Player", list(opts))
    if c.button("Name him", type="primary"):
        run(f"pick {slot} #{opts[who]}")
        st.rerun()
    named = set(club.lineup.values())
    out = [views.player_row(g, p) for p in g.squad(club.id) if p.id not in named]
    st.subheader("Not selected")
    df(sorted(out, key=lambda r: -r["OVR"]), column_order=["ID", "Name", "Pos", "Age", "OVR", "POT", "Fit", "Form", "Status"])


def page_game_plan(g):
    club = g.user
    st.subheader(f"Game plan - {club.philosophy}")
    new = {}
    cols = st.columns(len(C.TACTIC_OPTIONS))
    for col, (key, opts) in zip(cols, C.TACTIC_OPTIONS.items()):
        names = list(opts)
        new[key] = col.radio(key.title(), names, index=names.index(club.tactics[key]),
                             captions=[opts[n] for n in names])
    preset = st.selectbox("...or load a preset", ["-"] + list(C.PHILOSOPHIES))
    c1, c2 = st.columns([1, 5])
    if c1.button("Save game plan", type="primary"):
        if preset != "-":
            run(f"tactics preset {preset}", show=False)
        else:
            run("tactics " + " ".join(f"{k}={v}" for k, v in new.items()), show=False)
        st.rerun()
    st.divider()
    st.subheader("Training")
    f, i = st.columns(2)
    focus_names = list(C.TRAINING_FOCUS)
    focus = f.radio("Focus", focus_names, index=focus_names.index(club.training["focus"]),
                    captions=[C.TRAINING_FOCUS[n][0] for n in focus_names])
    inten_names = list(C.TRAINING_INTENSITY)
    inten = i.radio("Intensity", inten_names, index=inten_names.index(club.training["intensity"]),
                    captions=["Fresh legs, slower development.", "Standard week.",
                              "Faster development, slower recovery, more soft-tissue injuries."])
    if st.button("Save training"):
        run(f"training focus={focus} intensity={inten}", show=False)
        st.rerun()


def page_match_centre(g):
    club = g.user
    tabs = st.tabs(["Last match", "Next opponent", "All results"])
    played = [m for m in season.club_matches(g, club.id) if m["played"]]
    with tabs[0]:
        if played:
            labels = {f"{m['rnd']}: {views.result_text(g, m)}": m["id"] for m in reversed(played)}
            pick = st.selectbox("Match", list(labels))
            both = st.checkbox("Show both teams' player stats")
            st.code(execute(g, f"match {labels[pick]}" + (" all" if both else "")), language=None)
        else:
            st.info("No games played yet this season.")
    with tabs[1]:
        st.code(execute(g, "preview"), language=None)
    with tabs[2]:
        rnd = st.slider("Round", 1, C.HA_ROUNDS, max(1, min(C.HA_ROUNDS, g.meta["round"] - 1)))
        st.code(execute(g, f"results {rnd}"), language=None)
        if g.season["finals"]:
            st.code(execute(g, "results finals"), language=None)


def page_competition(g):
    tabs = st.tabs(["Ladder", "Fixture", "Leaders", "Honour roll"])
    with tabs[0]:
        df(views.ladder_rows(g), height=670, column_order=["Pos", "Club", "P", "W", "L", "D", "PF", "PA", "%", "Pts"])
    with tabs[1]:
        ids = list(g.clubs)
        cid = st.selectbox("Club", ids, index=ids.index(g.user.id), format_func=lambda c: g.clubs[c].full_name,
                           key="fixture_club")
        df(views.fixture_rows(g, cid), height=880)
    with tabs[2]:
        c1, c2 = st.columns(2)
        what = c1.selectbox("Category", list(views.LEADER_KEYS))
        only = c2.checkbox(f"{g.user.name} only")
        df(views.leader_rows(g, what, 25, g.user.id if only else None))
    with tabs[3]:
        st.code(execute(g, "history"), language=None)


def page_club(g):
    club = g.user
    tabs = st.tabs(["Board", "Finances", "News"])
    with tabs[0]:
        st.code(execute(g, "board"), language=None)
        if g.season.get("premier"):
            st.code(execute(g, "review"), language=None)
    with tabs[1]:
        df(views.finance_rows(g, club.id))
        st.caption("All figures $k. Negative numbers are costs.")
        st.code(execute(g, "finances").split("\n\n")[-1], language=None)
    with tabs[2]:
        st.code(execute(g, "news 40"), language=None)


def page_list_management(g):
    club = g.user
    senior, rookies = offseason.list_counts(g, club.id)
    st.caption(f"{senior}/{C.SENIOR_MAX} senior · {rookies}/{C.ROOKIE_MAX} rookie · payroll "
               f"{views.money(g.payroll(club.id))} of {views.money(g.cap)} · phase: {phase_label(g)}")
    flash()
    tabs = st.tabs(["Contracts", "Trades", "Draft", "Free agents"])
    squad = sorted(g.squad(club.id), key=ovr, reverse=True)
    with tabs[0]:
        df(views.contract_rows(g, club.id), height=420)
        opts = player_options(squad)
        a, b, c, d = st.columns([3, 1, 1, 2])
        who = a.selectbox("Player", list(opts), key="con_p")
        years = b.number_input("Years", 1, 5, 2)
        wage = c.number_input("Wage $k (0 = his asking)", 0, 2500, 0, step=10)
        with d:
            st.write("")
            x, y, z = st.columns(3)
            if x.button("Offer"):
                run(f"offer #{opts[who]} {years}" + (f" {wage}" if wage else ""))
                st.rerun()
            if y.button("Delist"):
                run(f"delist #{opts[who]}")
                st.rerun()
            if z.button("Promote"):
                run(f"promote #{opts[who]}")
                st.rerun()
        if st.button("Re-sign everyone out of contract at their asking price"):
            run("offer all")
            st.rerun()
    with tabs[1]:
        st.write("Offer players and picks to another club. *Check* asks what they think; "
                 "*Do the deal* only works in the trade period.")
        others = [c for c in g.clubs if c != club.id]
        other = st.selectbox("Trade partner", others, format_func=lambda c: g.clubs[c].full_name)
        mine, theirs = st.columns(2)
        my_p = player_options(squad)
        their_p = player_options(sorted(g.squad(other), key=ovr, reverse=True))
        my_k = {f"{r['Pick']} (~#{r['Est. position']}, {r['Value']} pts)": r["Code"] for r in views.pick_rows(g, club.id)}
        their_k = {f"{r['Pick']} (~#{r['Est. position']}, {r['Value']} pts)": r["Code"] for r in views.pick_rows(g, other)}
        give = [f"#{my_p[x]}" for x in mine.multiselect("You give: players", list(my_p))]
        give += [my_k[x] for x in mine.multiselect("You give: picks", list(my_k))]
        get = [f"#{their_p[x]}" for x in theirs.multiselect("You get: players", list(their_p))]
        get += [their_k[x] for x in theirs.multiselect("You get: picks", list(their_k))]
        deal = f"{other} give {', '.join(give) or 'nothing'} for {', '.join(get) or 'nothing'}"
        a, b, _ = st.columns([1, 1, 4])
        if a.button("Check"):
            run("trade check " + deal)
            st.rerun()
        if b.button("Do the deal", type="primary", disabled=g.phase not in ("trades", "draft")):
            run("trade " + deal)
            st.rerun()
        st.caption(f"{g.clubs[other].name} list")
        df(views.squad_rows(g, other, "value"), height=320,
           column_order=["ID", "Name", "Pos", "Age", "OVR", "POT", "Wage", "Until", "Value", "Status"])
    with tabs[2]:
        slot = offseason.draft_on_clock(g)
        if g.phase == "draft" and slot:
            st.info(f"On the clock: pick {slot['n']} - {g.clubs[slot['owner']].name}")
        board = offseason.draft_board(g)
        df(views.prospect_rows(g, 60), height=420)
        if g.phase == "draft" and slot and slot["owner"] == club.id and board:
            opts = player_options(board)
            a, b = st.columns([3, 1])
            who = a.selectbox("Your selection", list(opts))
            if b.button("Draft him", type="primary"):
                run(f"draft pick #{opts[who]}")
                st.rerun()
        df(views.pick_rows(g, club.id))
        live = g.draft.get("live")
        if live and live["log"]:
            st.caption("Picks so far")
            df([{"Pick": n, "Club": cid, "Player": name, "Pos": pos, "Age": age}
                for n, cid, _, name, pos, age in live["log"]], height=300)
    with tabs[3]:
        rows = views.free_agent_rows(g)
        df(rows, height=360)
        if rows:
            opts = {f"{r['Name']} ({r['Pos']} {r['OVR']}, {r['Age']}) #{r['ID']}": r["ID"] for r in rows}
            a, b, c = st.columns([3, 1, 1])
            who = a.selectbox("Free agent", list(opts))
            years = b.number_input("Years", 1, 5, 1, key="fa_years")
            if c.button("Sign"):
                run(f"sign #{opts[who]} {years}")
                st.rerun()


def page_console(g):
    st.write("Every text command works here - type `help` for the list.")
    with st.form("console", clear_on_submit=True):
        cmd = st.text_input("Command", placeholder="e.g. squad form   |   player Smith   |   trade check GEE give 2027R1 for #123")
        if st.form_submit_button("Run") and cmd:
            run(cmd)
    flash()


PAGES = {"Home": page_home, "Squad": page_squad, "Team selection": page_selection,
         "Game plan & training": page_game_plan, "Match centre": page_match_centre,
         "Competition": page_competition, "Club": page_club,
         "List management": page_list_management, "Command console": page_console}


def main():
    g = get_game()
    if g is None:
        return screen_new_game()
    if not g.user or g.meta.get("sacked"):
        return screen_choose_club(g)
    refresh_auto_lineup(g)
    with st.sidebar:
        st.title("🏉 AFL Manager")
        st.write(f"**{g.user.full_name}**")
        st.caption(f"{g.year} · {phase_label(g)}" + (f" · coach {g.meta['manager']}" if g.meta.get("manager") else ""))
        page = st.radio("Go to", list(PAGES), label_visibility="collapsed")
        st.divider()
        st.caption(f"Save: {g.meta.get('save_name')} (auto-saved after every action)")
        if st.button("Reload from disk"):
            st.session_state.pop("game")
            st.rerun()
    st.header(page)
    PAGES[page](g)


main()
