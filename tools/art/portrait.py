"""Retratos do HUD: busto da Vampirinha com expressões por estado + moldura."""
import math

from . import vampire as v
from .kit import P, add, rot

SIZE = 176
CENTER = (88, 96)       # centro do círculo da moldura
RADIUS = 62
SCALE = 2.7
HEAD_AT = (86, 88)      # onde fica o centro da cabeça no retrato

STATES = {
    # nome: (expressão, pálida, brilho nos olhos, inclinação)
    "normal": ("p_normal", 0.0, False, 0.04),
    "normal_blink": ("p_normal_blink", 0.0, False, 0.04),
    "normal_spit": ("p_normal_spit", 0.0, False, 0.10),
    "frenzy": ("p_frenzy", 0.0, True, -0.03),
    "frenzy_blink": ("p_frenzy_blink", 0.0, True, -0.03),
    "frenzy_spit": ("p_frenzy_spit", 0.0, True, 0.08),
    "low": ("p_low", 0.65, False, 0.10),
    "low_blink": ("p_low_blink", 0.65, False, 0.10),
    "low_spit": ("p_low_spit", 0.65, False, 0.14),
    "hurt": ("p_hurt", 0.0, False, -0.12),
    "dead": ("p_dead", 0.95, False, 0.22),
}


def portrait_pose(state):
    expr, pale, glow, tilt = STATES[state]
    tails = {"frenzy": -0.35, "frenzy_blink": -0.35, "frenzy_spit": -0.35, "hurt": 0.4}.get(state, 0.0)
    return v.pose(expr=expr, pale=pale, glow=glow, head=tilt, detail=True, tails=tails,
                  arm_n=(0.12, 0.2), arm_f=(-0.1, 0.2), ahoge=1.2 if state.startswith("frenzy") else 0.0)


def head_world(ps):
    J = v.joints(ps, False)
    return J["head"], J["head_ang"]


def draw_portrait(state):
    ps = portrait_pose(state)
    (hx, hy), ang = head_world(ps)
    ox = HEAD_AT[0] / SCALE - hx
    oy = HEAD_AT[1] / SCALE - hy

    def draw(pen):
        # a pena já vem escalada; desenha o corpo inteiro e o recorte cuida do resto
        with pen.at(ox, oy):
            v.draw_vampire(pen, ps, "front")
            if state == "dead":  # alminha saindo pela boca
                m = add((hx, hy), rot((4.2, 11.4), ang))
                with pen.at(m[0] + 5.5, m[1] - 6.0, 0.35):
                    g = P().M(0, -4.6).C(3.4, -4.6, 4.2, -1.0, 4.0, 2.2).L(2.6, 1.2).L(1.4, 2.8).L(0.2, 1.4).L(-1.2, 2.8) \
                        .C(-2.4, 1.0, -3.4, -4.6, 0, -4.6).Z()
                    pen.shape(g, "#f2f4ff", "#7d86b8", 0.4)
                    pen.fill(P().circle(-0.6, -2.0, 0.45), "#2a2a40")
                    pen.fill(P().circle(1.6, -2.0, 0.45), "#2a2a40")
                    pen.stroke(P().M(-2.0, 2.0).Q(-4.5, 3.0, -5.5, 6.0), "#c8ccef", 0.5)
    mouth = add((hx, hy), rot((4.2, 12.4), ang))
    mouth_px = ((mouth[0] + ox) * SCALE, (mouth[1] + oy) * SCALE)
    return draw, mouth_px


def draw_bat_portrait():
    def draw(pen):
        with pen.at(HEAD_AT[0] / SCALE + 1.5, HEAD_AT[1] / SCALE + 4.0):
            v.draw_bat(pen, flap=0.55, mood="normal", scale=1.25)
    return draw, ((HEAD_AT[0] / SCALE + 1.5 + 2.6 * 1.25) * SCALE, (HEAD_AT[1] / SCALE + 4.0 + 2.0 * 1.25) * SCALE)


def mask_portrait(arr):
    """Recorta o busto: círculo embaixo, livre em cima (a cabeça sai da moldura)."""
    import numpy as np
    h, w = arr.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = CENTER
    d = np.sqrt((xx + 0.5 - cx) ** 2 + (yy + 0.5 - cy) ** 2)
    circ = np.clip(RADIUS - 1.0 - d + 0.5, 0, 1)
    top = np.clip((cy - 6 - (yy + 0.5)) / 6.0, 0, 1)
    # acima do centro a cabeça pode sair da moldura (num círculo maior, sem cortes retos)
    big = np.clip(RADIUS + 18 - d, 0, 1)
    m = np.maximum(circ, top * big)
    out = arr.copy()
    out[:, :, 3] = (out[:, :, 3].astype(np.float32) * m).astype(np.uint8)
    return out


# ------------------------------------------------------------------ moldura
METAL = "#2b2036"
METAL_HL = "#8e7fb4"
METAL_SH = "#150d1c"


def draw_frame(front=True):
    """Anel gótico com asinhas e joia. front=False: anel inteiro (atrás do busto);
    front=True: só a metade de baixo + enfeites (na frente do busto)."""
    cx, cy, r = CENTER[0], CENTER[1], RADIUS

    def ring_arc(pen, a0, a1, w, col, alpha=255):
        n = 40
        outer = [(cx + math.cos(a0 + (a1 - a0) * i / n) * (r + w / 2), cy + math.sin(a0 + (a1 - a0) * i / n) * (r + w / 2)) for i in range(n + 1)]
        inner = [(cx + math.cos(a0 + (a1 - a0) * i / n) * (r - w / 2), cy + math.sin(a0 + (a1 - a0) * i / n) * (r - w / 2)) for i in range(n, -1, -1)]
        pen.fill(P().poly(outer + inner), col, alpha=alpha)

    def draw(pen):
        a0, a1 = (0.0, math.pi) if front else (0.0, math.tau)
        ring_arc(pen, a0, a1, 9.0, METAL_SH)
        ring_arc(pen, a0, a1, 6.0, METAL)
        ring_arc(pen, a0 + 0.02, a1 - 0.02, 1.4, METAL_HL, 200)
        if not front:
            return
        # asinhas de morcego dos lados
        for f in (-1, 1):
            with pen.at(cx + f * (r + 2), cy + 8, 0.0, 1.0):
                w = P().M(0, -10).C(f * 8, -18, f * 20, -18, f * 26, -8).Q(f * 21, -6, f * 21, -1).Q(f * 16, -4, f * 14, 1) \
                    .Q(f * 10, -3, f * 6, 3).Q(f * 3, -1, 0, 4).Z()
                pen.shape(w, METAL, METAL_SH, 1.2)
                pen.stroke(P().M(0, -9).C(f * 8, -15, f * 16, -15, f * 24, -8), METAL_HL, 0.9, alpha=200)
                for (x1, y1) in ((f * 21, -1), (f * 14, 1), (f * 6, 3)):
                    pen.stroke(P().M(f * 4, -8).L(x1, y1 - 2), METAL_SH, 0.8)
        # joia na base
        gem = P().M(cx, cy + r - 6).L(cx + 7, cy + r + 2).L(cx, cy + r + 12).L(cx - 7, cy + r + 2).Z()
        pen.shape(gem, "#c81a42", METAL_SH, 1.4)
        pen.fill(P().M(cx - 1, cy + r - 2).L(cx + 3, cy + r + 2).L(cx - 1, cy + r + 4).Z(), "#ff8aa4")
        # presas de enfeite saindo da joia
        for f in (-1, 1):
            fang = P().M(cx + f * 10, cy + r + 1).L(cx + f * 14, cy + r + 1).L(cx + f * 12.5, cy + r + 7).Z()
            pen.shape(fang, "#f4eef8", METAL_SH, 0.9)
    return draw
