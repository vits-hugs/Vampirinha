"""Projéteis, ícones dos elementos, efeitos e peças do HUD."""
import math

from . import vampire as v
from . import vampire_head as vh
from .kit import P, tapered

TOOTH = "#fffaf3"
TOOTH_SH = "#d8ccbf"
TOOTH_LINE = "#4e2c32"


def draw_tooth(pen, s=1.0, drop=False):
    """Presa apontando para +x (raiz à esquerda), centro em (0, 0)."""
    with pen.at(0, 0, 0, s):
        t = P().M(-5.2, -3.4).C(-2.0, -4.6, 2.0, -3.2, 5.6, 0.0).C(2.0, 2.4, -2.0, 4.0, -5.2, 3.2).C(-6.6, 1.6, -6.6, -1.8, -5.2, -3.4).Z()
        pen.fill(t, TOOTH)
        with pen.clip(t):
            pen.fill(P().M(-7, 0.8).C(-2, 2.0, 2, 1.4, 6, 0.2).L(6, 5).L(-7, 5).Z(), TOOTH_SH)
            pen.fill(P().oval(-2.6, -1.8, 2.4, 0.8), "#ffffff")
        pen.stroke(t, TOOTH_LINE, 0.8)
        # gengiva/raiz rosada
        pen.fill(P().M(-5.4, -3.0).C(-6.8, -1.4, -6.8, 1.4, -5.4, 2.8).L(-4.4, 2.2).C(-5.4, 1.0, -5.4, -1.0, -4.4, -2.4).Z(), "#ff8aa0")
        if drop:
            pen.shape(P().M(6.2, 0.4).C(7.6, 1.6, 8.4, 3.4, 7.2, 4.2).C(6.0, 4.6, 5.4, 3.2, 6.2, 0.4).Z(), "#d0183c", "#4a0816", 0.4)


def draw_leg_prop(pen, s=1.0):
    """A perninha cuspida: meia preta, liga de renda e o sapatinho; aponta para +x."""
    with pen.at(0, 0, 0, s):
        leg = tapered([(-11, 0), (-3, 0.2), (5, 0.6), (8.6, 0.8)], 5.2, 3.4, 4.4)
        pen.shape(leg, v.STOCK, v.LINE, 0.8)
        pen.fill(tapered([(-10, -1.2), (-2, -1.0), (6, -0.6)], 1.2, 0.5, 1.0), v.STOCK_HL)
        # liga de renda no topo
        garter = P().M(-12.6, -3.2).L(-9.6, -3.4).L(-9.4, 3.4).L(-12.4, 3.2).Z()
        pen.shape(garter, v.LACE, v.LINE, 0.6)
        pen.fill(P().circle(-11.0, 0.0, 1.0), vh.RIBBON)
        with pen.at(9.4, 0.8, -math.pi / 2):
            v.draw_shoe(pen, (0, 0), 0.0)


def draw_arm_prop(pen, s=1.0):
    """O braço bumerangue: manga bufante, braço, punho rendado e mão fechada; aponta para +x
    e fica centrado na origem (é em volta dela que ele gira)."""
    with pen.at(-8.6 * s, 0, 0, s):
        v.draw_arm(pen, (0, 0), math.pi / 2, 0.0, fist=True)


def draw_streak(pen, color="#ffe9f0"):
    """Rastro de velocidade (para os dentes): mais forte na ponta da frente (+x)."""
    from .kit import rgb
    import skia
    body = P().M(-22, 0).C(-8, -2.2, 6, -3.6, 14, -2.6).C(17, -1.4, 17, 1.4, 14, 2.6).C(6, 3.6, -8, 2.2, -22, 0).Z()
    pen.fill(body, "#ff4d6d", alpha=110, blur=2.0)
    paint = skia.Paint(AntiAlias=True)
    paint.setShader(skia.GradientShader.MakeLinear([skia.Point(-22, 0), skia.Point(16, 0)],
                                                   [rgb(color, 0), rgb(color, 170), rgb("#ffffff", 240)], [0.0, 0.6, 1.0]))
    pen.c.drawPath(P().M(-20, 0).C(-6, -1.2, 6, -2.2, 13, -1.6).C(15, -0.8, 15, 0.8, 13, 1.6).C(6, 2.2, -6, 1.2, -20, 0).Z().path, paint)


def draw_bullet(pen, enemy=True, k=0):
    if enemy:
        pen.fill(P().circle(0, 0, 8.5), "#ff5a1e", alpha=70, blur=3.0)
        pen.fill(P().circle(0, 0, 5.4), "#7a1414")
        pen.fill(P().circle(0, 0, 4.0 + k * 0.4), "#ffcf5a")
        pen.fill(P().circle(-1.2, -1.2, 1.4), "#fff6d0")
    else:  # tiro devolvido (embrulhado em sangue)
        pen.fill(P().circle(0, 0, 11), "#ff2a3a", alpha=80, blur=3.5)
        pen.fill(P().circle(0, 0, 7.2), "#9e0d26")
        pen.fill(P().circle(0, 0, 5.6 + k * 0.5), "#ff8a3a")
        pen.fill(P().circle(-1.6, -1.6, 2.0), "#fff2c8")
        pen.stroke(P().circle(0, 0, 7.2), "#3a0410", 0.8)


def draw_icon(pen, elem):
    """Ícones dos elementos para a fila (44 px), centro em (0, 0)."""
    if elem == "T":
        with pen.at(0, 2, -math.pi / 2 - 0.25):
            draw_tooth(pen, 2.6, drop=True)
    elif elem == "A":
        with pen.at(-4, 9, -0.95, 1.55):
            v.draw_arm(pen, (0, 0), math.pi * 0.55, -0.9, fist=True)
    else:
        with pen.at(-6, -8, 0.55, 1.6):
            leg = tapered([(-6, -6), (-1, 1), (4, 8)], 5.2, 3.6, 4.4)
            pen.shape(leg, v.STOCK, v.LINE, 0.8)
            pen.fill(tapered([(-6, -7.4), (-1.6, -0.6), (2.6, 5.6)], 1.2, 0.6, 1.1), v.STOCK_HL)
            pen.shape(P().M(-8.4, -8.6).L(-4.2, -10.6).L(-2.6, -7.2).L(-6.8, -5.2).Z(), v.LACE, v.LINE, 0.6)
            v.draw_shoe(pen, (4.6, 8.6), -0.55)


# ------------------------------------------------------------------ HUD
HUD_METAL = "#2b2036"
HUD_METAL_HL = "#8e7fb4"
HUD_METAL_SH = "#150d1c"
BAR_SIZE = (430, 46)
BAR_INNER = (22, 13, 392, 20)   # x, y, w, h da área do sangue dentro da moldura


def draw_bar_frame(pen):
    x, y, w, h = BAR_INNER
    outer = P().M(x - 8, y - 6).L(x + w + 4, y - 6).Q(x + w + 14, y + h / 2, x + w + 4, y + h + 6).L(x - 8, y + h + 6).Z()
    inner = P().M(x, y).L(x + w, y).Q(x + w + 6, y + h / 2, x + w, y + h).L(x, y + h).Z()
    from .kit import subtract
    ring = subtract(outer, inner)
    pen.fill(ring, HUD_METAL)
    pen.stroke(outer, HUD_METAL_SH, 1.6)
    pen.stroke(inner, HUD_METAL_SH, 1.2)
    pen.stroke(P().M(x - 6, y - 4).L(x + w + 3, y - 4), HUD_METAL_HL, 0.9, alpha=200)
    # marcas de 25/50/75%
    for k in (0.25, 0.5, 0.75):
        mx = x + w * k
        pen.fill(P().poly([(mx - 3, y + h + 5), (mx + 3, y + h + 5), (mx, y + h - 1)]), HUD_METAL_HL)
    # ponteira em asa de morcego
    ex = x + w + 10
    with pen.at(ex, y + h / 2, 0.0, 1.35):
        wing = P().M(-4, -6).C(4, -16, 14, -16, 20, -8).Q(16, -6, 16, -2).Q(12, -4, 10, 0).Q(8, -3, 4, 3).Q(2, 0, -4, 6).Z()
        pen.shape(wing, HUD_METAL, HUD_METAL_SH, 1.2)
        pen.stroke(P().M(-2, -6).C(4, -13, 12, -13, 18, -8), HUD_METAL_HL, 0.8, alpha=200)
        pen.shape(P().circle(0, 0, 4.6), "#c81a42", HUD_METAL_SH, 1.0)
        pen.fill(P().circle(-1.2, -1.2, 1.4), "#ff9db2")


def draw_slot(pen, size=68):
    r = size / 2 - 3
    box = P().M(-r + 8, -r).L(r - 8, -r).L(r, -r + 8).L(r, r - 8).L(r - 8, r).L(-r + 8, r).L(-r, r - 8).L(-r, -r + 8).Z()
    pen.fill(box, "#140c1a", alpha=225)
    pen.stroke(box, HUD_METAL_SH, 4.0)
    pen.stroke(box, HUD_METAL, 2.4)
    pen.stroke(P().M(-r + 8, -r + 1.2).L(r - 8, -r + 1.2), HUD_METAL_HL, 0.8, alpha=180)
    for (cx, cy) in ((-r + 2.5, -r + 2.5), (r - 2.5, -r + 2.5), (-r + 2.5, r - 2.5), (r - 2.5, r - 2.5)):
        pen.shape(P().circle(cx, cy, 2.2), HUD_METAL_HL, HUD_METAL_SH, 0.6)
