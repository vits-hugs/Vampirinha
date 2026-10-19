"""Inimigos em estilo anime chibi: caçador com espada, atirador, cão de caça e o Gigante.

Mesma convenção do sprite da vampira: pés em (0, 0), y para baixo, vista 3/4 olhando
para a direita (o jogo espelha para a esquerda). Ângulos de membros: 0 = para baixo,
positivo gira para a frente (+x); joelho positivo dobra para trás.
"""
import math

from .kit import P, add, lerp, lerp2, mix, rot, tapered

THIGH, SHIN = 11.4, 11.0
UPPER, FORE = 8.2, 7.6
HIP_Y = -26.5


def _dir(a):
    return (math.sin(a), math.cos(a))


def epose(**kw):
    d = dict(bob=0.0, lean=0.0, head=0.0, lift=0.0,
             arm_n=(0.18, 0.3), arm_f=(-0.12, 0.3), leg_n=(0.05, 0.0), leg_f=(-0.05, 0.0),
             expr="angry", hat=0.0, sword=None, smear=None, coat=0.0, scarf=0.0, flash=False, glint=0.0)
    d.update(kw)
    return d


def ground_offset(ps):
    def ank(leg):
        h, k = leg
        return THIGH * math.cos(h) + SHIN * math.cos(h - k)
    return (THIGH + SHIN) - max(ank(ps["leg_n"]), ank(ps["leg_f"]))


def ejoints(ps):
    H = (0.0, HIP_Y + ground_offset(ps) - ps["lift"] + ps["bob"] * 0.4)
    lean = ps["lean"]

    def T(p):
        q = rot(p, lean)
        return (H[0] + q[0], H[1] + q[1] + ps["bob"] * 0.6)

    return dict(H=H, T=T, sh_n=T((-8.2, -20.6)), sh_f=T((7.4, -21.0)),
                hip_n=(H[0] - 3.8, H[1]), hip_f=(H[0] + 3.6, H[1] - 0.3),
                head=T((1.2, -40.0)), head_ang=lean * 0.5 + ps["head"])


# ------------------------------------------------------------------ rosto genérico
def e_eye(pen, cx, cy, w, h, out, iris, expr, line="#1d1018"):
    if expr in ("hurt",):
        s = w * 0.42
        d = -out
        pen.fill(tapered([(cx + d * s, cy - h * 0.35), (cx - d * s * 0.7, cy), (cx + d * s, cy + h * 0.35)], 0.7, 0.7, 1.6), line)
        return
    if expr == "dead":
        s = min(w, h) * 0.42
        for a, b in (((-s, -s), (s, s)), ((-s, s), (s, -s))):
            pen.fill(tapered([add((cx, cy), a), (cx, cy), add((cx, cy), b)], 0.8, 0.8, 1.3), line)
        return
    if expr == "closed":
        pen.fill(tapered([(cx - w / 2, cy), (cx, cy + h * 0.2), (cx + w / 2, cy)], 0.6, 0.6, 1.3), line)
        return
    # olho "bravo": pálpebra reta inclinada para dentro
    inner = (cx - out * w / 2, cy - h * 0.05)
    outer = (cx + out * w / 2, cy - h * 0.42)
    shape = P().M(*inner).L(*outer).C(outer[0] + out * 0.6, cy + h * 0.2, cx + out * w * 0.2, cy + h * 0.55, cx - out * w * 0.1, cy + h * 0.5) \
        .C(cx - out * w * 0.4, cy + h * 0.45, inner[0], cy + h * 0.25, *inner).Z()
    with pen.clip(shape):
        pen.fill(shape, "#ffffff")
        ir = w * 0.33
        icx = cx + w * 0.12
        pen.fill(P().circle(icx, cy + h * 0.12, ir), iris)
        pen.fill(P().circle(icx, cy + h * 0.12, ir * 0.45), "#0d0a12")
        pen.fill(P().circle(icx - ir * 0.35, cy - h * 0.05, ir * 0.3), "#ffffff")
    if expr == "shout":
        pass
    pen.fill(tapered([inner, lerp2(inner, outer, 0.5), outer, add(outer, (out * 1.2, -0.3))], 0.7, 0.5, 1.7), line)


def e_brow(pen, x0, y0, x1, y1, w=1.4, col="#2a1810"):
    pen.fill(tapered([(x0, y0), lerp2((x0, y0), (x1, y1), 0.5), (x1, y1)], w * 0.8, w * 0.5, w), col)


def e_mouth(pen, mx, my, expr, line="#5a2a22"):
    if expr in ("shout", "hurt"):
        m = P().M(mx - 2.6, my - 0.8).L(mx + 2.8, my - 1.2).C(mx + 2.6, my + 2.6, mx - 2.0, my + 2.8, mx - 2.6, my - 0.8).Z()
        pen.fill(m, "#5a0f1e")
        with pen.clip(m):
            pen.fill(P().M(mx - 3, my - 2).L(mx + 3, my - 2).L(mx + 3, my - 0.2).L(mx - 3, my + 0.2).Z(), "#ffffff")
            pen.fill(P().oval(mx, my + 2.4, 2.2, 1.0), "#e25a6e")
        pen.stroke(m, line, 0.6)
    elif expr == "dead":
        pen.stroke(P().M(mx - 2.2, my + 0.6).Q(mx, my - 0.8, mx + 2.2, my + 0.6), line, 0.7)
        pen.shape(P().M(mx + 0.4, my + 0.3).C(mx + 0.6, my + 2.8, mx + 2.4, my + 2.8, mx + 2.2, my + 0.1).Z(), "#e25a6e", line, 0.4)
    elif expr == "grit":
        m = P().M(mx - 2.4, my - 0.6).L(mx + 2.6, my - 0.9).L(mx + 2.4, my + 1.0).L(mx - 2.2, my + 1.1).Z()
        pen.shape(m, "#ffffff", line, 0.55)
        pen.stroke(P().M(mx - 2.3, my + 0.2).L(mx + 2.5, my), line, 0.35)
    else:  # frown
        pen.stroke(P().M(mx - 2.2, my + 0.6).Q(mx, my - 0.6, mx + 2.2, my + 0.5), line, 0.75)


def limb(pen, a, b, w0, w1, fill, line, lw=0.8, shade=None, side=1):
    pts = [a, lerp2(a, b, 0.5), b]
    p = tapered(pts, w0, w1, (w0 + w1) / 2)
    pen.fill(p, fill)
    if shade:
        with pen.clip(p):
            d = (b[0] - a[0], b[1] - a[1])
            n = math.hypot(*d) or 1
            nx, ny = -d[1] / n * side, d[0] / n * side
            pen.fill(tapered([add(a, (nx, ny), w0 * 0.35), add(b, (nx, ny), w1 * 0.35)], w0 * 0.5, w1 * 0.5), shade)
    pen.stroke(p, line, lw)
    return p


# ------------------------------------------------------------------ caçador (espada)
H_COAT = "#4e6589"
H_COAT_SH = "#33455f"
H_COAT_HL = "#7f98bd"
H_LINE = "#141a28"
H_HAT = "#272c46"
H_HAT_SH = "#151827"
H_HAT_HL = "#4a5276"
H_BAND = "#8c2134"
E_SKIN = "#f7d7be"
E_SKIN_SH = "#e2ab90"
E_SKIN_LINE = "#6b3a2a"
H_HAIR = "#6b4630"
H_HAIR_SH = "#45291b"
PANTS = "#2b2a37"
PANTS_SH = "#1b1a24"
BOOT = "#4d2f22"
BOOT_HL = "#7c5241"
GLOVE = "#5c3b29"
CRAVAT = "#f3eff7"
BELT = "#5a3a26"
SILVER = "#d6dbe6"
BLADE = "#eef3fa"
BLADE_SH = "#9ca9c0"
HILT = "#d9a63e"


def e_boot(pen, ankle, ang, col=BOOT, hl=BOOT_HL, line=H_LINE, far=False):
    with pen.at(ankle[0], ankle[1], ang):
        b = P().M(-2.8, -4.5).L(2.4, -4.5).L(2.6, 0.2).C(4.6, 0.4, 6.8, 1.2, 6.8, 3.0).L(6.6, 4.0).L(-3.0, 4.0).C(-3.4, 2.0, -3.2, -1.0, -2.8, -4.5).Z()
        pen.fill(b, col if not far else mix(col, "#000000", 0.3))
        with pen.clip(b):
            pen.fill(P().M(-4, 3.0).L(8, 3.0).L(8, 5).L(-4, 5).Z(), "#1a100c")
            pen.fill(P().oval(-0.6, -2.2, 1.0, 2.0), hl, alpha=150)
            pen.fill(P().M(-4, -4.6).L(3, -4.6).L(3, -3.0).L(-4, -3.0).Z(), mix(col, "#000000", 0.25))
        pen.stroke(b, line, 0.75)


def e_leg(pen, hip, h, k, pants=PANTS, boot=BOOT, line=H_LINE, far=False):
    knee = add(hip, _dir(h), THIGH)
    ankle = add(knee, _dir(h - k), SHIN)
    col = pants if not far else mix(pants, "#000000", 0.3)
    limb(pen, hip, knee, 5.6, 4.8, col, line, 0.75)
    limb(pen, knee, ankle, 4.8, 4.2, col, line, 0.75)
    e_boot(pen, ankle, (h - k) * 0.3, col=boot, line=line, far=far)
    return knee, ankle


def e_arm(pen, sh, a, e, sleeve, sleeve_sh, cuff, glove, line, far=False, fist=True):
    elbow = add(sh, _dir(a), UPPER)
    hand = add(elbow, _dir(a + e), FORE)
    col = sleeve if not far else sleeve_sh
    limb(pen, sh, elbow, 5.0, 4.2, col, line, 0.75)
    limb(pen, elbow, hand, 4.2, 3.8, col, line, 0.75)
    d = _dir(a + e)
    c0 = add(hand, d, -1.4)
    pen.shape(tapered([c0, add(c0, d, 1.4)], 4.8, 4.8), cuff, line, 0.6)
    hc = add(hand, d, 1.0)
    pen.shape(P().circle(hc[0], hc[1], 2.7 if fist else 2.3), glove if not far else mix(glove, "#000000", 0.25), line, 0.7)
    return hc, d


def sabre(pen, hand, ang, length=25.0):
    """Sabre: lâmina levemente curva a partir da mão, guarda dourada."""
    with pen.at(hand[0], hand[1], ang):
        blade = P().M(2.0, -1.3).C(10, -2.0, 18, -1.8, length, 1.4).C(18, 0.4, 10, 1.0, 2.0, 1.2).Z()
        pen.fill(blade, BLADE)
        with pen.clip(blade):
            pen.fill(P().M(2, 0.3).C(10, 0.6, 18, 0.6, length, 1.6).L(length, 3).L(2, 3).Z(), BLADE_SH)
        pen.stroke(blade, H_LINE, 0.65)
        pen.stroke(P().M(4, -0.8).C(10, -1.2, 16, -1.0, length - 3, 0.6), "#ffffff", 0.5)
        # punho e guarda
        pen.shape(P().M(-4.5, -0.9).L(0.6, -0.9).L(0.6, 0.9).L(-4.5, 0.9).Z(), "#3a2418", H_LINE, 0.5)
        pen.shape(P().M(1.0, -3.4).L(2.4, -3.4).L(2.4, 3.4).L(1.0, 3.4).Z(), HILT, H_LINE, 0.5)
        pen.stroke(P().M(1.6, 3.2).Q(-1.8, 4.6, -4.4, 1.4), HILT, 0.9)
        pen.shape(P().circle(-5.0, 0, 1.3), HILT, H_LINE, 0.45)


def glint(pen, c, r, col="#ffffff"):
    """Brilho em estrela (aviso de golpe)."""
    st = P().M(c[0], c[1] - r).Q(c[0] + r * 0.12, c[1] - r * 0.12, c[0] + r, c[1]).Q(c[0] + r * 0.12, c[1] + r * 0.12, c[0], c[1] + r) \
        .Q(c[0] - r * 0.12, c[1] + r * 0.12, c[0] - r, c[1]).Q(c[0] - r * 0.12, c[1] - r * 0.12, c[0], c[1] - r).Z()
    pen.fill(P().circle(c[0], c[1], r * 0.7), "#ffe9a8", alpha=120, blur=1.2)
    pen.fill(st, col)


def draw_slash_smear(pen, c, r, a0, a1, w, col="#e8f0ff"):
    n = 16
    outer = [add(c, (math.cos(lerp(a0, a1, i / n)), math.sin(lerp(a0, a1, i / n))), r) for i in range(n + 1)]
    inner = [add(c, (math.cos(lerp(a0, a1, i / n)), math.sin(lerp(a0, a1, i / n))), r - w * math.sin(math.pi * i / n) ** 0.7) for i in range(n, -1, -1)]
    pen.fill(P().poly(outer + inner), col, alpha=170)
    pen.stroke(P().smooth(outer, close=False), "#ffffff", 0.8, alpha=230)


def hunter_head(pen, expr="angry", hat_tilt=0.0, hat_off=False):
    eyes = {"angry": "angry", "shout": "angry", "hurt": "hurt", "dead": "dead", "grit": "angry"}.get(expr, "angry")
    mouth = {"angry": "frown", "shout": "shout", "hurt": "shout", "dead": "dead", "grit": "grit"}.get(expr, "frown")
    # cabelo de trás
    pen.shape(P().oval(-2.0, -3.0, 15.5, 13.5), H_HAIR_SH, H_LINE, 0.7)
    # orelha
    pen.shape(P().oval(-14.2, 2.0, 2.6, 3.4), E_SKIN, E_SKIN_LINE, 0.6)
    face = P().M(-14.6, -4).C(-14.9, 5.5, -12.2, 12.0, -5.2, 15.4).C(-1.0, 17.2, 3.2, 17.4, 6.4, 16.0) \
        .C(10.4, 13.8, 13.8, 8.8, 14.6, 3.0).C(15.2, -1.2, 15.0, -4.6, 14.4, -7.0).C(10, -16, -10, -16, -14.6, -4).Z()
    pen.fill(face, E_SKIN)
    with pen.clip(face):
        pen.fill(P().M(12, -8).C(15, 2, 12.5, 10, 7, 17).L(18, 18).L(18, -8).Z(), E_SKIN_SH, alpha=220)
        if not hat_off:  # sombra da aba do chapéu
            pen.fill(P().M(-18, -12).L(18, -12).L(18, -1.0).C(6, 1.2, -6, 1.0, -18, -0.8).Z(), E_SKIN_SH)
        # cicatriz
        pen.stroke(P().M(-10.2, 6.0).L(-6.8, 10.2), "#c27a6e", 0.6)
        pen.stroke(P().M(-9.6, 8.6).L(-8.2, 7.2), "#c27a6e", 0.5)
    pen.stroke(face, E_SKIN_LINE, 0.85)
    e_eye(pen, -5.6, 4.0, 7.4, 6.0, -1, "#3f6d9e", eyes)
    e_eye(pen, 7.4, 3.9, 5.6, 5.8, +1, "#3f6d9e", eyes)
    if eyes != "dead":
        tilt = 1.0 if eyes == "angry" else -0.6
        e_brow(pen, -9.8, -0.4 - 0.5, -2.2, 0.9 + tilt)
        e_brow(pen, 4.4, 0.8 + tilt, 10.4, -0.6 - 0.5)
    pen.stroke(P().M(7.2, 7.8).L(8.4, 9.8).L(7.0, 10.0), E_SKIN_SH, 0.6)
    e_mouth(pen, 4.0, 12.6, mouth)
    # costeleta
    pen.shape(P().M(-15.2, -6).L(-11.6, -6).L(-12.4, 3.4).L(-14.8, 1.6).Z(), H_HAIR, H_LINE, 0.6)
    if hat_off:
        top = P().M(-15.5, -2).C(-16, -14, -6, -18.5, 2, -18.0).C(10, -18, 16, -12, 15.4, -3).L(11, -6).L(8, -2).L(4, -7).L(0, -2.5).L(-4, -7).L(-8, -2).L(-11.6, -6).Z()
        pen.shape(top, H_HAIR, H_LINE, 0.8)
        return
    # franjinha sob a aba
    pen.shape(P().M(-11, -4).L(-8.6, 1.2).L(-6.4, -3.4).L(-3.8, 0.8).L(-1.6, -3.6).L(1.4, 0.4).L(3.0, -4).Z(), H_HAIR, H_LINE, 0.55)
    # chapéu
    with pen.at(1.0, -8.6, -0.06 + hat_tilt):
        brim = P().oval(0, 0, 21.5, 6.6)
        pen.fill(brim, H_HAT)
        with pen.clip(brim):
            pen.fill(P().oval(-3, -2.2, 17, 4.2), H_HAT_HL, alpha=160)
            pen.fill(P().oval(4, 3.6, 20, 3.6), H_HAT_SH)
        pen.stroke(brim, H_LINE, 0.9)
        crown = P().M(-12.4, -0.6).C(-13.2, -7, -12.2, -15, -10.0, -18.6).Q(-4.4, -20.4, 0.0, -17.2).Q(4.8, -20.8, 10.6, -19.0) \
            .C(12.8, -15, 13.8, -7, 12.8, -1.2).Q(0.0, 1.6, -12.4, -0.6).Z()
        pen.fill(crown, H_HAT)
        with pen.clip(crown):
            pen.fill(P().M(6, -22).C(10, -14, 11, -6, 10, 2).L(16, 2).L(16, -22).Z(), H_HAT_SH)
            pen.fill(P().M(-14, -5.2).Q(0, -2.8, 14, -5.6).L(14, 2).L(-14, 2).Z(), H_BAND)
            pen.fill(P().oval(-6.5, -11, 2.4, 5.5), H_HAT_HL, alpha=140)
        pen.stroke(crown, H_LINE, 0.9)
        # cruz de prata na faixa
        with pen.at(4.2, -3.2):
            cr = P().M(-0.8, -3.6).L(0.8, -3.6).L(0.8, -1.4).L(2.6, -1.4).L(2.6, 0.2).L(0.8, 0.2).L(0.8, 3.0).L(-0.8, 3.0) \
                .L(-0.8, 0.2).L(-2.6, 0.2).L(-2.6, -1.4).L(-0.8, -1.4).Z()
            pen.shape(cr, SILVER, H_LINE, 0.45)


def hunter_coat_path(flare=0.0):
    f = flare
    return P().M(-8.8, -21.0).C(-10.6, -15.0, -9.6, -11.0, -7.8, -8.6).C(-10.2, -3.0, -13.0 - f * 2, 5.0, -14.4 - f * 3, 12.4 - f) \
        .L(-6.4 - f, 13.8).L(-1.0, 1.0).L(1.8, 1.0).L(6.2, 13.6).L(13.2 + f, 11.8).C(11.8, 5.0, 9.2, -3.0, 7.0, -8.8) \
        .C(8.6, -11.0, 9.2, -15.0, 7.8, -21.4).C(3.0, -23.6, -4.0, -23.6, -8.8, -21.0).Z()


def draw_hunter_body(pen, coat_flare=0.0):
    cp = hunter_coat_path(coat_flare)
    pen.fill(cp, H_COAT)
    with pen.clip(cp):
        pen.fill(P().M(4.0, -24).C(7.5, -14, 6.0, -6, 3.0, 2).L(6.2, 14).L(16, 14).L(16, -24).Z(), H_COAT_SH)
        pen.fill(tapered([(-6.4, -19), (-7.0, -12), (-9.6, 2), (-12.0, 11)], 1.6, 1.2, 2.2), H_COAT_HL, alpha=170)
        # forro escuro na abertura da frente
        pen.fill(P().M(-1.0, 1.0).L(1.8, 1.0).L(4.8, 14).L(-4.6, 14).Z(), "#1e2638")
        # cinto
        pen.fill(P().M(-12, -10.8).Q(0, -9.6, 12, -11.0).L(12, -8.0).Q(0, -6.8, -12, -8.0).Z(), BELT)
        pen.shape(P().M(-0.8, -10.6).L(2.2, -10.6).L(2.2, -7.6).L(-0.8, -7.6).Z(), SILVER, H_LINE, 0.4)
        for y in (-17.2, -13.6):
            pen.fill(P().circle(0.9, y, 0.8), SILVER)
    pen.stroke(cp, H_LINE, 0.85)
    # gola alta + gravata
    collar = P().M(-5.6, -21.4).L(-6.6, -26.4).C(-2.0, -24.6, 3.0, -24.8, 7.0, -26.8).L(6.2, -21.6).Q(0.4, -19.6, -5.6, -21.4).Z()
    pen.shape(collar, H_COAT_SH, H_LINE, 0.7)
    pen.shape(P().M(-2.4, -22.6).L(0.8, -17.0).L(3.8, -22.8).Q(0.6, -21.4, -2.4, -22.6).Z(), CRAVAT, H_LINE, 0.55)


def draw_hunter(pen, ps):
    J = ejoints(ps)
    hx, hy = J["head"]
    # braço da espada (de trás) + espada
    hand_f, df = e_arm(pen, J["sh_f"], *ps["arm_f"], H_COAT, H_COAT_SH, "#e9e4ee", GLOVE, H_LINE, far=True)
    if ps["sword"] is not None:
        sabre(pen, hand_f, ps["sword"])
        if ps["glint"]:
            tip = add(hand_f, (math.cos(ps["sword"]), math.sin(ps["sword"])), 22)
            glint(pen, tip, 5.5 * ps["glint"])
    e_leg(pen, J["hip_f"], *ps["leg_f"], far=True)
    e_leg(pen, J["hip_n"], *ps["leg_n"])
    with pen.at(J["H"][0], J["H"][1] + ps["bob"] * 0.6, ps["lean"]):
        draw_hunter_body(pen, ps["coat"])
    with pen.at(hx, hy, J["head_ang"]):
        hunter_head(pen, ps["expr"], ps["hat"])
    e_arm(pen, J["sh_n"], *ps["arm_n"], H_COAT, H_COAT_SH, "#e9e4ee", GLOVE, H_LINE)
    if ps["smear"]:
        c, r, a0, a1, w = ps["smear"]
        draw_slash_smear(pen, add(J["sh_f"], c), r, a0, a1, w)
    return {"head": (hx, hy), "hand": hand_f}


def hunter_anims():
    walk = []
    legs = [((0.42, 0.10), (-0.38, 0.35)), ((0.05, 0.30), (0.08, 0.85)), ((-0.38, 0.35), (0.42, 0.10)), ((0.08, 0.85), (0.05, 0.30))]
    for i, (ln, lf) in enumerate(legs):
        sw = math.cos(i / 4 * math.tau)
        walk.append(epose(leg_n=ln, leg_f=lf, lift=0.8 if i % 2 else 0.0, bob=0.0 if i % 2 else 0.8, lean=0.06,
                          arm_n=(-0.45 * sw, 0.5), arm_f=(0.55 + 0.1 * sw, 0.7), sword=0.75 + 0.08 * sw, coat=0.2))
    windup = [
        epose(expr="grit", lean=-0.10, arm_f=(-1.35, 0.35), sword=-2.75, arm_n=(0.7, 0.9), leg_n=(0.34, 0.15), leg_f=(-0.32, 0.2), glint=0.6),
        epose(expr="shout", lean=-0.18, arm_f=(-1.65, 0.25), sword=-2.95, arm_n=(0.9, 1.0), leg_n=(0.40, 0.15), leg_f=(-0.36, 0.2), glint=1.0),
    ]
    slash = [
        epose(expr="shout", lean=0.26, arm_f=(1.25, -0.05), sword=0.45, arm_n=(-0.8, 0.6), leg_n=(0.5, 0.2), leg_f=(-0.45, 0.3),
              coat=0.6, smear=((0, 0), 30, -1.9, 0.55, 9)),
        epose(expr="angry", lean=0.20, arm_f=(0.95, 0.15), sword=0.95, arm_n=(-0.6, 0.6), leg_n=(0.46, 0.2), leg_f=(-0.42, 0.3),
              coat=0.4, smear=((0, 0), 30, -0.4, 0.95, 5)),
    ]
    hurt = [epose(expr="hurt", lean=-0.32, head=-0.2, hat=-0.35, arm_f=(-1.0, 0.6), sword=-0.6, arm_n=(1.2, 0.6),
                  leg_n=(0.4, 0.5), leg_f=(-0.25, 0.3))]
    return {"walk": (8, True, walk), "windup": (8, False, windup), "slash": (12, False, slash), "hurt": (10, False, hurt)}


def hunter_dead_draw():
    """Caçador nocauteado: deitado, chapéu caído do lado."""
    def draw(pen):
        with pen.at(30, -6, -1.5):
            ps = epose(expr="dead", arm_n=(0.9, 0.3), arm_f=(-0.6, 0.3), leg_n=(0.3, 0.1), leg_f=(-0.1, 0.2), head=0.2)
            J = ejoints(ps)
            e_arm(pen, J["sh_f"], *ps["arm_f"], H_COAT, H_COAT_SH, "#e9e4ee", GLOVE, H_LINE, far=True)
            e_leg(pen, J["hip_f"], *ps["leg_f"], far=True)
            e_leg(pen, J["hip_n"], *ps["leg_n"])
            with pen.at(J["H"][0], J["H"][1], 0.0):
                draw_hunter_body(pen, 0.0)
            with pen.at(*J["head"], 0.2):
                hunter_head(pen, "dead", hat_off=True)
            e_arm(pen, J["sh_n"], *ps["arm_n"], H_COAT, H_COAT_SH, "#e9e4ee", GLOVE, H_LINE)
        # chapéu no chão e espada largada
        with pen.at(50, -5, 0.15, 0.85):
            pen.shape(P().oval(0, 0, 13, 4.2), H_HAT, H_LINE, 0.8)
            pen.shape(P().M(-7.6, -0.4).C(-8.2, -5, -6.4, -9.6, -4.6, -10.6).Q(0, -12, 4.6, -10.4).C(6.6, -8, 7.6, -4, 7.0, -0.6).Q(0, 1.2, -7.6, -0.4).Z(), H_HAT, H_LINE, 0.8)
            pen.fill(P().M(-7.8, -3.2).Q(0, -1.6, 7.6, -3.4).L(7.4, -0.8).Q(0, 0.8, -7.6, -0.6).Z(), H_BAND)
        sabre(pen, (-14, 4), -0.12, 24)
    return draw


# ------------------------------------------------------------------ atirador (pistola)
G_COAT = "#80542f"
G_COAT_SH = "#5a3a20"
G_COAT_HL = "#ad7c4f"
G_LINE = "#24140a"
G_HAT = "#4b3426"
G_HAT_SH = "#2c1e15"
G_TRIM = "#d1a94e"
G_SKIN = "#efc6a2"
G_SKIN_SH = "#d39a76"
G_HAIR = "#c25a2b"
G_HAIR_SH = "#86381a"
SCARF = "#e0722b"
SCARF_SH = "#a2481a"
G_PANTS = "#3d3b2e"
G_BOOT = "#2a1d1a"
BRASS = "#d8ad52"
GUNMETAL = "#5d6370"
GUNMETAL_HL = "#aab1bf"
WOOD = "#74431f"


def gunner_head(pen, expr="aim", hat_off=False):
    eyes_n = {"aim": "closed", "angry": "angry", "shout": "angry", "hurt": "hurt", "dead": "dead"}.get(expr, "angry")
    eyes_f = {"aim": "angry", "angry": "angry", "shout": "angry", "hurt": "hurt", "dead": "dead"}.get(expr, "angry")
    mouth = {"aim": "grit", "angry": "frown", "shout": "shout", "hurt": "shout", "dead": "dead"}.get(expr, "frown")
    # rabo de cavalo
    pen.shape(tapered([(-10, -6), (-17, -2), (-20, 6), (-18.5, 13)], 5.5, 1.5, 6.0), G_HAIR, G_LINE, 0.7)
    pen.shape(P().oval(-2.0, -3.0, 15.5, 13.5), G_HAIR_SH, G_LINE, 0.7)
    pen.shape(P().oval(-14.2, 2.0, 2.6, 3.4), G_SKIN, E_SKIN_LINE, 0.6)
    face = P().M(-14.6, -4).C(-14.9, 5.5, -12.2, 12.0, -5.2, 15.0).C(-1.0, 16.6, 3.2, 16.8, 6.2, 15.6) \
        .C(10.4, 13.6, 13.8, 8.8, 14.6, 3.0).C(15.2, -1.2, 15.0, -4.6, 14.4, -7.0).C(10, -16, -10, -16, -14.6, -4).Z()
    pen.fill(face, G_SKIN)
    with pen.clip(face):
        pen.fill(P().M(12, -8).C(15, 2, 12.5, 10, 7, 17).L(18, 18).L(18, -8).Z(), G_SKIN_SH, alpha=220)
        if not hat_off:
            pen.fill(P().M(-18, -12).L(18, -12).L(18, -1.6).C(6, 0.4, -6, 0.2, -18, -1.4).Z(), G_SKIN_SH)
        for (x, y) in ((-8.6, 8.6), (-7.0, 9.4), (-9.6, 9.8), (9.6, 8.8), (10.8, 9.6)):  # sardas
            pen.fill(P().circle(x, y, 0.45), "#b5653f")
    pen.stroke(face, E_SKIN_LINE, 0.85)
    e_eye(pen, -5.6, 4.0, 7.4, 6.0, -1, "#4f8a3a", eyes_n)
    e_eye(pen, 7.4, 3.9, 5.6, 5.8, +1, "#4f8a3a", eyes_f)
    if eyes_f != "dead":
        e_brow(pen, -9.8, 0.2, -2.2, 1.6, col="#6b2a10")
        e_brow(pen, 4.4, 1.5, 10.4, -0.4, col="#6b2a10")
    pen.stroke(P().M(7.2, 7.8).L(8.4, 9.8).L(7.0, 10.0), G_SKIN_SH, 0.6)
    e_mouth(pen, 4.0, 12.4, mouth)
    pen.shape(P().M(-15.2, -6).L(-11.6, -6).L(-12.4, 2.6).L(-14.8, 1.0).Z(), G_HAIR, G_LINE, 0.6)
    if hat_off:
        top = P().M(-15.5, -2).C(-16, -14, -6, -18.5, 2, -18.0).C(10, -18, 16, -12, 15.4, -3).L(11, -6).L(8, -2).L(4, -7).L(0, -2.5).L(-4, -7).L(-8, -2).L(-11.6, -6).Z()
        pen.shape(top, G_HAIR, G_LINE, 0.8)
        return
    pen.shape(P().M(-11, -4).L(-8.4, 1.0).L(-6.0, -3.4).L(-3.4, 0.6).L(-1.2, -3.6).L(1.8, 0.0).L(3.4, -4).Z(), G_HAIR, G_LINE, 0.55)
    # chapéu tricórnio
    with pen.at(1.0, -9.0, -0.05):
        brim = P().M(-20, 1.0).Q(-15, -9.5, -4, -6.0).Q(1.0, -11.5, 7, -6.2).Q(16, -9.8, 21, 0.4).Q(10, 6.6, 1, 4.6).Q(-9, 7.0, -20, 1.0).Z()
        pen.fill(brim, G_HAT)
        with pen.clip(brim):
            pen.fill(P().oval(3, 4.0, 20, 3.4), G_HAT_SH)
        pen.stroke(brim, G_LINE, 0.9)
        pen.stroke(P().M(-19, 0.6).Q(-9, 6.2, 1, 4.2).Q(10, 6.0, 20, 0.2), G_TRIM, 1.0)
        crown = P().M(-11, -2).C(-12, -9, -9, -15, 0, -15.5).C(9, -15, 12, -9, 11.6, -2.6).Q(0, 0.4, -11, -2).Z()
        pen.fill(crown, G_HAT)
        with pen.clip(crown):
            pen.fill(P().M(5, -18).C(10, -10, 11, -5, 10, 2).L(14, 2).L(14, -18).Z(), G_HAT_SH)
            pen.fill(P().oval(-4.6, -9.6, 2.4, 4.0), "#6e4c38", alpha=170)
        pen.stroke(crown, G_LINE, 0.9)
        # pena vermelha
        f = tapered([(-7, -10), (-12, -18), (-17, -21), (-21, -20)], 3.2, 0.6, 4.4)
        pen.shape(f, "#c8213c", "#4a0814", 0.7)
        pen.stroke(P().M(-7, -10).Q(-13, -17, -20, -20), "#ff7a8e", 0.5)
        # óculos de aviador no chapéu
        for gx in (-3.6, 3.6):
            pen.shape(P().circle(gx, -4.0, 2.7), BRASS, G_LINE, 0.6)
            pen.fill(P().circle(gx, -4.0, 1.7), "#7fd3df")
            pen.fill(P().circle(gx - 0.6, -4.6, 0.6), "#ffffff")
        pen.stroke(P().M(-1.0, -4.0).L(1.0, -4.0), G_LINE, 0.8)


def draw_gunner_body(pen, scarf=0.0):
    cp = P().M(-8.8, -21.0).C(-10.6, -15.0, -9.6, -11.0, -7.8, -8.6).C(-9.8, -4.0, -11.6, 1.0, -12.4, 6.4) \
        .L(-5.6, 7.4).L(-1.0, -1.0).L(1.8, -1.0).L(5.6, 7.2).L(11.6, 6.0).C(10.6, 1.0, 9.0, -4.0, 7.0, -8.8) \
        .C(8.6, -11.0, 9.2, -15.0, 7.8, -21.4).C(3.0, -23.6, -4.0, -23.6, -8.8, -21.0).Z()
    pen.fill(cp, G_COAT)
    with pen.clip(cp):
        pen.fill(P().M(4.0, -24).C(7.5, -14, 6.0, -6, 3.0, 0).L(6, 8).L(16, 8).L(16, -24).Z(), G_COAT_SH)
        pen.fill(tapered([(-6.4, -19), (-7.0, -12), (-9.0, -2), (-10.6, 5)], 1.6, 1.2, 2.2), G_COAT_HL, alpha=170)
        pen.fill(P().M(-1.0, -1.0).L(1.8, -1.0).L(4.6, 8).L(-4.4, 8).Z(), "#3a2414")
        # bandoleira com balas
        band = P().M(-8.6, -20).L(-5.6, -21.6).L(8.6, -9.6).L(5.8, -8.0).Z()
        pen.fill(band, "#3b2516")
        for i in range(5):
            t = (i + 0.5) / 5
            c = lerp2((-6.6, -20.2), (7.0, -9.2), t)
            pen.shape(P().M(c[0] - 0.7, c[1] - 1.6).L(c[0] + 0.7, c[1] - 1.6).L(c[0] + 0.7, c[1] + 1.2).L(c[0] - 0.7, c[1] + 1.2).Z(), BRASS, G_LINE, 0.3)
        pen.fill(P().M(-12, -10.8).Q(0, -9.6, 12, -11.0).L(12, -8.0).Q(0, -6.8, -12, -8.0).Z(), "#3b2516")
        pen.shape(P().M(-6.6, -9.6).L(-3.0, -9.6).L(-3.2, -5.6).L(-6.4, -5.6).Z(), "#5c3a20", G_LINE, 0.4)  # bolsinha
    pen.stroke(cp, G_LINE, 0.85)
    # cachecol laranja com as pontas voando
    sc = P().M(-6.6, -22.6).C(-3, -20.4, 3.4, -20.6, 7.0, -23.0).L(6.4, -25.6).C(3, -24.0, -3, -23.8, -6.0, -25.4).Z()
    pen.shape(sc, SCARF, G_LINE, 0.7)
    tail = tapered([(-5.0, -22.4), (-8.6 - scarf * 3, -18.6 + scarf), (-12.0 - scarf * 6, -15.6 + scarf * 2), (-14.6 - scarf * 9, -13.6 + scarf * 2)], 3.4, 1.6, 3.0)
    pen.shape(tail, SCARF_SH, G_LINE, 0.65)
    tail2 = tapered([(-4.0, -22.0), (-6.6 - scarf * 2, -17.0), (-9.0 - scarf * 4, -12.6 + scarf), (-11.4 - scarf * 6, -10.2 + scarf)], 3.2, 1.6, 2.8)
    pen.shape(tail2, SCARF, G_LINE, 0.65)


GUN_PIVOT = (14, 20)       # ombro dentro do sprite do braço da arma
GUN_MUZZLE = (33.6, -1.6)  # boca do cano relativa ao ombro (apontando para +x)
GUN_SIZE = (56, 36)


def draw_gun_arm(pen, recoil=0.0):
    """Braço estendido com pistola de pederneira, ombro em (0, 0), apontando para +x."""
    with pen.at(-recoil, 0):
        elbow = (UPPER, 0.4)
        hand = (UPPER + FORE, 0.6)
        limb(pen, (0, 0), elbow, 5.0, 4.2, G_COAT_SH, G_LINE, 0.75)
        limb(pen, elbow, hand, 4.2, 3.8, G_COAT_SH, G_LINE, 0.75)
        pen.shape(tapered([(hand[0] - 1.4, hand[1]), (hand[0], hand[1])], 4.8, 4.8), "#e9e4ee", G_LINE, 0.6)
        # pistola
        gx, gy = hand[0] + 1.2, hand[1]
        grip = P().M(gx - 1.6, gy - 1.6).L(gx + 2.6, gy - 1.6).L(gx + 1.0, gy + 4.6).C(gx - 0.6, gy + 6.0, gx - 3.4, gy + 5.2, gx - 3.0, gy + 3.4).Z()
        pen.shape(grip, WOOD, G_LINE, 0.6)
        barrel = P().M(gx, gy - 3.4).L(gx + 17.5, gy - 3.0).L(gx + 17.5, gy - 0.6).L(gx, gy - 0.2).Z()
        pen.fill(barrel, GUNMETAL)
        pen.fill(P().M(gx + 1, gy - 3.2).L(gx + 17, gy - 2.9).L(gx + 17, gy - 2.2).L(gx + 1, gy - 2.4).Z(), GUNMETAL_HL)
        pen.stroke(barrel, G_LINE, 0.6)
        pen.shape(P().M(gx + 16.0, gy - 3.8).L(gx + 18.2, gy - 3.8).L(gx + 18.2, gy + 0.2).L(gx + 16.0, gy + 0.2).Z(), BRASS, G_LINE, 0.5)
        pen.shape(P().M(gx - 0.8, gy - 3.2).L(gx + 4.2, gy - 3.2).L(gx + 4.2, gy + 0.4).L(gx - 0.8, gy + 0.4).Z(), BRASS, G_LINE, 0.5)
        pen.stroke(P().M(gx + 0.4, gy - 3.2).Q(gx - 0.6, gy - 6.0, gx + 1.6, gy - 6.2), G_LINE, 0.9)  # cão da pederneira
        # mão (luva) segurando
        pen.shape(P().circle(hand[0] + 1.2, hand[1] + 0.6, 2.6), GLOVE, G_LINE, 0.7)


def muzzle_flash(pen, k=1.0):
    pts = []
    for i in range(16):
        a = i / 16 * math.tau
        r = (9.0 if i % 2 == 0 else 3.6) * k * (1.4 if i in (0, 1, 15) else 1.0)
        pts.append((math.cos(a) * r * 1.2, math.sin(a) * r))
    pen.fill(P().poly(pts), "#ffb13b")
    pen.fill(P().poly([(x * 0.55, y * 0.55) for x, y in pts]), "#fff2b0")


def draw_gunner(pen, ps, with_arm=False):
    J = ejoints(ps)
    hx, hy = J["head"]
    e_leg(pen, J["hip_f"], *ps["leg_f"], pants=G_PANTS, boot=G_BOOT, line=G_LINE, far=True)
    e_leg(pen, J["hip_n"], *ps["leg_n"], pants=G_PANTS, boot=G_BOOT, line=G_LINE)
    with pen.at(J["H"][0], J["H"][1] + ps["bob"] * 0.6, ps["lean"]):
        draw_gunner_body(pen, ps["scarf"])
    with pen.at(hx, hy, J["head_ang"]):
        gunner_head(pen, ps["expr"])
    e_arm(pen, J["sh_n"], *ps["arm_n"], G_COAT, G_COAT_SH, "#e9e4ee", GLOVE, G_LINE)
    if with_arm:
        with pen.at(J["sh_f"][0], J["sh_f"][1], ps.get("gun_ang", 0.35)):
            draw_gun_arm(pen)
    return {"head": (hx, hy), "shoulder": J["sh_f"]}


def gunner_anims():
    walk = []
    legs = [((0.40, 0.10), (-0.36, 0.35)), ((0.05, 0.30), (0.08, 0.85)), ((-0.36, 0.35), (0.40, 0.10)), ((0.08, 0.85), (0.05, 0.30))]
    for i, (ln, lf) in enumerate(legs):
        sw = math.cos(i / 4 * math.tau)
        walk.append(epose(expr="angry", leg_n=ln, leg_f=lf, lift=0.8 if i % 2 else 0.0, bob=0.0 if i % 2 else 0.8, lean=0.04,
                          arm_n=(-0.4 * sw, 0.6), scarf=0.3 + 0.2 * sw))
    aim = [epose(expr="aim", lean=-0.04, leg_n=(0.34, 0.12), leg_f=(-0.36, 0.12), arm_n=(0.5, 1.4), scarf=0.2)]
    hurt = [epose(expr="hurt", lean=-0.3, head=-0.2, arm_n=(1.2, 0.6), leg_n=(0.4, 0.5), leg_f=(-0.25, 0.3), scarf=1.0, gun_ang=-1.4)]
    return {"walk": (8, True, walk), "aim": (6, True, aim), "hurt": (10, False, hurt)}


def gunner_dead_draw():
    def draw(pen):
        with pen.at(30, -6, -1.5):
            ps = epose(expr="dead", arm_n=(0.9, 0.3), leg_n=(0.3, 0.1), leg_f=(-0.1, 0.2))
            J = ejoints(ps)
            e_leg(pen, J["hip_f"], *ps["leg_f"], pants=G_PANTS, boot=G_BOOT, line=G_LINE, far=True)
            e_leg(pen, J["hip_n"], *ps["leg_n"], pants=G_PANTS, boot=G_BOOT, line=G_LINE)
            with pen.at(J["H"][0], J["H"][1], 0.0):
                draw_gunner_body(pen, 0.0)
            with pen.at(*J["head"], 0.2):
                gunner_head(pen, "dead", hat_off=True)
            e_arm(pen, J["sh_n"], *ps["arm_n"], G_COAT, G_COAT_SH, "#e9e4ee", GLOVE, G_LINE)
        with pen.at(51, -4, 0.1, 0.62):
            pen.shape(P().M(-20, 1.0).Q(-15, -9.5, -4, -6.0).Q(1.0, -11.5, 7, -6.2).Q(16, -9.8, 21, 0.4).Q(10, 6.6, 1, 4.6).Q(-9, 7.0, -20, 1.0).Z(), G_HAT, G_LINE, 0.9)
        with pen.at(-22, 2, 0.3):
            draw_gun_arm_pistol_only(pen)
    return draw


def draw_gun_arm_pistol_only(pen):
    gx, gy = 0, 0
    grip = P().M(gx - 1.6, gy - 1.6).L(gx + 2.6, gy - 1.6).L(gx + 1.0, gy + 4.6).C(gx - 0.6, gy + 6.0, gx - 3.4, gy + 5.2, gx - 3.0, gy + 3.4).Z()
    pen.shape(grip, WOOD, G_LINE, 0.6)
    barrel = P().M(gx, gy - 3.4).L(gx + 17.5, gy - 3.0).L(gx + 17.5, gy - 0.6).L(gx, gy - 0.2).Z()
    pen.shape(barrel, GUNMETAL, G_LINE, 0.6)


# ------------------------------------------------------------------ cão de caça
D_FUR = "#3b3338"
D_FUR_SH = "#221c20"
D_FUR_HL = "#5f555c"
D_TAN = "#c4803f"
D_TAN_SH = "#8c5426"
D_LINE = "#120c10"
D_COLLAR = "#a8202f"
D_EYE = "#ff3a3a"


def dpose(**kw):
    d = dict(bob=0.0, pitch=0.0, head=0.0, jaw=0.08, lift=0.0, stretch=1.0,
             fn=(0.1, 0.1), ff=(0.0, 0.0), bn=(-0.1, -0.5, 0.2), bf=(0.0, -0.5, 0.2),
             tail=-0.5, ears=0.0, mood="angry", hackles=0.0, drool=False)
    d.update(kw)
    return d


FU, FL = 8.4, 9.6            # pata da frente: braço, antebraço
BT, BS, BF = 8.2, 7.4, 5.4   # pata de trás: coxa, canela, pé


def _dog_legs(ps, C, pitch):
    def T(p):
        q = rot(p, pitch)
        return (C[0] + q[0], C[1] + q[1])
    S = T((9.0 * ps["stretch"], -1.0))
    Hh = T((-10.0 * ps["stretch"], -1.0))
    legs = {}
    for key, base, off in (("fn", S, (0.0, 0.0)), ("ff", S, (1.6, -0.6))):
        a, b = ps[key]
        top = add(base, off)
        elbow = add(top, _dir(a), FU)
        paw = add(elbow, _dir(b), FL)
        legs[key] = (top, elbow, paw)
    for key, base, off in (("bn", Hh, (0.0, 0.0)), ("bf", Hh, (1.6, -0.6))):
        a, b, c = ps[key]
        top = add(base, off)
        knee = add(top, _dir(a), BT)
        hock = add(knee, _dir(b), BS)
        paw = add(hock, _dir(c), BF)
        legs[key] = (top, knee, hock, paw)
    return legs, T, S, Hh


def dog_ground(ps):
    legs, _, _, _ = _dog_legs(ps, (0.0, 0.0), ps["pitch"])
    low = max(l[-1][1] for l in legs.values())
    return -low - 2.2


def draw_dog_head(pen, ps):
    jaw = ps["jaw"]
    mood = ps["mood"]
    # orelha de trás
    ears = ps["ears"]
    pen.shape(P().M(-3.8, -4.4).L(-7.6 - ears * 4, -14.8 + ears * 5).L(-0.6, -5.6).Z(), D_FUR_SH, D_LINE, 0.7)
    # mandíbula (abre girando)
    with pen.at(2.6, 2.4, jaw):
        lower = P().M(-2.0, -0.6).L(10.6, 0.0).C(11.6, 0.6, 11.2, 2.4, 9.6, 2.6).L(-1.6, 3.6).Z()
        pen.fill(lower, D_FUR)
        with pen.clip(lower):
            pen.fill(P().M(-3, 1.2).L(12, 0.8).L(12, 5).L(-3, 5).Z(), D_TAN)
        pen.stroke(lower, D_LINE, 0.7)
        if jaw > 0.2:
            for x in (3.0, 6.0, 9.0):
                pen.fill(P().poly([(x - 0.7, -0.2), (x + 0.7, -0.2), (x, -1.9)]), "#ffffff")
            pen.fill(P().oval(5.0, -0.4, 4.2, 1.0), "#e45b72")
    if jaw > 0.2:  # boca aberta (interior)
        pen.fill(P().M(2.4, 1.6).L(13.4, 0.4).L(12.0, 2.4 + jaw * 9).L(3.0, 3.6).Z(), "#5a0f1e")
    # crânio + focinho
    head = P().M(-6.6, -1.0).C(-6.8, -6.6, -2.2, -8.0, 1.6, -7.4).C(5.0, -6.8, 7.0, -4.4, 9.0, -3.6).L(14.2, -2.2) \
        .C(15.6, -1.6, 15.6, 0.8, 14.0, 1.4).L(4.6, 2.6).C(1.0, 5.4, -5.6, 4.6, -6.6, -1.0).Z()
    pen.fill(head, D_FUR)
    with pen.clip(head):
        pen.fill(P().M(4, 0.6).L(16, -0.6).L(16, 4).L(4, 4).Z(), D_TAN)        # lateral do focinho
        pen.fill(P().oval(-2, 3.0, 5.0, 2.4), D_TAN_SH)                          # bochecha
        pen.fill(P().oval(-1.6, -6.0, 4.2, 1.6), D_FUR_HL, alpha=200)
    pen.stroke(head, D_LINE, 0.85)
    pen.fill(P().oval(14.2, -0.8, 1.6, 1.3), "#0b0709")                         # trufa
    pen.fill(P().circle(13.8, -1.4, 0.45), "#8a8a95")
    # dentes de cima à mostra (rosnando)
    if jaw > 0.05 or mood == "snarl":
        for x in (6.0, 9.0, 12.0):
            pen.fill(P().poly([(x - 0.6, 1.4 - (x - 6) * 0.15), (x + 0.6, 1.3 - (x - 6) * 0.15), (x, 3.2 - (x - 6) * 0.15)]), "#ffffff")
            pen.stroke(P().poly([(x - 0.6, 1.4 - (x - 6) * 0.15), (x + 0.6, 1.3 - (x - 6) * 0.15), (x, 3.2 - (x - 6) * 0.15)]), D_LINE, 0.3)
    # olho
    if mood == "hurt":
        pen.fill(tapered([(1.0, -4.2), (3.6, -2.6), (1.0, -1.0)], 0.6, 0.6, 1.2), D_LINE)
    elif mood == "dead":
        for a, b in (((0.4, -4.2), (3.6, -1.0)), ((0.4, -1.0), (3.6, -4.2))):
            pen.stroke(P().M(*a).L(*b), D_LINE, 0.9)
    else:
        eye = P().M(0.0, -2.6).Q(2.0, -4.6, 4.4, -3.0).Q(2.4, -1.2, 0.0, -2.6).Z()
        pen.fill(P().circle(2.2, -2.8, 2.6), D_EYE, alpha=80, blur=1.0)
        pen.fill(eye, D_EYE)
        pen.fill(P().oval(2.4, -2.9, 0.4, 0.9), "#2a0006")
        pen.fill(P().circle(1.6, -3.3, 0.45), "#ffffff")
        pen.stroke(eye, D_LINE, 0.5)
        pen.fill(tapered([(-0.6, -5.6), (2.0, -5.0), (4.4, -3.8)], 0.8, 0.4, 1.2), D_TAN)  # sobrancelha cor de fogo
    # orelha da frente
    pen.shape(P().M(-2.4, -5.6).L(-5.0 - ears * 4, -16.4 + ears * 5).L(1.4, -6.6).Z(), D_FUR, D_LINE, 0.75)
    pen.fill(P().M(-1.8, -6.4).L(-4.0 - ears * 4, -14.0 + ears * 5).L(0.2, -6.8).Z(), "#7a4a52")
    if ps["drool"]:
        pen.shape(P().M(9.0, 2.8).C(9.6, 5.0, 10.4, 7.2, 9.4, 8.0).C(8.6, 8.4, 8.0, 7.0, 9.0, 2.8).Z(), "#d8f2ff", "#5a8aa8", 0.35)


def draw_dog(pen, ps):
    C = (0.0, -21.0 + ps["bob"] - ps["lift"])
    C = (C[0], C[1] + dog_ground(ps) * 0.0)
    legs, T, S, Hh = _dog_legs(ps, (0.0, 0.0), ps["pitch"])
    g = -max(l[-1][1] for l in legs.values()) - 2.2 - ps["lift"]
    with pen.at(0.0, g):
        legs, T, S, Hh = _dog_legs(ps, (0.0, 0.0), ps["pitch"])

        def front_leg(key, far):
            top, elbow, paw = legs[key]
            col = D_FUR if not far else D_FUR_SH
            limb(pen, top, elbow, 6.6, 4.2, col, D_LINE, 0.7)
            limb(pen, elbow, paw, 3.8, 3.1, D_TAN if not far else D_TAN_SH, D_LINE, 0.7)
            pen.shape(P().oval(paw[0] + 0.8, paw[1] + 0.6, 2.2, 1.5), D_TAN if not far else D_TAN_SH, D_LINE, 0.6)

        def back_leg(key, far):
            top, knee, hock, paw = legs[key]
            col = D_FUR if not far else D_FUR_SH
            limb(pen, top, knee, 8.8, 5.4, col, D_LINE, 0.7)
            limb(pen, knee, hock, 4.6, 3.3, col, D_LINE, 0.7)
            limb(pen, hock, paw, 3.3, 2.9, D_TAN if not far else D_TAN_SH, D_LINE, 0.7)
            pen.shape(P().oval(paw[0] + 0.8, paw[1] + 0.6, 2.2, 1.5), D_TAN if not far else D_TAN_SH, D_LINE, 0.6)

        back_leg("bf", True)
        front_leg("ff", True)
        # rabo
        t0 = T((-13.0 * ps["stretch"], -5.0))
        ta = ps["tail"]
        tail = [t0, add(t0, (-math.cos(ta) * 4.0, -math.sin(-ta) * 4.0 - 2.0)), add(t0, (-math.cos(ta) * 8.5, -math.sin(-ta) * 8.0 - 3.0)),
                add(t0, (-math.cos(ta) * 12.5, -math.sin(-ta) * 12.0 - 2.0))]
        pen.shape(tapered(tail, 3.0, 0.8, 2.4), D_FUR, D_LINE, 0.7)
        # corpo
        st = ps["stretch"]
        with pen.at(0, 0, ps["pitch"]):
            body = P().M(10.0 * st, -7.0).C(4 * st, -9.0, -6 * st, -9.4, -11.6 * st, -7.0).C(-15.6 * st, -6.0, -16.2 * st, -0.6, -14.0 * st, 3.0) \
                .C(-11 * st, 5.0, -6 * st, 3.2, -3 * st, 2.4).C(1 * st, 4.6, 7 * st, 8.4, 11.4 * st, 7.0).C(14.4 * st, 5.0, 14.2 * st, -3.0, 10.0 * st, -7.0).Z()
            pen.fill(body, D_FUR)
            with pen.clip(body):
                pen.fill(P().oval(0, 5.6, 16 * st, 4.6), D_FUR_SH)
                pen.fill(P().oval(9.6 * st, 3.8, 4.2, 4.4), D_TAN)                 # peito
                pen.fill(P().oval(-2 * st, -7.6, 9 * st, 1.8), D_FUR_HL, alpha=210)
                pen.fill(P().oval(-11.6 * st, -2.4, 3.4, 4.6), D_FUR_HL, alpha=110)
            pen.stroke(body, D_LINE, 0.85)
            if ps["hackles"]:
                for i in range(5):
                    x = 6.0 * st - i * 3.0 * st
                    pen.shape(P().poly([(x - 1.4, -8.2 + i * 0.15), (x + 0.2, -11.2 - ps["hackles"] * 1.5), (x + 1.4, -8.0)]), D_FUR, D_LINE, 0.5)
        back_leg("bn", False)
        front_leg("fn", False)
        # pescoço + coleira + cabeça
        neck0 = T((9.6 * st, -4.0))
        hc = add(T((17.0 * st, -11.0)), (0.0, ps["head"] * 4.0))
        pen.shape(tapered([neck0, lerp2(neck0, hc, 0.5), hc], 9.6, 7.6, 8.6), D_FUR, D_LINE, 0.75)
        cl = lerp2(neck0, hc, 0.62)
        na = math.atan2(hc[1] - neck0[1], hc[0] - neck0[0])
        with pen.at(cl[0], cl[1], na + math.pi / 2):
            pen.shape(P().M(-4.6, -1.2).L(4.6, -1.2).L(4.6, 1.2).L(-4.6, 1.2).Z(), D_COLLAR, D_LINE, 0.6)
            for x in (-2.6, 0.0, 2.6):
                pen.shape(P().poly([(x - 0.9, -1.2), (x + 0.9, -1.2), (x, -3.4)]), "#d8dde6", D_LINE, 0.35)
        with pen.at(hc[0], hc[1], ps["pitch"] * 0.6 + ps["head"] * 0.3, 1.22):
            draw_dog_head(pen, ps)
    return {"head": hc}


def dog_anims():
    run = [
        dpose(pitch=0.00, lift=3.0, fn=(1.0, 1.25), ff=(0.85, 1.1), bn=(-0.95, -1.25, -0.6), bf=(-0.8, -1.15, -0.5), tail=-0.2, ears=0.3, jaw=0.18),
        dpose(pitch=0.07, fn=(0.45, 0.45), ff=(0.7, 0.9), bn=(-0.3, -1.0, 0.0), bf=(-0.45, -1.1, -0.2), tail=-0.3, ears=0.2, jaw=0.15),
        dpose(pitch=0.12, fn=(-0.3, -0.2), ff=(0.05, 0.1), bn=(0.45, -0.5, 0.2), bf=(0.3, -0.6, 0.1), tail=-0.4, ears=0.2, jaw=0.12),
        dpose(pitch=0.02, lift=1.0, fn=(-0.6, -2.0), ff=(-0.4, -1.8), bn=(1.0, 0.25, 0.7), bf=(0.85, 0.15, 0.6), tail=-0.6, ears=0.1, jaw=0.15),
        dpose(pitch=-0.06, fn=(0.55, 0.2), ff=(0.35, 0.0), bn=(0.45, -0.35, 0.1), bf=(0.6, -0.2, 0.25), tail=-0.4, ears=0.2, jaw=0.18),
        dpose(pitch=-0.09, lift=1.5, fn=(0.95, 1.05), ff=(0.8, 0.95), bn=(-0.45, -0.95, -0.3), bf=(-0.3, -0.85, -0.2), tail=-0.25, ears=0.3, jaw=0.2),
    ]
    crouch = [
        dpose(mood="snarl", pitch=0.16, bob=4.0, head=0.8, jaw=0.35, fn=(-0.2, 0.5), ff=(-0.05, 0.55), bn=(0.9, -0.9, 0.3), bf=(0.8, -1.0, 0.25),
              tail=0.6, ears=0.8, hackles=1.0, drool=True),
        dpose(mood="snarl", pitch=0.18, bob=4.6, head=0.9, jaw=0.45, fn=(-0.25, 0.5), ff=(-0.1, 0.55), bn=(0.95, -0.95, 0.3), bf=(0.85, -1.05, 0.25),
              tail=0.7, ears=0.9, hackles=1.3, drool=True),
    ]
    lunge = [dpose(mood="angry", pitch=-0.12, lift=7.0, stretch=1.12, jaw=0.75, head=-0.3, fn=(1.35, 1.55), ff=(1.2, 1.45),
                   bn=(-1.25, -1.55, -1.25), bf=(-1.1, -1.45, -1.1), tail=-0.1, ears=1.0)]
    recover = [dpose(mood="angry", pitch=0.12, bob=1.0, jaw=0.2, fn=(0.55, 0.3), ff=(0.4, 0.25), bn=(0.7, -0.4, 0.3), bf=(0.6, -0.5, 0.2), tail=-0.3)]
    hurt = [dpose(mood="hurt", pitch=-0.2, head=-0.6, jaw=0.6, fn=(0.6, 0.8), ff=(0.4, 0.6), bn=(-0.2, -0.8, 0.0), bf=(-0.1, -0.7, 0.1), tail=0.2, ears=1.0)]
    return {"run": (14, True, run), "crouch": (10, True, crouch), "lunge": (10, False, lunge), "recover": (8, False, recover), "hurt": (10, False, hurt)}


def dog_dead_draw():
    def draw(pen):
        with pen.at(0, -33, math.pi * 0.97):
            ps = dpose(mood="dead", jaw=0.55, head=2.6, fn=(0.3, 0.2), ff=(0.6, 0.5), bn=(-0.3, -0.2, -0.1), bf=(-0.6, -0.5, -0.4), tail=0.4, ears=1.0)
            draw_dog(pen, ps)
    return draw


# ------------------------------------------------------------------ o Gigante (carrasco)
B_SKIN = "#c68c6c"
B_SKIN_SH = "#975f4a"
B_SKIN_HL = "#e3b393"
B_SKIN_LINE = "#3e1c12"
B_RAGE = "#d8735f"
HOOD = "#7c1828"
HOOD_SH = "#4c0f19"
HOOD_HL = "#a8394c"
HOOD_LINE = "#22050c"
LEATHER = "#6b4730"
LEATHER_SH = "#4a2f1f"
STRAP = "#3d2618"
IRON = "#70768a"
IRON_SH = "#474c5a"
IRON_HL = "#bac2d3"
IRON_LINE = "#1b1d24"
B_PANTS = "#3a2b30"

# âncoras (vista de frente olhando para a direita, pés em 0,0)
BOSS_SHOULDER_N = (-44.0, -110.0)
BOSS_SHOULDER_F = (41.0, -112.0)


def bpose(**kw):
    d = dict(bob=0.0, lean=0.0, legs=(0.0, 0.0), rage=False, eyes="glow", jiggle=0.0, steam=0.0)
    d.update(kw)
    return d


def _boss_leg(pen, hip, ang, far):
    knee = add(hip, _dir(ang), 22)
    foot = add(knee, _dir(-ang * 0.3), 20)
    col = B_PANTS if not far else mix(B_PANTS, "#000000", 0.3)
    limb(pen, hip, knee, 27, 22, col, B_SKIN_LINE, 1.2)
    limb(pen, knee, foot, 22, 19, col, B_SKIN_LINE, 1.2)
    with pen.at(foot[0], foot[1]):
        boot = P().M(-11, -12).L(10, -12).L(11, -2).C(16, -1.6, 20, 0.6, 20, 4.0).L(20, 6.4).L(-12, 6.4).C(-13, 2, -12.6, -6, -11, -12).Z()
        pen.fill(boot, "#3a2519" if not far else "#26180f")
        with pen.clip(boot):
            pen.fill(P().M(-14, 4.0).L(22, 4.0).L(22, 8).L(-14, 8).Z(), "#140b07")
            pen.fill(P().M(8, -4).C(16, -3, 21, 0, 21, 6).L(8, 6).Z(), IRON, alpha=230)     # biqueira de ferro
            pen.fill(P().M(-13, -12).L(11, -12).L(11, -8).L(-13, -8).Z(), "#24160e")
        pen.stroke(boot, B_SKIN_LINE, 1.1)
        for x in (12, 16):
            pen.fill(P().circle(x, 1.0, 0.9), IRON_HL)
    return foot


def draw_boss_body(pen, ps):
    rage = ps["rage"]
    skin = B_RAGE if rage else B_SKIN
    bob = ps["bob"]
    la, lb = ps["legs"]
    _boss_leg(pen, (14, -50 + bob * 0.3), lb, True)
    _boss_leg(pen, (-14, -50 + bob * 0.3), la, False)
    with pen.at(0, bob, ps["lean"]):
        j = ps["jiggle"]
        # tronco (peitoral + barriga)
        torso = P().M(-44, -110).C(-50, -96, -46, -80, -40, -70).C(-44, -62, -38, -50, -26, -46).L(26, -46) \
            .C(38, -50, 44, -62, 40, -70).C(46, -82, 48, -98, 41, -112).C(26, -122, -26, -122, -44, -110).Z()
        pen.fill(torso, skin)
        with pen.clip(torso):
            pen.fill(P().M(16, -124).C(34, -96, 36, -70, 20, -44).L(60, -44).L(60, -124).Z(), B_SKIN_SH)
            pen.fill(P().oval(-18, -98, 14, 9), B_SKIN_HL, alpha=150)                        # peitoral
            pen.fill(P().oval(-2, -66 + j, 30, 16), B_SKIN_SH, alpha=120)                       # barriga
            pen.fill(P().oval(-12, -74 + j, 10, 6), B_SKIN_HL, alpha=120)
            pen.stroke(P().M(-30, -90).Q(-14, -84, 2, -92), B_SKIN_LINE, 1.0, alpha=170)        # linha do peito
            pen.stroke(P().M(4, -92).Q(18, -86, 30, -92), B_SKIN_LINE, 1.0, alpha=140)
            pen.fill(P().oval(-4, -62 + j, 1.6, 2.2), B_SKIN_LINE, alpha=200)                   # umbigo
            # cicatrizes
            pen.stroke(P().M(-30, -78).L(-18, -86), "#7a3a2c", 1.2)
            pen.stroke(P().M(-27, -84).L(-25, -79), "#7a3a2c", 0.9)
            if rage:  # veias
                for vx, vy in ((-26, -100), (24, -96), (-8, -80)):
                    pen.stroke(P().M(vx, vy).L(vx + 3, vy + 5).L(vx + 1, vy + 9).L(vx + 4, vy + 13), "#8a1a22", 1.0)
            # tiras de couro em X + argola
            for (x0, y0, x1, y1) in ((-40, -112, 22, -50), (38, -114, -22, -50)):
                pen.fill(tapered([(x0, y0), ((x0 + x1) / 2, (y0 + y1) / 2), (x1, y1)], 9, 9, 9), STRAP)
                pen.stroke(P().M(x0, y0).L(x1, y1), "#6a4630", 0.8)
            pen.shape(P().circle(0, -82, 6.5), IRON, IRON_LINE, 1.0)
            pen.fill(P().circle(0, -82, 3.4), skin)
            pen.stroke(P().circle(0, -82, 3.4), IRON_LINE, 0.8)
        pen.stroke(torso, B_SKIN_LINE, 1.3)
        # cinto + avental
        apron = P().M(-30, -56).L(30, -56).C(33, -40, 34, -28, 32, -20).Q(0, -14, -32, -20).C(-34, -28, -33, -40, -30, -56).Z()
        pen.fill(apron, LEATHER)
        with pen.clip(apron):
            pen.fill(P().M(12, -60).C(22, -40, 24, -28, 22, -10).L(40, -10).L(40, -60).Z(), LEATHER_SH)
            pen.stroke(P().M(-27, -52).L(27, -52).C(30, -38, 30, -28, 28, -23).Q(0, -18, -28, -23).C(-30, -28, -30, -38, -27, -52), "#a8805c", 0.8)
            # manchas de sangue
            pen.fill(P().oval(-12, -36, 6, 4), "#6e1020", alpha=210)
            pen.fill(P().oval(-6, -32, 3, 2), "#6e1020", alpha=210)
            pen.fill(P().oval(10, -42, 3.4, 2.2), "#6e1020", alpha=190)
            pen.fill(P().M(-12, -33).L(-11, -24).L(-13, -24).Z(), "#6e1020", alpha=200)
        pen.stroke(apron, B_SKIN_LINE, 1.2)
        belt = P().M(-40, -62).Q(0, -56, 40, -63).L(40, -54).Q(0, -48, -40, -53).Z()
        pen.shape(belt, STRAP, B_SKIN_LINE, 1.1)
        pen.shape(P().M(-7, -63).L(7, -63).L(7, -50).L(-7, -50).Z(), IRON, IRON_LINE, 1.0)
        pen.fill(P().M(-3.6, -60).L(3.6, -60).L(3.6, -53).L(-3.6, -53).Z(), STRAP)
        # ombros (deltoides) — os braços saem daqui no jogo
        for (x, y), far in ((BOSS_SHOULDER_F, True), (BOSS_SHOULDER_N, False)):
            sh = P().circle(x, y, 15)
            pen.fill(sh, skin if not far else B_SKIN_SH)
            with pen.clip(sh):
                pen.fill(P().circle(x - 4, y - 6, 7), B_SKIN_HL, alpha=140 if not far else 60)
            pen.stroke(sh, B_SKIN_LINE, 1.2)
        # ombreira de ferro com cravos no ombro de perto
        x, y = BOSS_SHOULDER_N
        pad = P().M(x - 18, y + 2).C(x - 18, y - 14, x + 10, y - 20, x + 16, y - 6).Q(x + 2, y - 4, x - 18, y + 2).Z()
        pen.fill(pad, IRON)
        with pen.clip(pad):
            pen.fill(P().oval(x + 2, y + 2, 18, 6), IRON_SH)
            pen.fill(P().oval(x - 4, y - 10, 9, 3), IRON_HL, alpha=200)
        pen.stroke(pad, IRON_LINE, 1.1)
        for k in range(3):
            cx, cy = x - 10 + k * 9, y - 9 - (1 - abs(k - 1)) * 3
            pen.shape(P().poly([(cx - 3, cy + 2), (cx + 3, cy + 2), (cx, cy - 7)]), IRON_HL, IRON_LINE, 0.8)
        # corrente pendurada no ombro
        for k in range(6):
            c = lerp2((x + 6, y + 4), (x + 30, y + 30), k / 5)
            pen.stroke(P().oval(c[0], c[1], 3.2, 2.0), IRON_SH, 1.6)
            pen.stroke(P().oval(c[0], c[1], 3.2, 2.0), IRON_HL, 0.5)
        # capuz de carrasco + manto curto nos ombros
        mantle = P().M(-34, -112).L(-28, -101).L(-20, -107).L(-12, -97).L(-4, -105).L(4, -96).L(12, -104).L(20, -97).L(28, -105).L(34, -100) \
            .L(38, -114).C(26, -128, -24, -128, -34, -112).Z()
        pen.fill(mantle, HOOD)
        with pen.clip(mantle):
            pen.fill(P().M(10, -130).L(40, -130).L(40, -94).L(14, -94).Z(), HOOD_SH)
        pen.stroke(mantle, HOOD_LINE, 1.1)
        # mandíbula (fica abaixo do capuz)
        jaw = P().M(-14, -128).C(-16, -118, -10, -110, 4, -109).C(16, -110, 21, -118, 19, -128).Z()
        pen.fill(jaw, skin)
        with pen.clip(jaw):
            pen.fill(P().M(8, -132).C(18, -122, 16, -112, 8, -106).L(24, -106).L(24, -132).Z(), B_SKIN_SH)
            for (sx, sy) in ((-8, -116), (-4, -113), (0, -114), (5, -113), (10, -115), (-6, -119), (8, -118), (2, -117)):
                pen.fill(P().circle(sx, sy, 0.7), "#5a3020", alpha=200)                          # barba por fazer
        pen.stroke(jaw, B_SKIN_LINE, 1.1)
        # dentes cerrados
        mouth = P().M(-6, -122).L(12, -123).L(11, -117).L(-5, -116.6).Z()
        pen.shape(mouth, "#f1ead8", B_SKIN_LINE, 0.9)
        for x in (-2, 2, 6):
            pen.stroke(P().M(x, -122.6).L(x + 0.2, -116.8), B_SKIN_LINE, 0.6)
        pen.stroke(P().M(-6, -119.6).L(11.6, -120.2), B_SKIN_LINE, 0.6)
        # capuz
        hood = P().M(-17, -126).C(-20, -140, -16, -156, -6, -164).C(-12, -170, -20, -174, -24, -172).C(-14, -178, 2, -176, 10, -166) \
            .C(20, -158, 23, -142, 21, -127).Q(2, -122, -17, -126).Z()
        pen.fill(hood, HOOD)
        with pen.clip(hood):
            pen.fill(P().M(8, -180).C(20, -160, 24, -140, 20, -120).L(30, -120).L(30, -180).Z(), HOOD_SH)
            pen.fill(P().oval(-6, -152, 6, 11), HOOD_HL, alpha=150)
            pen.stroke(P().M(-12, -130).Q(2, -126, 18, -130), HOOD_SH, 1.2)
        pen.stroke(hood, HOOD_LINE, 1.2)
        # buracos dos olhos com brilho
        eye_col = "#ff3424" if rage else "#ffd75a"
        for (ex, ey, w) in ((-6, -142, 5.6), (10, -143, 4.6)):
            hole = P().M(ex - w, ey + 1).Q(ex, ey - 4.4, ex + w, ey).Q(ex, ey + 3.6, ex - w, ey + 1).Z()
            pen.fill(hole, "#0d0204")
            if ps["eyes"] != "dead":
                pen.fill(P().circle(ex + 0.6, ey + 0.4, 3.8), eye_col, alpha=110, blur=2.2)
                pen.fill(P().oval(ex + 0.6, ey + 0.4, 2.0, 1.4), eye_col)
                pen.fill(P().circle(ex + 0.2, ey, 0.6), "#ffffff")
            else:
                pen.stroke(P().M(ex - 2, ey - 1.6).L(ex + 2, ey + 2), eye_col, 1.0)
                pen.stroke(P().M(ex - 2, ey + 2).L(ex + 2, ey - 1.6), eye_col, 1.0)
            pen.stroke(hole, HOOD_LINE, 0.9)
        if ps["steam"]:
            for k, (sx, sy) in enumerate(((-14, -176), (8, -182), (-2, -190))):
                r = 4.5 + ps["steam"] * 2 + k
                pen.fill(P().circle(sx + ps["steam"] * 3, sy - ps["steam"] * 4, r), "#f0e8ee", alpha=150)
                pen.fill(P().circle(sx + ps["steam"] * 3 - 1.5, sy - ps["steam"] * 4 - 1.5, r * 0.5), "#ffffff", alpha=170)


def draw_boss(pen, ps):
    draw_boss_body(pen, ps)
    return {"shoulder_n": BOSS_SHOULDER_N, "shoulder_f": BOSS_SHOULDER_F}


def boss_anims():
    walk = []
    for i in range(4):
        ph = i / 4 * math.tau
        walk.append(bpose(bob=-2.0 * abs(math.sin(ph)) + 1.0, legs=(0.22 * math.sin(ph), -0.22 * math.sin(ph)), jiggle=1.6 * math.cos(ph * 2)))
    windup = [bpose(bob=3.0, lean=-0.06, legs=(0.2, -0.2), jiggle=1.0)]
    strike = [bpose(bob=1.0, lean=0.08, legs=(0.25, -0.25), jiggle=-1.5)]
    A = {"walk": (6, True, walk), "windup": (6, True, windup), "strike": (6, True, strike)}
    for n in list(A):
        fps, loop, frames = A[n]
        A[n + "_rage"] = (fps, loop, [dict(f, rage=True, steam=(i % 2) * 0.8 + 0.4) for i, f in enumerate(frames)])
    return A


def boss_dead_draw():
    def draw(pen):
        with pen.at(66, -24, -1.48, 0.9):
            draw_boss_body(pen, bpose(eyes="dead", legs=(0.15, -0.1)))
    return draw


# ------------------------------------------------------------------ manopla de ferro
FIST_SIZE = (64, 64)


def draw_fist(pen, rage=False):
    """Punho com manopla de ferro, nós dos dedos apontando para +x, centro em (0, 0)."""
    # punho de couro (pulso) com tiras
    cuff = P().M(-24, -11).L(-10, -12).L(-10, 12).L(-24, 11).Z()
    pen.fill(cuff, LEATHER)
    with pen.clip(cuff):
        for x in (-21, -15):
            pen.fill(P().M(x, -14).L(x + 3, -14).L(x + 3, 14).L(x, 14).Z(), STRAP)
    pen.stroke(cuff, B_SKIN_LINE, 1.1)
    # dorso da mão
    back = P().M(-11, -14).C(-2, -18, 10, -17, 15, -12).L(18, 12).C(10, 17, -2, 18, -11, 14).Z()
    pen.fill(back, IRON)
    with pen.clip(back):
        pen.fill(P().oval(4, 10, 18, 7), IRON_SH)
        pen.fill(P().oval(-2, -10, 12, 3.5), IRON_HL, alpha=220)
    pen.stroke(back, IRON_LINE, 1.2)
    # dedos (placas curvas) + cravos
    for k, y in enumerate((-10.5, -3.5, 3.5, 10.5)):
        f = P().M(12, y - 3.6).C(18, y - 4.2, 23, y - 2.6, 23.4, y).C(23, y + 2.8, 18, y + 4.0, 12, y + 3.4).Z()
        pen.fill(f, IRON if k % 2 == 0 else IRON_SH)
        with pen.clip(f):
            pen.fill(P().oval(18, y - 2.2, 4, 1.2), IRON_HL, alpha=220)
        pen.stroke(f, IRON_LINE, 1.0)
        pen.shape(P().poly([(21.6, y - 1.6), (21.6, y + 1.6), (26.6, y)]), IRON_HL, IRON_LINE, 0.7)
    # polegar
    th = P().M(0, 12).C(6, 14, 12, 16, 14, 13).C(14, 18, 6, 20, -2, 17).Z()
    pen.shape(th, IRON_SH, IRON_LINE, 1.0)
    for (x, y) in ((-6, -8), (-6, 8), (4, -11), (4, 11)):
        pen.fill(P().circle(x, y, 1.3), IRON_HL)
        pen.stroke(P().circle(x, y, 1.3), IRON_LINE, 0.5)
    if rage:
        pen.fill(P().oval(6, 0, 20, 18), "#ff3a20", alpha=55, blur=3.0)
