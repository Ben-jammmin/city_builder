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


class ZoneType(Enum):
    EMPTY = "empty"
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"


class BuildingType(Enum):
    NONE = "none"
    POWER_PLANT = "power_plant"
    WATER_TOWER = "water_tower"
    POLICE = "police"
    FIRE = "fire"
    SCHOOL = "school"


class Tool(Enum):
    INSPECT = "inspect"
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    ROAD = "road"
    POWER_LINE = "power_line"
    WATER_PIPE = "water_pipe"
    POWER_PLANT = "power_plant"
    WATER_TOWER = "water_tower"
    POLICE = "police"
    FIRE = "fire"
    SCHOOL = "school"
    BULLDOZE = "bulldoze"


ZONE_LABELS = {
    ZoneType.EMPTY: "Empty",
    ZoneType.RESIDENTIAL: "Residential",
    ZoneType.COMMERCIAL: "Commercial",
    ZoneType.INDUSTRIAL: "Industrial",
}

BUILDING_LABELS = {
    BuildingType.NONE: "None",
    BuildingType.POWER_PLANT: "Power Plant",
    BuildingType.WATER_TOWER: "Water Tower",
    BuildingType.POLICE: "Police",
    BuildingType.FIRE: "Fire",
    BuildingType.SCHOOL: "School",
}

TOOL_LABELS = {
    Tool.INSPECT: "Inspect",
    Tool.RESIDENTIAL: "Residential",
    Tool.COMMERCIAL: "Commercial",
    Tool.INDUSTRIAL: "Industrial",
    Tool.ROAD: "Road",
    Tool.POWER_LINE: "Power Line",
    Tool.WATER_PIPE: "Water Pipe",
    Tool.POWER_PLANT: "Power Plant",
    Tool.WATER_TOWER: "Water Tower",
    Tool.POLICE: "Police",
    Tool.FIRE: "Fire",
    Tool.SCHOOL: "School",
    Tool.BULLDOZE: "Bulldoze",
}

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
}

MENU_TOOLS = {
    "Zones": [
        Tool.INSPECT,
        Tool.RESIDENTIAL,
        Tool.COMMERCIAL,
        Tool.INDUSTRIAL,
        Tool.BULLDOZE,
    ],
    "Utilities": [
        Tool.ROAD,
        Tool.POWER_LINE,
        Tool.WATER_PIPE,
        Tool.POWER_PLANT,
        Tool.WATER_TOWER,
    ],
    "Services": [
        Tool.POLICE,
        Tool.FIRE,
        Tool.SCHOOL,
        Tool.BULLDOZE,
    ],
}

MENU_ORDER = list(MENU_TOOLS.keys())
TOOL_ORDER = [tool for tools in MENU_TOOLS.values() for tool in tools]

TOOL_TO_BUILDING = {
    Tool.POWER_PLANT: BuildingType.POWER_PLANT,
    Tool.WATER_TOWER: BuildingType.WATER_TOWER,
    Tool.POLICE: BuildingType.POLICE,
    Tool.FIRE: BuildingType.FIRE,
    Tool.SCHOOL: BuildingType.SCHOOL,
}


def menu_for_tool(tool: Tool) -> str:
    for menu_name, tools in MENU_TOOLS.items():
        if tool in tools:
            return menu_name
    return MENU_ORDER[0]


@dataclass
class Tile:
    zone: ZoneType = ZoneType.EMPTY
    building: BuildingType = BuildingType.NONE
    has_road: bool = False
    has_power_line: bool = False
    has_water_pipe: bool = False
    development: float = 0.0
    residents: int = 0
    jobs: int = 0
    land_value: float = 1.0
    powered: bool = False
    watered: bool = False
    police_coverage: bool = False
    fire_coverage: bool = False
    education_coverage: bool = False

    @property
    def is_empty(self) -> bool:
        return (
            self.zone == ZoneType.EMPTY
            and self.building == BuildingType.NONE
            and not self.has_road
            and not self.has_power_line
            and not self.has_water_pipe
        )

    def clear(self) -> None:
        self.zone = ZoneType.EMPTY
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


@dataclass
class CityStats:
    money: int = STARTING_MONEY
    population: int = 0
    jobs: int = 0
    tax_rate: int = STARTING_TAX_RATE
    year: int = STARTING_YEAR
    month: int = STARTING_MONTH
    paused: bool = True
    last_revenue: int = 0
    last_expenses: int = 0
    last_population_delta: int = 0
    last_job_delta: int = 0
    demand_residential: int = 50
    demand_commercial: int = 50
    demand_industrial: int = 50
    power_capacity: int = 0
    power_usage: int = 0
    water_capacity: int = 0
    water_usage: int = 0
    service_score: int = 0
    powered_tiles: int = 0
    watered_tiles: int = 0
    messages: list[str] = field(default_factory=lambda: ["Game starts paused. Press Space or Run."])

    def clamp_tax_rate(self) -> None:
        self.tax_rate = max(MIN_TAX_RATE, min(MAX_TAX_RATE, self.tax_rate))

    def change_tax_rate(self, amount: int) -> None:
        self.tax_rate += amount
        self.clamp_tax_rate()

    def advance_month(self) -> None:
        self.month += 1
        if self.month > 12:
            self.month = 1
            self.year += 1

    def add_message(self, message: str) -> None:
        if self.messages and self.messages[-1] == message:
            return
        self.messages.append(message)
        self.messages = self.messages[-5:]

    def demand_for(self, zone: ZoneType) -> int:
        if zone == ZoneType.RESIDENTIAL:
            return self.demand_residential
        if zone == ZoneType.COMMERCIAL:
            return self.demand_commercial
        if zone == ZoneType.INDUSTRIAL:
            return self.demand_industrial
        return 0
