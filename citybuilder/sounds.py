"""Procedural sound effects generated at startup using Python's built-in array module.
No audio files needed — every sound is synthesised from sine waves and noise."""
from __future__ import annotations

import array
import math
import random as _rng

import pygame


class SoundManager:
    def __init__(self) -> None:
        self._sounds: dict[str, pygame.mixer.Sound | None] = {}
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            except pygame.error:
                return
        self._sounds = {
            "build":     self._tone(440, 0.08),
            "bulldoze":  self._noise(0.10),
            "click":     self._tone(880, 0.05),
            "fire":      self._alarm(),
            "milestone": self._fanfare(),
            "crime":     self._tone(180, 0.14),
        }

    def play(self, name: str) -> None:
        snd = self._sounds.get(name)
        if snd:
            try:
                snd.play()
            except pygame.error:
                pass

    # ------------------------------------------------------------------ #
    # Generators                                                           #
    # ------------------------------------------------------------------ #

    def _tone(self, freq: float, duration: float, volume: float = 0.18) -> pygame.mixer.Sound | None:
        return self._buf(self._sine(freq, duration, volume))

    def _sine(self, freq: float, duration: float, volume: float) -> array.array:
        sr = 22050
        n = int(sr * duration)
        buf: array.array = array.array("h")
        for i in range(n):
            wave = math.sin(2 * math.pi * freq * i / sr)
            env = max(0.0, 1.0 - i / n)
            s = int(wave * env * volume * 32767)
            buf.append(s)
            buf.append(s)
        return buf

    def _noise(self, duration: float, volume: float = 0.10) -> pygame.mixer.Sound | None:
        sr = 22050
        n = int(sr * duration)
        buf: array.array = array.array("h")
        for i in range(n):
            env = max(0.0, 1.0 - i / n)
            s = int(_rng.uniform(-1.0, 1.0) * env * volume * 32767)
            buf.append(s)
            buf.append(s)
        return self._buf(buf)

    def _alarm(self) -> pygame.mixer.Sound | None:
        sr = 22050
        dur = 0.30
        n = int(sr * dur)
        buf: array.array = array.array("h")
        for i in range(n):
            t = i / sr
            f = 800.0 if int(t * 7) % 2 == 0 else 1050.0
            wave = math.sin(2 * math.pi * f * t)
            env = max(0.0, min(1.0, 1.5 - abs(i / n - 0.5) * 3))
            s = int(wave * env * 0.22 * 32767)
            buf.append(s)
            buf.append(s)
        return self._buf(buf)

    def _fanfare(self) -> pygame.mixer.Sound | None:
        notes = [(523.25, 0.10), (659.25, 0.10), (783.99, 0.10), (1046.50, 0.22)]
        sr = 22050
        buf: array.array = array.array("h")
        for freq, dur in notes:
            n = int(sr * dur)
            for i in range(n):
                wave = math.sin(2 * math.pi * freq * i / sr)
                env = max(0.0, 1.0 - i / n * 1.8)
                s = int(wave * env * 0.18 * 32767)
                buf.append(s)
                buf.append(s)
        return self._buf(buf)

    def _buf(self, buf: array.array) -> pygame.mixer.Sound | None:
        try:
            return pygame.mixer.Sound(buffer=buf)
        except Exception:
            return None
