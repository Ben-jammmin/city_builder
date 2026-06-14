WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 800
SIDEBAR_WIDTH = 320
FPS = 60

MAP_WIDTH = 64
MAP_HEIGHT = 48
TILE_SIZE = 32

STARTING_MONEY = 25000
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
}
ROAD_COST = 60
BULLDOZE_COST = 8
POWER_LINE_COST = 20
WATER_PIPE_COST = 20

BUILDING_COST = {
    "power_plant": 2500,
    "water_tower": 1200,
    "police": 900,
    "fire": 900,
    "school": 1100,
}

ROAD_MAINTENANCE = 2
ZONE_MAINTENANCE = 0.2
POWER_LINE_MAINTENANCE = 1
WATER_PIPE_MAINTENANCE = 1

BUILDING_MAINTENANCE = {
    "power_plant": 45,
    "water_tower": 25,
    "police": 35,
    "fire": 35,
    "school": 40,
}

POWER_PLANT_CAPACITY = 220
WATER_TOWER_CAPACITY = 180
SERVICE_RADIUS = 6
SAVE_FILE = "savegame.json"

COLORS = {
    "background": (28, 34, 39),
    "sidebar": (38, 43, 49),
    "sidebar_panel": (48, 54, 61),
    "sidebar_panel_active": (63, 76, 86),
    "text": (235, 239, 242),
    "muted_text": (165, 176, 184),
    "money_good": (118, 213, 140),
    "money_bad": (236, 104, 94),
    "grid": (63, 74, 68),
    "grid_light": (88, 101, 94),
    "empty": (80, 126, 72),
    "empty_alt": (75, 119, 70),
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
    "service": (122, 201, 148),
    "zone_border": (31, 41, 36),
    "hover_ok": (255, 255, 255),
    "hover_blocked": (235, 92, 92),
    "shadow": (19, 22, 25),
    "building_dark": (42, 47, 53),
    "building_light": (219, 226, 226),
}
