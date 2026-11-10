"""Static game data: clubs, venues, attributes, positions and league rules.

Everything that is "rules of the world" rather than "state of a career" lives
here so it is easy to tune without touching simulation code.
"""

SAVE_VERSION = 1
START_YEAR = 2027

# --------------------------------------------------------------------------
# League rules
# --------------------------------------------------------------------------
SALARY_CAP = 18_500          # Total Player Payments, in $k
CAP_FLOOR_PCT = 0.95         # clubs must spend at least 95% of the cap
CAP_GROWTH = 1.03            # yearly cap / wage inflation
SENIOR_MAX = 38              # senior list spots
ROOKIE_MAX = 6               # rookie list spots
LIST_MAX = SENIOR_MAX + ROOKIE_MAX
LIST_MIN = 38                # minimum total list going into a season
ROOKIE_WAGE = 115            # $k, flat rookie-list wage
MIN_WAGE = 130               # $k, minimum senior wage
HA_ROUNDS = 23               # home-and-away rounds (every club plays 23 games)
DRAFT_ROUNDS = 4
DRAFT_POOL_SIZE = 84

# --------------------------------------------------------------------------
# Clubs.  supporters = membership base in thousands (drives gates/finances).
# --------------------------------------------------------------------------
CLUBS = [
    # id,   name,               nickname,   home ground,            state, colours,                     supporters
    ("ADE", "Adelaide",          "Crows",    "Adelaide Oval",        "SA",  "navy, red and gold",          68),
    ("BRI", "Brisbane",          "Lions",    "Gabba",                "QLD", "maroon, blue and gold",       58),
    ("CAR", "Carlton",           "Blues",    "MCG",                  "VIC", "navy blue",                   96),
    ("COL", "Collingwood",       "Magpies",  "MCG",                  "VIC", "black and white",            108),
    ("ESS", "Essendon",          "Bombers",  "Marvel Stadium",       "VIC", "red and black",               86),
    ("FRE", "Fremantle",         "Dockers",  "Optus Stadium",        "WA",  "purple and white",            62),
    ("GEE", "Geelong",           "Cats",     "GMHBA Stadium",        "VIC", "navy and white hoops",        88),
    ("GCS", "Gold Coast",        "Suns",     "People First Stadium", "QLD", "red and gold",                26),
    ("GWS", "GWS",               "Giants",   "ENGIE Stadium",        "NSW", "orange and charcoal",         34),
    ("HAW", "Hawthorn",          "Hawks",    "MCG",                  "VIC", "brown and gold",              82),
    ("MEL", "Melbourne",         "Demons",   "MCG",                  "VIC", "red and blue",                66),
    ("NTH", "North Melbourne",   "Kangaroos","Marvel Stadium",       "VIC", "royal blue and white",        50),
    ("PTA", "Port Adelaide",     "Power",    "Adelaide Oval",        "SA",  "black, white and teal",       64),
    ("RIC", "Richmond",          "Tigers",   "MCG",                  "VIC", "yellow and black",            98),
    ("STK", "St Kilda",          "Saints",   "Marvel Stadium",       "VIC", "red, white and black",        60),
    ("SYD", "Sydney",            "Swans",    "SCG",                  "NSW", "red and white",               72),
    ("WCE", "West Coast",        "Eagles",   "Optus Stadium",        "WA",  "royal blue and gold",        102),
    ("WBD", "Western Bulldogs",  "Bulldogs", "Marvel Stadium",       "VIC", "red, white and blue",         58),
]

# Club colours for badges and theming: (main, second, accent that reads on a dark page)
CLUB_COLOURS = {
    "ADE": ("#0b2a5b", "#e21937", "#ffd200"), "BRI": ("#7c003e", "#0054a4", "#fdbe57"),
    "CAR": ("#0e1e2d", "#ffffff", "#8fb4d9"), "COL": ("#111111", "#ffffff", "#e8e8e8"),
    "ESS": ("#111111", "#cc2031", "#ff4d5e"), "FRE": ("#2a0d54", "#ffffff", "#b79cf0"),
    "GEE": ("#12305a", "#ffffff", "#8db8ee"), "GCS": ("#d93e39", "#f6bd00", "#f6bd00"),
    "GWS": ("#414042", "#f47920", "#f47920"), "HAW": ("#4d2004", "#fbbf15", "#fbbf15"),
    "MEL": ("#0f1131", "#cc2031", "#ff5468"), "NTH": ("#013b9f", "#ffffff", "#7fb0ff"),
    "PTA": ("#111111", "#008aab", "#29c2e0"), "RIC": ("#111111", "#ffd200", "#ffd200"),
    "STK": ("#111111", "#ed0f05", "#ff5a4f"), "SYD": ("#ed171f", "#ffffff", "#ff6b70"),
    "WCE": ("#002b79", "#f2a900", "#f2a900"), "WBD": ("#014896", "#e21937", "#7fb0ff"),
}

# Traditional rivalries: these nine pairs always meet twice a season.
RIVALRIES = [
    ("ADE", "PTA"),   # Showdown
    ("WCE", "FRE"),   # Western Derby
    ("BRI", "GCS"),   # QClash
    ("SYD", "GWS"),   # Sydney Derby
    ("COL", "CAR"),
    ("ESS", "RIC"),   # Dreamtime
    ("GEE", "HAW"),
    ("MEL", "NTH"),
    ("STK", "WBD"),
]

# venue -> (state, capacity, has roof, chance of a wet day)
VENUES = {
    "MCG":                  ("VIC", 100_000, False, 0.24),
    "Marvel Stadium":       ("VIC",  53_000, True,  0.00),
    "GMHBA Stadium":        ("VIC",  40_000, False, 0.26),
    "Adelaide Oval":        ("SA",   53_500, False, 0.18),
    "Optus Stadium":        ("WA",   60_000, False, 0.16),
    "Gabba":                ("QLD",  37_000, False, 0.14),
    "People First Stadium": ("QLD",  25_000, False, 0.16),
    "SCG":                  ("NSW",  48_000, False, 0.22),
    "ENGIE Stadium":        ("NSW",  24_000, False, 0.20),
}
GRAND_FINAL_VENUE = "MCG"

# --------------------------------------------------------------------------
# Player attributes (1-20).  The first twelve are the classic set; tackling,
# goal sense and defensive craft were added so that forwards, defenders and
# midfielders are genuinely different players in the match engine.
# --------------------------------------------------------------------------
ATTRS = [
    "kicking", "marking", "handballing", "speed", "endurance", "strength",
    "toughness", "decision", "ruck", "tackling", "goal_sense", "intercept",
    "leadership", "consistency", "injury_prone",
]
# Attributes that develop with training / decline with age.
SKILL_ATTRS = ATTRS[:12]
ATTR_LABEL = {
    "kicking": "Kicking", "marking": "Marking", "handballing": "Handballing",
    "speed": "Speed", "endurance": "Endurance", "strength": "Strength",
    "toughness": "Toughness", "decision": "Decision Making", "ruck": "Ruck Work",
    "tackling": "Tackling", "goal_sense": "Goal Sense", "intercept": "Defensive Craft",
    "leadership": "Leadership", "consistency": "Consistency",
    "injury_prone": "Injury Proneness",
}
ATTR_SHORT = {
    "kicking": "KIC", "marking": "MAR", "handballing": "HBL", "speed": "SPD",
    "endurance": "END", "strength": "STR", "toughness": "TGH", "decision": "DEC",
    "ruck": "RUC", "tackling": "TCK", "goal_sense": "GLS", "intercept": "DEF",
    "leadership": "LDR", "consistency": "CON", "injury_prone": "INJ",
}

# --------------------------------------------------------------------------
# Positions.  Thirteen position types; each has an attribute weighting that
# sums to 1.0 and defines "how good is this player in that role".
# --------------------------------------------------------------------------
POS_WEIGHTS = {
    "FB":   {"intercept": .28, "strength": .22, "marking": .18, "decision": .10, "kicking": .08, "toughness": .08, "speed": .06},
    "BP":   {"intercept": .26, "speed": .20, "tackling": .16, "kicking": .12, "decision": .12, "toughness": .08, "handballing": .06},
    "CHB":  {"intercept": .26, "marking": .22, "strength": .14, "kicking": .14, "decision": .12, "endurance": .06, "speed": .06},
    "HBF":  {"kicking": .24, "speed": .16, "decision": .16, "intercept": .16, "endurance": .12, "handballing": .08, "marking": .08},
    "W":    {"endurance": .24, "kicking": .22, "speed": .20, "decision": .12, "handballing": .12, "marking": .10},
    "C":    {"handballing": .18, "decision": .18, "kicking": .16, "endurance": .14, "toughness": .12, "tackling": .10, "speed": .06, "strength": .06},
    "RR":   {"toughness": .18, "handballing": .18, "strength": .14, "tackling": .14, "endurance": .12, "decision": .12, "kicking": .12},
    "ROV":  {"handballing": .18, "speed": .16, "decision": .16, "kicking": .14, "goal_sense": .12, "tackling": .10, "endurance": .08, "toughness": .06},
    "RUCK": {"ruck": .40, "strength": .16, "marking": .14, "endurance": .12, "handballing": .06, "toughness": .06, "kicking": .06},
    "HFF":  {"kicking": .20, "goal_sense": .20, "speed": .16, "marking": .14, "decision": .12, "endurance": .10, "tackling": .08},
    "CHF":  {"marking": .28, "goal_sense": .18, "strength": .16, "kicking": .16, "endurance": .12, "speed": .05, "decision": .05},
    "FP":   {"goal_sense": .28, "speed": .20, "tackling": .16, "kicking": .14, "marking": .08, "decision": .08, "handballing": .06},
    "FF":   {"marking": .28, "goal_sense": .28, "strength": .20, "kicking": .14, "speed": .06, "decision": .04},
}
POS_TYPES = list(POS_WEIGHTS)
POS_NAME = {
    "FB": "Full-back", "BP": "Back pocket", "CHB": "Centre half-back",
    "HBF": "Half-back flank", "W": "Wing", "C": "Centre", "RR": "Ruck-rover",
    "ROV": "Rover", "RUCK": "Ruck", "HFF": "Half-forward flank",
    "CHF": "Centre half-forward", "FP": "Forward pocket", "FF": "Full-forward",
}
# Position families, used for "how comfortable is he out of position".
POS_GROUP = {
    "FB": "KD", "CHB": "KD", "BP": "GD", "HBF": "GD", "W": "WG",
    "C": "MD", "RR": "MD", "ROV": "MD", "RUCK": "RK",
    "HFF": "GF", "FP": "GF", "CHF": "KF", "FF": "KF",
}
GROUP_NAME = {"KD": "Key Def", "GD": "Gen Def", "WG": "Wing", "MD": "Midfield",
              "RK": "Ruck", "GF": "Gen Fwd", "KF": "Key Fwd"}
# Pairs of families that translate reasonably well to each other.
RELATED_GROUPS = {
    frozenset(p) for p in [
        ("GD", "WG"), ("MD", "WG"), ("MD", "GF"), ("GD", "MD"), ("KD", "KF"),
        ("RK", "KF"), ("RK", "KD"), ("GD", "KD"), ("GF", "KF"), ("GF", "WG"),
    ]
}
# Which third of the ground a position type plays in.
LINE_OF = {"FB": "D", "BP": "D", "CHB": "D", "HBF": "D", "W": "M", "C": "M",
           "RR": "M", "ROV": "M", "RUCK": "M", "HFF": "F", "CHF": "F",
           "FP": "F", "FF": "F"}

# The team sheet: 18 on-field slots + 5 interchange.  slot -> position type.
FIELD_SLOTS = {
    "BPL": "BP", "FB": "FB", "BPR": "BP",
    "HBL": "HBF", "CHB": "CHB", "HBR": "HBF",
    "WL": "W", "C": "C", "WR": "W",
    "HFL": "HFF", "CHF": "CHF", "HFR": "HFF",
    "FPL": "FP", "FF": "FF", "FPR": "FP",
    "RUCK": "RUCK", "RR": "RR", "ROV": "ROV",
}
BENCH_SLOTS = ["IC1", "IC2", "IC3", "IC4", "IC5"]
ALL_SLOTS = list(FIELD_SLOTS) + BENCH_SLOTS
# Layout used when printing a team sheet, back line to forward line.
TEAM_SHEET_ROWS = [
    ("B", ["BPL", "FB", "BPR"]),
    ("HB", ["HBL", "CHB", "HBR"]),
    ("C", ["WL", "C", "WR"]),
    ("HF", ["HFL", "CHF", "HFR"]),
    ("F", ["FPL", "FF", "FPR"]),
    ("Foll", ["RUCK", "RR", "ROV"]),
    ("I/C", BENCH_SLOTS),
]
# Who a forward normally lines up on (used by man-on-man defences).
MATCHUP = {"FF": "FB", "CHF": "CHB", "FPL": "BPR", "FPR": "BPL",
           "HFL": "HBR", "HFR": "HBL"}

# --------------------------------------------------------------------------
# Tactics.  option -> one-line description (shown in the UI).
# --------------------------------------------------------------------------
TACTIC_OPTIONS = {
    "style": {
        "contested": "Win the hard ball: stoppage and clearance focus, scrappy entries.",
        "balanced": "Mix of inside and outside ball.",
        "outside": "Spread and run: uncontested chains and precise entries. Needs skill.",
    },
    "tempo": {
        "slow": "Chip and hold possession. Safe, low scoring, hard to rebound against.",
        "balanced": "Take the game on when it is on.",
        "fast": "Corridor, play on at all costs. Higher scoring both ways and more tiring.",
    },
    "pressure": {
        "low": "Sit off and save the legs.",
        "medium": "Honest pressure around the ball.",
        "high": "Manic pressure. Forces turnovers but drains fitness and fades late.",
    },
    "forward": {
        "tall": "Three talls: bomb it to marking targets.",
        "balanced": "Two talls and a mix of mediums and smalls.",
        "small": "Small-ball: crumbers and ground-level pressure. Great in the wet.",
    },
    "defence": {
        "man": "Man on man: your defenders' one-on-one quality decides it.",
        "zone": "Zone off and intercept. Shuts down poor kicking sides, elite users slice it.",
        "loose": "Plus-one behind the ball. Hard to score against, costs you a forward.",
    },
}
DEFAULT_TACTICS = {"style": "balanced", "tempo": "balanced", "pressure": "medium",
                   "forward": "balanced", "defence": "man"}

# AI coaching philosophies: name -> tactics
PHILOSOPHIES = {
    "Contested Beasts":   {"style": "contested", "tempo": "balanced", "pressure": "high",   "forward": "tall",     "defence": "man"},
    "Run and Gun":        {"style": "outside",   "tempo": "fast",     "pressure": "medium", "forward": "small",    "defence": "zone"},
    "Possession Chip":    {"style": "outside",   "tempo": "slow",     "pressure": "medium", "forward": "balanced", "defence": "zone"},
    "Defensive Lockdown": {"style": "balanced",  "tempo": "slow",     "pressure": "high",   "forward": "balanced", "defence": "loose"},
    "Forward Press":      {"style": "contested", "tempo": "fast",     "pressure": "high",   "forward": "small",    "defence": "man"},
    "Tall Timber":        {"style": "balanced",  "tempo": "balanced", "pressure": "medium", "forward": "tall",     "defence": "man"},
    "Balanced":           dict(DEFAULT_TACTICS),
}

# --------------------------------------------------------------------------
# Training
# --------------------------------------------------------------------------
TRAINING_FOCUS = {
    "balanced":  ("Even spread across every attribute.", {}),
    "skills":    ("Kicking, handball and marking drills.", {"kicking": 2.2, "handballing": 2.2, "marking": 2.0, "goal_sense": 1.4}),
    "fitness":   ("Running power and speed work.", {"endurance": 2.6, "speed": 2.0}),
    "contested": ("Stoppage craft, tackling and bodywork.", {"strength": 2.2, "toughness": 2.2, "tackling": 2.2, "ruck": 1.6}),
    "tactical":  ("Game sense, structures and defensive craft.", {"decision": 2.6, "intercept": 2.2}),
    "recovery":  ("Light week: freshen up, no development.", {}),
}
# intensity -> (development multiplier, weekly fitness recovery, training injury risk multiplier)
TRAINING_INTENSITY = {
    "light":  (0.6, 17.0, 0.5),
    "normal": (1.0, 13.0, 1.0),
    "heavy":  (1.35, 8.5, 1.8),
}

# --------------------------------------------------------------------------
# Injuries: (name, min weeks, max weeks, relative frequency)
# --------------------------------------------------------------------------
INJURIES = [
    ("corked thigh", 1, 1, 12), ("concussion", 1, 2, 9), ("ankle", 1, 4, 11),
    ("hamstring", 2, 5, 14), ("calf", 2, 4, 9), ("quad", 2, 4, 6),
    ("groin", 2, 5, 6), ("shoulder", 2, 8, 7), ("knee", 2, 7, 8),
    ("back", 1, 4, 5), ("broken hand", 3, 5, 4), ("syndesmosis", 4, 8, 4),
    ("foot stress fracture", 6, 12, 3), ("ACL", 40, 48, 2),
]

# Board expectation tiers: (worst acceptable ladder position, label)
BOARD_TIERS = [
    (4, "Finish top four and contend for the flag"),
    (8, "Play finals"),
    (12, "Push for finals - finish top 12"),
    (16, "Develop the list and stay out of the bottom two"),
]
