from __future__ import annotations

import itertools
import math
import random
import struct
import zlib
from pathlib import Path


SIZE = 64
ROOT = Path(__file__).resolve().parent.parent / "assets"


Color = tuple[int, int, int, int]


def rgba(color: tuple[int, int, int], alpha: int = 255) -> Color:
    return color[0], color[1], color[2], alpha


def shift(color: Color, amount: int) -> Color:
    return (
        max(0, min(255, color[0] + amount)),
        max(0, min(255, color[1] + amount)),
        max(0, min(255, color[2] + amount)),
        color[3],
    )


class Canvas:
    def __init__(self, width: int = SIZE, height: int = SIZE, bg: Color = (0, 0, 0, 0)) -> None:
        self.width = width
        self.height = height
        self.pixels = [[bg for _ in range(width)] for _ in range(height)]

    def set(self, x: int, y: int, color: Color) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y][x] = color

    def fill(self, color: Color) -> None:
        for y in range(self.height):
            for x in range(self.width):
                self.pixels[y][x] = color

    def rect(self, x: int, y: int, w: int, h: int, color: Color) -> None:
        for py in range(y, y + h):
            for px in range(x, x + w):
                self.set(px, py, color)

    def rect_outline(self, x: int, y: int, w: int, h: int, color: Color, thickness: int = 1) -> None:
        self.rect(x, y, w, thickness, color)
        self.rect(x, y + h - thickness, w, thickness, color)
        self.rect(x, y, thickness, h, color)
        self.rect(x + w - thickness, y, thickness, h, color)

    def line(self, x0: int, y0: int, x1: int, y1: int, color: Color, thickness: int = 1) -> None:
        dx = abs(x1 - x0)
        sx = 1 if x0 < x1 else -1
        dy = -abs(y1 - y0)
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            radius = thickness // 2
            self.rect(x0 - radius, y0 - radius, max(1, thickness), max(1, thickness), color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def circle(self, cx: int, cy: int, radius: int, color: Color) -> None:
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2:
                    self.set(x, y, color)

    def ellipse(self, x: int, y: int, w: int, h: int, color: Color) -> None:
        rx = max(1, w / 2)
        ry = max(1, h / 2)
        cx = x + rx
        cy = y + ry
        for py in range(y, y + h):
            for px in range(x, x + w):
                if ((px + 0.5 - cx) / rx) ** 2 + ((py + 0.5 - cy) / ry) ** 2 <= 1:
                    self.set(px, py, color)

    def polygon(self, points: list[tuple[int, int]], color: Color) -> None:
        if not points:
            return
        min_y = max(0, min(y for _, y in points))
        max_y = min(self.height - 1, max(y for _, y in points))
        for y in range(min_y, max_y + 1):
            nodes: list[int] = []
            j = len(points) - 1
            for i, point in enumerate(points):
                xi, yi = point
                xj, yj = points[j]
                if (yi < y and yj >= y) or (yj < y and yi >= y):
                    nodes.append(int(xi + (y - yi) / (yj - yi) * (xj - xi)))
                j = i
            nodes.sort()
            for left, right in zip(nodes[0::2], nodes[1::2]):
                for x in range(left, right):
                    self.set(x, y, color)

    def paste(self, other: Canvas, x: int, y: int) -> None:
        for py in range(other.height):
            for px in range(other.width):
                color = other.pixels[py][px]
                if color[3] > 0:
                    self.set(x + px, y + py, color)


def write_png(canvas: Canvas, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = bytearray()
    for row in canvas.pixels:
        raw.append(0)
        for pixel in row:
            raw.extend(pixel)
    payload = zlib.compress(bytes(raw), level=9)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", canvas.width, canvas.height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", payload)
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def save(name: str, canvas: Canvas) -> None:
    write_png(canvas, ROOT / f"{name}.png")


def noise_fill(canvas: Canvas, base: Color, seed: int, strength: int = 8) -> None:
    rng = random.Random(seed)
    for y in range(canvas.height):
        for x in range(canvas.width):
            canvas.set(x, y, shift(base, rng.randint(-strength, strength)))


def terrain_grass(variant: int) -> Canvas:
    base = rgba((82, 135, 74))
    canvas = Canvas(bg=base)
    noise_fill(canvas, shift(base, variant * 2 - 3), 100 + variant, 7)
    rng = random.Random(20 + variant)
    for _ in range(58):
        x = rng.randrange(3, 61)
        y = rng.randrange(3, 61)
        color = rgba((96, 157, 84)) if rng.random() > 0.35 else rgba((59, 107, 62))
        canvas.line(x, y + 2, x + rng.choice((-1, 1, 2)), y, color, 1)
    if variant in (1, 3):
        for _ in range(5):
            canvas.circle(rng.randrange(8, 57), rng.randrange(8, 57), 1, rgba((220, 205, 126)))
    return canvas


def terrain_water() -> Canvas:
    canvas = Canvas()
    noise_fill(canvas, rgba((46, 105, 150)), 240, 5)
    canvas.rect_outline(0, 0, SIZE, SIZE, rgba((28, 73, 113)), 2)
    for y in (15, 29, 44):
        canvas.line(8, y, 24, y - 2, rgba((93, 163, 199)), 2)
        canvas.line(29, y - 2, 52, y, rgba((93, 163, 199)), 2)
        canvas.line(12, y + 6, 34, y + 5, rgba((58, 125, 172)), 1)
    return canvas


def terrain_forest(variant: int) -> Canvas:
    canvas = terrain_grass(variant)
    rng = random.Random(350 + variant)
    positions = [(22, 24), (42, 26), (31, 42), (15, 44), (50, 46)]
    for x, y in positions[: 4 + variant % 2]:
        trunk = rgba((87, 70, 45))
        dark = rgba((30, 77, 44))
        mid = rgba((45, 109, 58))
        light = rgba((75, 146, 75))
        canvas.rect(x - 2, y + 7, 4, 11, trunk)
        canvas.circle(x, y, rng.randrange(7, 10), dark)
        canvas.circle(x - 3, y - 3, 5, mid)
        canvas.circle(x - 5, y - 5, 2, light)
    return canvas


def terrain_hill() -> Canvas:
    canvas = terrain_grass(2)
    canvas.polygon([(7, 48), (30, 15), (57, 48)], rgba((102, 108, 92)))
    canvas.polygon([(13, 46), (31, 20), (36, 46)], rgba((136, 139, 117)))
    canvas.line(30, 15, 57, 48, rgba((69, 76, 68)), 2)
    canvas.line(19, 37, 43, 37, rgba((152, 153, 130)), 2)
    canvas.line(24, 29, 38, 29, rgba((152, 153, 130)), 1)
    return canvas


def zone_tile(kind: str, level: int = 1) -> Canvas:
    colors = {
        "residential": rgba((85, 158, 90)),
        "commercial": rgba((74, 122, 190)),
        "industrial": rgba((192, 153, 62)),
    }
    base = terrain_grass({"residential": 0, "commercial": 1, "industrial": 2}[kind])
    color = colors[kind]
    base.rect(7, 7, 50, 50, shift(color, -28))
    inset = 11 if level == 1 else 8
    base.rect(inset, inset, SIZE - inset * 2, SIZE - inset * 2, color)
    base.rect_outline(7, 7, 50, 50, rgba((35, 45, 41)), 2)
    base.line(13, 33, 51, 33, shift(color, 24), 1)
    base.line(33, 13, 33, 51, shift(color, 24), 1)
    if level > 1:
        base.rect_outline(12, 12, 40, 40, shift(color, 38), 1)
        base.rect(48, 8, 7, 7, rgba((236, 224, 135)))
        base.rect(50, 10, 3, 3, rgba((62, 66, 48)))
    if kind == "residential":
        base.circle(47, 19, 4, rgba((42, 107, 58)))
    elif kind == "commercial":
        base.rect(16, 15, 32, 5, rgba((226, 217, 167)))
    else:
        for x in range(14, 49, 9):
            base.line(x, 16, x + 6, 23, rgba((116, 91, 49)), 1)
    return base


def shadow(canvas: Canvas, x: int, y: int, w: int, h: int) -> None:
    canvas.rect(x + 3, y + 3, w, h, rgba((19, 22, 24), 130))


def windows(canvas: Canvas, x: int, y: int, w: int, h: int, step: int = 8) -> None:
    for px in range(x + 4, x + w - 4, step):
        for py in range(y + 5, y + h - 4, step):
            canvas.rect(px, py, 3, 4, rgba((96, 151, 179)))
            canvas.set(px + 1, py, rgba((170, 210, 216)))


def house(stage: int, variant: int, level: int = 1) -> Canvas:
    canvas = Canvas()
    if level > 1:
        facade = [rgba((201, 213, 205)), rgba((213, 203, 185)), rgba((196, 215, 216)), rgba((216, 198, 200))][variant]
        roof = [rgba((111, 76, 67)), rgba((94, 83, 78)), rgba((82, 85, 99)), rgba((132, 87, 63))][variant]
        floors = 2 + min(3, stage)
        w = 28 + stage * 4
        h = 20 + floors * 6
        x = 32 - w // 2
        y = 55 - h
        shadow(canvas, x, y, w, h)
        canvas.rect(x, y, w, h, facade)
        canvas.rect(x, y, w, 6, roof)
        canvas.rect_outline(x, y, w, h, rgba((64, 58, 55)), 2)
        for px in range(x + 5, x + w - 5, 8):
            for py in range(y + 10, y + h - 8, 8):
                canvas.rect(px, py, 3, 4, rgba((82, 132, 151)))
        canvas.rect(x + w // 2 - 3, y + h - 9, 7, 9, rgba((86, 61, 46)))
        canvas.rect(10, 55, 44, 4, rgba((184, 161, 112)))
        return canvas

    wall = [rgba((219, 220, 196)), rgba((220, 207, 180)), rgba((199, 219, 218)), rgba((222, 202, 198))][variant]
    roof = [rgba((126, 70, 58)), rgba((101, 82, 70)), rgba((91, 83, 96)), rgba((145, 86, 55))][variant]
    w = 22 + stage * 4
    h = 15 + stage * 3
    x = 32 - w // 2 + (variant % 3 - 1) * 2
    y = 47 - h
    shadow(canvas, x, y, w, h)
    canvas.rect(x, y, w, h, wall)
    canvas.rect_outline(x, y, w, h, rgba((73, 62, 53)), 1)
    canvas.polygon([(x - 4, y), (x + w // 2, y - 13), (x + w + 4, y)], roof)
    canvas.line(x - 4, y, x + w // 2, y - 13, shift(roof, 20), 1)
    canvas.rect(x + 5, y + 6, 5, 5, rgba((77, 128, 151)))
    canvas.rect(x + w - 10, y + 6, 5, 5, rgba((77, 128, 151)))
    canvas.rect(x + w // 2 - 2, y + h - 8, 5, 8, rgba((82, 57, 42)))
    if stage >= 3:
        canvas.rect(x + w - 4, y + h - 7, 12, 7, rgba((186, 188, 174)))
        canvas.rect_outline(x + w - 4, y + h - 7, 12, 7, rgba((82, 72, 62)), 1)
    if stage == 4:
        canvas.rect(11, 49, 42, 5, rgba((184, 161, 112)))
    return canvas


def commercial(stage: int, variant: int, level: int = 1) -> Canvas:
    canvas = Canvas()
    facade = [rgba((197, 210, 216)), rgba((214, 208, 186)), rgba((199, 209, 225)), rgba((194, 216, 207))][variant]
    accent = [rgba((232, 197, 82)), rgba((216, 123, 95)), rgba((117, 179, 137)), rgba((175, 145, 210))][variant]
    w = 22 + stage * 7 + (6 if level > 1 else 0)
    h = 17 + stage * 8 + (12 if level > 1 else 0)
    x = 32 - w // 2
    y = 54 - h
    shadow(canvas, x, y, w, h)
    canvas.rect(x, y, w, h, facade)
    canvas.rect(x, y, w, 8, rgba((65, 85, 98)))
    canvas.rect_outline(x, y, w, h, rgba((45, 53, 60)), 2)
    windows(canvas, x, y + 8, w, h - 16, max(7, 11 - stage))
    canvas.rect(x + 4, y + h - 10, w - 8, 6, accent)
    if level > 1:
        canvas.line(x + 7, y + 11, x + w - 8, y + 11, rgba((236, 239, 223)), 1)
        canvas.line(x + 7, y + h - 17, x + w - 8, y + h - 17, rgba((236, 239, 223)), 1)
        canvas.rect(x + w - 8, y + 3, 4, h - 8, rgba((92, 120, 136)))
    if stage >= 3:
        canvas.line(x + w // 2, y, x + w // 2, y - 9, rgba((49, 58, 64)), 2)
    return canvas


def industrial(stage: int, variant: int) -> Canvas:
    canvas = Canvas()
    w = 30 + stage * 5
    h = 16 + stage * 3
    x = 32 - w // 2
    y = 53 - h
    body = [rgba((155, 146, 120)), rgba((146, 142, 128)), rgba((164, 139, 110)), rgba((135, 147, 136))][variant]
    shadow(canvas, x, y, w, h)
    canvas.rect(x, y, w, h, body)
    canvas.rect_outline(x, y, w, h, rgba((69, 67, 60)), 2)
    for i in range(4):
        sx = x + i * w // 4
        canvas.polygon([(sx, y), (sx + w // 8, y - 8), (sx + w // 4, y)], rgba((93, 91, 82)))
    stack_x = x + w - 11 if variant % 2 == 0 else x + 6
    canvas.rect(stack_x, y - 16, 7, 18, rgba((87, 85, 78)))
    canvas.rect_outline(stack_x, y - 16, 7, 18, rgba((51, 50, 46)), 1)
    canvas.circle(stack_x + 3, y - 20, 4 + stage // 2, rgba((131, 133, 122), 170))
    canvas.rect(x + 7, y + h - 10, 12, 10, rgba((82, 76, 67)))
    for stripe in range(x + 7, x + 19, 5):
        canvas.line(stripe, y + h - 10, stripe + 5, y + h, rgba((213, 174, 70)), 1)
    return canvas


def civic(kind: str) -> Canvas:
    canvas = Canvas()
    colors = {
        "power_plant": rgba((205, 171, 69)),
        "large_power_plant": rgba((211, 164, 58)),
        "water_tower": rgba((79, 151, 184)),
        "large_water_tower": rgba((65, 158, 193)),
        "police": rgba((70, 103, 170)),
        "fire": rgba((194, 73, 61)),
        "school": rgba((130, 99, 183)),
        "train_station": rgba((176, 125, 79)),
        "airport": rgba((86, 137, 185)),
    }
    color = colors[kind]
    x, y, w, h = 15, 22, 34, 29
    shadow(canvas, x, y, w, h)
    canvas.rect(x, y, w, h, rgba((216, 222, 218)))
    canvas.rect_outline(x, y, w, h, rgba((48, 52, 56)), 2)
    canvas.rect(x, y, w, 8, shift(color, -20))
    if kind in ("water_tower", "large_water_tower"):
        tank = (20, 10, 24, 15) if kind == "water_tower" else (15, 6, 34, 20)
        canvas.ellipse(*tank, color)
        if kind == "large_water_tower":
            canvas.ellipse(21, 12, 22, 8, rgba((144, 210, 226)))
        canvas.line(24, 24, 18, 51, rgba((51, 59, 66)), 2)
        canvas.line(40, 24, 47, 51, rgba((51, 59, 66)), 2)
        canvas.line(32, 24, 32, 51, rgba((51, 59, 66)), 1)
    elif kind in ("power_plant", "large_power_plant"):
        canvas.rect(41, 8, 8, 25, shift(color, -30))
        canvas.circle(45, 5, 5, rgba((143, 145, 134), 170))
        if kind == "large_power_plant":
            canvas.rect(26, 11, 8, 22, shift(color, -42))
            canvas.circle(30, 8, 6, rgba((143, 145, 134), 170))
            canvas.rect(16, 35, 33, 8, rgba((126, 101, 56)))
    elif kind == "airport":
        canvas.line(18, 36, 46, 36, color, 6)
        canvas.line(32, 22, 32, 50, shift(color, 20), 5)
        canvas.polygon([(32, 14), (25, 27), (39, 27)], shift(color, 30))
    elif kind == "train_station":
        canvas.line(18, 44, 46, 44, color, 3)
        canvas.line(18, 49, 46, 49, color, 3)
        for tx in range(19, 45, 7):
            canvas.line(tx, 41, tx + 4, 52, rgba((49, 52, 55)), 1)
    elif kind == "police":
        canvas.rect(27, 29, 10, 10, color)
        canvas.rect(29, 31, 6, 2, rgba((235, 235, 188)))
    elif kind == "fire":
        canvas.rect(25, 34, 14, 17, color)
        canvas.line(32, 34, 32, 50, rgba((238, 214, 181)), 1)
    elif kind == "school":
        canvas.polygon([(15, 22), (32, 10), (49, 22)], color)
        canvas.rect(29, 34, 7, 17, rgba((90, 65, 50)))
    return canvas


def road(mask: str) -> Canvas:
    canvas = Canvas()
    road_color = rgba((55, 58, 62))
    curb = rgba((88, 89, 85))
    line = rgba((213, 198, 122))
    cx = cy = 32
    half = 11
    curb_half = 15
    dirs = {
        "north": mask[0] == "1",
        "east": mask[1] == "1",
        "south": mask[2] == "1",
        "west": mask[3] == "1",
    }
    canvas.rect(cx - curb_half, cy - curb_half, curb_half * 2, curb_half * 2, curb)
    canvas.rect(cx - half, cy - half, half * 2, half * 2, road_color)
    if not any(dirs.values()):
        canvas.circle(cx, cy, 16, curb)
        canvas.circle(cx, cy, 12, road_color)
    if dirs["north"]:
        canvas.rect(cx - curb_half, 0, curb_half * 2, cy, curb)
        canvas.rect(cx - half, 0, half * 2, cy, road_color)
        canvas.line(cx, 7, cx, cy - 6, line, 2)
    if dirs["east"]:
        canvas.rect(cx, cy - curb_half, SIZE - cx, curb_half * 2, curb)
        canvas.rect(cx, cy - half, SIZE - cx, half * 2, road_color)
        canvas.line(cx + 6, cy, SIZE - 7, cy, line, 2)
    if dirs["south"]:
        canvas.rect(cx - curb_half, cy, curb_half * 2, SIZE - cy, curb)
        canvas.rect(cx - half, cy, half * 2, SIZE - cy, road_color)
        canvas.line(cx, cy + 6, cx, SIZE - 7, line, 2)
    if dirs["west"]:
        canvas.rect(0, cy - curb_half, cx, curb_half * 2, curb)
        canvas.rect(0, cy - half, cx, half * 2, road_color)
        canvas.line(7, cy, cx - 6, cy, line, 2)
    if sum(dirs.values()) >= 3:
        for offset in (-8, 0, 8):
            if dirs["north"]:
                canvas.line(23, 19 + offset // 4, 41, 19 + offset // 4, rgba((214, 214, 190)), 1)
            if dirs["south"]:
                canvas.line(23, 45 + offset // 4, 41, 45 + offset // 4, rgba((214, 214, 190)), 1)
            if dirs["east"]:
                canvas.line(45 + offset // 4, 23, 45 + offset // 4, 41, rgba((214, 214, 190)), 1)
            if dirs["west"]:
                canvas.line(19 + offset // 4, 23, 19 + offset // 4, 41, rgba((214, 214, 190)), 1)
    return canvas


def utility(kind: str, mask: str) -> Canvas:
    canvas = Canvas()
    color = rgba((235, 206, 72)) if kind == "power" else rgba((80, 176, 220))
    shadow_color = rgba((85, 74, 39), 180) if kind == "power" else rgba((35, 73, 100), 180)
    dirs = {"north": mask[0] == "1", "east": mask[1] == "1", "south": mask[2] == "1", "west": mask[3] == "1"}
    endpoints = {"north": (32, 2), "east": (62, 32), "south": (32, 62), "west": (2, 32)}
    if not any(dirs.values()):
        dirs = {"north": False, "east": False, "south": False, "west": False}
    for target in endpoints.values():
        pass
    for direction, connected in dirs.items():
        if connected:
            canvas.line(32, 32, *endpoints[direction], shadow_color, 6)
    for direction, connected in dirs.items():
        if connected:
            canvas.line(32, 32, *endpoints[direction], color, 4)
    canvas.circle(32, 32, 7, shadow_color)
    canvas.circle(32, 32, 5, color)
    if kind == "power":
        canvas.rect(29, 20, 6, 25, rgba((94, 76, 45)))
        canvas.line(22, 25, 42, 25, color, 2)
    else:
        canvas.circle(26, 25, 3, rgba((151, 216, 236)))
    return canvas


def pedestrian(index: int) -> Canvas:
    canvas = Canvas()
    palette = [
        (rgba((238, 185, 112)), rgba((62, 91, 143))),
        (rgba((224, 124, 103)), rgba((77, 126, 88))),
        (rgba((217, 195, 140)), rgba((137, 82, 124))),
    ]
    shirt, pants = palette[index]
    canvas.ellipse(20, 42, 24, 9, rgba((20, 24, 24), 130))
    canvas.rect(27, 31, 10, 14, pants)
    canvas.rect(25, 22, 14, 13, shirt)
    canvas.circle(32, 18, 7, rgba((239, 197, 158)))
    canvas.rect(27, 35, 4, 12, rgba((48, 48, 55)))
    canvas.rect(34, 35, 4, 12, rgba((48, 48, 55)))
    canvas.set(30, 17, rgba((53, 43, 35)))
    canvas.set(35, 17, rgba((53, 43, 35)))
    return canvas


ISO_W = 96
ISO_H = 128
PED_W = 24
PED_H = 32


def iso_shadow(canvas: Canvas, cx: int, base_y: int, width: int, depth: int) -> None:
    canvas.polygon(
        [
            (cx, base_y - depth),
            (cx + width // 2 + 8, base_y - depth // 2 + 3),
            (cx, base_y + 7),
            (cx - width // 2 - 8, base_y - depth // 2 + 3),
        ],
        rgba((11, 14, 16), 95),
    )


def iso_box(
    canvas: Canvas,
    cx: int,
    base_y: int,
    width: int,
    depth: int,
    height: int,
    left: Color,
    right: Color,
    roof: Color,
    outline: Color = rgba((43, 42, 40)),
) -> dict[str, tuple[int, int] | int]:
    top = base_y - height
    back = (cx, top - depth)
    right_top = (cx + width // 2, top - depth // 2)
    front = (cx, top)
    left_top = (cx - width // 2, top - depth // 2)
    base_front = (cx, base_y)
    base_right = (cx + width // 2, base_y - depth // 2)
    base_left = (cx - width // 2, base_y - depth // 2)

    canvas.polygon([left_top, front, base_front, base_left], left)
    canvas.polygon([front, right_top, base_right, base_front], right)
    canvas.polygon([back, right_top, front, left_top], roof)
    canvas.line(*left_top, *front, outline, 1)
    canvas.line(*front, *right_top, outline, 1)
    canvas.line(*left_top, *base_left, outline, 1)
    canvas.line(*right_top, *base_right, outline, 1)
    canvas.line(*base_left, *base_front, outline, 1)
    canvas.line(*base_front, *base_right, outline, 1)
    canvas.line(*back, *right_top, shift(outline, 18), 1)
    canvas.line(*back, *left_top, shift(outline, 12), 1)
    return {
        "cx": cx,
        "base_y": base_y,
        "width": width,
        "depth": depth,
        "height": height,
        "top": top,
        "front": front,
        "left_top": left_top,
        "right_top": right_top,
        "base_front": base_front,
    }


def iso_windows(canvas: Canvas, box: dict, rows: int, cols: int, color: Color, lit: Color | None = None) -> None:
    cx = int(box["cx"])
    base_y = int(box["base_y"])
    width = int(box["width"])
    depth = int(box["depth"])
    height = int(box["height"])
    top = int(box["top"])
    rows = max(1, rows)
    cols = max(1, cols)
    lit = lit or shift(color, 60)

    for row in range(rows):
        wy = top + 8 + row * max(5, (height - 14) // rows)
        for col in range(cols):
            offset = -width // 2 + 8 + col * max(5, (width // 2 - 12) // max(1, cols - 1))
            if offset < -3:
                x = cx + offset
                y = wy + (offset + width // 2) // 3
                canvas.rect(x, y, 4, 5, color if (row + col) % 3 else lit)
                canvas.rect_outline(x, y, 4, 5, rgba((38, 50, 55)), 1)
            offset_r = col * max(5, (width // 2 - 12) // max(1, cols - 1)) + 4
            x = cx + offset_r
            y = wy + (width // 2 - offset_r) // 3
            canvas.rect(x, y, 4, 5, color if (row + col + 1) % 3 else lit)
            canvas.rect_outline(x, y, 4, 5, rgba((38, 50, 55)), 1)


def roof_cap(canvas: Canvas, box: dict, roof_color: Color) -> None:
    cx = int(box["cx"])
    top = int(box["top"])
    width = int(box["width"])
    depth = int(box["depth"])
    canvas.polygon(
        [
            (cx - width // 2 - 4, top - depth // 2 + 2),
            (cx, top - depth - 13),
            (cx + width // 2 + 4, top - depth // 2 + 2),
            (cx, top + 7),
        ],
        roof_color,
    )
    canvas.polygon(
        [(cx, top - depth - 13), (cx + width // 2 + 4, top - depth // 2 + 2), (cx, top + 7)],
        shift(roof_color, -28),
    )
    canvas.line(cx, top - depth - 13, cx, top + 7, shift(roof_color, -45), 1)


def house(stage: int, variant: int, level: int = 1) -> Canvas:
    canvas = Canvas(ISO_W, ISO_H)
    cx = ISO_W // 2
    base_y = 110
    wall = [
        rgba((202, 190, 157)),
        rgba((194, 179, 145)),
        rgba((188, 202, 194)),
        rgba((205, 184, 176)),
    ][variant]
    roof = [
        rgba((128, 71, 58)),
        rgba((104, 82, 68)),
        rgba((82, 88, 108)),
        rgba((146, 88, 59)),
    ][variant]

    if level > 1:
        width = 36 + stage * 7
        depth = 24 + stage * 3
        height = 34 + stage * 13
        iso_shadow(canvas, cx, base_y, width, depth)
        box = iso_box(canvas, cx, base_y, width, depth, height, shift(wall, -22), shift(wall, -4), shift(roof, -18))
        iso_windows(canvas, box, rows=stage + 2, cols=3, color=rgba((82, 132, 151)), lit=rgba((207, 217, 174)))
        canvas.rect(cx - 4, base_y - 13, 8, 13, rgba((76, 54, 42)))
        canvas.rect(cx + width // 4, int(box["top"]) - 8, 5, 13, shift(roof, -10))
        canvas.line(cx + width // 4, int(box["top"]) - 8, cx + width // 4 + 5, int(box["top"]) - 8, shift(roof, 26), 1)
        return canvas

    width = 28 + stage * 5
    depth = 20 + stage * 2
    height = 18 + stage * 6
    iso_shadow(canvas, cx, base_y, width, depth)
    box = iso_box(canvas, cx, base_y, width, depth, height, shift(wall, -18), shift(wall, 2), shift(roof, -6))
    roof_cap(canvas, box, roof)
    iso_windows(canvas, box, rows=max(1, stage), cols=2, color=rgba((83, 132, 154)), lit=rgba((219, 201, 128)))
    canvas.rect(cx - 3, base_y - 10, 7, 10, rgba((74, 52, 39)))
    if stage >= 3:
        canvas.rect(cx + width // 4, int(box["top"]) - 5, 4, 10, shift(roof, -18))
    if stage >= 4:
        canvas.polygon([(cx - 36, base_y - 3), (cx - 10, base_y + 10), (cx + 22, base_y - 2), (cx - 3, base_y - 14)], rgba((174, 151, 110)))
    return canvas


def commercial(stage: int, variant: int, level: int = 1) -> Canvas:
    canvas = Canvas(ISO_W, ISO_H)
    cx = ISO_W // 2
    base_y = 111
    facade = [
        rgba((146, 174, 191)),
        rgba((166, 176, 185)),
        rgba((141, 166, 198)),
        rgba((150, 188, 184)),
    ][variant]
    accent = [
        rgba((218, 190, 75)),
        rgba((207, 112, 90)),
        rgba((112, 166, 128)),
        rgba((161, 132, 201)),
    ][variant]
    width = 34 + stage * 7 + (10 if level > 1 else 0)
    depth = 24 + stage * 3
    height = 30 + stage * 14 + (18 if level > 1 else 0)
    iso_shadow(canvas, cx, base_y, width, depth)
    box = iso_box(canvas, cx, base_y, width, depth, height, shift(facade, -26), shift(facade, -4), rgba((60, 75, 89)))
    iso_windows(canvas, box, rows=stage + (3 if level > 1 else 1), cols=3 if level == 1 else 4, color=rgba((102, 165, 190)), lit=rgba((198, 230, 229)))
    canvas.rect(cx - 11, base_y - 11, 22, 7, accent)
    canvas.line(cx - width // 3, int(box["top"]) + 8, cx + width // 3, int(box["top"]) + 8, shift(accent, 25), 1)
    if stage >= 3:
        canvas.rect(cx + width // 5, int(box["top"]) - 6, 10, 5, rgba((77, 89, 99)))
        canvas.line(cx, int(box["top"]), cx, int(box["top"]) - 14, rgba((55, 63, 70)), 2)
    return canvas


def industrial(stage: int, variant: int) -> Canvas:
    canvas = Canvas(ISO_W, ISO_H)
    cx = ISO_W // 2
    base_y = 111
    body = [
        rgba((142, 134, 111)),
        rgba((135, 137, 127)),
        rgba((157, 128, 100)),
        rgba((124, 140, 128)),
    ][variant]
    width = 46 + stage * 8
    depth = 28 + stage * 3
    height = 20 + stage * 7
    iso_shadow(canvas, cx, base_y, width, depth)
    box = iso_box(canvas, cx, base_y, width, depth, height, shift(body, -22), shift(body, 0), rgba((82, 79, 69)))
    for i in range(3 + stage):
        x = cx - width // 2 + 8 + i * max(6, width // (3 + stage))
        canvas.line(x, int(box["top"]) - depth // 2 + 2, x + 7, int(box["top"]) - depth // 2 + 7, shift(body, -48), 1)
    iso_windows(canvas, box, rows=max(1, stage // 2), cols=3, color=rgba((176, 157, 118)), lit=rgba((219, 186, 98)))
    stack_x = cx + width // 3 if variant % 2 == 0 else cx - width // 3
    canvas.rect(stack_x, int(box["top"]) - 18, 7, 29, rgba((80, 76, 68)))
    canvas.rect_outline(stack_x, int(box["top"]) - 18, 7, 29, rgba((43, 41, 38)), 1)
    canvas.ellipse(stack_x - 4, int(box["top"]) - 28, 17, 9, rgba((122, 126, 118), 145))
    if stage >= 3:
        canvas.rect(cx - width // 3, base_y - 13, 18, 13, rgba((82, 73, 63)))
        for sx in range(cx - width // 3, cx - width // 3 + 18, 6):
            canvas.line(sx, base_y - 13, sx + 6, base_y, rgba((213, 174, 70)), 1)
    return canvas


def civic(kind: str) -> Canvas:
    canvas = Canvas(ISO_W, ISO_H)
    cx = ISO_W // 2
    base_y = 111
    colors = {
        "power_plant": rgba((207, 178, 74)),
        "large_power_plant": rgba((213, 160, 58)),
        "water_tower": rgba((84, 166, 204)),
        "large_water_tower": rgba((74, 175, 210)),
        "police": rgba((82, 112, 184)),
        "fire": rgba((202, 77, 66)),
        "school": rgba((139, 108, 193)),
        "train_station": rgba((188, 137, 87)),
        "airport": rgba((93, 145, 195)),
    }
    color = colors[kind]

    if "water_tower" in kind:
        width = 38 if kind == "water_tower" else 50
        depth = 25 if kind == "water_tower" else 31
        tank_r = 15 if kind == "water_tower" else 20
        iso_shadow(canvas, cx, base_y, width, depth)
        leg_c = rgba((62, 72, 80))
        for lx in (cx - width // 4, cx + width // 4, cx):
            canvas.line(lx, base_y - 8, cx, base_y - 58, leg_c, 2)
        canvas.ellipse(cx - tank_r, base_y - 75, tank_r * 2, tank_r + 9, shift(color, -22))
        canvas.ellipse(cx - tank_r, base_y - 83, tank_r * 2, tank_r + 11, shift(color, 25))
        canvas.rect(cx - 5, base_y - 58, 10, 28, shift(color, -10))
        canvas.rect_outline(cx - tank_r, base_y - 78, tank_r * 2, tank_r + 15, rgba((42, 50, 56)), 1)
        return canvas

    if "power_plant" in kind:
        width = 50 if kind == "power_plant" else 66
        depth = 30
        height = 34 if kind == "power_plant" else 44
        iso_shadow(canvas, cx, base_y, width, depth)
        box = iso_box(canvas, cx, base_y, width, depth, height, shift(color, -30), shift(color, -8), rgba((100, 83, 54)))
        for sx in ([cx + width // 4] if kind == "power_plant" else [cx - 13, cx + 22]):
            canvas.rect(sx, int(box["top"]) - 30, 9, 38, rgba((122, 88, 66)))
            for band in range(int(box["top"]) - 28, int(box["top"]) + 3, 8):
                canvas.rect(sx, band, 9, 3, rgba((226, 228, 214)))
            canvas.ellipse(sx - 5, int(box["top"]) - 38, 19, 10, rgba((133, 134, 124), 140))
        return canvas

    if kind == "airport":
        iso_shadow(canvas, cx, base_y, 64, 30)
        box = iso_box(canvas, cx, base_y, 64, 30, 24, shift(color, -20), color, rgba((57, 87, 117)))
        canvas.line(cx - 28, base_y - 17, cx + 30, base_y - 17, rgba((226, 230, 219)), 5)
        canvas.line(cx, int(box["top"]) - 3, cx, base_y - 3, shift(color, 35), 4)
        canvas.polygon([(cx, int(box["top"]) - 22), (cx - 11, int(box["top"]) - 2), (cx + 11, int(box["top"]) - 2)], shift(color, 48))
        return canvas

    width = 46
    depth = 26
    height = 31
    if kind == "train_station":
        width = 62
        height = 24
    iso_shadow(canvas, cx, base_y, width, depth)
    box = iso_box(canvas, cx, base_y, width, depth, height, shift(rgba((207, 208, 196)), -20), rgba((207, 208, 196)), shift(color, -18))
    canvas.rect(cx - 13, base_y - 15, 26, 10, color)
    if kind == "fire":
        canvas.rect(cx - 9, base_y - 18, 18, 18, color)
        canvas.line(cx, base_y - 18, cx, base_y, rgba((240, 216, 182)), 1)
    elif kind == "police":
        canvas.rect(cx - 10, base_y - 17, 20, 13, color)
        canvas.rect(cx - 4, base_y - 14, 8, 3, rgba((236, 230, 168)))
    elif kind == "school":
        canvas.polygon([(cx - width // 2 - 2, int(box["top"]) - depth // 2), (cx, int(box["top"]) - depth - 18), (cx + width // 2 + 2, int(box["top"]) - depth // 2)], color)
        canvas.rect(cx - 5, base_y - 15, 10, 15, rgba((84, 60, 44)))
    elif kind == "train_station":
        for rail_y in (base_y - 8, base_y - 2):
            canvas.line(cx - 32, rail_y, cx + 32, rail_y, color, 3)
        for tie in range(cx - 28, cx + 29, 10):
            canvas.line(tie, base_y - 13, tie + 5, base_y + 2, rgba((54, 51, 45)), 1)
    return canvas


def pedestrian(index: int) -> Canvas:
    canvas = Canvas(PED_W, PED_H)
    palette = [
        (rgba((238, 185, 112)), rgba((62, 91, 143))),
        (rgba((224, 124, 103)), rgba((77, 126, 88))),
        (rgba((217, 195, 140)), rgba((137, 82, 124))),
    ]
    shirt, pants = palette[index]
    canvas.ellipse(5, 27, 14, 4, rgba((20, 24, 24), 120))
    canvas.rect(10, 18, 5, 8, pants)
    canvas.rect(8, 12, 9, 8, shirt)
    canvas.circle(12, 9, 4, rgba((239, 197, 158)))
    canvas.rect(8, 21, 3, 8, rgba((48, 48, 55)))
    canvas.rect(14, 21, 3, 8, rgba((48, 48, 55)))
    canvas.set(10, 8, rgba((53, 43, 35)))
    canvas.set(14, 8, rgba((53, 43, 35)))
    return canvas


def make_preview() -> Canvas:
    samples = [
        terrain_grass(0),
        terrain_grass(1),
        terrain_water(),
        terrain_forest(0),
        terrain_hill(),
        zone_tile("residential"),
        zone_tile("residential", 2),
        zone_tile("commercial"),
        zone_tile("commercial", 2),
        zone_tile("industrial"),
        road("1010"),
        road("0101"),
        road("1100"),
        road("1111"),
        utility("power", "1010"),
        utility("water", "0101"),
        pedestrian(0),
        pedestrian(1),
        house(1, 0),
        house(4, 2, 2),
        commercial(2, 0),
        commercial(4, 3, 2),
        industrial(2, 1),
        industrial(4, 2),
        civic("water_tower"),
        civic("large_water_tower"),
        civic("power_plant"),
        civic("large_power_plant"),
        civic("police"),
        civic("fire"),
        civic("school"),
        civic("train_station"),
        civic("airport"),
    ]
    gap = 8
    columns = 8
    rows = math.ceil(len(samples) / columns)
    cell_w = max(sample.width for sample in samples)
    cell_h = max(sample.height for sample in samples)
    preview = Canvas(columns * cell_w + (columns + 1) * gap, rows * cell_h + (rows + 1) * gap, rgba((34, 39, 44)))
    for index, sample in enumerate(samples):
        col = index % columns
        row = index // columns
        x = gap + col * (cell_w + gap)
        y = gap + row * (cell_h + gap)
        preview.rect(x - 2, y - 2, cell_w + 4, cell_h + 4, rgba((22, 26, 30)))
        preview.paste(sample, x + (cell_w - sample.width) // 2, y + cell_h - sample.height)
    return preview


def generate() -> None:
    for variant in range(4):
        save(f"terrain/grass_{variant}", terrain_grass(variant))
    save("terrain/grass", terrain_grass(0))
    save("terrain/water", terrain_water())
    for variant in range(2):
        save(f"terrain/forest_{variant}", terrain_forest(variant))
    save("terrain/forest", terrain_forest(0))
    save("terrain/hill", terrain_hill())

    for kind in ("residential", "commercial", "industrial"):
        save(f"zones/{kind}", zone_tile(kind))
    for kind in ("residential", "commercial"):
        save(f"zones/{kind}_tier2", zone_tile(kind, 2))
    for stage, variant in itertools.product(range(1, 5), range(4)):
        save(f"buildings/residential_{stage}_{variant}", house(stage, variant))
        save(f"buildings/residential_tier2_{stage}_{variant}", house(stage, variant, 2))
        save(f"buildings/commercial_{stage}_{variant}", commercial(stage, variant))
        save(f"buildings/commercial_tier2_{stage}_{variant}", commercial(stage, variant, 2))
        save(f"buildings/industrial_{stage}_{variant}", industrial(stage, variant))

    for kind in ("power_plant", "large_power_plant", "water_tower", "large_water_tower", "police", "fire", "school", "train_station", "airport"):
        save(f"civic/{kind}", civic(kind))

    for bits in itertools.product("01", repeat=4):
        mask = "".join(bits)
        save(f"roads/road_{mask}", road(mask))
        save(f"utilities/power_{mask}", utility("power", mask))
        save(f"utilities/water_{mask}", utility("water", mask))

    for index in range(3):
        save(f"pedestrians/pedestrian_{index}", pedestrian(index))

    save("preview", make_preview())


if __name__ == "__main__":
    generate()
