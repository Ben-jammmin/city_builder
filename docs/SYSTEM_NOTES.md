# System Notes

These notes explain how the main game systems work. The goal is to keep each system simple enough to understand, test, and improve one piece at a time.

## How to Improve Any System

Use this pattern when adding or changing a system:

1. Add or update the data in `citybuilder/models.py`.
2. Add map rules or helper methods in `citybuilder/city_map.py`.
3. Add monthly behavior in `citybuilder/simulation.py`.
4. Add visuals in `citybuilder/renderer.py`.
5. Add sidebar or tile details in `citybuilder/ui.py`.
6. Add save/load fields in `citybuilder/save_load.py`.
7. Add focused tests in `tests/`.
8. Update this notes file and the README if players need to know about it.

## Terrain and Demolition

Main files:

- `citybuilder/terrain.py`
- `citybuilder/city_map.py`
- `citybuilder/game.py`

The map has four terrain types generated during city creation:

- Grass (buildable)
- Water (blocks construction, must be cleared to build)
- Forest (can be cleared for land)
- Hills (buildable but can be flattened)

**Terrain Demolition**: Use the bulldoze tool (key `9`) to demolish terrain:

- **Water**: $50 per tile
- **Forest**: $15 per tile
- **Hills**: $25 per tile
- **Grass**: Cannot bulldoze (already clear)

First, bulldoze clears any man-made structures (zones, roads, utilities, buildings). Once a tile is empty, the next bulldoze will clear the terrain to grass.

Good next improvements:

- Add different clearing time for different terrain types
- Add erosion or flooding that recreates water
- Add terrain features (mountains, canyons) that affect water flow

Main files:

- `citybuilder/models.py`
- `citybuilder/city_map.py`

The map is a grid of `Tile` objects. Each tile stores its own state:

- terrain type
- zone type
- building type
- road/power/water line flags
- development amount
- residents and jobs
- service coverage
- risk values

`CityMap` owns placement rules. For example, it decides whether a road, zone, utility line, or building can be placed on a tile.

The map has small `can_place_*` helper methods for placement rules:

- `can_place_zone()`
- `can_place_road()`
- `can_place_power_line()`
- `can_place_water_pipe()`
- `can_place_building()`

The actual `place_*` methods call those helpers, then make the change if allowed. This keeps the rule check and the action easy to read.

Good next improvements:

- Add placement costs based on terrain.
- Add clearer reasons for every blocked placement, not just water.

## Roads

Main files:

- `citybuilder/city_map.py`
- `citybuilder/renderer.py`

Roads are stored with `tile.has_road`.

The helper `CityMap.road_connections(x, y)` checks the four neighboring tiles and returns which directions connect:

- north
- east
- south
- west

The renderer uses those connections to draw dead ends, straight roads, corners, T-junctions, and intersections.

Roads matter because zones need an adjacent road before they can grow.

Roads cannot be placed on water terrain.

Good next improvements:

- Add road maintenance by road type.
- Add bridges when terrain generation adds rivers.
- Add bridges across water.
- Add traffic later, after population and jobs are more advanced.

## Power

Main files:

- `citybuilder/models.py`
- `citybuilder/city_map.py`
- `citybuilder/simulation.py`
- `citybuilder/renderer.py`
- `citybuilder/ui.py`

Power plants are buildings. Power lines are stored with `tile.has_power_line`.

The helper `CityMap.power_connections(x, y)` checks whether a power line connects to neighboring power lines or power plants.

The simulation builds a connected power network starting from power plants. A zone is powered if it touches that network.

Tracked city stats:

- `power_capacity`
- `power_usage`
- `power_satisfaction`
- `powered_tiles`
- `unpowered_zones`

Zones need power before they can grow.

Good next improvements:

- Add multiple power plant types.
- Add pollution from power plants.
- Add power line upkeep or power outages.
- Add an overlay mode that highlights powered and unpowered tiles.

## Water

Main files:

- `citybuilder/models.py`
- `citybuilder/city_map.py`
- `citybuilder/simulation.py`
- `citybuilder/renderer.py`
- `citybuilder/ui.py`

Water towers are buildings. Water pipes are stored with `tile.has_water_pipe`.

The helper `CityMap.water_connections(x, y)` checks whether a pipe connects to neighboring pipes or water towers.

The simulation builds a connected water network starting from water towers. A zone is watered if it touches that network.

Tracked city stats:

- `water_capacity`
- `water_usage`
- `water_satisfaction`
- `watered_tiles`
- `unwatered_zones`

Zones need water before they can grow.

Good next improvements:

- Add pumps that must be near water terrain.
- Add water pollution later.
- Add pipe cost based on terrain.
- Add an overlay mode that highlights watered and unwatered tiles.

## Fire Stations

Main files:

- `citybuilder/models.py`
- `citybuilder/simulation.py`
- `citybuilder/ui.py`
- `citybuilder/renderer.py`

Fire stations are service buildings. A fire station covers tiles within `FIRE_RADIUS`.

Each zoned tile gets a `fire_risk` score from 0 to 100.

Fire risk goes up when:

- the tile is developed
- the zone is industrial or commercial
- industrial zones are nearby
- the tile has no fire coverage
- the tile has no water
- the tile has no adjacent road

Fire risk goes down when:

- the tile is covered by a fire station

Tracked city stats:

- `fire_coverage_percent`
- `fire_uncovered_zones`
- `average_fire_risk`

Good next improvements:

- Add actual fire events when risk is high.
- Let fire stations respond along roads.
- Add fire station capacity or monthly upkeep effects.
- Add a fire overlay.

## Police Stations

Main files:

- `citybuilder/models.py`
- `citybuilder/simulation.py`
- `citybuilder/ui.py`
- `citybuilder/renderer.py`

Police stations are service buildings. A police station covers tiles within `POLICE_RADIUS`.

Each zoned tile gets a `crime_risk` score from 0 to 100.

Crime risk goes up when:

- the tile is developed
- the zone is commercial or industrial
- commercial zones are nearby
- the tile has no police coverage
- the tile has no adjacent road
- taxes are very high

Crime risk goes down when:

- the tile is covered by a police station

Tracked city stats:

- `police_coverage_percent`
- `police_uncovered_zones`
- `average_crime_risk`

Good next improvements:

- Add actual crime events.
- Let police coverage follow roads instead of simple radius.
- Add police station capacity.
- Add a crime overlay.

## Services Score

Main files:

- `citybuilder/simulation.py`
- `citybuilder/ui.py`

The service score is a simple summary of police, fire, and school coverage.

Each zoned tile can have:

- police coverage
- fire coverage
- education coverage

The service score is the percentage of those service needs being met across all zoned tiles.

Good next improvements:

- Split the service score into separate bars.
- Make service quality affect demand more clearly.
- Add more service buildings, like hospitals or parks.

## Zoning and Growth

Main file:

- `citybuilder/simulation.py`

Zones develop during the monthly simulation.

A zone grows only when:

- it has an adjacent road
- it has power
- it has water

Growth is affected by:

- demand
- taxes
- land value
- utility capacity

Zone outputs:

- residential zones create residents
- commercial zones create jobs
- industrial zones create jobs

Good next improvements:

- Add abandonment when services are bad.
- Add more detailed demand formulas.
- Add pollution and land value effects.
- Add density levels.

## Demand

Main files:

- `citybuilder/models.py`
- `citybuilder/simulation.py`
- `citybuilder/ui.py`

Demand is stored as three percentages:

- `demand_residential`
- `demand_commercial`
- `demand_industrial`

Demand is recalculated each month using simple formulas based on:

- population
- jobs
- taxes
- service score
- utility capacity

Good next improvements:

- Show what is helping or hurting demand.
- Add separate demand factors for crime, fire risk, and education.
- Add charts or history.

## Economy

Main files:

- `citybuilder/models.py`
- `citybuilder/simulation.py`
- `citybuilder/settings.py`

Money changes every simulated month.

Revenue comes from:

- population
- jobs
- tax rate

Expenses come from:

- roads
- zones
- power lines
- water pipes
- service buildings

Good next improvements:

- Show a fuller budget breakdown.
- Add loans.
- Add separate residential, commercial, and industrial tax rates.
- Add building upkeep tooltips.

## Save and Load

Main file:

- `citybuilder/save_load.py`

The save file is `savegame.json` in the project folder.

Save/load uses plain JSON so the file is easy to inspect and edit while learning.

When a new field is added to `Tile` or `CityStats`, also add it to:

- `tile_to_data()`
- `tile_from_data()`
- `stats_to_data()`
- `stats_from_data()`

Good next improvements:

- Add multiple save slots.
- Add autosave.
- Add save version migrations.

## UI Panels

Main file:

- `citybuilder/ui.py`

The sidebar is split into panels:

- city stats
- menu tabs
- controls
- demand
- systems
- tools
- tile details
- advisor messages

The UI reads from `CityStats` and the hovered tile. It should not contain simulation rules.

Good next improvements:

- Add overlays.
- Add tooltips.
- Split UI code into smaller panel classes if it gets too large.

## Map View Modes

Main files:

- `citybuilder/models.py`
- `citybuilder/game.py`
- `citybuilder/renderer.py`
- `citybuilder/ui.py`

Map view modes let the player inspect one system at a time.

Current modes:

- `Normal`: full city view
- `Power`: power plants, power lines, powered zones, unpowered zones
- `Water`: water towers, water pipes, watered zones, unwatered zones
- `Fire`: fire stations, fire coverage, fire risk
- `Police`: police stations, police coverage, crime risk
- `Terrain`: grass, water, forests, hills, and light city context

Non-normal views still draw a small amount of context:

- roads show as faint dark connection lines
- active system buildings draw as full tiles
- other service buildings draw as small labeled markers

This keeps the overlay readable while still letting the player see where buildings are when routing power lines, pipes, or checking service coverage.

The current view is stored in `Game.view_mode`. It is not saved because it is only a viewing preference, not city data.

The `V` key cycles views forward. `Shift+V` cycles backward.

When adding a new view:

1. Add it to `ViewMode`, `VIEW_LABELS`, and `VIEW_ORDER` in `models.py`.
2. Add drawing logic in `renderer.py`.
3. Pass any needed state from `game.py`.
4. Show the view name in `ui.py`.
5. Add tests for the new model entries or helper logic.

## Renderer

Main file:

- `citybuilder/renderer.py`

The renderer draws the map. It should only care about visual presentation.

It currently draws:

- terrain
- terrain base color
- roads
- zones
- buildings
- power lines
- water pipes
- utility/service warning markers
- hover outlines
- system-specific map views
- context roads and building markers inside system views

Good next improvements:

- Add terrain art.
- Add simple animations for development or warnings.

## Terrain Generation

Main files:

- `citybuilder/models.py`
- `citybuilder/terrain.py`
- `citybuilder/city_map.py`
- `citybuilder/renderer.py`
- `citybuilder/save_load.py`

Terrain is stored on each tile as `tile.terrain`.

Current terrain types:

- `Grass`: normal buildable land
- `Water`: blocks zones, roads, utility lines, and buildings
- `Forest`: buildable, but construction clears it to grass
- `Hill`: buildable land that can later get special costs or rules

The new city generator starts with grass, draws a simple winding river, then adds forest and hill patches.

After that, it clears a starter area near the first camera view. This gives the player a reliable place to begin building even if the river or hills generated nearby.

The first version keeps the rules simple:

- `CityMap.can_place_*` helpers own the construction rules
- bulldozing clears city construction but keeps the terrain
- building on forest clears that tile to grass
- clicking water with a build tool gives an advisor message
- water stays visible in system views so planning is easier
- save/load stores terrain so the map does not change when loaded

Good next improvements:

- Add a terrain brush or regenerate-map button.
- Make hills cost more to build on.
- Add bridges or tunnels.
- Make pumps require nearby water terrain.
- Add parks, trees, or land value bonuses for natural land.
