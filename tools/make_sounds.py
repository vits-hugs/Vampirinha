#!/usr/bin/env python3
"""Gera os efeitos sonoros do jogo em assets/sfx/ (síntese com numpy/scipy, sem arquivos de fora).

Cada som é montado em camadas (transiente, corpo, cauda) com filtros ressonantes, vozes por
formantes e um reverb de convolução (sala de pedra). É gravado em OGG estéreo 44,1 kHz, com
até 3 variações de tom (nome.v1.ogg...); o jogo sorteia uma a cada vez. Precisa de: numpy, scipy, soundfile.

    python3 tools/make_sounds.py
"""
import os

import numpy as np
from scipy import signal

SR = 44100
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sfx")
rng = np.random.default_rng(11)


# ------------------------------------------------------------------ blocos básicos
def n_(d):
    return int(SR * d)


def t_(d):
    return np.arange(n_(d)) / SR


def noise(d, color="white"):
    x = rng.standard_normal(n_(d))
    if color == "pink":
        b, a = [0.049922035, -0.095993537, 0.050612699, -0.004408786], [1, -2.494956002, 2.017265875, -0.522189400]
        x = signal.lfilter(b, a, x) * 4
    elif color == "brown":
        x = np.cumsum(x) * 0.02
        x -= signal.lfilter([1], [1, -0.995], x) * 0.005
    return x


def env(d, a=0.002, decay=None, hold=0.0, shape=1.0):
    """Ataque linear, sustentação e queda exponencial (decay = tempo até ~-60 dB)."""
    t = t_(d)
    e = np.clip(t / max(a, 1e-5), 0, 1)
    if decay is None:
        decay = d
    rel = np.where(t < a + hold, 1.0, np.exp(-6.9 * (t - a - hold) / max(decay, 1e-4)))
    return e * rel ** shape


def adsr_lin(d, a=0.01, r=0.3):
    t = t_(d)
    return np.clip(t / a, 0, 1) * np.clip((d - t) / r, 0, 1)


def bp(x, f, q=2.0):
    """Passa-faixa ressonante centrado em f (Hz)."""
    f = min(f, SR * 0.45)
    b, a = signal.iirpeak(f, q, SR)
    return signal.lfilter(b, a, x)


def lp(x, f, order=2):
    b, a = signal.butter(order, min(f, SR * 0.45) / (SR / 2), "low")
    return signal.lfilter(b, a, x)


def hp(x, f, order=2):
    b, a = signal.butter(order, min(f, SR * 0.45) / (SR / 2), "high")
    return signal.lfilter(b, a, x)


def band(x, lo, hi, order=2):
    b, a = signal.butter(order, [lo / (SR / 2), min(hi, SR * 0.45) / (SR / 2)], "band")
    return signal.lfilter(b, a, x)


def sweep_lp(x, f0, f1, steps=24, q=0.9):
    """Passa-baixa ressonante com corte variando no tempo (processado em blocos)."""
    out = np.zeros_like(x)
    edges = np.linspace(0, len(x), steps + 1).astype(int)
    zi = None
    for k in range(steps):
        f = f0 * (f1 / f0) ** (k / max(1, steps - 1))
        b, a = signal.iirfilter(2, min(f, SR * 0.45) / (SR / 2), btype="low", ftype="butter")
        if zi is None:
            zi = signal.lfilter_zi(b, a) * 0
        seg, zi = signal.lfilter(b, a, x[edges[k]:edges[k + 1]], zi=zi)
        out[edges[k]:edges[k + 1]] = seg
    return out


def osc(freq, d, kind="sine", phase=0.0):
    """Oscilador com frequência que pode variar (array) ou fixa."""
    f = np.broadcast_to(np.asarray(freq, float), (n_(d),))
    ph = 2 * np.pi * np.cumsum(f) / SR + phase
    if kind == "sine":
        return np.sin(ph)
    if kind == "saw":
        return 2 * ((ph / (2 * np.pi)) % 1) - 1
    if kind == "square":
        return np.tanh(np.sin(ph) * 6)
    if kind == "tri":
        return 2 * np.abs(2 * ((ph / (2 * np.pi)) % 1) - 1) - 1
    raise ValueError(kind)


def glide(f0, f1, d, curve=1.0):
    t = np.linspace(0, 1, n_(d)) ** curve
    return f0 * (f1 / f0) ** t


def place(x, at, total):
    out = np.zeros(n_(total))
    i = n_(at)
    j = min(len(out), i + len(x))
    out[i:j] += x[:j - i]
    return out


def mix(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[:len(p)] += p
    return out


def crush(x, bits=6, keep=3):
    """Bitcrusher leve: dá textura de "crocante" (ossos, dentes)."""
    q = 2 ** bits
    y = np.round(x * q) / q
    y = np.repeat(y[::keep], keep)[:len(x)]
    return y


def drive(x, k=2.0):
    return np.tanh(x * k) / np.tanh(k)


# ------------------------------------------------------------------ peças sonoras
def whoosh(d, f0=300, f1=3000, f2=500, amp=1.0, q=1.2):
    """Deslocamento de ar: ruído rosa num filtro que abre e fecha."""
    x = noise(d, "pink")
    n = len(x)
    out = np.zeros(n)
    steps = 28
    edges = np.linspace(0, n, steps + 1).astype(int)
    for k in range(steps):
        u = k / (steps - 1)
        f = f0 + (f1 - f0) * np.sin(np.pi * min(1, u * 1.4)) if u < 0.7 else f1 + (f2 - f1) * (u - 0.7) / 0.3
        out[edges[k]:edges[k + 1]] = bp(x, max(80, f), q)[edges[k]:edges[k + 1]]
    shape = np.sin(np.pi * np.linspace(0, 1, n)) ** 1.6
    return out * shape * amp


def thump(f0, f1, d, amp=1.0, click=0.3):
    """Pancada grave: seno com queda de afinação + clique de ataque."""
    body = osc(glide(f0, f1, d, 0.35), d) * env(d, 0.001, d * 0.9)
    ck = hp(noise(0.012), 2000) * env(0.012, 0.0005, 0.01) * click
    return mix(body * amp, ck)


def crackle(d, density=900, amp=1.0, lo=1500, hi=9000):
    """Estalos granulares (ossos, pedra, fogo)."""
    x = np.zeros(n_(d))
    k = int(density * d)
    pos = rng.integers(0, max(1, len(x) - 60), k)
    for p in pos:
        g = rng.standard_normal(40) * np.exp(-np.arange(40) / rng.uniform(4, 12))
        x[p:p + 40] += g * rng.uniform(0.3, 1.0)
    return band(x, lo, hi) * amp


def voice(f0_curve, d, vowel="a", breath=0.15, vib=0.0):
    """Voz sintética simples: pulsos glotais filtrados por formantes."""
    F = {"a": (800, 1150, 2900), "e": (450, 2000, 2800), "o": (500, 900, 2600), "u": (350, 800, 2500),
         "i": (300, 2300, 3000), "uh": (600, 1000, 2400), "woof": (550, 1000, 2300)}[vowel]
    f = np.broadcast_to(np.asarray(f0_curve, float), (n_(d),)).copy()
    if vib:
        f *= 1 + vib * np.sin(2 * np.pi * 5.5 * t_(d))
    src = osc(f, d, "saw") * 0.7 + noise(d, "pink") * breath
    out = bp(src, F[0], 5) * 1.0 + bp(src, F[1], 7) * 0.6 + bp(src, F[2], 9) * 0.3
    return out


def room_ir(length=0.9, damp=4500, seed=3, pre=0.008):
    r = np.random.default_rng(seed)
    t = t_(length)
    ir = r.standard_normal(len(t)) * np.exp(-6.9 * t / length)
    ir = lp(ir, damp)
    ir[:n_(pre)] = 0
    ir[0] = 0
    # primeiras reflexões da pedra
    for d_, g in ((0.011, 0.5), (0.019, 0.35), (0.027, 0.3), (0.041, 0.22)):
        ir[n_(d_)] += g
    return ir / np.sqrt(np.sum(ir ** 2))


IR_L = room_ir(seed=3)
IR_R = room_ir(seed=4)


def stereo_verb(x, wet=0.18, width=0.35, ir_len=None):
    """Mono seco + reverb de sala (estéreo descorrelacionado)."""
    irl, irr = (IR_L, IR_R) if ir_len is None else (room_ir(ir_len, seed=5), room_ir(ir_len, seed=6))
    wl = signal.fftconvolve(x, irl)[:len(x) + len(irl)]
    wr = signal.fftconvolve(x, irr)[:len(x) + len(irr)]
    n = max(len(wl), len(wr))
    dry = np.zeros(n)
    dry[:len(x)] = x
    wl = np.pad(wl, (0, n - len(wl)))
    wr = np.pad(wr, (0, n - len(wr)))
    L = dry + wet * (wl * (1 + width) + wr * (1 - width)) / 2
    R = dry + wet * (wr * (1 + width) + wl * (1 - width)) / 2
    return np.stack([L, R], axis=1)


def finish(st, gain=0.8):
    """Normaliza, limita suave e corta o silêncio do fim."""
    st = st - st.mean(axis=0)
    peak = np.max(np.abs(st)) or 1.0
    st = drive(st / peak * 1.15, 1.3) * gain
    mag = np.max(np.abs(st), axis=1)
    above = np.nonzero(mag > 0.002)[0]
    end = min(len(st), (above[-1] if len(above) else len(st)) + n_(0.02))
    st = st[:end]
    fade = min(len(st), n_(0.015))
    st[-fade:] *= np.linspace(1, 0, fade)[:, None]
    st[:n_(0.002)] *= np.linspace(0, 1, n_(0.002))[:, None]
    return st


def pitch(st, ratio):
    """Muda tom e duração juntos (como fita mais rápida/lenta)."""
    n = len(st)
    m = int(n / ratio)
    xi = np.linspace(0, n - 1, m)
    return np.stack([np.interp(xi, np.arange(n), st[:, c]) for c in range(2)], axis=1)


SPREAD = {}


def save(name, mono, gain=0.8, wet=0.18, width=0.35, ir_len=None, spread=0.05):
    import soundfile as sf
    st = finish(stereo_verb(mono, wet, width, ir_len), gain)
    ratios = (1.0, 1.0 + spread, 1.0 - spread * 0.9) if spread else (1.0,)
    for k, ratio in enumerate(ratios, start=1):  # variações de tom (o jogo sorteia uma)
        sf.write(os.path.join(OUT, "%s.v%d.ogg" % (name, k)), np.clip(pitch(st, ratio), -1, 1).astype(np.float32), SR,
                 format="OGG", subtype="VORBIS")
    SPREAD[name] = spread


# ------------------------------------------------------------------ os sons
def build():
    os.makedirs(OUT, exist_ok=True)
    for fn in os.listdir(OUT):  # apaga a geração anterior
        if fn.endswith((".wav", ".ogg", ".json")):
            os.remove(os.path.join(OUT, fn))

    # ---------------- vampira
    swish = lambda d, f: hp(whoosh(d, 900, f, 1500, 1.0, 1.6), 600)  # noqa: E731
    claw = mix(place(swish(0.16, 7000), 0.0, 0.4), place(swish(0.14, 6200) * 0.8, 0.035, 0.4),
               place(swish(0.13, 5600) * 0.65, 0.065, 0.4),
               place(crackle(0.12, 1400, 0.5, 2500, 9000) * env(0.12, 0.002, 0.1), 0.06, 0.4),  # rasgo
               place(band(noise(0.05), 3000, 9000) * env(0.05, 0.0005, 0.04) * 0.6, 0.075, 0.4))
    save("claw", claw, 0.75, wet=0.14)

    spit = mix(place(band(noise(0.04), 600, 5000) * env(0.04, 0.0005, 0.03), 0.0, 0.35),     # "p"
               place(voice(glide(260, 200, 0.08), 0.08, "uh", 0.4) * env(0.08, 0.003, 0.07) * 0.5, 0.012, 0.35),
               place(osc(glide(3400, 1900, 0.18, 0.6), 0.18) * env(0.18, 0.01, 0.17) * 0.18, 0.05, 0.35),  # dente assobiando
               place(band(noise(0.1), 2500, 8000) * env(0.1, 0.001, 0.09) * 0.25, 0.02, 0.35))
    save("spit", spit, 0.62, wet=0.12, spread=0.08)

    kick = mix(place(whoosh(0.15, 300, 2600, 600, 0.9), 0.0, 0.45),
               place(thump(170, 48, 0.3, 1.4, 0.6), 0.1, 0.45),
               place(band(noise(0.06), 700, 4000) * env(0.06, 0.0005, 0.05) * 0.8, 0.1, 0.45))
    save("kick", kick, 0.82, wet=0.16)

    punch = mix(thump(130, 38, 0.45, 1.6, 0.8),
                crush(band(noise(0.16), 300, 5000) * env(0.16, 0.0005, 0.14), 5, 3) * 0.9,
                place(crackle(0.3, 600, 0.5, 2000, 9000) * env(0.3, 0.002, 0.28), 0.015, 0.5),  # dentes quebrando
                place(osc(glide(2200, 1400, 0.25), 0.25) * env(0.25, 0.002, 0.2) * 0.08, 0.02, 0.5))
    save("punch", punch, 0.88, wet=0.2)

    d = 0.42
    flap = np.zeros(n_(d))
    for k in range(9):  # bater de asas dos morcegos
        at = 0.04 + k * 0.035 + rng.uniform(-0.006, 0.006)
        flap += place(band(noise(0.03), 400, 2200) * env(0.03, 0.002, 0.025) * rng.uniform(0.5, 1.0), at, d)
    dash = mix(whoosh(d, 200, 2400, 300, 1.2, 0.9), flap * 0.7,
               place(osc(glide(1800, 2600, 0.06), 0.06) * env(0.06, 0.004, 0.05) * 0.12, 0.15, d),   # guinchinho
               lp(noise(d, "brown"), 300) * adsr_lin(d, 0.05, 0.2) * 0.6)                             # sombra
    save("dash", dash, 0.72, wet=0.2)

    throw = mix(whoosh(0.32, 400, 2000, 500, 1.0),
                place(whoosh(0.22, 400, 1800, 500, 0.7), 0.12, 0.45), place(whoosh(0.18, 400, 1600, 400, 0.5), 0.24, 0.45))
    save("throw", throw, 0.62, wet=0.18)

    bite_ = lambda: crush(band(noise(0.05), 1200, 8000), 5, 2) * env(0.05, 0.0005, 0.04)  # noqa: E731
    chomp = mix(place(bite_(), 0.0, 0.5), place(bite_() * 0.9, 0.09, 0.5),
                place(voice(glide(190, 120, 0.2), 0.2, "u", 0.2) * env(0.2, 0.02, 0.18) * 0.6, 0.2, 0.5),  # gulp
                place(thump(160, 90, 0.08, 0.6, 0.1), 0.2, 0.5))
    save("chomp", chomp, 0.75, wet=0.15)

    spit_back = mix(place(band(noise(0.04), 600, 5000) * env(0.04, 0.0005, 0.03), 0.0, 0.6),
                    place(thump(220, 90, 0.1, 0.7, 0.4), 0.0, 0.6),
                    place(whoosh(0.35, 800, 4500, 900, 0.8), 0.02, 0.6),
                    place(osc(glide(500, 1500, 0.3, 0.5), 0.3, "saw") * env(0.3, 0.01, 0.28) * 0.08, 0.02, 0.6))
    save("spit_back", spit_back, 0.72, wet=0.22)

    hurt = mix(voice(glide(520, 330, 0.24, 0.6), 0.24, "a", 0.25, 0.01) * env(0.24, 0.005, 0.2) * 0.8,
               band(noise(0.08), 400, 2500) * env(0.08, 0.0005, 0.06) * 0.7,
               thump(180, 70, 0.12, 0.6, 0.2))
    save("hurt", hurt, 0.7, wet=0.16, spread=0.04)

    d = 1.1
    heart = mix(place(thump(70, 42, 0.18, 1.3, 0.1), 0.0, d), place(thump(66, 40, 0.16, 1.0, 0.1), 0.17, d),
                place(thump(70, 42, 0.18, 1.3, 0.1), 0.55, d), place(thump(66, 40, 0.16, 1.0, 0.1), 0.72, d))
    swell = mix(*[osc(glide(f, f * 1.5, d, 2.0), d, "saw") for f in (98, 146.8, 196, 207.6)]) * 0.18
    frenzy = mix(heart, sweep_lp(swell, 200, 3800) * adsr_lin(d, 0.3, 0.35),
                 band(noise(d), 2000, 6000) * adsr_lin(d, 0.6, 0.3) * 0.15)
    save("frenzy", frenzy, 0.75, wet=0.3, ir_len=1.4)

    d = 0.8
    flaps = np.zeros(n_(d))
    for k in range(16):
        flaps += place(band(noise(0.035), 300, 2000) * env(0.035, 0.002, 0.03) * rng.uniform(0.4, 1.0), k * 0.045, d)
    bat = mix(flaps,
              place(osc(glide(2600, 3400, 0.07), 0.07) * env(0.07, 0.005, 0.06) * 0.25, 0.1, d),
              place(osc(glide(3000, 3800, 0.06), 0.06) * env(0.06, 0.005, 0.05) * 0.2, 0.32, d),
              osc(glide(600, 150, d), d, "tri") * env(d, 0.02, 0.7) * 0.25,
              lp(noise(d, "pink"), 900) * adsr_lin(d, 0.05, 0.5) * 0.35)
    save("bat", bat, 0.65, wet=0.28, ir_len=1.2)

    rev = np.zeros(n_(0.9))
    for k, f in enumerate((392, 523.3, 659.3, 784, 1046.5)):
        tone = (osc(f, 0.5) + 0.3 * osc(f * 2, 0.5) + 0.12 * osc(f * 3.01, 0.5)) * env(0.5, 0.003, 0.45)
        rev += place(tone, k * 0.07, 0.9)
    save("revert", rev, 0.55, wet=0.35, ir_len=1.3)

    bite = mix(bite_(), place(thump(320, 140, 0.09, 0.7, 0.3), 0.005, 0.2),
               place(osc(glide(3200, 2600, 0.05), 0.05) * env(0.05, 0.003, 0.04) * 0.15, 0.0, 0.2))
    save("bite", bite, 0.66, wet=0.12, spread=0.07)

    d = 1.8
    death = mix(voice(glide(440, 150, d, 0.7), d, "a", 0.2, 0.02) * env(d, 0.02, 1.5) * 0.6,
                osc(glide(220, 70, d), d, "saw") * env(d, 0.01, 1.4) * 0.2,
                lp(noise(d, "pink"), 700) * env(d, 0.1, 1.2) * 0.4,
                place(mix(*[osc(f, 1.2) * a for f, a in ((196, 0.5), (233, 0.35), (294, 0.25))]) * env(1.2, 0.01, 1.1) * 0.3, 0.5, d))
    save("death", death, 0.72, wet=0.35, ir_len=1.6, spread=0.0)

    # ---------------- acertos
    hit = mix(thump(240, 90, 0.1, 1.0, 0.7), band(noise(0.07), 1000, 6000) * env(0.07, 0.0005, 0.05) * 0.9,
              place(crackle(0.06, 900, 0.3, 2000, 8000), 0.003, 0.12))
    save("hit", hit, 0.58, wet=0.1, spread=0.09)

    d = 0.45
    kill = mix(thump(150, 45, 0.35, 1.0, 0.4),
               sweep_lp(noise(d), 4000, 250) * env(d, 0.002, 0.35) * 0.8,          # respingo
               place(bp(noise(0.25), 700, 6) * env(0.25, 0.01, 0.2) * 0.6, 0.04, d),
               place(crackle(0.2, 500, 0.4, 800, 5000), 0.02, d))
    save("kill", kill, 0.62, wet=0.18, spread=0.07)

    # ---------------- inimigos
    d = 0.7
    ring = mix(*[osc(f, d) * env(d, 0.001, 0.6 * (1.2 - k * 0.2)) * a
                 for k, (f, a) in enumerate(((1830, 0.5), (1830 * 2.76, 0.32), (1830 * 5.4, 0.18), (1830 * 8.93, 0.08)))])
    sword = mix(place(hp(whoosh(0.18, 800, 5000, 1200, 1.0, 1.4), 500), 0.0, d), place(ring * 0.5, 0.07, d))
    save("sword", sword, 0.55, wet=0.2, spread=0.04)

    d = 0.9
    gun = mix(band(noise(0.02), 1500, 12000) * env(0.02, 0.0002, 0.015) * 1.5,                # estalo
              thump(110, 35, 0.4, 1.3, 0.6),
              lp(noise(0.5), 1200) * env(0.5, 0.002, 0.45) * 0.8,
              place(lp(noise(0.6, "pink"), 500) * env(0.6, 0.02, 0.5) * 0.4, 0.05, d))
    save("gunshot", gun, 0.62, wet=0.32, ir_len=1.3, spread=0.04)

    aim = mix(osc(glide(1500, 2300, 0.14), 0.14, "tri") * env(0.14, 0.01, 0.13) * 0.5,
              place(band(noise(0.03), 2000, 6000) * env(0.03, 0.001, 0.02) * 0.4, 0.0, 0.14))  # engatilha
    save("aim", aim, 0.35, wet=0.1)

    woof = lambda f0: voice(glide(f0, f0 * 0.6, 0.15, 0.7), 0.15, "woof", 0.35) * env(0.15, 0.006, 0.12)  # noqa: E731
    bark = mix(place(woof(420), 0.0, 0.45), place(woof(380) * 0.85, 0.2, 0.45))
    save("bark", drive(bark * 1.5, 1.5), 0.6, wet=0.2, spread=0.06)

    d = 0.6
    growl = voice(110 + 8 * np.sin(2 * np.pi * 3 * t_(d)), d, "uh", 0.5) * (0.6 + 0.4 * np.abs(np.sin(2 * np.pi * 14 * t_(d)))) \
        * adsr_lin(d, 0.08, 0.2)
    save("growl", growl, 0.5, wet=0.18)

    # ---------------- Gigante
    save("boss_swing", mix(whoosh(0.45, 120, 1100, 200, 1.4, 0.8), lp(noise(0.45, "brown"), 200) * adsr_lin(0.45, 0.1, 0.2) * 0.8),
         0.78, wet=0.22)
    d = 1.6
    slam = mix(thump(85, 26, 1.0, 2.0, 0.8),
               sweep_lp(noise(d, "pink"), 2500, 120) * env(d, 0.002, 1.2) * 0.9,
               place(crackle(0.9, 700, 0.7, 600, 6000) * env(0.9, 0.005, 0.8), 0.02, d),          # pedras
               place(lp(noise(1.2, "brown"), 120) * env(1.2, 0.05, 1.0) * 0.8, 0.0, d))
    save("slam", slam, 0.92, wet=0.3, ir_len=1.6, spread=0.06)

    d = 0.9
    warn = np.zeros(n_(d))
    for k, f in enumerate((587, 880, 587, 880)):
        warn += place((osc(f, 0.16, "square") * 0.3 + osc(f / 2, 0.16, "tri") * 0.3) * env(0.16, 0.003, 0.14), k * 0.18, d)
    save("rain_warn", warn, 0.45, wet=0.25)

    d = 1.6
    roar = mix(voice(glide(95, 70, d, 1.2) * (1 + 0.04 * np.sin(2 * np.pi * 7 * t_(d))), d, "a", 0.6) * adsr_lin(d, 0.15, 0.6),
               voice(glide(142, 104, d, 1.2), d, "o", 0.4) * adsr_lin(d, 0.2, 0.6) * 0.5,
               lp(noise(d, "pink"), 900) * adsr_lin(d, 0.2, 0.6) * 0.5)
    save("roar", drive(roar * 1.6, 1.8), 0.8, wet=0.3, ir_len=1.6, spread=0.03)

    # ---------------- ondas
    d = 2.6
    gong = mix(*[osc(f * (1 + 0.003 * np.sin(2 * np.pi * b * t_(d))), d) * env(d, 0.002, dec) * a
                 for f, a, dec, b in ((98, 0.7, 2.4, 0.7), (196.6, 0.4, 1.8, 1.1), (293, 0.3, 1.4, 1.7),
                                      (412, 0.2, 1.0, 2.3), (587, 0.12, 0.7, 2.9))],
               thump(120, 60, 0.3, 0.5, 0.3))
    save("wave", gong, 0.6, wet=0.35, ir_len=1.8, spread=0.0)

    d = 1.3
    clear = np.zeros(n_(d))
    for k, f in enumerate((523.3, 659.3, 784, 1046.5, 1318.5)):
        tone = (osc(f, 0.9) + 0.4 * osc(f * 2.01, 0.9) + 0.15 * osc(f * 4.1, 0.9)) * env(0.9, 0.002, 0.8)
        clear += place(tone, k * 0.09, d)
    save("clear", clear, 0.5, wet=0.35, ir_len=1.5, spread=0.0)

    print("sons gerados em", OUT, "(%d sons)" % len(SPREAD))


if __name__ == "__main__":
    build()
