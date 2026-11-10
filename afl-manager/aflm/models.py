"""Core data models: Player, Club and the Game container.

Design notes
------------
* Everything is plain data (dataclasses + dicts/lists) so the whole career
  serialises to JSON with no custom encoders.  See storage.py.
* Players are stored once in ``Game.players`` keyed by id; clubs, lineups,
  draft pools and free-agent lists refer to them by id.
* Matches are plain dicts (see season.py) because their shape differs
  between "fixture", "played with summary" and "played with full detail".
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict, fields
from typing import Optional

from . import constants as C


@dataclass
class Player:
    id: int
    first: str
    last: str
    age: int
    height: int
    club: Optional[str]              # club id, or None (prospect / free agent)
    positions: list                  # position types, primary first e.g. ["CHB", "FB"]
    attrs: dict                      # attribute -> float 1..20 (shown rounded)
    potential: float                 # hidden ceiling on the 0-100 overall scale
    scout_noise: float = 0.0         # error in how non-owners perceive potential
    dev_rate: float = 1.0            # hidden: how fast he develops (0.6 - 1.4)
    wage: int = 0                    # $k per season
    contract_end: int = 0            # last season covered by the current deal
    rookie: bool = False             # on the rookie list
    status: str = "listed"           # listed | prospect | free_agent
    fitness: float = 100.0           # 100 = fresh
    form: list = field(default_factory=list)       # last five match ratings
    reserves: float = 0.0            # last reserves (twos) rating, 0 = n/a
    injury: Optional[dict] = None    # {"type": "hamstring", "weeks": 3}
    stats: dict = field(default_factory=dict)      # {"2027": {gm, k, hb, ...}}
    career: dict = field(default_factory=lambda: {"games": 0, "goals": 0})
    drafted: str = ""                # e.g. "2027 pick 4 (COL)"

    @property
    def name(self) -> str:
        return f"{self.first} {self.last}"

    @property
    def short(self) -> str:
        return f"{self.first[0]}. {self.last}"

    @property
    def pos(self) -> str:
        return self.positions[0]

    def season(self, year: int) -> dict:
        """Season stat line (created on demand)."""
        key = str(year)
        if key not in self.stats:
            self.stats[key] = {"gm": 0, "k": 0, "hb": 0, "m": 0, "t": 0, "g": 0,
                               "b": 0, "ho": 0, "cl": 0, "i50": 0, "rt": 0.0, "v": 0}
        return self.stats[key]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["attrs"] = {k: round(v, 2) for k, v in self.attrs.items()}
        d["fitness"] = round(self.fitness, 1)
        d["potential"] = round(self.potential, 1)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Player":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class Club:
    id: str
    name: str
    nickname: str
    ground: str
    state: str
    colours: str
    supporters: float                 # members, thousands
    balance: int = 0                  # $k in the bank
    dev: float = 1.0                  # development program quality (0.85 - 1.15)
    recruit: float = 1.0              # recruiting / scouting quality (0.85 - 1.15)
    strategy: str = "balanced"        # list strategy: contend | balanced | rebuild
    philosophy: str = "Balanced"      # coaching philosophy name (AI flavour)
    tactics: dict = field(default_factory=lambda: dict(C.DEFAULT_TACTICS))
    training: dict = field(default_factory=lambda: {"focus": "balanced", "intensity": "normal"})
    lineup: dict = field(default_factory=dict)     # slot -> player id
    captain: Optional[int] = None
    board: dict = field(default_factory=lambda: {"target": 12, "label": "", "confidence": 60.0})
    ledger: dict = field(default_factory=dict)     # season-to-date income/expense totals, $k
    last_ledger: dict = field(default_factory=dict)  # most recent round only

    @property
    def full_name(self) -> str:
        return self.name if self.nickname in self.name else f"{self.name} {self.nickname}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Club":
        known = {f.name for f in fields(cls)}
        d = {k: v for k, v in d.items() if k in known}
        # JSON turns nothing here into non-str keys, but lineup values must be ints
        d["lineup"] = {s: int(p) for s, p in d.get("lineup", {}).items()}
        return cls(**d)


class Game:
    """The whole career.  One instance == one save."""

    def __init__(self):
        self.meta: dict = {}          # year, phase, round, user club, cap ...
        self.clubs: dict[str, Club] = {}
        self.players: dict[int, Player] = {}
        self.season: dict = {}        # fixtures + results for the current year
        self.draft: dict = {}         # picks, prospect pool, live draft state
        self.free_agents: list = []   # player ids
        self.history: list = []       # one summary dict per completed season
        self.news: list = []          # newest last: {"year", "when", "text", "tag"}

    # -- convenience accessors ------------------------------------------------
    @property
    def year(self) -> int:
        return self.meta["year"]

    @property
    def phase(self) -> str:
        """preseason-less flow: season -> finals -> review -> contracts -> trades -> draft -> season"""
        return self.meta["phase"]

    @property
    def user(self) -> Optional[Club]:
        cid = self.meta.get("user_club")
        return self.clubs[cid] if cid else None

    @property
    def cap(self) -> int:
        return self.meta["cap"]

    def squad(self, club_id: str) -> list:
        return [p for p in self.players.values() if p.club == club_id and p.status == "listed"]

    def payroll(self, club_id: str) -> int:
        return sum(p.wage for p in self.squad(club_id))

    def new_player_id(self) -> int:
        self.meta["next_pid"] += 1
        return self.meta["next_pid"]

    def add_news(self, text: str, tag: str = "league", when: str = "") -> None:
        self.news.append({"year": self.year, "when": when or self.when(), "text": text, "tag": tag})
        if len(self.news) > 400:
            del self.news[:-400]

    def when(self) -> str:
        ph = self.phase
        if ph == "season":
            return f"R{self.meta['round']}"
        return {"finals": "Finals", "review": "Season review", "contracts": "Contracts",
                "trades": "Trade period", "draft": "Draft"}.get(ph, ph)
