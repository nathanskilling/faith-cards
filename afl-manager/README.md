# AFL Manager

A management sim for Australian Rules football in the Football Manager tradition: pick
one of the 18 clubs, run the list, the game plan and match day, and try to build a
premiership side over many seasons.

Unofficial fan project. Club names are used for flavour only; **every player is fictional**
and randomly generated, and each new world deals out the talent differently.

Lives in its own folder (`afl-manager/`) and shares nothing with the rest of this repo.

## The app

`index.html` is a browser app: no server, no account, nothing to install. It works on a
phone or a desktop and can be added to the home screen.

- **Hosted:** it is a static site, so GitHub Pages (or any static host) serves it as is.
  With Pages enabled for this repo it lives at `<your pages url>/afl-manager/`.
- **Locally:** it must be served, not opened as a file:

  ```bash
  cd afl-manager
  python -m http.server 8600      # then open http://localhost:8600
  ```

The first launch downloads the Python runtime the engine runs on (Pyodide, roughly 6 MB,
cached afterwards), so it needs an internet connection once. Careers are saved in the
browser's own storage; **Settings → Download save file** makes a backup you can load on
another device.

What you get:

| Screen | What it is for |
|---|---|
| Home | Next match, assistant coach's notes, last result, ladder, squad pulse, inbox, board and cap at a glance |
| Squad | Sortable list in four views (overview, all 15 attributes, season stats, contracts), any club |
| Player | Attributes, best roles, contract, season history; offer a deal, make captain, delist |
| Team sheet | The 23 on an oval. Tap a spot then a player, or two spots to swap. Assistant or manual selection |
| Game plan | Style, ball movement, pressure, forward structure, defensive system, presets, training week |
| Match centre | Scouting report on the next opponent; live replay with scoreboard, score worm and play-by-play; full report |
| Fixtures, Ladder, Stats, Clubs | The competition |
| Contracts, Trades, Draft, Free agents | List management. Trades are valued live as you tick players and picks |
| Board & finances | Confidence, expectations, ledger, honour roll |

The **Continue** button (top right) always moves the game on: play the round, play a
final, open contract talks, end the signing period, go to the draft, start the next
season. The arrow beside it plays several rounds at once.

## Text commands

The same engine has a command-line front end, handy for scripting or playing in a chat:

```bash
python play.py new                 # create a world, prints the 18 clubs ranked by list strength
python play.py choose GEE Your Name
python play.py                     # interactive session, or one-shot commands:
python play.py squad
python play.py sim
python play.py help                # everything else
```

`python play.py export career.json` writes a file the app can load, and
`python play.py import career.json` brings an app save back.

(`app.py` is the earlier Streamlit interface. It still works - `pip install -r requirements.txt`
then `streamlit run app.py` - but the browser app replaces it.)

## What is simulated

- **18 clubs, 42-man lists** (senior + rookie), ~760 players with 15 attributes on a 1–20
  scale, a primary and often a secondary position, hidden potential and development rate.
- **13 position types** on a traditional team sheet (B / HB / C / HF / F / followers + 5 on
  the bench). Anyone can play anywhere; ratings fall away the further out of position.
- **Match engine**: ~105 passages a game, each resolved from the players involved –
  ruck contest → clearance → inside 50 → marking contest / crumb / long shot → set shot.
  Game style, tempo, pressure, forward structure and defensive system all change the odds;
  so do fitness, form, consistency, leadership, wet weather, home ground and interstate
  travel. Output: a scoring timeline, quarter-by-quarter scores, team and player stats,
  1–10 ratings, 3-2-1 votes and highlights.
- **Season**: 23 rounds (everyone once, nine rivalries plus others twice), ladder on points
  then percentage, the AFL final eight with double chances, Grand Final at the MCG
  (extra time if scores are level in a final).
- **List management**: contracts and wage demands, salary cap and 95% floor, delistings,
  free agents, pick-and-player trades judged by AI clubs with their own list strategies,
  a four-round national draft of ~84 prospects seen through imperfect scouting.
- **Players change**: weekly training (focus + intensity), growth towards potential,
  pre-season breakouts and busts, decline from 29, retirements, fatigue and injuries.
- **Club**: round-by-round finances, board expectations and confidence, the sack.
- **Assistant coach**: weekly notes on tired legs, players banging the door down,
  contract deadlines and how to attack the next opponent's structure.
- **Awards**: Brownlow, Coleman, Rising Star, club best and fairest, honour roll.

## How the code is organised

```
index.html           the app
web/
  app.css            styles (dark and light; the accent follows your club)
  js/engine.js       loads the engine in the browser, autosaves to IndexedDB
  js/ui.js           tables, badges, meters, dialogs
  js/screens.js      every screen except the match centre
  js/match.js        match preview, live replay and report
  js/main.js         start-up, club selection, navigation, the Continue button, settings
  engine.json        the aflm package, bundled for the browser (generated)
tools/build_web.py   regenerates web/engine.json
play.py              command-line front end
aflm/
  constants.py       rules of the world: clubs, venues, positions, tactics, cap, injuries
  models.py          Player, Club and the Game container (plain data)
  storage.py         save/load: a folder of JSON files, or one bundle for the app
  generator.py       world, list and draft-class generation
  ratings.py         role ratings, overall, team selection
  match_engine.py    the match simulation (pure function, no side effects)
  season.py          fixture, ladder, playing rounds, finals, awards
  development.py     match wear, training, injuries, ageing, retirement
  finance.py         ledger, gate receipts, board expectations
  offseason.py       contracts, trades, valuations, draft, new-year rollover
  assistant.py       the assistant coach's advice
  views.py           table rows shared by the front ends
  commands.py        the text commands (and the rules every front end goes through)
  webapi.py          the JSON interface the app talks to
tests/
  test_smoke.py      end-to-end: three full seasons through every off-season phase
  test_webapi.py     the app's API through a full year; checks the bundle is current
  calibrate.py       engine realism report (scores, margins, stat leaders ...)
  tactics_lab.py     checks that no tactic is a free lunch
  longrun.py         ten-season league health check (talent, payroll, parity)
```

Design choices worth knowing:

- **One engine, in Python, everywhere.** The app runs the `aflm` package unchanged in the
  browser through Pyodide, so the command line, the tests and the app can never disagree
  about the rules. The app only talks to it through `webapi.handle(json) -> json`, which
  keeps the door open to moving the engine to a server or rewriting it later.
- **Engine is pure.** `simulate_match` reads two selected sides and returns a result;
  `season.py` applies it. That makes it easy to test, tune or replace.
- **No build step for the UI.** Plain ES modules and CSS. The only generated file is
  `web/engine.json`: **run `python tools/build_web.py` after changing anything in `aflm/`**
  (a test fails if you forget).
- **Saves are JSON**: a readable folder on disk, one file in the app.
- **Attributes beyond the brief.** Tackling, Goal Sense and Defensive Craft were added to
  the requested twelve so that forwards, defenders and midfielders are different players.
- **Calibrated against real footy**: ~85 points a side, ~35-point average margin, Coleman
  medallists on 60–100 goals, ball magnets on 30–35 touches, ~37 clearances a team.

Run the checks:

```bash
python tests/test_smoke.py && python tests/test_webapi.py     # or: python -m pytest tests -q
python tests/calibrate.py 4
```

## Simplifications (for now)

- No byes, pre-season games, reserves competition (a reserves rating is simulated),
  suspensions, taggers, father-son/academy bidding, or mid-season draft.
- Trades are player/pick swaps judged on value; players have no say in where they go.
- Draft uses a simple pick-value curve rather than the full Draft Value Index and bidding.
- Finances are a ledger; there is nothing to spend the surplus on yet.
- Interchange players contribute to bulk stats and depth, not to individual contests.
- The live match view replays a result that is already decided; you cannot change
  tactics mid-game yet.
- The app needs a connection on first launch and has no offline mode.
