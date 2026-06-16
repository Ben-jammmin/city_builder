"""
settings.py — Central configuration file for the entire game.

Every tunable number lives here. Adjust values in this one file to re-balance
the simulation without touching game logic. Constants are grouped by topic:
window/map sizes, economy, zone density, buildings, simulation math, disasters,
milestones, colours.
"""

# ── Window & display ───────────────────────────────────────────────────────────
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 800
COMMAND_BAR_HEIGHT = 296       # height of the bottom sidebar when expanded
MINIMIZED_COMMAND_BAR_HEIGHT = 44   # height when the sidebar is hidden
FPS = 60

# ── Map dimensions ─────────────────────────────────────────────────────────────
MAP_WIDTH = 64    # default map width in tiles
MAP_HEIGHT = 48   # default map height in tiles
TILE_SIZE = 32    # base tile size used for coordinate conversions

# ── Economy ────────────────────────────────────────────────────────────────────
STARTING_MONEY = 50000
STARTING_YEAR = 1
STARTING_MONTH = 1
STARTING_TAX_RATE = 9        # percent; affects revenue and demand
# Real-time seconds that pass for every simulated month at "Normal" speed
SIM_SECONDS_PER_MONTH = 1.25
# Each tuple is (display label, seconds_per_month) for the speed selector
SIM_SPEED_PRESETS: list[tuple[str, float]] = [
    ("Slow",   2.5),
    ("Normal", 1.25),
    ("Fast",   0.4),
    ("Max",    0.15),
]

MIN_TAX_RATE = 1
MAX_TAX_RATE = 20

# ── Zone placement costs ───────────────────────────────────────────────────────
# Cost charged once when the player paints a zone tile.
ZONE_COST = {
    "residential": 25,
    "commercial": 35,
    "industrial": 30,
    "park": 150,
}

# Each park neighbor raises adjacent land values by this fraction.
PARK_LAND_VALUE_BONUS = 0.07

# ── Recreation buildings ───────────────────────────────────────────────────────
# One-time construction cost for each recreation type.
RECREATION_COST = {
    "park": 150,
    "playground": 80,
    "sports_field": 250,
    "stadium": 3000,
    "golf_course": 1500,
    "pool": 400,
    "cinema": 600,
    "museum": 1000,
    "zoo": 2000,
}

# Monthly upkeep deducted from city funds each simulation tick.
RECREATION_MAINTENANCE = {
    "park": 3,
    "playground": 2,
    "sports_field": 5,
    "stadium": 80,
    "golf_course": 40,
    "pool": 12,
    "cinema": 20,
    "museum": 25,
    "zoo": 50,
}

# How much each recreation tile boosts nearby land value (multiplied by presence).
RECREATION_LAND_VALUE = {
    "park": 0.07,
    "playground": 0.05,
    "sports_field": 0.06,
    "stadium": 0.10,
    "golf_course": 0.14,
    "pool": 0.07,
    "cinema": 0.08,
    "museum": 0.09,
    "zoo": 0.11,
}

# Residential demand bonus per recreation tile
RECREATION_DEMAND_RES = {
    "park": 0.5,
    "playground": 0.9,
    "sports_field": 0.6,
    "stadium": 0.4,
    "golf_course": 0.7,
    "pool": 0.6,
    "cinema": 0.3,
    "museum": 0.4,
    "zoo": 0.8,
}

# Commercial demand bonus per recreation tile
RECREATION_DEMAND_COM = {
    "park": 0.0,
    "playground": 0.0,
    "sports_field": 0.3,
    "stadium": 2.5,   # stadiums draw big commercial crowds
    "golf_course": 0.5,
    "pool": 0.3,
    "cinema": 2.0,
    "museum": 0.8,
    "zoo": 1.5,
}

# ── Zone density levels ────────────────────────────────────────────────────────
# Zone density levels (level 1 = standard, level 2 = dense)
ZONE_LEVEL_COST_MULTIPLIERS = {
    1: 1.0,
    2: 3.0,    # dense zones cost 3× as much to place
    3: 9.0,    # highrise zones cost 9× as much to place
}
ZONE_LEVEL_CAPACITY_MULTIPLIERS = {
    1: 1.0,
    2: 2.35,   # dense zones hold 2.35× more residents/jobs
    3: 4.8,    # highrise zones hold 4.8× more
}
ZONE_LEVEL_GROWTH_MULTIPLIERS = {
    1: 1.0,
    2: 0.85,   # dense zones grow slower but hold more people
    3: 0.55,   # highrise zones grow very slowly
}
ZONE_LEVEL_LABELS = {
    1: "Standard",
    2: "Dense",
    3: "Highrise",
}

# Highrise zones require this land value to be upgradeable and to grow.
HIGHRISE_MIN_LAND_VALUE  = 1.05
# Highrise zones also require this minimum development on the existing dense tile.
HIGHRISE_MIN_DEVELOPMENT = 0.45

# ── Infrastructure costs ───────────────────────────────────────────────────────
ROAD_COST = 60
BULLDOZE_COST = 8
POWER_LINE_COST = 20
WATER_PIPE_COST = 20

# Terrain demolition costs
TERRAIN_CLEAR_COSTS = {
    "water": 50,    # draining water is expensive
    "forest": 15,
    "hill": 25,
}

# One-time construction cost for civic buildings.
BUILDING_COST = {
    "power_plant": 2500,
    "large_power_plant": 6500,
    "water_tower": 1200,
    "large_water_tower": 3200,
    "police": 900,
    "fire": 900,
    "school": 1100,
    "hospital": 1600,
    "train_station": 3000,
    "airport": 5000,
}

# ── Monthly maintenance costs ──────────────────────────────────────────────────
# Deducted each simulated month to represent operating costs.
ROAD_MAINTENANCE = 2           # per road tile
ZONE_MAINTENANCE = 0.2         # per zone-level unit (dense zones count as 2)
POWER_LINE_MAINTENANCE = 1     # per power line tile
WATER_PIPE_MAINTENANCE = 1     # per water pipe tile

BUILDING_MAINTENANCE = {
    "power_plant": 45,
    "large_power_plant": 115,
    "water_tower": 25,
    "large_water_tower": 70,
    "police": 35,
    "fire": 35,
    "school": 40,
    "hospital": 60,
    "train_station": 50,
    "airport": 80,
}

# ── Utility capacities ─────────────────────────────────────────────────────────
# How many power/water units each building type provides.
POWER_PLANT_CAPACITY = 220
WATER_TOWER_CAPACITY = 180
POWER_CAPACITY_BY_BUILDING = {
    "power_plant": POWER_PLANT_CAPACITY,
    "large_power_plant": 2000,
}
WATER_CAPACITY_BY_BUILDING = {
    "water_tower": WATER_TOWER_CAPACITY,
    "large_water_tower": 1500,
}

# ── Service coverage radii ─────────────────────────────────────────────────────
# Tiles within this Manhattan distance of a service building receive coverage.
SERVICE_RADIUS = 6    # schools
HEALTH_RADIUS = 9     # hospitals
FIRE_RADIUS = 12      # fire stations
POLICE_RADIUS = 12    # police stations
TRAIN_STATION_RADIUS = 8
AIRPORT_RADIUS = 10

# ── Simulation multipliers and coefficients ────────────────────────────────────
# Tax revenue: population * tax_rate * coefficient = residential income per month.
POPULATION_TAX_COEFFICIENT = 0.16
JOBS_TAX_COEFFICIENT = 0.08

# How much power/water each person or job consumes per month.
POWER_CONSUMPTION_PER_RESIDENT = 0.8
POWER_CONSUMPTION_PER_JOB = 0.6
WATER_CONSUMPTION_PER_RESIDENT = 0.7
WATER_CONSUMPTION_PER_JOB = 0.5

# Rate at which undeveloped (or disconnected) zones lose progress per month.
DEVELOPMENT_DECLINE_RATE = 0.04
# Extra decline penalty when tax rate is above HIGH_TAX_THRESHOLD.
HIGH_TAX_DECLINE_RATE = 0.03
HIGH_TAX_THRESHOLD = 16          # tax rate % that triggers extra decline
TAX_RATE_PENALTY_FACTOR = 18     # divisor used in the tax penalty formula
MIN_TAX_FACTOR = 0.15            # minimum growth multiplier even at max tax
TAX_FACTOR_BASELINE = 1.2        # growth multiplier at zero tax

# Base monthly growth rate before demand and tax adjustments.
BASE_GROWTH_RATE = 0.018
# How strongly demand (0-100) scales growth on top of the base.
DEMAND_GROWTH_MULTIPLIER = 0.035
# Bonus growth for each service-coverage point (multiplied by service score).
SERVICE_BONUS_MULTIPLIER = 0.18
# Bonus demand when city utilities are running at full capacity.
UTILITY_BONUS_MULTIPLIER = 14

# Per-unit demand penalties from tax rate.
TAX_PENALTY_RESIDENTIAL = 2.0
TAX_PENALTY_COMMERCIAL = 1.4
TAX_PENALTY_INDUSTRIAL = 1.1

# Maximum residents/jobs a single tile can hold at full development.
RESIDENTIAL_CAPACITY = 20
COMMERCIAL_CAPACITY = 12
INDUSTRIAL_CAPACITY = 18

# Land value is clamped between these bounds (1.0 = neutral).
LAND_VALUE_MIN = 0.65
LAND_VALUE_MAX = 1.25

# Small bonuses/penalties applied to land value based on neighbours and services.
SERVICE_COVERAGE_BONUS = 0.04
EDUCATION_COVERAGE_BONUS = 0.06
COMMERCIAL_NEIGHBOR_BONUS = 0.03
INDUSTRIAL_NEIGHBOR_PENALTY = 0.025
ROAD_NEIGHBOR_BONUS = 0.015

# ── Fire risk formula constants ────────────────────────────────────────────────
FIRE_RISK_BASE = 10                   # every zoned tile starts with this risk
FIRE_RISK_DEVELOPMENT_FACTOR = 45     # scales with development level
FIRE_RISK_INDUSTRIAL = 25             # extra risk for industrial zones
FIRE_RISK_COMMERCIAL = 15
FIRE_RISK_RESIDENTIAL = 8
FIRE_RISK_INDUSTRIAL_NEIGHBOR = 5     # risk from each adjacent industrial tile
FIRE_RISK_COVERAGE_REDUCTION = 25     # deducted when fire station covers the tile
FIRE_RISK_NO_COVERAGE = 20            # added when no fire station coverage
FIRE_RISK_NO_WATER = 10               # added when tile has no water supply
FIRE_RISK_NO_ROAD = 8                 # fire trucks need roads

# ── Crime risk formula constants ───────────────────────────────────────────────
CRIME_RISK_BASE = 8
CRIME_RISK_DEVELOPMENT_FACTOR = 35
CRIME_RISK_COMMERCIAL = 25
CRIME_RISK_INDUSTRIAL = 18
CRIME_RISK_RESIDENTIAL = 12
CRIME_RISK_COMMERCIAL_NEIGHBOR = 4    # commercial areas attract more crime
CRIME_RISK_COVERAGE_REDUCTION = 25    # police presence deters crime
CRIME_RISK_NO_COVERAGE = 25
CRIME_RISK_NO_ROAD = 8
CRIME_RISK_HIGH_TAX = 8               # economic stress raises crime

# Tiles with risk above this percent are considered high-risk.
HIGH_RISK_THRESHOLD = 70
# Minimum capacity fraction when utility supply is zero.
MIN_CAPACITY_FACTOR = 0.25
# Service score = total service points / (zoned tiles * this divisor) * 100.
SERVICE_SCORE_DIVISOR = 3

# Demand boosts from transport infrastructure.
TRAIN_STATION_DEMAND_BOOST = 15
AIRPORT_DEMAND_BOOST = 20

# Walking speed for pedestrians in tile-units per second.
PEDESTRIAN_SPEED = 0.5

# Growth multipliers applied when a tile has school/hospital coverage.
EDUCATION_GROWTH_BONUS  = 0.20   # growth rate multiplier for education-covered zones
HEALTH_GROWTH_BONUS     = 0.15   # growth rate multiplier for hospital-covered zones

# Roads become congested once traffic load exceeds this value.
ROAD_TRAFFIC_CAPACITY   = 12     # traffic units before a road is considered congested
# Commercial demand is reduced for each congested road tile (capped at -25).
CONGESTION_DEMAND_PENALTY = 1    # commercial demand penalty per congested road tile
# Duration of one complete day/night visual cycle in real-time seconds.
DAY_CYCLE_SECONDS       = 90.0   # real-time seconds per full day/night cycle

# ── Fire disaster ──────────────────────────────────────────────────────────────
FIRE_UPDATE_INTERVAL    = 0.5    # real-time seconds between fire simulation ticks
FIRE_IGNITION_PROB      = 0.008  # per uncovered high-risk tile per month
FIRE_SPREAD_INTERVAL    = 2.0    # real seconds between spread attempts
FIRE_SPREAD_CHANCE      = 0.30   # chance fire spreads to each adjacent zone tile
FIRE_BURN_RATE          = 0.05   # development lost per fire tick (~0.1/sec)
FIRE_SUPPRESS_TIME      = 4.5    # real sec to extinguish with fire station coverage
FIRE_NATURAL_EXTINGUISH = 18.0   # real sec until fire burns out on its own
FIRE_EMERGENCY_COST     = 250    # money charged when a fire breaks out

# ── Pollution ──────────────────────────────────────────────────────────────────
# Industrial zones generate pollution that spreads to adjacent tiles.
POLLUTION_INDUSTRIAL_SOURCE = 0.8   # base pollution at an industrial tile (0-1)
POLLUTION_ROAD_SOURCE       = 0.15  # roads add a small amount of pollution
POLLUTION_SPREAD_FACTOR     = 0.4   # each neighbor receives this fraction of the source
POLLUTION_DECAY             = 0.25  # per-tick decay toward 0 for non-source tiles
# Pollution above this level suppresses residential growth and land value.
POLLUTION_PENALTY_THRESHOLD = 0.3
# Maximum land-value penalty applied at max pollution.
POLLUTION_LAND_VALUE_PENALTY = 0.3

# ── Crime incident ─────────────────────────────────────────────────────────────
CRIME_INCIDENT_PROB     = 0.012  # per uncovered high-crime tile per month
CRIME_DAMAGE_RATE       = 0.10   # development set back on incident tile
CRIME_CLEANUP_COST      = 100    # money charged per crime incident

# ── City events ───────────────────────────────────────────────────────────────
# Random monthly events that add narrative variety.  Each entry is a dict:
#   id          — unique string key (also used for deduplication)
#   message     — shown in the advisor feed, prefixed with "★ "
#   prob        — probability of firing in any given month (independent rolls)
#   min_pop     — city population required before this event can fire
#   duration    — how many months the effect lasts (0 = instant money/penalty)
#   effects     — dict of modifier keys → values applied while the event is active:
#                   res_demand, com_demand, ind_demand  — flat additions to demand (0-100)
#                   money                              — one-time payment (negative = penalty)
#                   growth_mult                        — multiplier on all zone growth rates
CITY_EVENTS: list[dict] = [
    # ── Good events ──────────────────────────────────────────────────────────
    {
        "id": "tech_boom",
        "message": "A major tech company chose your city for its new headquarters! Commercial demand surges.",
        "prob": 0.018, "min_pop": 800, "duration": 4,
        "effects": {"com_demand": 22, "res_demand": 10},
    },
    {
        "id": "state_grant",
        "message": "The state awarded your city an infrastructure grant.",
        "prob": 0.025, "min_pop": 200, "duration": 0,
        "effects": {"money": 4000},
    },
    {
        "id": "tourism_award",
        "message": "Travel magazine named your city a top destination! Tourism boosts commercial income.",
        "prob": 0.016, "min_pop": 1500, "duration": 3,
        "effects": {"com_demand": 15, "res_demand": 5},
    },
    {
        "id": "factory_expansion",
        "message": "Regional factories are expanding operations. Industrial demand rises.",
        "prob": 0.020, "min_pop": 300, "duration": 3,
        "effects": {"ind_demand": 20, "res_demand": 8},
    },
    {
        "id": "housing_boom",
        "message": "Low interest rates sparked a housing boom. Residential growth accelerates.",
        "prob": 0.022, "min_pop": 100, "duration": 3,
        "effects": {"res_demand": 20, "growth_mult": 1.25},
    },
    {
        "id": "sports_team",
        "message": "The city's sports team made the playoffs! Morale is high.",
        "prob": 0.014, "min_pop": 2000, "duration": 2,
        "effects": {"res_demand": 12, "com_demand": 8},
    },
    {
        "id": "federal_stimulus",
        "message": "Federal economic stimulus package benefits your region.",
        "prob": 0.012, "min_pop": 500, "duration": 0,
        "effects": {"money": 8000},
    },
    {
        "id": "university_opens",
        "message": "A new university branch opens nearby, attracting educated residents.",
        "prob": 0.010, "min_pop": 3000, "duration": 6,
        "effects": {"res_demand": 14, "com_demand": 10, "growth_mult": 1.15},
    },
    # ── Bad events ──────────────────────────────────────────────────────────
    {
        "id": "recession",
        "message": "Economic recession is dampening growth across the region.",
        "prob": 0.015, "min_pop": 500, "duration": 4,
        "effects": {"res_demand": -15, "com_demand": -20, "ind_demand": -10},
    },
    {
        "id": "factory_closure",
        "message": "A major factory closed, leaving many workers unemployed.",
        "prob": 0.014, "min_pop": 600, "duration": 3,
        "effects": {"ind_demand": -18, "res_demand": -8},
    },
    {
        "id": "infrastructure_fine",
        "message": "City infrastructure inspection resulted in an emergency repair bill.",
        "prob": 0.018, "min_pop": 300, "duration": 0,
        "effects": {"money": -2500},
    },
    {
        "id": "crime_wave",
        "message": "A crime wave is unsettling residents. Police resources stretched thin.",
        "prob": 0.016, "min_pop": 800, "duration": 3,
        "effects": {"res_demand": -12, "com_demand": -8},
    },
    {
        "id": "drought",
        "message": "Drought conditions are straining the water supply.",
        "prob": 0.013, "min_pop": 200, "duration": 3,
        "effects": {"growth_mult": 0.75, "res_demand": -8},
    },
    {
        "id": "heatwave",
        "message": "Extreme heat wave strained the power grid and slowed construction.",
        "prob": 0.015, "min_pop": 100, "duration": 2,
        "effects": {"growth_mult": 0.80, "com_demand": -6},
    },
    {
        "id": "pollution_scandal",
        "message": "Industrial pollution scandal drove away residents.",
        "prob": 0.012, "min_pop": 1000, "duration": 3,
        "effects": {"res_demand": -18, "com_demand": -6},
    },
]

# ── City milestones ────────────────────────────────────────────────────────────
# When the city reaches each population threshold the player earns a title
# and a one-time state grant. Format: (population_threshold, title, grant).
POPULATION_MILESTONES: list[tuple[int, str, int]] = [
    (100,     "Hamlet",      1_000),
    (500,     "Village",     3_000),
    (2_000,   "Town",       10_000),
    (10_000,  "City",       35_000),
    (50_000,  "Metropolis", 120_000),
    (100_000, "Megalopolis",300_000),
]

# ── Save system ────────────────────────────────────────────────────────────────
SAVE_DIR = "saves"       # folder relative to the project root
NUM_SAVE_SLOTS = 5       # how many named save slots exist

# Use the generated transparent isometric PNG pack for buildings, civic buildings,
# and pedestrians. Terrain, roads, utilities, overlays, and zones remain procedural.
USE_IMAGE_SPRITES = True

# ── Colour palette ─────────────────────────────────────────────────────────────
# All RGB colours used by the renderer and UI. Centralising them here means you
# can re-skin the whole game by editing this one dict.
COLORS = {
    "background": (16, 20, 26),
    "sidebar": (18, 22, 28),
    "sidebar_panel": (26, 32, 40),
    "sidebar_panel_active": (42, 62, 88),
    "text": (235, 239, 242),
    "muted_text": (165, 176, 184),
    "money_good": (118, 213, 140),   # green for positive numbers
    "money_bad": (236, 104, 94),     # red for negative numbers
    "grid": (63, 74, 68),
    "grid_light": (88, 101, 94),
    "empty": (80, 126, 72),
    "empty_alt": (75, 119, 70),
    "terrain_water": (52, 112, 148),
    "terrain_forest": (45, 102, 62),
    "terrain_hill": (115, 116, 101),
    "road": (54, 57, 62),
    "road_line": (202, 188, 116),
    "residential": (84, 168, 93),
    "commercial": (75, 129, 207),
    "industrial": (211, 174, 77),
    "power": (240, 213, 88),
    "water": (82, 174, 220),
    "police": (74, 109, 184),
    "fire": (211, 84, 70),
    "school": (137, 104, 196),
    "hospital": (215, 80, 90),
    "train_station": (200, 150, 100),
    "airport": (100, 150, 200),
    "park": (58, 190, 100),
    "playground": (230, 120, 50),
    "sports_field": (40, 185, 70),
    "stadium": (130, 100, 175),
    "golf_course": (100, 210, 110),
    "pool": (70, 165, 230),
    "cinema": (195, 55, 90),
    "museum": (200, 185, 145),
    "zoo": (165, 120, 65),
    "pedestrian": (255, 200, 100),
    "service": (122, 201, 148),
    "zone_border": (31, 41, 36),
    "hover_ok": (255, 255, 255),       # highlight when placement is valid
    "hover_blocked": (235, 92, 92),    # highlight when placement is blocked
    "shadow": (19, 22, 25),
    "building_dark": (42, 47, 53),
    "building_light": (219, 226, 226),
}
