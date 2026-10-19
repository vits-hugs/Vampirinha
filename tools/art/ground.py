"""Cenário: piso de lajotas de cemitério (textura contínua), decalques e túmulos."""
import math
import random

from .kit import P, mix, tapered

STONE = ["#342d3f", "#3a3245", "#302a3a", "#373042", "#3e3549"]
MORTAR = "#211b2a"
STONE_HL = "#4f4661"
STONE_SH = "#28212f"
MOSS = "#2e4a3f"
MOSS_HL = "#41654f"
LINE = "#16111c"


def draw_flagstones(pen, size=512, seed=3):
    """Lajotas irregulares em fileiras deslocadas; desenhadas 3x3 vezes para emendar sem costura."""
    rnd = random.Random(seed)
    pen.fill(P().M(0, 0).L(size, 0).L(size, size).L(0, size).Z(), MORTAR)
    rows = 12
    rh = size / rows
    stones = []
    for r in range(rows):
        x = -rnd.uniform(0, 30)
        while x < size:
            w = rnd.uniform(34, 70)
            stones.append((x, r * rh, w, rh, rnd.choice(STONE), rnd.random()))
            x += w
    for ox in (-size, 0, size):
        for oy in (-size, 0, size):
            for (x, y, w, h, col, k) in stones:
                x0, y0 = x + ox + 2.2, y + oy + 2.2
                x1, y1 = x + ox + w - 2.2, y + oy + h - 2.2
                if x1 < -4 or y1 < -4 or x0 > size + 4 or y0 > size + 4:
                    continue
                j = [(k * 7.3 + i * 1.7) % 1.0 * 2.0 - 1.0 for i in range(8)]
                st = P().M(x0 + 3 + j[0], y0 + j[1]).L(x1 - 3 + j[2], y0 + j[3]).Q(x1, y0, x1 + j[4] * 0.6, y0 + 3) \
                    .L(x1 + j[5] * 0.6, y1 - 3).Q(x1, y1, x1 - 3, y1 + j[6] * 0.6).L(x0 + 3, y1 + j[7] * 0.6) \
                    .Q(x0, y1, x0, y1 - 3).L(x0, y0 + 3).Q(x0, y0, x0 + 3 + j[0], y0 + j[1]).Z()
                pen.fill(st, col)
                with pen.clip(st):
                    pen.fill(P().M(x0 - 2, y1 - 4).L(x1 + 2, y1 - 4).L(x1 + 2, y1 + 2).L(x0 - 2, y1 + 2).Z(), STONE_SH, alpha=170)
                    pen.fill(P().M(x0 - 2, y0 - 2).L(x1 + 2, y0 - 2).L(x1 + 2, y0 + 2.0).L(x0 - 2, y0 + 2.0).Z(), STONE_HL, alpha=95)
                    if k < 0.10:  # musgo
                        pen.fill(P().oval(x0 + w * 0.3, y1 - 6, w * 0.3, 4.5), MOSS, alpha=150)
                    if 0.22 < k < 0.30:  # rachadura
                        cx = x0 + w * 0.5
                        pen.stroke(P().M(cx - 8, y0 + 4).L(cx - 2, y0 + h * 0.45).L(cx + 5, y0 + h * 0.55).L(cx + 9, y1 - 2), LINE, 0.9, alpha=150)
                    if 0.6 < k < 0.75:  # manchinhas
                        for q in range(3):
                            pen.fill(P().circle(x0 + w * (0.2 + 0.3 * q), y0 + h * (0.3 + 0.2 * (q % 2)), 1.3), STONE_SH, alpha=180)


# ------------------------------------------------------------------ decalques (no chão)
def decal(pen, kind, rnd):
    if kind == "grass":
        for i in range(7):
            a = -math.pi / 2 + rnd.uniform(-0.8, 0.8)
            ln = rnd.uniform(6, 12)
            x = rnd.uniform(-8, 8)
            tip = (x + math.cos(a) * ln, math.sin(a) * ln + 4)
            col = rnd.choice(["#2f5244", "#3a6150", "#284438"])
            pen.fill(tapered([(x, 4), ((x + tip[0]) / 2, (4 + tip[1]) / 2 - 1), tip], 2.4, 0.2, 1.8), col)
    elif kind == "pebbles":
        for i in range(4):
            x, y, r = rnd.uniform(-10, 10), rnd.uniform(-5, 5), rnd.uniform(1.6, 3.4)
            pen.shape(P().oval(x, y, r * 1.3, r), "#5a5068", LINE, 0.6)
            pen.fill(P().oval(x - r * 0.3, y - r * 0.4, r * 0.5, r * 0.3), "#7d7290")
    elif kind == "bones":
        for (x, y, a) in ((-3, 0, 0.4), (4, 2, -0.9)):
            with pen.at(x, y, a):
                pen.shape(P().M(-7, -1).L(7, -1).L(7, 1).L(-7, 1).Z(), "#d8cfbd", LINE, 0.6)
                for ex in (-7, 7):
                    pen.shape(P().circle(ex, -1.4, 1.6), "#d8cfbd", LINE, 0.5)
                    pen.shape(P().circle(ex, 1.4, 1.6), "#d8cfbd", LINE, 0.5)
    elif kind == "skull":
        pen.shape(P().M(-6, 1).C(-7, -8, 7, -8, 6, 1).L(4, 5).L(-4, 5).Z(), "#ddd4c2", LINE, 0.7)
        pen.fill(P().oval(-2.4, -1.2, 1.7, 2.0), "#2a2028")
        pen.fill(P().oval(2.4, -1.2, 1.7, 2.0), "#2a2028")
        pen.fill(P().poly([(0, 1.0), (-0.8, 2.6), (0.8, 2.6)]), "#2a2028")
        for x in (-2, 0, 2):
            pen.stroke(P().M(x, 3.4).L(x, 5), LINE, 0.5)
    elif kind == "flowers":
        for i in range(4):
            x, y = rnd.uniform(-9, 9), rnd.uniform(-5, 5)
            pen.stroke(P().M(x, y + 5).Q(x + 1, y + 2, x, y), "#2f5244", 0.9)
            for k in range(5):
                a = k / 5 * math.tau
                pen.fill(P().circle(x + math.cos(a) * 1.6, y + math.sin(a) * 1.6, 1.3), rnd.choice(["#9c6ad6", "#c47ae0", "#7d5bd0"]))
            pen.fill(P().circle(x, y, 1.0), "#ffe08a")
    elif kind == "crack":
        x, y = -12, -2
        pts = [(x, y)]
        for i in range(5):
            x += rnd.uniform(4, 7)
            y += rnd.uniform(-3, 3)
            pts.append((x, y))
        pen.stroke(P().poly(pts, close=False), LINE, 1.2)
    elif kind == "puddle":
        pen.fill(P().oval(0, 0, 16, 6), "#1b1426", alpha=220)
        pen.fill(P().oval(-3, -1.5, 8, 2), "#4a4066", alpha=160)


DECALS = ["grass", "grass", "pebbles", "bones", "skull", "flowers", "crack", "puddle"]
DECAL_WEIGHTS = [5, 5, 3, 1, 1, 2, 3, 2]


# ------------------------------------------------------------------ objetos em pé (ordenados com os personagens)
GRAVE = "#77708a"
GRAVE_SH = "#4f4960"
GRAVE_HL = "#a59cbb"
GRAVE_LINE = "#1d1826"


def prop(pen, kind):
    """Objeto com a base em (0, 0)."""
    if kind == "tomb":
        t = P().M(-15, 0).L(-15, -30).C(-15, -46, 15, -46, 15, -30).L(15, 0).Z()
        pen.fill(t, GRAVE)
        with pen.clip(t):
            pen.fill(P().M(6, -50).L(20, -50).L(20, 2).L(6, 2).Z(), GRAVE_SH)
            pen.fill(P().oval(-6, -34, 5, 9), GRAVE_HL, alpha=140)
            pen.fill(P().oval(-4, -2, 16, 5), MOSS, alpha=230)
            pen.fill(P().oval(-8, -4, 6, 2.4), MOSS_HL, alpha=200)
        pen.stroke(t, GRAVE_LINE, 1.2)
        pen.stroke(P().M(0, -34).L(0, -16), GRAVE_SH, 1.8)
        pen.stroke(P().M(-6, -28).L(6, -28), GRAVE_SH, 1.8)
        for y in (-12, -8):
            pen.stroke(P().M(-8, y).L(8, y), GRAVE_SH, 0.9)
    elif kind == "tomb2":
        t = P().M(-17, 0).L(-17, -26).L(-12, -34).L(12, -34).L(17, -26).L(17, 0).Z()
        pen.fill(t, mix(GRAVE, "#5a5468", 0.3))
        with pen.clip(t):
            pen.fill(P().M(8, -40).L(20, -40).L(20, 2).L(8, 2).Z(), GRAVE_SH)
            pen.stroke(P().M(-6, -34).L(-2, -22).L(4, -16).L(2, -6), GRAVE_LINE, 1.0)
            pen.fill(P().oval(0, -1, 18, 5), MOSS, alpha=220)
        pen.stroke(t, GRAVE_LINE, 1.2)
        pen.stroke(P().M(-10, -24).L(10, -24), GRAVE_HL, 1.0, alpha=160)
    elif kind == "cross":
        c = P().M(-3.5, 0).L(-3.5, -34).L(-12, -34).L(-12, -41).L(-3.5, -41).L(-3.5, -50).L(3.5, -50).L(3.5, -41).L(12, -41) \
            .L(12, -34).L(3.5, -34).L(3.5, 0).Z()
        pen.fill(c, GRAVE)
        with pen.clip(c):
            pen.fill(P().M(1.5, -52).L(14, -52).L(14, 2).L(1.5, 2).Z(), GRAVE_SH)
            pen.fill(P().oval(-1, -2, 6, 4), MOSS, alpha=220)
        pen.stroke(c, GRAVE_LINE, 1.2)
        pen.shape(P().M(-9, 0).L(9, 0).L(7, -5).L(-7, -5).Z(), GRAVE_SH, GRAVE_LINE, 1.0)
    elif kind == "woodcross":
        with pen.at(0, 0, 0.12):
            for (x0, y0, x1, y1, w) in ((0, 0, 0, -38, 4.4), (-10, -28, 10, -29, 3.8)):
                pen.shape(tapered([(x0, y0), ((x0 + x1) / 2, (y0 + y1) / 2), (x1, y1)], w, w, w), "#5c3f2c", "#1e130c", 1.0)
            pen.stroke(P().M(-4, -27).L(4, -31), "#b9a27a", 0.9)
            pen.stroke(P().M(-4, -31).L(4, -27), "#b9a27a", 0.9)
    elif kind == "candles":
        for (x, h) in ((-7, 14), (0, 20), (7, 11)):
            pen.shape(P().M(x - 2.6, 0).L(x - 2.6, -h).L(x + 2.6, -h).L(x + 2.6, 0).Z(), "#efe6d6", "#3a3030", 0.8)
            pen.fill(P().M(x + 2.6, -h).Q(x + 3.4, -h + 3, x + 2.8, -h + 6).L(x + 2.6, -h + 6).Z(), "#efe6d6")
            pen.stroke(P().M(x, -h).L(x, -h - 2), "#2a2020", 0.6)
            pen.fill(P().M(x, -h - 9).C(x + 2.6, -h - 5, x + 2.2, -h - 2, x, -h - 1.6).C(x - 2.2, -h - 2, x - 2.6, -h - 5, x, -h - 9).Z(), "#ffb340")
            pen.fill(P().M(x, -h - 6).C(x + 1.2, -h - 4, x + 1.0, -h - 2.6, x, -h - 2.4).C(x - 1.0, -h - 2.6, x - 1.2, -h - 4, x, -h - 6).Z(), "#fff1b8")
        pen.fill(P().oval(0, 0, 13, 3), "#e8ddcc", alpha=150)
    elif kind == "bush":
        for (x, y, r) in ((-9, -8, 8), (2, -12, 10), (10, -6, 7), (-1, -4, 9)):
            pen.shape(P().circle(x, y, r), "#26413a", "#0e1a16", 1.0)
            pen.fill(P().circle(x - r * 0.3, y - r * 0.35, r * 0.4), "#355a4c", alpha=200)
        for i in range(6):
            a = -math.pi / 2 + (i - 2.5) * 0.4
            pen.stroke(P().M(0, -10).L(math.cos(a) * 20, -10 + math.sin(a) * 14), "#1a120e", 1.2)


PROPS = ["tomb", "tomb", "tomb2", "cross", "woodcross", "candles", "bush"]
PROP_CANDLE_FLAMES = [(-7, -14 - 5), (0, -20 - 5), (7, -11 - 5)]
