"""
models.py — Core data types shared across the whole game.

Contains:
  - Enums for zone types, terrain, buildings, tools, and view modes
  - Lookup tables that map enums to display labels, costs, and menu groupings
  - Tile dataclass: the data stored for every grid cell
  - CityStats dataclass: the global city scoreboard (money, population, etc.)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .settings import (
    MAX_TAX_RATE,
    MIN_TAX_RATE,
    STARTING_MONTH,
    STARTING_MONEY,
    STARTING_TAX_RATE,
    STARTING_YEAR,
)

# ── Enums ──────────────────────────────────────────────────────────────────────

class ZoneType(Enum):
    """What kind of zone the player has painted on a tile."""
    EMPTY = "empty"
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    PARK = "park"


class RecreationType(Enum):
    """Specific recreation sub-type for PARK zone tiles."""
    PARK = "park"
    PLAYGROUND = "playground"
    SPORTS_FIELD = "sports_field"
    STADIUM = "stadium"
    GOLF_COURSE = "golf_course"
    POOL = "pool"
    CINEMA = "cinema"
    MUSEUM = "museum"
    ZOO = "zoo"


class TerrainType(Enum):
    """Natural terrain beneath all human construction."""
    GRASS = "grass"
    WATER = "water"
    FOREST = "forest"
    HILL = "hill"


class BuildingType(Enum):
    """Civic buildings placed by the player (not the same as zone buildings)."""
    NONE = "none"
    POWER_PLANT = "power_plant"
    LARGE_POWER_PLANT = "large_power_plant"
    WATER_TOWER = "water_tower"
    LARGE_WATER_TOWER = "large_water_tower"
    POLICE = "police"
    FIRE = "fire"
    SCHOOL = "school"
    HOSPITAL = "hospital"
    TRAIN_STATION = "train_station"
    AIRPORT = "airport"


class Tool(Enum):
    """Every tool the player can select from the sidebar."""
    INSPECT = "inspect"
    RESIDENTIAL = "residential"
    DENSE_RESIDENTIAL = "dense_residential"
    COMMERCIAL = "commercial"
    DENSE_COMMERCIAL = "dense_commercial"
    INDUSTRIAL = "industrial"
    ROAD = "road"
    POWER_LINE = "power_line"
    WATER_PIPE = "water_pipe"
    POWER_PLANT = "power_plant"
    LARGE_POWER_PLANT = "large_power_plant"
    WATER_TOWER = "water_tower"
    LARGE_WATER_TOWER = "large_water_tower"
    POLICE = "police"
    FIRE = "fire"
    SCHOOL = "school"
    HOSPITAL = "hospital"
    TRAIN_STATION = "train_station"
    AIRPORT = "airport"
    PARK = "park"
    PLAYGROUND = "playground"
    SPORTS_FIELD = "sports_field"
    STADIUM = "stadium"
    GOLF_COURSE = "golf_course"
    POOL = "pool"
    CINEMA = "cinema"
    MUSEUM = "museum"
    ZOO = "zoo"
    BULLDOZE = "bulldoze"


class ViewMode(Enum):
    """Overlay modes that tint the map to show infrastructure coverage."""
    NORMAL = "normal"
    POWER = "power"
    WATER = "water"
    FIRE = "fire"
    POLICE = "police"
    TERRAIN = "terrain"


# ── Display label lookups ──────────────────────────────────────────────────────
# These dicts map each enum value to the human-readable string shown in the UI.

RECREATION_LABELS = {
    RecreationType.PARK: "Park",
    RecreationType.PLAYGROUND: "Playground",
    RecreationType.SPORTS_FIELD: "Sports Field",
    RecreationType.STADIUM: "Stadium",
    RecreationType.GOLF_COURSE: "Golf Course",
    RecreationType.POOL: "Pool",
    RecreationType.CINEMA: "Cinema",
    RecreationType.MUSEUM: "Museum",
    RecreationType.ZOO: "Zoo",
}

ZONE_LABELS = {
    ZoneType.EMPTY: "Empty",
    ZoneType.RESIDENTIAL: "Residential",
    ZoneType.COMMERCIAL: "Commercial",
    ZoneType.INDUSTRIAL: "Industrial",
    ZoneType.PARK: "Park",
}

TERRAIN_LABELS = {
    TerrainType.GRASS: "Grass",
    TerrainType.WATER: "Water",
    TerrainType.FOREST: "Forest",
    TerrainType.HILL: "Hill",
}

VIEW_LABELS = {
    ViewMode.NORMAL: "Normal",
    ViewMode.POWER: "Power",
    ViewMode.WATER: "Water",
    ViewMode.FIRE: "Fire",
    ViewMode.POLICE: "Police",
    ViewMode.TERRAIN: "Terrain",
}

# Ordered list used when cycling through view modes with the V key.
VIEW_ORDER = [
    ViewMode.NORMAL,
    ViewMode.POWER,
    ViewMode.WATER,
    ViewMode.FIRE,
    ViewMode.POLICE,
    ViewMode.TERRAIN,
]


BUILDING_LABELS = {
    BuildingType.NONE: "None",
    BuildingType.POWER_PLANT: "Power Plant",
    BuildingType.LARGE_POWER_PLANT: "Large Power Plant",
    BuildingType.WATER_TOWER: "Water Tower",
    BuildingType.LARGE_WATER_TOWER: "Large Water Tower",
    BuildingType.POLICE: "Police",
    BuildingType.FIRE: "Fire",
    BuildingType.SCHOOL: "School",
    BuildingType.HOSPITAL: "Hospital",
    BuildingType.TRAIN_STATION: "Train Station",
    BuildingType.AIRPORT: "Airport",
}

TOOL_LABELS = {
    Tool.INSPECT: "Inspect",
    Tool.RESIDENTIAL: "Residential",
    Tool.DENSE_RESIDENTIAL: "Dense Residential",
    Tool.COMMERCIAL: "Commercial",
    Tool.DENSE_COMMERCIAL: "Dense Commercial",
    Tool.INDUSTRIAL: "Industrial",
    Tool.ROAD: "Road",
    Tool.POWER_LINE: "Power Line",
    Tool.WATER_PIPE: "Water Pipe",
    Tool.POWER_PLANT: "Power Plant",
    Tool.LARGE_POWER_PLANT: "Large Power Plant",
    Tool.WATER_TOWER: "Water Tower",
    Tool.LARGE_WATER_TOWER: "Large Water Tower",
    Tool.POLICE: "Police",
    Tool.FIRE: "Fire",
    Tool.SCHOOL: "School",
    Tool.HOSPITAL: "Hospital",
    Tool.TRAIN_STATION: "Train Station",
    Tool.AIRPORT: "Airport",
    Tool.PARK: "Park",
    Tool.PLAYGROUND: "Playground",
    Tool.SPORTS_FIELD: "Sports Field",
    Tool.STADIUM: "Stadium",
    Tool.GOLF_COURSE: "Golf Course",
    Tool.POOL: "Pool",
    Tool.CINEMA: "Cinema",
    Tool.MUSEUM: "Museum",
    Tool.ZOO: "Zoo",
    Tool.BULLDOZE: "Bulldoze",
}

# Keyboard shortcuts — maps a key name string to the tool it activates.
TOOL_HOTKEYS = {
    "0": Tool.INSPECT,
    "1": Tool.RESIDENTIAL,
    "2": Tool.COMMERCIAL,
    "3": Tool.INDUSTRIAL,
    "4": Tool.ROAD,
    "5": Tool.POWER_LINE,
    "6": Tool.WATER_PIPE,
    "7": Tool.POWER_PLANT,
    "8": Tool.WATER_TOWER,
    "9": Tool.BULLDOZE,
    "p": Tool.POLICE,
    "f": Tool.FIRE,
    "h": Tool.SCHOOL,
    "t": Tool.TRAIN_STATION,
    "a": Tool.AIRPORT,
    "k": Tool.PARK,
}

# ── Menu groupings ─────────────────────────────────────────────────────────────
# Controls which tools appear under each sidebar tab.
MENU_TOOLS = {
    "Zones": [
        Tool.INSPECT,
        Tool.RESIDENTIAL,
        Tool.DENSE_RESIDENTIAL,
        Tool.COMMERCIAL,
        Tool.DENSE_COMMERCIAL,
        Tool.INDUSTRIAL,
        Tool.BULLDOZE,
    ],
    "Recreation": [
        Tool.PARK,
        Tool.PLAYGROUND,
        Tool.SPORTS_FIELD,
        Tool.STADIUM,
        Tool.GOLF_COURSE,
        Tool.POOL,
        Tool.CINEMA,
        Tool.MUSEUM,
        Tool.ZOO,
    ],
    "Utilities": [
        Tool.ROAD,
        Tool.POWER_LINE,
        Tool.WATER_PIPE,
        Tool.POWER_PLANT,
        Tool.LARGE_POWER_PLANT,
        Tool.WATER_TOWER,
        Tool.LARGE_WATER_TOWER,
    ],
    "Services": [
        Tool.POLICE,
        Tool.FIRE,
        Tool.SCHOOL,
        Tool.HOSPITAL,
        Tool.BULLDOZE,
    ],
    "Transport": [
        Tool.TRAIN_STATION,
        Tool.AIRPORT,
    ],
}

# Ordered list of menu tab names, so tabs appear in a consistent left-to-right order.
MENU_ORDER = list(MENU_TOOLS.keys())

# ── Conversion lookups ─────────────────────────────────────────────────────────
# Maps a tool to the BuildingType it places (for civic buildings).
TOOL_TO_BUILDING = {
    Tool.POWER_PLANT: BuildingType.POWER_PLANT,
    Tool.LARGE_POWER_PLANT: BuildingType.LARGE_POWER_PLANT,
    Tool.WATER_TOWER: BuildingType.WATER_TOWER,
    Tool.LARGE_WATER_TOWER: BuildingType.LARGE_WATER_TOWER,
    Tool.POLICE: BuildingType.POLICE,
    Tool.FIRE: BuildingType.FIRE,
    Tool.SCHOOL: BuildingType.SCHOOL,
    Tool.HOSPITAL: BuildingType.HOSPITAL,
    Tool.TRAIN_STATION: BuildingType.TRAIN_STATION,
    Tool.AIRPORT: BuildingType.AIRPORT,
}

# Maps a tool to the (ZoneType, level) pair it paints.
TOOL_TO_ZONE = {
    Tool.RESIDENTIAL: (ZoneType.RESIDENTIAL, 1),
    Tool.DENSE_RESIDENTIAL: (ZoneType.RESIDENTIAL, 2),
    Tool.COMMERCIAL: (ZoneType.COMMERCIAL, 1),
    Tool.DENSE_COMMERCIAL: (ZoneType.COMMERCIAL, 2),
    Tool.INDUSTRIAL: (ZoneType.INDUSTRIAL, 1),
    Tool.PARK: (ZoneType.PARK, 1),
    Tool.PLAYGROUND: (ZoneType.PARK, 1),
    Tool.SPORTS_FIELD: (ZoneType.PARK, 1),
    Tool.STADIUM: (ZoneType.PARK, 1),
    Tool.GOLF_COURSE: (ZoneType.PARK, 1),
    Tool.POOL: (ZoneType.PARK, 1),
    Tool.CINEMA: (ZoneType.PARK, 1),
    Tool.MUSEUM: (ZoneType.PARK, 1),
    Tool.ZOO: (ZoneType.PARK, 1),
}

# Maps a tool to its specific RecreationType (for park sub-types).
TOOL_TO_RECREATION = {
    Tool.PARK: RecreationType.PARK,
    Tool.PLAYGROUND: RecreationType.PLAYGROUND,
    Tool.SPORTS_FIELD: RecreationType.SPORTS_FIELD,
    Tool.STADIUM: RecreationType.STADIUM,
    Tool.GOLF_COURSE: RecreationType.GOLF_COURSE,
    Tool.POOL: RecreationType.POOL,
    Tool.CINEMA: RecreationType.CINEMA,
    Tool.MUSEUM: RecreationType.MUSEUM,
    Tool.ZOO: RecreationType.ZOO,
}

# Sets used by the simulation to identify which buildings supply power/water.
POWER_SOURCE_BUILDINGS = {
    BuildingType.POWER_PLANT,
    BuildingType.LARGE_POWER_PLANT,
}

WATER_SOURCE_BUILDINGS = {
    BuildingType.WATER_TOWER,
    BuildingType.LARGE_WATER_TOWER,
}


# ── Helper function ────────────────────────────────────────────────────────────

def menu_for_tool(tool: Tool) -> str:
    """Returns the name of the sidebar menu tab that contains the given tool."""
    for menu_name, tools in MENU_TOOLS.items():
        if tool in tools:
            return menu_name
    return MENU_ORDER[0]


# ── Tile dataclass ─────────────────────────────────────────────────────────────

@dataclass
class Tile:
    """
    All data stored for a single grid cell on the city map.

    Tiles start as empty grass. The simulation updates most numeric fields
    (development, residents, powered, fire_risk, …) each month.
    """
    terrain: TerrainType = TerrainType.GRASS
    zone: ZoneType = ZoneType.EMPTY
    zone_level: int = 1                        # 1 = standard, 2 = dense
    recreation_type: RecreationType = RecreationType.PARK
    building: BuildingType = BuildingType.NONE
    has_road: bool = False
    has_power_line: bool = False
    has_water_pipe: bool = False
    development: float = 0.0      # 0.0 = bare lot, 1.0 = fully built-up
    residents: int = 0
    jobs: int = 0
    land_value: float = 1.0       # multiplier applied to capacity (0.65-1.25)
    powered: bool = False         # True when connected to a working power network
    watered: bool = False         # True when connected to a working water network
    police_coverage: bool = False
    fire_coverage: bool = False
    education_coverage: bool = False
    health_coverage: bool = False
    fire_risk: int = 0            # 0-100 percent
    traffic_load: int = 0         # traffic units generated by adjacent zones
    crime_risk: int = 0           # 0-100 percent
    on_fire: bool = False
    fire_burn_time: float = 0.0   # seconds the tile has been burning

    @property
    def is_empty(self) -> bool:
        """Returns True when no man-made infrastructure exists on this tile."""
        return (
            self.zone == ZoneType.EMPTY
            and self.building == BuildingType.NONE
            and not self.has_road
            and not self.has_power_line
            and not self.has_water_pipe
        )

    def clear(self) -> None:
        """Resets all man-made data on a tile back to bare defaults (used by bulldoze)."""
        self.zone = ZoneType.EMPTY
        self.zone_level = 1
        self.recreation_type = RecreationType.PARK
        self.building = BuildingType.NONE
        self.has_road = False
        self.has_power_line = False
        self.has_water_pipe = False
        self.development = 0.0
        self.residents = 0
        self.jobs = 0
        self.land_value = 1.0
        self.powered = False
        self.watered = False
        self.police_coverage = False
        self.fire_coverage = False
        self.education_coverage = False
        self.health_coverage = False
        self.fire_risk = 0
        self.traffic_load = 0
        self.crime_risk = 0
        self.on_fire = False
        self.fire_burn_time = 0.0


# ── CityStats dataclass ────────────────────────────────────────────────────────

@dataclass
class CityStats:
    """
    The city-wide scoreboard shown in the sidebar.

    Updated by the Simulation each month. The UI reads from this to display
    money, population, demands, utility levels, coverage percentages, etc.
    """
    money: int = STARTING_MONEY
    population: int = 0
    jobs: int = 0
    tax_rate: int = STARTING_TAX_RATE
    year: int = STARTING_YEAR
    month: int = STARTING_MONTH
    paused: bool = True
    last_revenue: int = 0       # revenue from the most recent month
    last_expenses: int = 0      # expenses from the most recent month
    last_population_delta: int = 0   # change in population last month
    last_job_delta: int = 0
    demand_residential: int = 50   # 0-100; drives how fast residential zones grow
    demand_commercial: int = 50
    demand_industrial: int = 50
    power_capacity: int = 0
    power_usage: int = 0
    power_satisfaction: int = 0    # percent of demand that is met
    unpowered_zones: int = 0
    powered_tiles: int = 0
    water_capacity: int = 0
    water_usage: int = 0
    water_satisfaction: int = 0
    unwatered_zones: int = 0
    watered_tiles: int = 0
    service_score: int = 0         # composite 0-100 coverage score
    fire_coverage_percent: int = 0
    fire_uncovered_zones: int = 0
    average_fire_risk: int = 0
    police_coverage_percent: int = 0
    police_uncovered_zones: int = 0
    average_crime_risk: int = 0
    education_coverage_percent: int = 0
    health_coverage_percent: int = 0
    milestone_pop: int = 0         # highest population milestone already awarded
    rev_residential: int = 0       # revenue breakdown for the budget panel
    rev_commercial: int = 0
    rev_industrial: int = 0
    exp_roads: int = 0             # expense breakdown
    exp_utilities: int = 0
    exp_buildings: int = 0
    exp_recreation: int = 0
    # The advisor message feed — last 5 messages are kept.
    messages: list[str] = field(default_factory=lambda: ["Game starts paused. Press Space or Run."])

    def clamp_tax_rate(self) -> None:
        """Keeps tax rate within the allowed 1-20 percent range."""
        self.tax_rate = max(MIN_TAX_RATE, min(MAX_TAX_RATE, self.tax_rate))

    def change_tax_rate(self, amount: int) -> None:
        """Adjusts tax rate by amount then clamps it to the legal range."""
        self.tax_rate += amount
        self.clamp_tax_rate()

    def advance_month(self) -> None:
        """Increments the in-game calendar by one month, rolling over December to January."""
        self.month += 1
        if self.month > 12:
            self.month = 1
            self.year += 1

    def add_message(self, message: str) -> None:
        """Appends a message to the advisor feed, ignoring duplicates and keeping only the last 5."""
        if self.messages and self.messages[-1] == message:
            return
        self.messages.append(message)
        # Only keep the five most recent messages to avoid the feed growing forever.
        self.messages = self.messages[-5:]

    def demand_for(self, zone: ZoneType) -> int:
        """Returns the current demand value (0-100) for the given zone type."""
        if zone == ZoneType.RESIDENTIAL:
            return self.demand_residential
        if zone == ZoneType.COMMERCIAL:
            return self.demand_commercial
        if zone == ZoneType.INDUSTRIAL:
            return self.demand_industrial
        return 0
