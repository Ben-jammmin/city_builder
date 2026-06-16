"""
sounds.py — Procedural audio synthesis using Python's built-in array module.

No audio files needed — every sound is synthesised from sine waves and noise
at startup.  The mixer runs at 22050 Hz, 16-bit signed, stereo (channels=2).

Audio samples are stored as 16-bit integers in the range -32767 … 32767.
Each sample is appended twice (left channel then right channel) to produce
a stereo buffer that pygame.mixer.Sound can play.

Sounds
------
  build      — short 440 Hz tone (pleasant confirmation)
  bulldoze   — short noise burst (destructive action)
  click      — very short 880 Hz tick (UI button press)
  fire       — alternating 800/1050 Hz alarm (fire event)
  milestone  — ascending 4-note fanfare (C5-E5-G5-C6)
  crime      — low 180 Hz tone (crime incident warning)
"""
from __future__ import annotations

import array
import math
import random as _rng

import pygame


class SoundManager:
    """Synthesises and plays all game sound effects."""

    def __init__(self) -> None:
        self._sounds: dict[str, pygame.mixer.Sound | None] = {}
        if not pygame.mixer.get_init():
            try:
                # 22050 Hz, 16-bit signed (-16), stereo (2 channels), small buffer
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            except pygame.error:
                return   # if audio init fails, play() calls are silently ignored

        # Synthesise all sounds at startup so there's no delay on first play.
        self._sounds = {
            "build":     self._tone(440, 0.08),    # 440 Hz = concert A
            "bulldoze":  self._noise(0.10),
            "click":     self._tone(880, 0.05),    # 880 Hz = one octave above A
            "fire":      self._alarm(),
            "milestone": self._fanfare(),
            "crime":     self._tone(180, 0.14),    # deep bass note
        }

    def play(self, name: str) -> None:
        """Plays a named sound (silently does nothing if audio is unavailable)."""
        snd = self._sounds.get(name)
        if snd:
            try:
                snd.play()
            except pygame.error:
                pass

    # ── Sound generators ───────────────────────────────────────────────────────

    def _tone(self, freq: float, duration: float, volume: float = 0.18) -> pygame.mixer.Sound | None:
        """Generates a pure sine wave tone and wraps it in a Sound object."""
        return self._buf(self._sine(freq, duration, volume))

    def _sine(self, freq: float, duration: float, volume: float) -> array.array:
        """
        Builds a stereo PCM buffer for a sine wave with a linear fade-out envelope.

        sr = sample rate (22050 samples/sec)
        n  = total sample count = sr * duration
        env = 1 - (i/n) makes the sound fade from full volume to silence.
        """
        sr = 22050
        n = int(sr * duration)
        buf: array.array = array.array("h")   # "h" = signed 16-bit int
        for i in range(n):
            wave = math.sin(2 * math.pi * freq * i / sr)
            env  = max(0.0, 1.0 - i / n)     # linear fade-out over the full clip
            s    = int(wave * env * volume * 32767)
            buf.append(s)   # left channel
            buf.append(s)   # right channel (same value → centre panning)
        return buf

    def _noise(self, duration: float, volume: float = 0.10) -> pygame.mixer.Sound | None:
        """Generates white noise (random samples) with the same fade-out envelope."""
        sr = 22050
        n  = int(sr * duration)
        buf: array.array = array.array("h")
        for i in range(n):
            env = max(0.0, 1.0 - i / n)
            s   = int(_rng.uniform(-1.0, 1.0) * env * volume * 32767)
            buf.append(s)
            buf.append(s)
        return self._buf(buf)

    def _alarm(self) -> pygame.mixer.Sound | None:
        """
        Alternates between 800 Hz and 1050 Hz at 7 Hz to create a fire alarm effect.

        The envelope here is a triangle shape that peaks in the middle and
        fades at both ends, so the alarm blends in and out smoothly.
        """
        sr  = 22050
        dur = 0.30
        n   = int(sr * dur)
        buf: array.array = array.array("h")
        for i in range(n):
            t   = i / sr
            # Switch frequency every 1/14 second (7 Hz toggle).
            f   = 800.0 if int(t * 7) % 2 == 0 else 1050.0
            wave = math.sin(2 * math.pi * f * t)
            # Triangle envelope: louder in the middle, quieter at start and end.
            env = max(0.0, min(1.0, 1.5 - abs(i / n - 0.5) * 3))
            s   = int(wave * env * 0.22 * 32767)
            buf.append(s)
            buf.append(s)
        return self._buf(buf)

    def _fanfare(self) -> pygame.mixer.Sound | None:
        """
        Stitches together four ascending notes (C5, E5, G5, C6) for a milestone jingle.

        Each note has a short duration and its own fast fade-out so notes
        don't overlap or blur together.
        """
        # Frequencies: C5, E5, G5, C6 — a major chord ascending.
        notes = [(523.25, 0.10), (659.25, 0.10), (783.99, 0.10), (1046.50, 0.22)]
        sr  = 22050
        buf: array.array = array.array("h")
        for freq, dur in notes:
            n = int(sr * dur)
            for i in range(n):
                wave = math.sin(2 * math.pi * freq * i / sr)
                # 1.8x speed fade so each note dies out before the next starts.
                env  = max(0.0, 1.0 - i / n * 1.8)
                s    = int(wave * env * 0.18 * 32767)
                buf.append(s)
                buf.append(s)
        return self._buf(buf)

    def _buf(self, buf: array.array) -> pygame.mixer.Sound | None:
        """Wraps a raw PCM buffer in a pygame.mixer.Sound. Returns None on failure."""
        try:
            return pygame.mixer.Sound(buffer=buf)
        except Exception:
            return None
