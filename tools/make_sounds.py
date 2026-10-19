#!/usr/bin/env python3
"""Gera os efeitos sonoros do jogo em assets/sfx/*.wav (síntese com numpy, sem arquivos de fora).

    python3 tools/make_sounds.py
"""
import os
import wave

import numpy as np

SR = 22050
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sfx")
rng = np.random.default_rng(7)


def t_(d):
    return np.arange(int(SR * d)) / SR


def env(n, a=0.005, r=None, curve=3.0):
    """Envelope: ataque curto e queda exponencial."""
    t = np.arange(n) / SR
    att = np.clip(t / max(a, 1e-4), 0, 1)
    rel = np.exp(-t * curve / (r or (n / SR))) if r else (1 - t / (n / SR)) ** curve
    return att * rel


def noise(d):
    return rng.uniform(-1, 1, int(SR * d))


def lowpass(x, cut):
    """Filtro passa-baixa de 1 polo (cut em Hz, pode variar no tempo)."""
    cut = np.broadcast_to(np.asarray(cut, float), x.shape)
    a = 1 - np.exp(-2 * np.pi * cut / SR)
    y = np.zeros_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


def bandpass(x, lo, hi):
    return lowpass(x, hi) - lowpass(x, lo)


def sweep(f0, f1, d, wave_="sine"):
    t = t_(d)
    f = f0 * (f1 / f0) ** (t / d)
    ph = 2 * np.pi * np.cumsum(f) / SR
    if wave_ == "square":
        return np.sign(np.sin(ph))
    if wave_ == "saw":
        return 2 * ((ph / (2 * np.pi)) % 1) - 1
    return np.sin(ph)


def mix(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[:len(p)] += p
    return out


def pad(x, before=0.0):
    return np.concatenate([np.zeros(int(SR * before)), x])


def whoosh(d, lo, hi, amp=1.0):
    n = int(SR * d)
    t = np.arange(n) / n
    cut = lo + (hi - lo) * np.sin(np.pi * t) ** 1.5
    return lowpass(noise(d), cut) * np.sin(np.pi * t) ** 1.2 * amp * 3


def thump(f0, f1, d, amp=1.0):
    return sweep(f0, f1, d) * env(int(SR * d), 0.002, curve=4) * amp


def save(name, x, gain=0.8):
    x = np.asarray(x, float)
    peak = np.max(np.abs(x)) or 1.0
    x = np.tanh(x / peak * 1.6) / np.tanh(1.6) * gain
    fade = min(len(x), int(SR * 0.008))
    x[-fade:] *= np.linspace(1, 0, fade)
    data = (x * 32767).astype(np.int16)
    with wave.open(os.path.join(OUT, name + ".wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def build():
    os.makedirs(OUT, exist_ok=True)
    # --- vampira
    save("claw", mix(whoosh(0.2, 600, 5200), bandpass(noise(0.12), 2500, 7000) * env(int(SR * 0.12), 0.002, curve=5) * 0.8,
                     pad(bandpass(noise(0.08), 3000, 8000) * env(int(SR * 0.08), 0.001, curve=6) * 0.6, 0.07)), 0.7)
    spit_pop = sweep(900, 250, 0.07) * env(int(SR * 0.07), 0.001, curve=5)
    save("spit", mix(bandpass(noise(0.12), 700, 3500) * env(int(SR * 0.12), 0.002, curve=6), spit_pop * 0.9,
                     pad(sweep(2400, 1600, 0.05) * env(int(SR * 0.05), curve=4) * 0.25, 0.03)), 0.6)
    save("kick", mix(whoosh(0.16, 400, 3000, 0.8), pad(thump(160, 55, 0.18, 1.3), 0.08),
                     pad(bandpass(noise(0.05), 800, 4000) * env(int(SR * 0.05), 0.001, curve=6) * 0.7, 0.08)), 0.8)
    save("punch", mix(thump(140, 40, 0.3, 1.4), bandpass(noise(0.12), 400, 3000) * env(int(SR * 0.12), 0.001, curve=5),
                      pad(bandpass(noise(0.18), 2000, 6000) * env(int(SR * 0.18), 0.002, curve=5) * 0.4, 0.02)), 0.85)
    n = int(SR * 0.35)
    flutter = (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 34 * np.arange(n) / SR))) * env(n, 0.03, curve=2)
    save("dash", mix(whoosh(0.3, 300, 2600, 1.0), lowpass(noise(0.35), 1800) * flutter * 0.9), 0.7)
    save("throw", mix(whoosh(0.28, 500, 2200), pad(whoosh(0.2, 500, 2000, 0.7), 0.1)), 0.6)
    save("chomp", mix(bandpass(noise(0.06), 1500, 6000) * env(int(SR * 0.06), 0.001, curve=7),
                      pad(bandpass(noise(0.06), 1500, 6000) * env(int(SR * 0.06), 0.001, curve=7), 0.09),
                      pad(sweep(420, 140, 0.2) * env(int(SR * 0.2), 0.01, curve=3) * 0.8, 0.17)), 0.75)
    save("spit_back", mix(spit_pop, pad(sweep(300, 900, 0.15, "saw") * env(int(SR * 0.15), curve=3) * 0.4, 0.02),
                          pad(bandpass(noise(0.25), 1000, 5000) * env(int(SR * 0.25), curve=4) * 0.5, 0.03)), 0.7)
    save("hurt", mix(sweep(520, 180, 0.22, "square") * env(int(SR * 0.22), 0.003, curve=3) * 0.35,
                     bandpass(noise(0.1), 300, 2000) * env(int(SR * 0.1), 0.001, curve=5)), 0.6)
    chord = mix(*[sweep(f, f * 1.5, 0.7, "saw") * 0.3 for f in (110, 165, 220)])
    save("frenzy", mix(lowpass(chord, np.linspace(300, 4000, len(chord))) * env(len(chord), 0.05, curve=1.5),
                       lowpass(noise(0.7), 2500) * env(int(SR * 0.7), 0.3, curve=2) * 0.4), 0.7)
    n = int(SR * 0.6)
    save("bat", mix(sweep(900, 180, 0.6, "square") * env(n, 0.01, curve=2) * 0.25,
                    lowpass(noise(0.6), 2400) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 22 * np.arange(n) / SR))) * env(n, curve=1.5) * 0.7), 0.6)
    notes = [mix(pad(sweep(f, f, 0.18) * env(int(SR * 0.18), 0.005, curve=3), i * 0.08)) for i, f in enumerate((392, 523, 659, 784))]
    save("revert", mix(*notes), 0.55)
    save("bite", mix(bandpass(noise(0.05), 1500, 7000) * env(int(SR * 0.05), 0.001, curve=7),
                     pad(thump(300, 120, 0.08, 0.7), 0.01)), 0.65)
    save("death", mix(sweep(440, 70, 1.2, "saw") * env(int(SR * 1.2), 0.01, curve=1.6) * 0.5,
                      lowpass(noise(1.2), 900) * env(int(SR * 1.2), 0.05, curve=2) * 0.5), 0.7)
    # --- acertos
    save("hit", mix(thump(220, 90, 0.09, 1.0), bandpass(noise(0.07), 1200, 5000) * env(int(SR * 0.07), 0.001, curve=6) * 0.8), 0.55)
    save("kill", mix(lowpass(noise(0.3), np.linspace(2500, 300, int(SR * 0.3))) * env(int(SR * 0.3), 0.002, curve=3),
                     thump(160, 50, 0.25, 1.0)), 0.6)
    # --- inimigos
    shing = mix(*[np.sin(2 * np.pi * f * t_(0.4)) * env(int(SR * 0.4), 0.002, curve=4) * a for f, a in ((2630, 0.5), (3950, 0.3), (5270, 0.2))])
    save("sword", mix(whoosh(0.18, 700, 4500, 0.9), pad(shing, 0.06)), 0.55)
    save("gunshot", mix(bandpass(noise(0.25), 200, 6000) * env(int(SR * 0.25), 0.001, curve=7), thump(120, 40, 0.3, 1.2),
                        pad(lowpass(noise(0.5), 700) * env(int(SR * 0.5), 0.02, curve=3) * 0.4, 0.05)), 0.6)
    save("aim", sweep(1200, 1800, 0.12) * env(int(SR * 0.12), 0.005, curve=2) * 0.4, 0.3)
    bark = mix(sweep(520, 300, 0.13, "saw") * env(int(SR * 0.13), 0.005, curve=2),
               bandpass(noise(0.13), 400, 2500) * env(int(SR * 0.13), 0.002, curve=3) * 0.6)
    save("bark", lowpass(mix(bark, pad(bark * 0.8, 0.17)), 2600), 0.6)
    save("growl", lowpass(sweep(90, 70, 0.4, "saw") * (0.6 + 0.4 * np.sin(2 * np.pi * 28 * t_(0.4))) * env(int(SR * 0.4), 0.05, curve=2), 900), 0.55)
    # --- Gigante
    save("boss_swing", whoosh(0.35, 150, 1200, 1.2), 0.75)
    save("slam", mix(thump(90, 28, 0.9, 1.6), lowpass(noise(1.0), np.linspace(1500, 120, int(SR * 1.0))) * env(int(SR * 1.0), 0.003, curve=3),
                     pad(bandpass(noise(0.4), 300, 2500) * env(int(SR * 0.4), 0.01, curve=3) * 0.5, 0.05)), 0.9)
    save("rain_warn", mix(*[pad(sweep(f, f, 0.12, "square") * env(int(SR * 0.12), curve=2) * 0.3, i * 0.14)
                            for i, f in enumerate((660, 880, 660, 880))]), 0.45)
    save("roar", lowpass(mix(sweep(120, 70, 1.0, "saw") * (0.7 + 0.3 * np.sin(2 * np.pi * 9 * t_(1.0))),
                             lowpass(noise(1.0), 800) * 0.6) * env(int(SR * 1.0), 0.08, curve=1.8), 1400), 0.8)
    # --- ondas
    bell = mix(*[np.sin(2 * np.pi * f * t_(1.4)) * env(int(SR * 1.4), 0.003, curve=3) * a for f, a in ((196, 0.6), (392, 0.35), (588, 0.2), (930, 0.12))])
    save("wave", bell, 0.55)
    save("clear", mix(*[pad(np.sin(2 * np.pi * f * t_(0.5)) * env(int(SR * 0.5), 0.004, curve=3), i * 0.1)
                        for i, f in enumerate((523, 659, 784, 1047))]), 0.5)
    print("sons gerados em", OUT, "(%d arquivos)" % len([f for f in os.listdir(OUT) if f.endswith(".wav")]))


if __name__ == "__main__":
    build()
