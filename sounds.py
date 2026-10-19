"""Efeitos sonoros (assets/sfx/*.ogg, gerados por tools/make_sounds.py).

Se não houver saída de áudio, tudo vira silêncio sem erro. Cada som tem um intervalo
mínimo entre repetições, para que 10 acertos no mesmo quadro não virem um estouro.
"""
import os
import random

import pygame

SFX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sfx")

VOLUME = {"claw": 0.6, "spit": 0.55, "kick": 0.7, "punch": 0.8, "dash": 0.55, "throw": 0.5, "chomp": 0.7,
          "spit_back": 0.6, "hurt": 0.7, "frenzy": 0.6, "bat": 0.6, "revert": 0.5, "bite": 0.6, "death": 0.7,
          "hit": 0.35, "kill": 0.45, "sword": 0.4, "gunshot": 0.35, "aim": 0.15, "bark": 0.45, "growl": 0.35,
          "boss_swing": 0.6, "slam": 0.9, "rain_warn": 0.4, "roar": 0.7, "wave": 0.45, "clear": 0.45}
GAP = {"hit": 0.05, "kill": 0.06, "sword": 0.08, "gunshot": 0.1, "aim": 0.15, "bark": 0.25, "growl": 0.6, "slam": 0.12}

_sounds = {}
_last = {}
_ok = False
muted = False


def init():
    """Abre o mixer e carrega os sons; devolve False (e fica mudo) se não der."""
    global _ok
    if _ok:
        return True
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(44100, -16, 2, 512)
        pygame.mixer.set_num_channels(32)
        for fn in sorted(os.listdir(SFX_DIR)):
            if fn.endswith(".ogg"):
                name = fn.split(".")[0]
                snd = pygame.mixer.Sound(os.path.join(SFX_DIR, fn))
                snd.set_volume(VOLUME.get(name, 0.5))
                _sounds.setdefault(name, []).append(snd)
        _ok = True
    except (pygame.error, OSError):
        _ok = False
    return _ok


def play(name, volume=1.0):
    if muted or not _ok:
        return None
    variants = _sounds.get(name)
    if not variants:
        return None
    snd = random.choice(variants)
    now = pygame.time.get_ticks() / 1000.0
    if now - _last.get(name, -9.0) < GAP.get(name, 0.03):
        return None
    _last[name] = now
    ch = snd.play()
    if ch is not None and volume != 1.0:
        ch.set_volume(max(0.0, min(1.0, volume)))
    return ch


def toggle_mute():
    global muted
    muted = not muted
    if muted and _ok:
        pygame.mixer.stop()
    return muted
