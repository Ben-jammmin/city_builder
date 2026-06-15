"""All tunable game constants in one place. Adjust values here to balance the simulation."""
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 800
COMMAND_BAR_HEIGHT = 268
MINIMIZED_COMMAND_BAR_HEIGHT = 44
FPS = 60

MAP_WIDTH = 64
MAP_HEIGHT = 48
TILE_SIZE = 32

STARTING_MONEY = 50000
STARTING_YEAR = 1
STARTING_MONTH = 1
STARTING_TAX_RATE = 9
SIM_SECONDS_PER_MONTH = 1.25

MIN_TAX_RATE = 1
MAX_TAX_RATE = 20

ZONE_COST = {
    "residential": 25,
    "commercial": 35,
    "industrial": 30,
    "park": 150,
}

PARK_MAINTENANCE = 3
PARK_LAND_VALUE_BONUS = 0.07
PARK_DEMAND_BONUS = 0.5

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
    "stadium": 2.5,
    "golf_course": 0.5,
    "pool": 0.3,
    "cinema": 2.0,
    "museum": 0.8,
    "zoo": 1.5,
}
# Zone density levels (level 1 = standard, level 2 = dense)
ZONE_LEVEL_COST_MULTIPLIERS = {
    1: 1.0,
    2: 3.0,
}
ZONE_LEVEL_CAPACITY_MULTIPLIERS = {
    1: 1.0,
    2: 2.35,
}
ZONE_LEVEL_GROWTH_MULTIPLIERS = {
    1: 1.0,
    2: 0.85,  # dense zones grow slower but hold more people
}
ZONE_LEVEL_LABELS = {
    1: "Standard",
    2: "Dense",
}
ROAD_COST = 60
BULLDOZE_COST = 8
POWER_LINE_COST = 20
WATER_PIPE_COST = 20

# Terrain demolition costs
TERRAIN_CLEAR_COSTS = {
    "water": 50,
    "forest": 15,
    "hill": 25,
}

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

ROAD_MAINTENANCE = 2
ZONE_MAINTENANCE = 0.2
POWER_LINE_MAINTENANCE = 1
WATER_PIPE_MAINTENANCE = 1

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
SERVICE_RADIUS = 6
HEALTH_RADIUS = 9
FIRE_RADIUS = 12
POLICE_RADIUS = 12
TRAIN_STATION_RADIUS = 8
AIRPORT_RADIUS = 10

# Simulation multipliers and coefficients
POPULATION_TAX_COEFFICIENT = 0.16
JOBS_TAX_COEFFICIENT = 0.08
POWER_CONSUMPTION_PER_RESIDENT = 0.8
POWER_CONSUMPTION_PER_JOB = 0.6
WATER_CONSUMPTION_PER_RESIDENT = 0.7
WATER_CONSUMPTION_PER_JOB = 0.5
DEVELOPMENT_DECLINE_RATE = 0.04
HIGH_TAX_DECLINE_RATE = 0.03
HIGH_TAX_THRESHOLD = 16
TAX_RATE_PENALTY_FACTOR = 18
MIN_TAX_FACTOR = 0.15
TAX_FACTOR_BASELINE = 1.2
BASE_GROWTH_RATE = 0.014
DEMAND_GROWTH_MULTIPLIER = 0.035
SERVICE_BONUS_MULTIPLIER = 0.18
UTILITY_BONUS_MULTIPLIER = 14
TAX_PENALTY_RESIDENTIAL = 2.0
TAX_PENALTY_COMMERCIAL = 1.4
TAX_PENALTY_INDUSTRIAL = 1.1
RESIDENTIAL_CAPACITY = 20
COMMERCIAL_CAPACITY = 12
INDUSTRIAL_CAPACITY = 18
LAND_VALUE_MIN = 0.65
LAND_VALUE_MAX = 1.25
SERVICE_COVERAGE_BONUS = 0.04
EDUCATION_COVERAGE_BONUS = 0.06
COMMERCIAL_NEIGHBOR_BONUS = 0.03
INDUSTRIAL_NEIGHBOR_PENALTY = 0.025
ROAD_NEIGHBOR_BONUS = 0.015
FIRE_RISK_BASE = 10
FIRE_RISK_DEVELOPMENT_FACTOR = 45
FIRE_RISK_INDUSTRIAL = 25
FIRE_RISK_COMMERCIAL = 15
FIRE_RISK_RESIDENTIAL = 8
FIRE_RISK_INDUSTRIAL_NEIGHBOR = 5
FIRE_RISK_COVERAGE_REDUCTION = 25
FIRE_RISK_NO_COVERAGE = 20
FIRE_RISK_NO_WATER = 10
FIRE_RISK_NO_ROAD = 8
CRIME_RISK_BASE = 8
CRIME_RISK_DEVELOPMENT_FACTOR = 35
CRIME_RISK_COMMERCIAL = 25
CRIME_RISK_INDUSTRIAL = 18
CRIME_RISK_RESIDENTIAL = 12
CRIME_RISK_COMMERCIAL_NEIGHBOR = 4
CRIME_RISK_COVERAGE_REDUCTION = 25
CRIME_RISK_NO_COVERAGE = 25
CRIME_RISK_NO_ROAD = 8
CRIME_RISK_HIGH_TAX = 8
HIGH_RISK_THRESHOLD = 70
MIN_CAPACITY_FACTOR = 0.25
SERVICE_SCORE_DIVISOR = 3
TRAIN_STATION_DEMAND_BOOST = 15
AIRPORT_DEMAND_BOOST = 20
PEDESTRIAN_SPAWN_RATE = 0.08
PEDESTRIAN_MAX_COUNT = 50
PEDESTRIAN_SPEED = 0.5

EDUCATION_GROWTH_BONUS  = 0.20   # growth rate multiplier for education-covered zones
HEALTH_GROWTH_BONUS     = 0.15   # growth rate multiplier for hospital-covered zones
ROAD_TRAFFIC_CAPACITY   = 12     # traffic units before a road is considered congested
CONGESTION_DEMAND_PENALTY = 1    # commercial demand penalty per congested road tile
DAY_CYCLE_SECONDS       = 90.0   # real-time seconds per full day/night cycle

# ── Fire disaster ─────────────────────────────────────────────────────────────
FIRE_UPDATE_INTERVAL    = 0.5    # real-time seconds between fire simulation ticks
FIRE_IGNITION_PROB      = 0.008  # per uncovered high-risk tile per month
FIRE_SPREAD_INTERVAL    = 2.0    # real seconds between spread attempts
FIRE_SPREAD_CHANCE      = 0.30   # chance fire spreads to each adjacent zone tile
FIRE_BURN_RATE          = 0.05   # development lost per fire tick (~0.1/sec)
FIRE_SUPPRESS_TIME      = 4.5    # real sec to extinguish with fire station coverage
FIRE_NATURAL_EXTINGUISH = 18.0   # real sec until fire burns out on its own
FIRE_EMERGENCY_COST     = 250    # money charged when a fire breaks out

# ── Crime incident ─────────────────────────────────────────────────────────────
CRIME_INCIDENT_PROB     = 0.012  # per uncovered high-crime tile per month
CRIME_DAMAGE_RATE       = 0.10   # development set back on incident tile
CRIME_CLEANUP_COST      = 100    # money charged per crime incident

# ── City milestones ────────────────────────────────────────────────────────────
# (population_threshold, title, state_grant)
POPULATION_MILESTONES: list[tuple[int, str, int]] = [
    (100,     "Hamlet",      1_000),
    (500,     "Village",     3_000),
    (2_000,   "Town",       10_000),
    (10_000,  "City",       35_000),
    (50_000,  "Metropolis", 120_000),
    (100_000, "Megalopolis",300_000),
]

SAVE_FILE = "savegame.json"

# Use the generated transparent isometric PNG pack for buildings, civic buildings,
# and pedestrians. Terrain, roads, utilities, overlays, and zones remain procedural.
USE_IMAGE_SPRITES = True

COLORS = {
    "background": (16, 20, 26),
    "sidebar": (18, 22, 28),
    "sidebar_panel": (26, 32, 40),
    "sidebar_panel_active": (42, 62, 88),
    "text": (235, 239, 242),
    "muted_text": (165, 176, 184),
    "money_good": (118, 213, 140),
    "money_bad": (236, 104, 94),
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
    "hover_ok": (255, 255, 255),
    "hover_blocked": (235, 92, 92),
    "shadow": (19, 22, 25),
    "building_dark": (42, 47, 53),
    "building_light": (219, 226, 226),
}
