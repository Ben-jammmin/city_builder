# Isometric Sprite Style Guide

This project can move toward a late-90s isometric city-builder look without copying assets from SimCity 3000 or any other game.

## Target Look

- Original 2:1 isometric pixel art.
- Transparent PNG sprites anchored to a diamond tile footprint.
- Buildings should have visible left and right faces, a roof plane, and a clear shadow.
- Use muted wall colors, darker shaded faces, bright but tiny windows, and small rooftop details.
- Make several variants per zone, stage, and density so neighborhoods do not repeat too obviously.

## Sprite Sizes

Recommended source sizes:

- Terrain/roads: `64x32` or `128x64` diamond sprites.
- Small buildings: `64x96`.
- Tall/dense buildings: `96x128`.
- Civic buildings: `96x128`.
- Pedestrians: `24x32`.

Keep the bottom center of each building aligned to the bottom center of the tile diamond.

## File Names

The game already has an optional image-sprite hook for buildings, civic buildings, and pedestrians. Enable it with `USE_IMAGE_SPRITES = True` in `citybuilder/settings.py` after adding proper isometric assets.

Buildings:

```text
assets/buildings/residential_1_0.png
assets/buildings/residential_2_0.png
assets/buildings/residential_3_0.png
assets/buildings/residential_4_0.png
assets/buildings/residential_tier2_4_0.png
assets/buildings/commercial_4_0.png
assets/buildings/commercial_tier2_4_0.png
assets/buildings/industrial_4_0.png
```

Civic:

```text
assets/civic/power_plant.png
assets/civic/large_power_plant.png
assets/civic/water_tower.png
assets/civic/large_water_tower.png
assets/civic/police.png
assets/civic/fire.png
assets/civic/school.png
assets/civic/train_station.png
assets/civic/airport.png
```

Pedestrians:

```text
assets/pedestrians/pedestrian_0.png
assets/pedestrians/pedestrian_1.png
assets/pedestrians/pedestrian_2.png
```

## Good Workflow

1. Draw one full residential set first: stages 1-4, variants 0-3.
2. Turn on `USE_IMAGE_SPRITES`.
3. Run `python -B tools/codex_smoke_test.py --screenshots smoke_screenshots`.
4. Inspect `after_all_tools.png`, `view_power.png`, and `view_water.png`.
5. Only then build out commercial, industrial, civic, and pedestrian sprites.

## What To Avoid

- Do not rip or trace copyrighted game sprites.
- Do not use flat square top-down tiles on the isometric map.
- Do not leave opaque backgrounds in PNGs.
- Do not make every building the same height or color.
