# City Builder Sprite Assets

The game uses this generated PNG pack for buildings, civic buildings, and pedestrians. It can still run with no image files because `citybuilder/sprites.py` draws procedural fallback art.

Building and civic sprites are transparent, bottom-centered isometric PNGs based on `docs/SPRITE_STYLE_GUIDE.md`. Terrain, roads, utilities, zone bases, overlays, and warnings remain procedural in the renderer.

The PNG hook is controlled by `USE_IMAGE_SPRITES` in `citybuilder/settings.py`.

This folder includes a generated starter pack. To rebuild it, run:

```powershell
python -B tools/generate_pixel_assets.py
```

## Terrain

- `terrain/grass_0.png`
- `terrain/grass_1.png`
- `terrain/grass_2.png`
- `terrain/grass_3.png`
- `terrain/grass.png` fallback used if a grass variant is missing
- `terrain/water.png`
- `terrain/forest_0.png`
- `terrain/forest_1.png`
- `terrain/forest.png` fallback used if a forest variant is missing
- `terrain/hill.png`

## Zones

Zone images are base lots. Building overlays are loaded separately when zones develop.

- `zones/residential.png`
- `zones/residential_tier2.png`
- `zones/commercial.png`
- `zones/commercial_tier2.png`
- `zones/industrial.png`

## Zone Buildings

Use this pattern:

```text
buildings/{zone}_{stage}_{variant}.png
```

- `{zone}` is `residential`, `commercial`, or `industrial`
- `{stage}` is `1`, `2`, `3`, or `4`
- `{variant}` is `0`, `1`, `2`, or `3`

Examples:

- `buildings/residential_1_0.png`
- `buildings/commercial_3_2.png`
- `buildings/industrial_4_1.png`

Dense residential and commercial use this pattern:

```text
buildings/{zone}_tier2_{stage}_{variant}.png
```

Examples:

- `buildings/residential_tier2_2_0.png`
- `buildings/commercial_tier2_4_3.png`

## Civic Buildings

- `civic/power_plant.png`
- `civic/large_power_plant.png`
- `civic/water_tower.png`
- `civic/large_water_tower.png`
- `civic/police.png`
- `civic/fire.png`
- `civic/school.png`
- `civic/train_station.png`
- `civic/airport.png`

## Roads and Utilities

Road and utility connections use a four-digit mask in north, east, south, west order.

- `1` means connected
- `0` means not connected

Examples:

- `roads/road_1010.png` is a north-south road
- `roads/road_0101.png` is an east-west road
- `roads/road_1111.png` is a four-way intersection
- `utilities/power_1100.png` connects north and east
- `utilities/water_0011.png` connects south and west

For a complete set, add:

- `roads/road_0000.png` through `roads/road_1111.png`
- `utilities/power_0000.png` through `utilities/power_1111.png`
- `utilities/water_0000.png` through `utilities/water_1111.png`

## Pedestrians

- `pedestrians/pedestrian_0.png`
- `pedestrians/pedestrian_1.png`
- `pedestrians/pedestrian_2.png`
