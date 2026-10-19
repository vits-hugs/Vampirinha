"""Corpo, poses e animações da Vampirinha (sprite do jogador) + forma de morcego.

Coordenadas do sprite: pés em (0, 0), y para baixo, 1 unidade = 1 px.
Vistas: "front" (3/4 de frente, olhando para a direita) e "back" (3/4 de costas,
olhando para cima-direita). A esquerda é o espelho, feito no jogo.

Convenção de ângulos (radianos): 0 = membro apontando para baixo; positivo gira
para +x (para a frente). Cotovelo positivo dobra para a frente; joelho positivo
dobra para trás.
"""
import math

from . import vampire_head as vh
from .kit import P, add, lerp, lerp2, mix, rot, tapered

# ------------------------------------------------------------------ paleta da roupa
DRESS = "#a3162f"
DRESS_SH = "#680b1e"
DRESS_HL = "#d33a55"
CORSET = "#1d1420"
LACE = "#fff6f8"
LACE_SH = "#e4cad8"
CAPE_OUT = "#1b1219"
CAPE_OUT_HL = "#3e2c40"
CAPE_IN = "#a3162f"
CAPE_IN_SH = "#5e0a1c"
STOCK = "#211823"
STOCK_HL = "#4a3a50"
SHOE = "#5e1428"
SHOE_HL = "#9a2c45"
SOLE = "#1c0f18"
LINE = "#2a1028"
GEM = "#ff2a4a"

SKIN, SKIN_SH, SKIN_LINE = vh.SKIN, vh.SKIN_SH, vh.SKIN_LINE

THIGH, SHIN = 10.6, 10.4
UPPER, FORE = 7.6, 7.0
HIP_Y = -24.5


def pose(**kw):
    d = dict(bob=0.0, lean=0.0, head=0.0, hx=0.0, hy=0.0,
             arm_n=(0.22, 0.30), arm_f=(-0.16, 0.30),
             leg_n=(0.05, 0.0), leg_f=(-0.05, 0.0),
             foot_n=0.0, foot_f=0.0, hip=0.0, hip_x=0.0,
             cape=0.0, wave=0.0, tails=0.0, skirt=0.0, skirt_swing=0.0,
             expr="normal", fist_n=False, fist_f=False,
             no_arm=False, no_leg=False, smear=None, pale=0.0, glow=False, ahoge=0.0,
             st_arm=1.0, st_leg=1.0, spit=False, lift=0.0, detail=False)
    d.update(kw)
    return d


def _dir(a):
    return (math.sin(a), math.cos(a))


# ------------------------------------------------------------------ peças
def draw_shoe(pen, ankle, ang, flip=1, far=False, back=False):
    with pen.at(ankle[0], ankle[1], ang):
        if back:  # vista de costas: calcanhar para a câmera
            sh = P().M(-2.6, -1.0).C(-3.2, 2.0, -2.0, 3.8, 0.4, 3.8).L(3.2, 3.6).C(5.0, 3.0, 5.0, 0.8, 3.6, -0.2).C(2.2, -1.2, -0.6, -1.6, -2.6, -1.0).Z()
        else:
            sh = P().M(-2.4, -1.2).C(-2.8, 1.8, -1.8, 3.8, 0.2, 3.8).L(4.4, 3.8).C(6.6, 3.8, 6.9, 1.2, 5.2, 0.2).C(3.8, -0.7, 1.2, -1.5, -2.4, -1.2).Z()
        pen.fill(sh, SHOE if not far else mix(SHOE, "#000000", 0.25))
        with pen.clip(sh):
            pen.fill(P().M(-4, 2.8).L(8, 2.8).L(8, 5).L(-4, 5).Z(), SOLE)
            if not back:
                pen.fill(P().oval(2.6, 0.6, 2.2, 0.9), SHOE_HL, alpha=200)
                pen.stroke(P().M(-1.2, 0.2).Q(0.8, 1.0, 2.4, 0.0), LACE, 0.6, alpha=230)  # tira
            else:
                pen.fill(P().oval(-0.6, 0.8, 1.6, 0.8), SHOE_HL, alpha=180)
        pen.stroke(sh, LINE, 0.75)


def draw_leg(pen, hip, h, k, foot, far=False, back=False, stretch=1.0):
    knee = add(hip, _dir(h), THIGH * stretch)
    ankle = add(knee, _dir(h - k), SHIN * stretch)
    pts = [hip, lerp2(hip, knee, 0.5), knee, lerp2(knee, ankle, 0.5), ankle]
    leg = tapered(pts, 4.8, 2.9, 3.9)
    col = STOCK if not far else mix(STOCK, "#000000", 0.25)
    pen.fill(leg, col)
    with pen.clip(leg):
        hl = [(x - 0.9, y) for x, y in pts[1:]]
        pen.fill(tapered(hl, 1.0, 0.4, 0.9), STOCK_HL, alpha=200 if not far else 120)
    pen.stroke(leg, LINE, 0.75)
    draw_shoe(pen, ankle, foot + (h - k) * 0.25, far=far, back=back)
    return knee, ankle


def draw_arm(pen, sh, a, e, fist=False, far=False, sleeve=True, stump=False, stretch=1.0):
    """Braço: ombro bufante, braço de pele, punho rendado, mão (ou só o toco)."""
    skin = SKIN if not far else SKIN_SH
    if not stump:
        elbow = add(sh, _dir(a), UPPER * stretch)
        hand = add(elbow, _dir(a + e), FORE * stretch)
        pts = [sh, lerp2(sh, elbow, 0.5), elbow, lerp2(elbow, hand, 0.5), hand]
        arm = tapered(pts, 3.9, 2.9, 3.2)
        pen.fill(arm, skin)
        with pen.clip(arm):
            pen.fill(tapered([(x + 0.9, y) for x, y in pts], 1.2, 0.8, 1.2), SKIN_SH, alpha=200)
        pen.stroke(arm, SKIN_LINE, 0.7)
        # punho de renda preta no pulso
        wr = lerp2(elbow, hand, 0.62)
        d = _dir(a + e)
        cuff = tapered([add(wr, d, -0.9), wr, add(wr, d, 0.9)], 3.6, 3.6, 4.2)
        pen.shape(cuff, CORSET, LINE, 0.5)
        # mão
        hr = 3.0 if fist else 2.3
        hc = add(hand, d, 0.8)
        pen.shape(P().circle(hc[0], hc[1], hr), skin, SKIN_LINE, 0.7)
        if fist:
            perp = (-d[1], d[0])
            for k in (-0.8, 0.8):
                q0 = add(add(hc, d, hr * 0.35), perp, k)
                pen.stroke(P().M(*q0).L(*add(q0, d, hr * 0.5)), SKIN_LINE, 0.4)
    else:
        hand = sh
    if sleeve:
        r = 3.7 if not far else 3.2
        puff = P().circle(sh[0], sh[1] - 0.3, r)
        pen.fill(puff, DRESS if not far else DRESS_SH)
        with pen.clip(puff):
            pen.fill(P().circle(sh[0] - 1.0, sh[1] - 1.6, r * 0.55), DRESS_HL, alpha=170)
            pen.fill(P().oval(sh[0], sh[1] + r * 0.9, r * 1.1, r * 0.42), LACE)
        pen.stroke(puff, LINE, 0.75)
        if stump:  # bracinho sumiu: fiapo de sangue
            pen.fill(P().oval(sh[0], sh[1] + r + 0.4, 1.4, 0.9), "#d01a3c")
            pen.fill(P().M(sh[0] - 0.4, sh[1] + r + 0.8).Q(sh[0], sh[1] + r + 3.0, sh[0] + 0.5, sh[1] + r + 0.8).Z(), "#d01a3c")
    return hand


def skirt_path(flare, swing):
    wl, wr = (-6.2, -11.6), (5.8, -11.6)
    hl = (-14.6 - flare * 2.5 + swing, 3.4 - flare * 2.2)
    hr = (14.0 + flare * 1.5 + swing, 3.0 - flare * 1.2)
    p = P().M(*wl).C(wl[0] - 2.2, wl[1] + 5.0, hl[0] + 2.4, hl[1] - 4.2, *hl)
    # barra ondulada
    n = 8
    pts = []
    for i in range(1, n + 1):
        t = i / n
        x = lerp(hl[0], hr[0], t)
        y = lerp(hl[1], hr[1], t) + math.sin(t * math.pi) * 1.8
        pts.append((x, y))
    prev = hl
    for i, q in enumerate(pts):
        mx, my = (prev[0] + q[0]) / 2, (prev[1] + q[1]) / 2 + 1.3
        p.Q(mx, my, *q)
        prev = q
    p.C(hr[0] - 2.2, hr[1] - 4.2, wr[0] + 2.2, wr[1] + 5.0, *wr)
    p.Z()
    return p, hl, hr


def draw_skirt(pen, flare=0.0, swing=0.0, back=False):
    sp, hl, hr = skirt_path(flare, swing)
    # anágua de renda aparecendo por baixo
    pet = P().M(hl[0] + 0.6, hl[1] - 1.2)
    n = 9
    prev = (hl[0] + 0.6, hl[1] - 1.2)
    for i in range(1, n + 1):
        t = i / n
        q = (lerp(hl[0] + 0.4, hr[0] - 0.4, t), lerp(hl[1], hr[1], t) + math.sin(t * math.pi) * 1.8 + 1.6)
        mx, my = (prev[0] + q[0]) / 2, (prev[1] + q[1]) / 2 + 1.5
        pet.Q(mx, my, *q)
        prev = q
    pet.L(hr[0] - 0.6, hr[1] - 2.0).L(0, -2).Z()
    pen.shape(pet, LACE, LINE, 0.6)
    pen.fill(sp, DRESS if not back else DRESS_SH)
    with pen.clip(sp):
        # pregas
        for x0, x1 in ((-3.2, -9.5), (0.4, -2.0), (3.6, 6.5)):
            pen.fill(P().M(x0, -12).L(x0 + 0.9, -12).L(x1 + 2.2, 8).L(x1 - 1.4, 8).Z(), DRESS_SH, alpha=200)
        pen.fill(P().M(6, -12).C(10, -6, 14, 0, 16, 8).L(20, 8).L(20, -12).Z(), DRESS_SH, alpha=170)
        pen.fill(P().oval(-6, -6.5, 2.6, 4.2), DRESS_HL, alpha=120)
        # renda na barra
        pen.stroke(sp, LACE, 1.6, alpha=0)
    pen.stroke(sp, LINE, 0.8)


def bodice_path():
    return P().M(-7.6, -21.2).C(-8.6, -17.4, -7.4, -14.2, -6.4, -11.4).L(6.0, -11.4).C(6.8, -14.2, 7.6, -17.4, 6.6, -21.4) \
        .C(3.0, -22.8, -4.0, -22.8, -7.6, -21.2).Z()


def draw_torso(pen, back=False):
    bp = bodice_path()
    pen.fill(bp, DRESS if not back else DRESS_SH)
    with pen.clip(bp):
        pen.fill(P().M(3.6, -24).C(6, -18, 5.4, -14, 4.2, -10).L(10, -10).L(10, -24).Z(), DRESS_SH, alpha=220)
        # espartilho
        pen.fill(P().M(-9, -14.6).L(9, -14.6).L(9, -10).L(-9, -10).Z(), CORSET)
        if not back:
            for i in range(3):
                y = -14.1 + i * 1.15
                pen.stroke(P().M(-0.6, y).L(1.6, y + 0.9), LACE, 0.35, alpha=210)
                pen.stroke(P().M(1.6, y).L(-0.6, y + 0.9), LACE, 0.35, alpha=210)
        pen.fill(P().oval(-4.2, -18.5, 1.8, 2.6), DRESS_HL, alpha=110)
    pen.stroke(bp, LINE, 0.8)
    if not back:
        # gola de babado (jabô) + broche
        jab = P().M(-5.0, -22.6).C(-5.8, -20.2, -3.8, -17.6, 0.6, -15.4).C(4.8, -17.6, 6.4, -20.4, 5.8, -22.8).Z()
        pen.fill(jab, LACE)
        with pen.clip(jab):
            pen.fill(P().oval(2.8, -18.6, 3.0, 3.6), LACE_SH)
            for k in range(4):
                y = -21.6 + k * 1.5
                pen.stroke(P().M(-4.4 + k * 0.9, y).Q(0.6, y + 1.2, 5.2 - k * 0.8, y - 0.2), LACE_SH, 0.4)
        pen.stroke(jab, LINE, 0.65)
        pen.fill(P().circle(0.6, -20.4, 1.55), GEM)
        pen.stroke(P().circle(0.6, -20.4, 1.55), LINE, 0.5)
        pen.fill(P().circle(0.2, -20.9, 0.5), "#ffd0d8")
    else:
        pen.stroke(P().M(-1.0, -22.4).L(-0.6, -11.8), DRESS_SH, 0.5)


def cape_shape(flare, wave, back=False):
    f, w = flare, wave
    if not back:
        p = P().M(-8.6, -21.0)
        p.C(-13.5 - f * 5, -12.0, -18.6 - f * 9, 1.0 + w, -20.6 - f * 12 + w * 0.6, 14.4 - f * 7)
        p.L(-13.6 - f * 7, 11.6 - f * 4 + w * 0.5)
        p.L(-6.8 - f * 4, 16.4 - f * 2)
        p.L(0.4 - f * 1.5, 13.0 + w * 0.3)
        p.L(7.4, 16.2)
        p.L(15.6, 12.0)
        p.C(17.4, 3.0, 12.6, -12.0, 7.6, -21.4)
        p.C(3.0, -23.5, -4.0, -23.5, -8.6, -21.0).Z()
    else:
        p = P().M(-8.8, -21.4)
        p.C(-12.4 - f * 6, -12.0, -15.6 - f * 10, 1.0 + w, -17.0 - f * 13 + w * 0.6, 14.4 - f * 7)
        p.L(-10.8 - f * 8, 11.6 - f * 4 + w * 0.5)
        p.L(-4.6 - f * 4, 16.2 - f * 2)
        p.L(1.6 - f * 1.5, 12.8 + w * 0.3)
        p.L(7.6, 15.8)
        p.L(13.6, 12.0)
        p.C(15.2, 3.0, 12.0, -12.0, 8.2, -21.2)
        p.C(3.0, -24.0, -4.0, -24.0, -8.8, -21.4).Z()
    return p


def draw_cape(pen, flare=0.0, wave=0.0, back=False):
    f, w = flare, wave
    cp = cape_shape(flare, wave, back)
    if not back:
        # de frente vemos o forro vermelho, com a borda externa preta
        pen.fill(cp, CAPE_IN)
        with pen.clip(cp):
            pen.radial(P().circle(0, -6, 26), (0.5, -6), 18, [CAPE_IN_SH, CAPE_IN_SH, CAPE_IN], [0.0, 0.45, 1.0])
            pen.stroke(cp, CAPE_OUT, 4.4)
            # dobra externa aparecendo no lado que voa
            if flare > 0.15:
                fl = P().M(-9, -18).C(-13 - flare * 6, -8, -16 - flare * 10, 2, -18 - flare * 12, 14 - flare * 7).L(-12 - flare * 8, 12).C(-12, 2, -10, -8, -9, -18).Z()
                pen.fill(fl, CAPE_OUT)
                pen.stroke(P().M(-10.5, -14).C(-13 - flare * 6, -6, -15 - flare * 9, 3, -16 - flare * 10, 10), CAPE_OUT_HL, 0.7)
        pen.stroke(cp, LINE, 0.85)
        pen.stroke(P().M(-9.4, -19.0).C(-14.0 - f * 5, -10.0, -18.4 - f * 9, 2.0 + w, -20.0 - f * 12 + w * 0.6, 13.0 - f * 7), CAPE_OUT_HL, 0.8, alpha=230)
    else:
        pen.fill(cp, CAPE_OUT)
        with pen.clip(cp):
            pen.fill(P().M(4, -24).C(12, -10, 14, 2, 14, 20).L(20, 20).L(20, -24).Z(), "#1c1124", alpha=220)
            for x0, x1 in ((-4.0, -8.0 - flare * 6), (2.0, 0.0 - flare * 3), (7.0, 8.0)):
                pen.stroke(P().M(x0, -18).Q((x0 + x1) / 2 - 1, 0, x1, 14), CAPE_OUT_HL, 0.7, alpha=200)
            # forro vermelho aparecendo na barra
            pen.fill(P().M(-24 - f * 13, 13.6 - f * 7).L(-17.0 - f * 13 + w * 0.6, 14.4 - f * 7).L(-10.8 - f * 8, 11.6 - f * 4 + w * 0.5)
                     .L(-4.6 - f * 4, 16.2 - f * 2).L(1.6 - f * 1.5, 12.8 + w * 0.3).L(7.6, 15.8).L(13.6, 12.0).L(20, 13).L(20, 20).L(-24, 20).Z(), CAPE_IN, alpha=0)
            hem = [(-17.0 - f * 13 + w * 0.6, 14.4 - f * 7), (-10.8 - f * 8, 11.6 - f * 4 + w * 0.5), (-4.6 - f * 4, 16.2 - f * 2),
                   (1.6 - f * 1.5, 12.8 + w * 0.3), (7.6, 15.8), (13.6, 12.0)]
            pen.stroke(P().poly(hem, close=False), CAPE_IN, 2.2)
            # forro aparecendo na barra que voa
            if flare > 0.15:
                pen.fill(P().M(-18 - flare * 13, 15).L(-11 - flare * 8, 10).L(-4 - flare * 4, 14).L(-6, 18).L(-20 - flare * 13, 18).Z(), CAPE_IN, alpha=255)
        pen.stroke(cp, LINE, 0.85)


def collar_path(back=False):
    if not back:
        return P().M(-6.2, -21.4).C(-11.0, -23.5, -18.0, -27.5, -22.6, -33.6).C(-16.0, -32.4, -8.0, -31.6, -0.8, -31.0) \
            .C(6.0, -31.6, 13.0, -32.6, 19.6, -35.0).C(15.6, -28.6, 10.2, -23.8, 6.4, -21.8).Z()
    return P().M(-6.8, -21.6).C(-12.0, -23.6, -19.0, -27.8, -23.4, -34.0).C(-16.0, -33.0, -8.0, -32.4, 0.0, -32.0) \
        .C(8.0, -32.4, 16.0, -33.0, 23.4, -34.4).C(19.0, -27.8, 12.0, -23.6, 7.0, -21.6).Z()


def draw_collar(pen, back=False):
    cp = collar_path(back)
    if not back:
        pen.fill(cp, CAPE_IN)
        with pen.clip(cp):
            pen.fill(P().M(-18, -24).C(-6, -28, 6, -28, 18, -24).L(18, -20).L(-18, -20).Z(), CAPE_IN_SH)
            pen.stroke(cp, CAPE_OUT, 2.6)
            pen.stroke(P().M(-19.6, -31.6).C(-14, -28, -9, -25, -5, -22.6), "#ff6a84", 0.6, alpha=180)
            pen.stroke(P().M(16.8, -32.6).C(12, -28, 8, -25, 5.2, -22.8), "#ff6a84", 0.6, alpha=150)
    else:
        pen.fill(cp, CAPE_OUT)
        with pen.clip(cp):
            pen.stroke(cp, CAPE_IN, 2.0)
            pen.fill(P().M(-18, -26).C(-6, -30, 6, -30, 18, -26).L(18, -20).L(-18, -20).Z(), "#1c1124", alpha=200)
    pen.stroke(cp, LINE, 0.8)


# ------------------------------------------------------------------ efeitos de movimento
def draw_smear(pen, smear, hand=None):
    if not smear:
        return
    for sm in smear:
        if sm[0] == "lines" and sm[1] is None:
            sm = ("lines", add(hand, (-4.0, 0.0)), sm[2], sm[3], sm[4])
        kind = sm[0]
        if kind == "arc":  # arco de golpe: centro, raio, ângulo inicial/final
            _, c, r, a0, a1, w = sm
            n = 14
            outer = [add(c, (math.cos(lerp(a0, a1, i / n)), math.sin(lerp(a0, a1, i / n))), r) for i in range(n + 1)]
            inner = [add(c, (math.cos(lerp(a0, a1, i / n)), math.sin(lerp(a0, a1, i / n))), r - w * (i / n) ** 1.2) for i in range(n, -1, -1)]
            pen.fill(P().poly(outer + inner), "#ffffff", alpha=95)
            pen.stroke(P().smooth(outer, close=False), "#ffffff", 0.6, alpha=170)
        elif kind == "lines":  # linhas de velocidade atrás de um ponto
            _, p0, d, n, length = sm
            perp = (-d[1], d[0])
            for i in range(n):
                off = (i - (n - 1) / 2) * 2.4
                a = add(p0, perp, off)
                a = add(a, d, -abs(off) * 0.6)
                b = add(a, d, -length * (0.6 + 0.4 * ((i * 37) % 5) / 4))
                pen.fill(tapered([a, lerp2(a, b, 0.5), b], 1.0, 0.1, 0.8), "#ffffff", alpha=170)


# ------------------------------------------------------------------ montagem
def ground_offset(ps):
    """Quanto o quadril precisa descer para o pé mais baixo encostar no chão."""
    def ank(leg, st=1.0):
        h, k = leg
        return THIGH * st * math.cos(h) + SHIN * st * math.cos(h - k)
    lows = [ank(ps["leg_f"])]
    if not ps["no_leg"]:
        lows.append(ank(ps["leg_n"], ps["st_leg"]))
    reach = max(lows)
    return (THIGH + SHIN) - reach


def joints(ps, back=False):
    H = (ps["hip_x"], HIP_Y + ps["hip"] + ground_offset(ps) - ps["lift"])
    lean = ps["lean"]

    def T(p):  # torso local -> mundo
        q = rot(p, lean)
        return (H[0] + q[0], H[1] + q[1] + ps["bob"] * 0.6)

    if not back:
        sh_n, sh_f = T((-6.9, -19.6)), T((6.1, -20.0))
        hip_n, hip_f = (H[0] - 3.4, H[1] - 0.2), (H[0] + 3.2, H[1] - 0.4)
    else:
        sh_n, sh_f = T((7.6, -18.6)), T((-6.4, -19.8))
        hip_n, hip_f = (H[0] + 3.4, H[1] - 0.2), (H[0] - 3.2, H[1] - 0.4)
    head = T((1.0 + ps["hx"], -38.6 + ps["hy"]))
    head_ang = lean * 0.55 + ps["head"]
    return dict(H=H, T=T, sh_n=sh_n, sh_f=sh_f, hip_n=hip_n, hip_f=hip_f, head=head, head_ang=head_ang)


def draw_vampire(pen, ps, view="front"):
    """Desenha a vampira inteira numa pose. Devolve âncoras úteis (boca, mão...)."""
    back = view == "back"
    J = joints(ps, back)
    expr = vh.EXPR[ps["expr"]] if isinstance(ps["expr"], str) else ps["expr"]
    hx, hy = J["head"]
    anchors = {}

    def head_at():
        return pen.at(hx, hy, J["head_ang"])

    if not back:
        with head_at():
            vh.draw_tails_front(pen, ps["tails"], 38.0)
        with pen.at(J["H"][0], J["H"][1] + ps["bob"] * 0.6, ps["lean"]):
            draw_cape(pen, ps["cape"], ps["wave"])
        with head_at():
            vh.draw_head_front(pen, expr, part="back", pale=ps["pale"])
        hand_f = draw_arm(pen, J["sh_f"], *ps["arm_f"], fist=ps["fist_f"], far=True)
        draw_leg(pen, J["hip_f"], *ps["leg_f"], ps["foot_f"], far=True)
        if not ps["no_leg"]:
            draw_leg(pen, J["hip_n"], *ps["leg_n"], ps["foot_n"], stretch=ps["st_leg"])
        with pen.at(J["H"][0], J["H"][1] + ps["bob"] * 0.6, ps["lean"] * 0.6):
            draw_skirt(pen, ps["skirt"], ps["skirt_swing"])
        with head_at():
            vh.draw_head_front(pen, expr, part="neck", pale=ps["pale"])
        with pen.at(J["H"][0], J["H"][1] + ps["bob"] * 0.6, ps["lean"]):
            draw_torso(pen)
        hand_n = draw_arm(pen, J["sh_n"], *ps["arm_n"], fist=ps["fist_n"], stump=ps["no_arm"], stretch=ps["st_arm"])
        with head_at():
            vh.draw_head_front(pen, expr, part="front", pale=ps["pale"], glow=ps["glow"], ahoge=ps["ahoge"], detail=ps["detail"])
        mouth_local = (4.2, 11.4)
    else:
        draw_leg(pen, J["hip_f"], *ps["leg_f"], ps["foot_f"], far=True, back=True)
        if not ps["no_leg"]:
            draw_leg(pen, J["hip_n"], *ps["leg_n"], ps["foot_n"], back=True, stretch=ps["st_leg"])
        with pen.at(J["H"][0], J["H"][1] + ps["bob"] * 0.6, ps["lean"] * 0.6):
            draw_skirt(pen, ps["skirt"], ps["skirt_swing"], back=True)
        hand_f = draw_arm(pen, J["sh_f"], *ps["arm_f"], fist=ps["fist_f"], far=True)
        with pen.at(J["H"][0], J["H"][1] + ps["bob"] * 0.6, ps["lean"]):
            draw_torso(pen, back=True)
        # de costas o braço sai de baixo da capa
        hand_n = draw_arm(pen, J["sh_n"], *ps["arm_n"], fist=ps["fist_n"], stump=ps["no_arm"], stretch=ps["st_arm"],
                          sleeve=ps["no_arm"])
        with pen.at(J["H"][0], J["H"][1] + ps["bob"] * 0.6, ps["lean"]):
            draw_cape(pen, ps["cape"], ps["wave"], back=True)
        with head_at():
            vh.draw_head_back(pen, part="hair", ahoge=ps["ahoge"])
            vh.draw_tails_back(pen, ps["tails"], 38.0)
        mouth_local = (8.0, 10.0)
    draw_smear(pen, ps["smear"], hand_n)
    anchors["mouth"] = add((hx, hy), rot(mouth_local, J["head_ang"]))
    anchors["hand_n"] = hand_n
    anchors["hand_f"] = hand_f
    anchors["head"] = (hx, hy)
    anchors["eyes"] = [add((hx, hy), rot(e, J["head_ang"])) for e in ((-5.8, 4.2), (7.5, 4.0))] if not back else []
    return anchors


# ------------------------------------------------------------------ efeitos na boca
def draw_spit_burst(pen, mouth, strength=1.0):
    """Risquinhos saindo da boca quando ela cospe."""
    for ang, ln in ((-0.55, 4.6), (0.0, 6.0), (0.55, 4.6)):
        d = (math.cos(ang), math.sin(ang))
        a = add(mouth, d, 3.0)
        b = add(a, d, ln * strength)
        pen.fill(tapered([a, lerp2(a, b, 0.5), b], 1.6, 0.3, 1.3), "#2a1028", alpha=200)
        pen.fill(tapered([a, lerp2(a, b, 0.5), b], 1.0, 0.2, 0.8), "#ffffff", alpha=255)


# ------------------------------------------------------------------ animações
def _run_cycle(no_arm=False, no_leg=False):
    # (perna perto, perna longe, braço perto, braço longe, elevação, bob)
    legs = [
        ((0.62, 0.18), (-0.55, 0.75), 0.4, 0.6),
        ((0.22, 0.45), (0.25, 1.55), 0.8, 0.0),
        ((-0.35, 0.35), (0.62, 0.70), 1.8, -0.8),
        ((-0.55, 0.75), (0.62, 0.18), 0.4, 0.6),
        ((0.25, 1.55), (0.22, 0.45), 0.8, 0.0),
        ((0.62, 0.70), (-0.35, 0.35), 1.8, -0.8),
    ]
    out = []
    for i, (ln, lf, lift, bob) in enumerate(legs):
        ph = i / 6 * math.tau
        sw = math.cos(ph)  # +1: perna perto à frente -> braço perto atrás
        out.append(pose(
            lean=0.14, bob=bob, lift=lift,
            leg_n=ln, leg_f=lf, foot_n=0.15 * sw, foot_f=-0.15 * sw,
            arm_n=(-0.75 * sw, 1.0 + 0.3 * sw), arm_f=(0.75 * sw, 1.0 - 0.3 * sw),
            cape=0.75 + 0.12 * math.sin(ph * 2), wave=2.2 * math.sin(ph), tails=-0.55 + 0.18 * math.sin(ph * 2),
            skirt=0.35 + 0.15 * math.sin(ph * 2), skirt_swing=-1.0, ahoge=-0.6 + 0.4 * math.sin(ph * 2),
            expr="normal", no_arm=no_arm, no_leg=no_leg))
    return out


def anim_poses():
    """Nome -> (fps, loop, [poses]). Variantes '_na' = sem o braço (bumerangue no ar)."""
    A = {}
    idle = []
    for i in range(4):
        ph = i / 4 * math.tau
        b = 0.5 - 0.5 * math.cos(ph)
        idle.append(pose(bob=b * 1.1, tails=0.10 * math.sin(ph), wave=0.8 * math.sin(ph), cape=0.05 * b,
                         arm_n=(0.22 + 0.04 * b, 0.30 + 0.08 * b), arm_f=(-0.16 - 0.04 * b, 0.30 + 0.08 * b),
                         ahoge=0.5 * math.sin(ph)))
    A["idle"] = (6, True, idle)
    A["run"] = (13, True, _run_cycle())

    A["punch"] = (14, False, [
        pose(expr="focus", lean=-0.10, arm_n=(-0.75, 1.95), fist_n=True, arm_f=(0.55, 1.5), fist_f=True,
             leg_n=(0.30, 0.30), leg_f=(-0.32, 0.20), tails=0.15),
        pose(expr="attack", lean=0.24, arm_n=(1.57, 0.0), fist_n=True, st_arm=1.75, arm_f=(-0.75, 0.9),
             leg_n=(0.48, 0.20), leg_f=(-0.48, 0.25), cape=0.55, tails=-0.6, skirt=0.25, skirt_swing=-0.8, ahoge=-1,
             smear=[("lines", None, (1, 0), 3, 9)]),
        pose(expr="attack", lean=0.20, arm_n=(1.52, 0.1), fist_n=True, st_arm=1.5, arm_f=(-0.65, 0.9),
             leg_n=(0.46, 0.20), leg_f=(-0.46, 0.25), cape=0.45, tails=-0.45, skirt=0.2, skirt_swing=-0.6),
        pose(expr="focus", lean=0.06, arm_n=(0.85, 1.0), fist_n=True, arm_f=(-0.2, 0.6),
             leg_n=(0.25, 0.15), leg_f=(-0.25, 0.15), tails=-0.15),
    ])
    A["kick"] = (14, False, [
        pose(expr="focus", lean=-0.14, leg_n=(1.15, 2.0), arm_n=(0.9, 0.7), arm_f=(-0.95, 0.6), skirt=0.35, tails=0.2),
        pose(expr="attack", lean=-0.26, leg_n=(1.57, 0.02), st_leg=1.4, arm_n=(-1.0, 0.6), arm_f=(-1.25, 0.5),
             skirt=0.8, skirt_swing=0.6, cape=0.35, tails=0.45, ahoge=1,
             ),
        pose(expr="attack", lean=-0.22, leg_n=(1.50, 0.15), st_leg=1.25, arm_n=(-0.9, 0.6), arm_f=(-1.1, 0.5),
             skirt=0.7, skirt_swing=0.5, cape=0.3, tails=0.35),
        pose(expr="focus", lean=-0.06, leg_n=(0.6, 1.2), arm_n=(0.4, 0.6), arm_f=(-0.5, 0.6), skirt=0.3),
    ])
    A["spit"] = (14, False, [
        pose(expr="puff", lean=-0.13, head=-0.16, arm_n=(0.45, 1.0), arm_f=(-0.35, 1.0), tails=0.15),
        pose(expr="spit", lean=0.14, head=0.16, hx=1.2, arm_n=(-0.5, 0.5), arm_f=(-0.6, 0.5), tails=-0.35,
             cape=0.25, spit=True),
        pose(expr="spit", lean=0.10, head=0.12, hx=1.0, arm_n=(-0.4, 0.5), arm_f=(-0.5, 0.5), tails=-0.25, cape=0.2),
        pose(expr="smug", lean=0.03, arm_n=(0.2, 0.4), arm_f=(-0.2, 0.4)),
    ])
    A["throw"] = (14, False, [
        pose(expr="focus", lean=-0.20, arm_n=(-1.75, 0.35), fist_n=True, arm_f=(0.7, 0.9), leg_n=(0.35, 0.2), leg_f=(-0.3, 0.2), tails=0.25),
        pose(expr="attack", lean=0.24, no_arm=True, arm_f=(-0.8, 0.7), leg_n=(0.5, 0.2), leg_f=(-0.45, 0.25), cape=0.5, tails=-0.5,
             smear=[("lines", (2, -46), (1, 0), 3, 10)]),
        pose(expr="smug", lean=0.16, no_arm=True, arm_f=(-0.6, 0.7), leg_n=(0.4, 0.2), leg_f=(-0.4, 0.2), cape=0.35, tails=-0.35),
        pose(expr="smug", lean=0.05, no_arm=True, arm_f=(-0.2, 0.5)),
    ])
    dash = []
    for i in range(2):
        dash.append(pose(expr="focus", lean=0.5, lift=1.5, leg_n=(-0.55, 1.1), leg_f=(-0.95, 0.75), arm_n=(-1.05, 0.35), arm_f=(-1.3, 0.35),
                         cape=1.0, wave=2.0 * (1 if i else -1), tails=-1.0 + 0.1 * i, skirt=0.75, skirt_swing=-2.2, ahoge=-1.5,
                         smear=[("lines", (-8, -40), (1, 0), 5, 16)]))
    A["dash"] = (16, True, dash)
    A["dash_strike"] = (16, True, [
        pose(expr="attack", lean=0.45, lift=1.5, leg_n=(-0.55, 1.1), leg_f=(-0.95, 0.75), arm_n=(1.55, 0.0), fist_n=True, st_arm=1.5,
             arm_f=(-1.3, 0.35), cape=1.0, wave=2.0 * k, tails=-1.0, skirt=0.75, skirt_swing=-2.2, ahoge=-1.5,
             smear=[("lines", (-8, -40), (1, 0), 5, 16)]) for k in (-1, 1)])
    A["hurt"] = (10, False, [
        pose(expr="hurt", lean=-0.32, head=-0.2, arm_n=(1.25, 0.7), arm_f=(-1.45, 0.6), leg_n=(0.45, 0.6), leg_f=(-0.2, 0.4),
             tails=0.7, cape=0.3, skirt=0.4, skirt_swing=1.0, ahoge=1.5),
        pose(expr="hurt", lean=-0.16, arm_n=(0.7, 0.6), arm_f=(-0.9, 0.5), leg_n=(0.25, 0.3), leg_f=(-0.15, 0.3), tails=0.3),
    ])
    A["chomp"] = (12, False, [
        pose(expr="chomp", lean=-0.18, head=-0.28, arm_n=(0.95, 1.0), arm_f=(-0.85, 1.0), tails=0.3, ahoge=1),
        pose(expr="puff", lean=0.10, head=0.10, arm_n=(0.3, 0.9), arm_f=(-0.2, 0.9)),
        pose(expr={"eyes": "closed", "brows": "normal", "mouth": "smirk"}, lean=0.0, arm_n=(0.25, 0.4), arm_f=(-0.2, 0.4)),
    ])
    A["hop"] = (8, True, [
        pose(expr={"eyes": "wide", "brows": "up", "mouth": "open"}, no_leg=True, lift=3.5, leg_f=(0.1, 0.9),
             arm_n=(1.3, 0.3), arm_f=(-1.3, 0.3), tails=0.3, skirt=0.4, ahoge=1),
        pose(expr={"eyes": "wide", "brows": "up", "mouth": "open"}, no_leg=True, lift=0.0, leg_f=(0.0, 0.1),
             arm_n=(1.0, 0.4), arm_f=(-1.0, 0.4), tails=-0.1, skirt=0.1, ahoge=-0.5),
    ])
    # variantes sem o braço (enquanto ele voa como bumerangue)
    for name in ("idle", "run", "kick", "spit", "dash", "hurt", "chomp", "hop"):
        fps, loop, frames = A[name]
        A[name + "_na"] = (fps, loop, [dict(f, no_arm=True, fist_n=False) for f in frames])
    return A


def frame_draw(ps, view):
    """Desenha uma pose e os efeitos que dependem das âncoras (cuspe)."""
    def draw(pen):
        anc = draw_vampire(pen, ps, view)
        if ps.get("spit") and view == "front":
            draw_spit_burst(pen, anc["mouth"])
        return anc
    return draw


# ------------------------------------------------------------------ forma de morcego
FUR = "#3a2f44"
FUR_SH = "#241c2c"
FUR_LINE = "#07040a"
WING = "#1b1219"
WING_IN = "#8e1029"
WING_LINE = "#050306"


def bat_wing(flap, side, scale=1.0):
    """Asa de morcego (side=+1 asa da frente/direita, -1 de trás). flap: -1 baixo .. +1 cima."""
    rootx = side * 5.5
    # pontas dos "dedos" da asa
    up = flap
    tips = [
        (side * 26 * scale, -6 - up * 15),
        (side * 22 * scale, 4 - up * 9),
        (side * 15 * scale, 9 - up * 4),
    ]
    elbow = (side * 15 * scale, -9 - up * 10)
    p = P().M(rootx, -4)
    p.Q(side * 10, -12 - up * 8, *elbow)
    p.Q(side * 22 * scale, -10 - up * 14, *tips[0])
    # membrana recortada entre os dedos
    p.Q(side * 21 * scale, 0 - up * 9, *tips[1])
    p.Q(side * 16 * scale, 4 - up * 5, *tips[2])
    p.Q(side * 10, 6 - up * 2, rootx, 3)
    p.Z()
    return p, elbow, tips


def draw_bat(pen, flap=0.0, mood="normal", lunge=0.0, tilt=0.0, scale=1.0):
    """Morcego-vampirinha, centro do corpo em (0, 0), olhando para a direita."""
    with pen.at(lunge, 0, tilt, scale):
        # asa de trás
        wb, eb, tb = bat_wing(flap * 0.9, -1, 0.85)
        pen.fill(wb, WING_IN if flap > 0.2 else WING)
        with pen.clip(wb):
            pen.fill(P().circle(-10, 0, 14), WING, alpha=150)
        for t in tb:
            pen.stroke(P().M(*eb).L(*t), WING_LINE, 0.6)
        pen.stroke(wb, WING_LINE, 0.8)
        # orelhas
        for f, x in ((-1, -3.6), (1, 3.4)):
            ear = P().M(x - 2.6, -5).L(x + f * 1.2 - 0.4, -14.5).L(x + 3.0, -4.2).Z()
            pen.shape(ear, FUR, FUR_LINE, 0.7)
            pen.fill(P().M(x - 1.2, -6).L(x + f * 0.8 - 0.3, -11.6).L(x + 1.6, -5.5).Z(), "#ff9db0")
        # corpo (bolinha de pelo)
        body = P().M(-8.6, -1).C(-9.4, -8.4, -4, -10.6, 0.4, -10.4).C(5.6, -10.4, 9.6, -7, 9.2, 0)
        body.C(9.0, 4.6, 6.2, 8.6, 1.6, 9.4).L(0.6, 11).L(-0.6, 9.4).C(-5.6, 9.2, -8.2, 5.4, -8.6, -1).Z()
        pen.fill(body, FUR)
        with pen.clip(body):
            pen.fill(P().oval(3.0, 6.0, 9, 5), FUR_SH)
            pen.fill(P().oval(-3.6, -6.4, 3.6, 2.0), "#ffffff", alpha=200)
        pen.stroke(body, FUR_LINE, 0.85)
        # topete (ahoge)
        pen.shape(tapered([(0.2, -10), (1.2, -13.4), (3.6, -15.0), (5.4, -13.6)], 2.0, 0.4, 1.4), FUR, FUR_LINE, 0.6)
        # rosto
        if mood == "dead":
            for cx in (-1.6, 4.4):
                pen.stroke(P().M(cx - 1.5, -4.5).L(cx + 1.5, -1.5), "#2a0a1c", 0.9)
                pen.stroke(P().M(cx - 1.5, -1.5).L(cx + 1.5, -4.5), "#2a0a1c", 0.9)
            pen.shape(P().M(1.2, 1.4).C(1.4, 3.6, 3.0, 3.8, 3.0, 1.4).Z(), vh.TONGUE, vh.SKIN_LINE, 0.4)
        else:
            for cx, w in ((-1.6, 2.6), (4.4, 2.1)):
                eye = P().oval(cx, -3.0, w * 0.5 + 0.4, 2.3)
                pen.grad(eye, (cx, -5.3), (cx, -0.7), ["#4a0016", "#d0122f", "#ff6a5a"], [0, 0.5, 1])
                pen.stroke(eye, "#2a0a1c", 0.55)
                pen.fill(P().oval(cx, -2.8, 0.35, 1.3), "#16000a")
                pen.fill(P().circle(cx - 0.6, -4.0, 0.7), "#ffffff")
            if mood == "bite":
                m = P().M(-0.6, 1.0).C(-0.4, 4.6, 4.6, 4.8, 5.2, 0.8).Q(2.2, 1.8, -0.6, 1.0).Z()
                pen.shape(m, vh.MOUTH_IN, vh.SKIN_LINE, 0.45)
                for fx in (0.6, 3.6):
                    pen.fill(P().poly([(fx - 0.6, 1.2), (fx + 0.6, 1.1), (fx, 3.0)]), "#ffffff")
            else:
                pen.stroke(P().M(0.2, 1.4).Q(1.6, 2.4, 3.0, 1.2), vh.SKIN_LINE, 0.55)
                pen.fill(P().poly([(1.9, 1.7), (2.8, 1.5), (2.4, 3.0)]), "#ffffff")
            pen.fill(P().oval(-3.6, 0.6, 1.5, 0.8), vh.BLUSH, alpha=140, blur=0.5)
            pen.fill(P().oval(6.2, 0.4, 1.2, 0.7), vh.BLUSH, alpha=120, blur=0.5)
        # joia vermelha na orelha (presilha)
        pen.fill(P().circle(4.6, -8.4, 1.1), vh.RIBBON)
        pen.fill(P().circle(4.3, -8.8, 0.4), "#ffd0d8")
        # pezinhos
        for fx in (-1.6, 2.6):
            pen.stroke(P().M(fx, 8.8).L(fx - 0.4, 11.6), WING_LINE, 0.9)
        # asa da frente
        wf, ef, tf = bat_wing(flap, 1, 1.0)
        pen.fill(wf, WING)
        with pen.clip(wf):
            pen.fill(P().M(4, -2).Q(14, -6 - flap * 8, 24, -5 - flap * 15).L(26, 12).L(4, 12).Z(), WING_IN, alpha=200)
        for t in tf:
            pen.stroke(P().M(*ef).L(*t), WING_LINE, 0.65)
        pen.stroke(P().M(5.5, -4).Q(10, -12 - flap * 8, *ef), "#5a4070", 0.9)
        pen.stroke(wf, WING_LINE, 0.85)


def bat_anims():
    """Morcego: voo (4), mordida (2), queda (2). Corpo a ~34 px do chão."""
    H = -34
    fly = []
    for i, fl in enumerate((1.0, 0.2, -0.9, 0.0)):
        fly.append(dict(flap=fl, y=H + (-1.5 if fl < 0 else 1.0), lunge=0, mood="normal", tilt=0.0))
    bite = [dict(flap=-0.4, y=H + 1, lunge=4, mood="bite", tilt=0.25), dict(flap=0.8, y=H, lunge=2, mood="bite", tilt=0.1)]
    die = [dict(flap=-0.6, y=H + 8, lunge=0, mood="dead", tilt=1.4), dict(flap=-1.0, y=H + 22, lunge=0, mood="dead", tilt=2.6)]
    return {"bat_fly": (12, True, fly), "bat_bite": (12, False, bite), "bat_die": (6, False, die)}


def bat_draw(f):
    def draw(pen):
        with pen.at(0, f["y"]):
            draw_bat(pen, f["flap"], f["mood"], f["lunge"], f["tilt"], scale=1.35)
        return {"mouth": (f["lunge"] * 1.35 + 3.2, f["y"] + 2.7)}
    return draw
