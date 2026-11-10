# AFL Manager

A Football Manager-style career sim for Australian Rules football: pick one of the 18
clubs, run the list, the game plan and match day, and try to build a premiership side
over many seasons.

Unofficial fan project. Club names are used for flavour only; **every player is fictional**
and randomly generated, and each new world deals out the talent differently.

Lives in its own folder (`afl-manager/`) and shares nothing with the rest of this repo.

## Play

The engine and text interface need only Python 3.10+ (no packages).

```bash
cd afl-manager
python play.py new                 # create a world, prints the 18 clubs ranked by list strength
python play.py choose GEE Your Name
python play.py                     # interactive session ("afl>" prompt), or one-shot commands:
python play.py squad
python play.py sim
```

Web interface (same engine, same save):

```bash
pip install -r requirements.txt
streamlit run app.py
```

The career is written to `saves/<name>/` after every command, so you can stop any time.
`python play.py saves` lists careers; `--save NAME` picks one.

### A week in the job

| Step | Commands |
|---|---|
| See where you stand | `status`, `ladder`, `news`, `board` |
| Scout the opposition | `preview` (their form, lines, game plan, likely side) |
| Pick the side | `lineup`, `pick auto`, `pick CHF Smith`, `swap Smith, Jones`, `selection auto\|manual` |
| Set the game plan | `tactics style=contested pressure=high`, `tactics preset Run and Gun` |
| Set the training week | `training skills heavy`, `training recovery` |
| Play | `sim` (one round), `sim 5`, then `match` for the full report |
| Dig into numbers | `squad form`, `player Smith`, `stats goals`, `stats disposals`, `fixture` |

Selection starts on **auto**: your assistant coach names the best fit 23 each week.
The moment you `pick` or `swap`, selection becomes **manual** and the side stays as you
set it (injured players are replaced, nobody is recalled or rested for you).

### The off-season

`advance` (same as `sim`) steps through: Grand Final → season review → **contracts**
(`contracts`, `offer Smith 3`, `offer all`, `delist`, `promote`) → **trade period**
(`trade check GEE give 2027R1, Smith for Jones`, `trade ...`, `freeagents`, `sign`) →
**national draft** (`draft`, `draft pick <player>`, `draft auto`) → new season.

`help` prints the full command list. Plain English works for the common ones
("show squad", "simulate next match", "set team", "run draft").

## What is simulated

- **18 clubs, 42-man lists** (senior + rookie), ~760 players with 15 attributes on a 1–20
  scale, a primary and often a secondary position, hidden potential and development rate.
- **13 position types** on a traditional team sheet (B / HB / C / HF / F / followers + 5 on
  the bench). Anyone can play anywhere; ratings fall away the further out of position.
- **Match engine**: ~105 passages a game, each resolved from the players involved –
  ruck contest → clearance → inside 50 → marking contest / crumb / long shot → set shot.
  Game style, tempo, pressure, forward structure and defensive system all change the odds;
  so do fitness, form, consistency, leadership, wet weather, home ground and interstate
  travel. Output: quarter-by-quarter scores, team and player stats, 1–10 ratings,
  3-2-1 votes and a highlights reel.
- **Season**: 23 rounds (everyone once, nine rivalries plus others twice), ladder on points
  then percentage, the AFL final eight with double chances, Grand Final at the MCG
  (extra time if scores are level in a final).
- **List management**: contracts and wage demands, salary cap and 95% floor, delistings,
  free agents, pick-and-player trades judged by AI clubs with their own list strategies,
  a four-round national draft of ~84 prospects seen through imperfect scouting.
- **Players change**: weekly training (focus + intensity), growth towards potential,
  pre-season breakouts and busts, decline from 29, retirements, fatigue and injuries.
- **Club**: round-by-round finances, board expectations and confidence, the sack.
- **Awards**: Brownlow, Coleman, Rising Star, club best and fairest, honour roll.

## How the code is organised

```
play.py              command-line front end (one-shot commands or a REPL)
app.py               Streamlit front end
aflm/
  constants.py       rules of the world: clubs, venues, positions, tactics, cap, injuries
  models.py          Player, Club and the Game container (plain data)
  storage.py         save/load a career as a folder of JSON files
  generator.py       world, list and draft-class generation
  ratings.py         role ratings, overall, team selection
  match_engine.py    the match simulation (pure function, no side effects)
  season.py          fixture, ladder, playing rounds, finals, awards
  development.py     match wear, training, injuries, ageing, retirement
  finance.py         ledger, gate receipts, board expectations
  offseason.py       contracts, trades, valuations, draft, new-year rollover
  views.py           table rows shared by both front ends
  commands.py        the text commands
tests/
  test_smoke.py      end-to-end: three full seasons through every off-season phase
  calibrate.py       engine realism report (scores, margins, stat leaders ...)
  tactics_lab.py     checks that no tactic is a free lunch
  longrun.py         ten-season league health check (talent, payroll, parity)
```

Design choices worth knowing:

- **Engine is pure.** `simulate_match` reads two selected sides and returns a result;
  `season.py` applies it. That makes it easy to test, tune or replace.
- **One rules layer, two front ends.** The Streamlit app calls the same `execute()` the
  CLI does, so both always behave identically.
- **Saves are JSON folders** (`meta`, `clubs`, `players`, `season`, `draft`, `history`):
  readable, hand-editable and diff-friendly.
- **Attributes beyond the brief.** Tackling, Goal Sense and Defensive Craft were added to
  the requested twelve so that forwards, defenders and midfielders are different players.
- **Calibrated against real footy**: ~85 points a side, ~35-point average margin, Coleman
  medallists on 60–90 goals, ball magnets on 30–35 touches, ~37 clearances a team.

Run the checks:

```bash
python tests/test_smoke.py        # or: python -m pytest tests -q
python tests/calibrate.py 4
```

## Simplifications (for now)

- No byes, pre-season games, reserves competition (a reserves rating is simulated),
  suspensions, father-son/academy bidding, or mid-season draft.
- Trades are player/pick swaps judged on value; players have no say in where they go.
- Draft uses a simple pick-value curve rather than the full Draft Value Index and bidding.
- Finances are a ledger; there is nothing to spend the surplus on yet.
- Interchange players contribute to bulk stats and depth, not to individual contests.
