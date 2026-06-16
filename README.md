# Python / Pygame City Builder

A city-builder game inspired by SimCity 3000. Build zones, roads, power and water utilities, service buildings, and watch your city grow month by month. The game runs in an isometric (angled top-down) view you can pan, zoom, and rotate.

---

## How to Run

**First time setup** (only needed once):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Start the game:**
```powershell
python main.py
```

If you already have `pygame` installed, just run `python main.py` directly.

> **Tip:** New cities start paused so you can look around and plan. Press `Space` or click **Run** to start the simulation.

---

## Controls

| Key / Mouse | Action |
|---|---|
| `WASD` or arrow keys | Move the camera |
| Mouse wheel | Zoom in / out |
| Left click & drag | Paint with the selected tool |
| Right click & drag | Bulldoze tiles |
| Middle mouse drag | Pan the camera |
| `Q` / `E` | Rotate the map view left / right |
| `Space` | Pause or resume the simulation |
| `V` | Cycle through map view modes |
| `Shift+V` | Cycle map views backward |
| `+` / `-` | Raise / lower tax rate |
| `F5` | Open save panel |
| `F9` | Open load panel |
| `F11` or `Alt+Enter` | Toggle fullscreen |
| `Esc` | Close open panel / return to menu |

**Build tool hotkeys:**

| Key | Tool |
|---|---|
| `0` | Inspect tile |
| `1` | Residential zone |
| `2` | Commercial zone |
| `3` | Industrial zone |
| `4` | Road |
| `5` | Power line |
| `6` | Water pipe |
| `7` | Power plant |
| `8` | Water tower |
| `9` | Bulldoze |
| `P` | Police station |
| `F` | Fire station |
| `H` | School |
| `J` | Hospital |
| `T` | Train station |
| `A` | Airport |

---

## How to Play

### 1. Zone land
Place **Residential**, **Commercial**, and **Industrial** zones on grass tiles. Zones only grow if they are next to a **road**, connected to **power** and **water**, and the city has demand for that zone type.

### 2. Build roads
Roads connect zones to the city. Every zone tile needs at least one adjacent road tile to develop.

### 3. Add utilities
- Place a **Power Plant** and run **Power Lines** to your zones.
- Place a **Water Tower** and run **Water Pipes** to your zones.
Without power and water, zones will develop slowly.

### 4. Add services
- **Police stations** reduce crime.
- **Fire stations** reduce fire risk and put out fires faster.
- **Schools** boost growth in nearby zones.
- **Hospitals** provide a bonus growth multiplier.
- **Train stations** and **Airports** boost commercial and industrial demand across the whole city.

### 5. Watch your budget
Each month, population and jobs pay taxes. Roads, zones, utility lines, and buildings all have maintenance costs. Keep your income above your expenses or the city will go into debt.

---

## Terrain

New cities have procedurally generated terrain: grass, water, forests, and hills.

| Terrain | Rule | Bulldoze cost |
|---|---|---|
| Water | Cannot build on it at all | $50 per tile |
| Forest | Must be cleared before placing zones or buildings | $15 per tile |
| Hill | Must be cleared before placing zones or buildings | $25 per tile |

Roads and utility lines can be built on forest and hill terrain without clearing first.

---

## Map Views

Press `V` to cycle through these views:

| View | What it shows |
|---|---|
| Normal | Full city — zones, buildings, roads, utilities |
| Power | Power plants, lines, and which zones are powered (yellow = powered, red = no power) |
| Water | Water towers, pipes, and which zones have water (blue = watered, red = no water) |
| Fire | Fire stations, coverage radius, and fire risk per tile |
| Police | Police stations, coverage radius, and crime risk per tile |
| Terrain | Raw terrain without zone/building overlays |

---

## Saving and Loading

Press **F5** to open the save panel and choose one of 5 slots. Press **F9** to open the load panel. Each slot shows the city's year, population, money, and map size so you can tell them apart at a glance.

Save files are stored in the `saves/` folder as plain JSON, so you can open them in any text editor and see exactly what is stored.

---

## Dense Zones

The Zones menu includes **Dense Residential** and **Dense Commercial** options. Dense zones:
- Cost more to place (3× the standard price)
- Grow a little slower
- Hold significantly more residents or jobs once fully developed

Use dense zones in the city core once you have strong utility coverage and services.

---

## Code Tour (for developers / learners)

The code is split into focused modules. Start here if you want to understand or modify the game:

| File | What it does |
|---|---|
| `main.py` | Entry point — starts the menu and game loop |
| `citybuilder/settings.py` | **All tunable numbers in one place** — costs, speeds, colors, map size |
| `citybuilder/models.py` | Data classes: `Tile`, `CityStats`, enums for zones / buildings / tools |
| `citybuilder/city_map.py` | The tile grid — placement rules for zones, roads, utilities |
| `citybuilder/simulation.py` | Monthly simulation: growth, taxes, power/water, fires, crime |
| `citybuilder/game.py` | Main game loop — handles input, camera, drawing, save/load overlay |
| `citybuilder/renderer.py` | Draws the isometric map using painter's algorithm |
| `citybuilder/camera.py` | Camera pan, zoom, and 4-way rotation math |
| `citybuilder/save_load.py` | Save and load city state to/from JSON files in `saves/` |
| `citybuilder/terrain.py` | Procedural terrain generation (rivers, lakes, forests, hills) |
| `citybuilder/pedestrian.py` | Small people that walk along roads as population grows |
| `citybuilder/ui.py` | Bottom command bar layout and scroll handling |
| `citybuilder/ui_panels.py` | Individual panels: stats, systems, inspector, demand bars |
| `citybuilder/menu.py` | Main menu, new game screen, settings screen |
| `citybuilder/menu_config.py` | Options passed from the menu into the game (map size, difficulty, etc.) |
| `citybuilder/sounds.py` | Simple sound effect player |
| `citybuilder/sprites.py` | Procedural isometric tile art and PNG asset naming |
| `citybuilder/asset_loader.py` | Loads and caches optional PNG sprite files |

> **Want to tweak the game?** Start with `citybuilder/settings.py` — almost every number in the game (costs, taxes, growth rates, colors) is a named constant in that one file.

---

## Running Tests

Tests use Python's built-in `unittest` — no extra packages needed:

```powershell
python -B -m unittest discover
```

To run a full smoke test of the game loop (save/load, all build tools, views, rotation):

```powershell
python -B tools/codex_smoke_test.py
```

To also capture screenshots for visual inspection:

```powershell
python -B tools/codex_smoke_test.py --screenshots smoke_screenshots
```

---

## Regenerating Sprite Assets

The game works without any PNG files (it draws everything procedurally as a fallback). To regenerate the included pixel-art sprite pack:

```powershell
python -B tools/generate_pixel_assets.py
```

See `docs/SPRITE_STYLE_GUIDE.md` for the art direction if you want to draw your own sprites.
