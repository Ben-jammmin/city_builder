# Python/Pygame City Builder Prototype

A small city-builder prototype inspired by SimCity 3000. It has a scrollable grid map, zoning, roads, money, population, taxes, power, water, services, demand bars, save/load, and a basic monthly simulation loop.

## Run it

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

If Pygame is already installed, you can run `python main.py` directly from this folder.

New cities start paused so you can look around and build before time begins. Press `Space` or the `Run` button to start the simulation.

## Run tests

The tests use Python's built-in `unittest` module, so there is no extra test dependency.

```powershell
python -m unittest discover
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
- `Space`: pause or resume
- `F11`: toggle fullscreen
- `Alt+Enter`: toggle fullscreen
- `Full` / `Window` button: toggle fullscreen
- `+` / `-`: adjust taxes
- `F5`: save
- `F9`: load

## Menus and panels

The right sidebar has three tool menus:

- `Zones`: inspect, residential, commercial, industrial, bulldoze
- `Utilities`: roads, power lines, water pipes, power plants, water towers
- `Services`: police, fire, schools, bulldoze

It also shows:

- city money, population, jobs, and date
- save/load, pause, and tax controls
- residential, commercial, and industrial demand bars
- power and water capacity/usage
- service coverage score
- selected tile details
- advisor messages

## How the simulation works

Every simulated month:

- Zoned tiles grow only when they are next to a road.
- Zones also need power and water to develop.
- Residential zones create population.
- Commercial and industrial zones create jobs.
- Lower taxes encourage growth, while very high taxes slow development.
- Roads, zones, utility lines, and service buildings have maintenance costs.
- Population and jobs generate tax revenue.
- Power plants and water towers create utility capacity.
- Power lines and water pipes connect nearby zones to those systems.
- Police, fire, and schools improve service coverage and land value.

## Save files

The game saves to `savegame.json` in this project folder. The save is plain JSON so it is easy to inspect while learning.

The code is split into beginner-friendly modules:

- `main.py`: starts the game
- `citybuilder/game.py`: main loop and input handling
- `citybuilder/city_map.py`: grid and tile placement rules
- `citybuilder/simulation.py`: monthly city growth and budget logic
- `citybuilder/save_load.py`: JSON save/load helpers
- `citybuilder/renderer.py`: map drawing
- `citybuilder/ui.py`: sidebar and HUD
- `citybuilder/models.py`: shared data classes and enums
- `citybuilder/settings.py`: constants and colors
