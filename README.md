# Python/Pygame City Builder Prototype

A small city-builder prototype inspired by SimCity 3000. It has a scrollable grid map, generated terrain, zoning, roads, money, population, taxes, power, water, services, transport buildings, demand bars, save/load, pedestrians, and a basic monthly simulation loop.

## Run it

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

If Pygame is already installed, you can run `python main.py` directly from this folder.

New cities start paused so you can look around and build before time begins. Press `Space` or the `Run` button to start the simulation.

New cities start with generated terrain: grass, water, forests, and hills. Water blocks construction. Forest and hill terrain must be cleared before placing zones or buildings. Use the bulldoze tool to clear terrain:
- **Water**: $50 per tile
- **Forest**: $15 per tile  
- **Hills**: $25 per tile

The starting view keeps a clear buildable area to begin with.

## Run tests

The tests use Python's built-in `unittest` module, so there is no extra test dependency.

```powershell
python -B -m unittest discover
```

## System notes

For beginner-friendly notes on how each system works and how to improve it, read:

```text
docs/SYSTEM_NOTES.md
```

## Controls

- `WASD` or arrow keys: move the camera
- Mouse wheel: zoom
- Left mouse: paint with the selected tool
- Right mouse: bulldoze
- Middle mouse drag: pan the camera
- `0`: inspect
- `1`: residential zone
- `2`: commercial zone
- `3`: industrial zone
- `4`: road
- `5`: power line
- `6`: water pipe
- `7`: power plant
- `8`: water tower
- `9`: bulldoze tool
- `P`: police station
- `F`: fire station
- `H`: school
- `T`: train station
- `A`: airport
- `Space`: pause or resume
- `F11`: toggle fullscreen
- `Alt+Enter`: toggle fullscreen
- `Full` / `Window` button: toggle fullscreen
- `V`: cycle map view mode
- `Shift+V`: cycle map view mode backward
- `+` / `-`: adjust taxes
- `F5`: save
- `F9`: load

## Map views

Press `V` to cycle through system views:

- `Normal`: full city view with roads, zones, buildings, utilities, and warnings
- `Power`: shows power plants, power lines, powered zones, and unpowered zones
- `Water`: shows water towers, water pipes, watered zones, and unwatered zones
- `Fire`: shows fire stations, fire coverage, and fire risk
- `Police`: shows police stations, police coverage, and crime risk
- `Terrain`: shows grass, water, forests, hills, and light city context

System views keep faint roads and small markers for every service building visible, so you can plan hookups and coverage without losing track of the city layout.

## Sprite assets

The game now supports optional PNG sprites. It still runs with no image files because procedural sprites are used as a fallback.

To replace the generated art, add square PNGs under `assets/`. See `assets/README.md` for the exact filenames for terrain, roads, zones, buildings, utilities, and pedestrians.

The included starter pack can be regenerated with:

```powershell
python -B tools/generate_pixel_assets.py
```

## Menus and panels

The right sidebar has four tool menus:

- `Zones`: inspect, residential, commercial, industrial, bulldoze
- `Utilities`: roads, power lines, water pipes, power plants, water towers
- `Services`: police, fire, schools, bulldoze
- `Transport`: train stations, airports

It also shows:

- city money, population, jobs, and date
- save/load, pause, and tax controls
- residential, commercial, and industrial demand bars
- power and water capacity/usage
- service coverage score
- selected tile details
- advisor messages

The `Zones` menu includes standard and dense residential/commercial zones. Dense zones cost more to place and grow a little slower, but they support more residents or jobs once developed.

The `Utilities` menu includes standard and large power/water buildings. Large power plants and large water towers cost more and have higher upkeep, but provide much more capacity.

## How the simulation works

Every simulated month:

- Roads automatically connect visually to neighboring road tiles.
- Water terrain blocks zones, roads, utility lines, and buildings.
- Forest and hill terrain must be bulldozed before placing zones or buildings.
- Roads and utility lines can be built on non-water terrain.
- If you try to build on water, the advisor explains why it failed.
- Zoned tiles grow only when they are next to a road.
- Zones also need power and water to develop.
- Residential zones create population.
- Commercial and industrial zones create jobs.
- Dense residential and dense commercial zones cost more and support more people or jobs.
- Lower taxes encourage growth, while very high taxes slow development.
- Roads, zones, utility lines, and service buildings have maintenance costs.
- Population and jobs generate tax revenue.
- Power plants and water towers create utility capacity.
- Large power plants and large water towers provide more utility capacity with higher maintenance.
- Power lines and water pipes connect nearby zones to those systems.
- Power lines automatically connect visually to neighboring power lines and power plants.
- The Systems panel shows power usage, capacity, supply percent, and unpowered zones.
- Water pipes automatically connect visually to neighboring water pipes and water towers.
- The Systems panel shows water usage, capacity, supply percent, and unwatered zones.
- Fire stations provide local fire coverage.
- The Systems panel shows fire coverage percent and average fire risk.
- Tiles show fire risk in the inspector, and high-risk zones get a small red marker on the map.
- Police stations provide local police coverage.
- The Systems panel shows police coverage percent and average crime risk.
- Tiles show crime risk in the inspector, and high-crime zones get a small blue marker on the map.
- Police, fire, and schools improve service coverage and land value.
- Train stations and airports raise city demand, with the strongest effect on commercial and industrial growth.
- Pedestrians appear on the map as population grows.

## Save files

The game saves to `savegame.json` in this project folder. The save is plain JSON so it is easy to inspect while learning.

The code is split into beginner-friendly modules:

- `main.py`: starts the game
- `citybuilder/game.py`: main loop and input handling
- `citybuilder/city_map.py`: grid and tile placement rules
- `citybuilder/simulation.py`: monthly city growth and budget logic
- `citybuilder/save_load.py`: JSON save/load helpers
- `citybuilder/renderer.py`: map drawing
- `citybuilder/sprites.py`: generated sprite-style tile art and asset naming
- `citybuilder/asset_loader.py`: optional PNG sprite loading and scaling
- `citybuilder/ui.py`: sidebar and HUD
- `citybuilder/pedestrian.py`: simple pedestrian movement
- `citybuilder/terrain.py`: simple terrain generation
- `citybuilder/models.py`: shared data classes and enums
- `citybuilder/settings.py`: constants and colors
