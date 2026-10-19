"""Cabeça da Vampirinha (estilo anime), compartilhada entre o sprite e o retrato do HUD.

Coordenadas locais: centro do crânio em (0, 0), y para baixo, ~1 unidade = 1 px no sprite.
Vista 'front' = 3/4 de frente olhando para a direita; 'back' = 3/4 de costas.
"""
import math

from .kit import P, add, bezier_pts, lerp2, mix, rot, tapered

# ------------------------------------------------------------------ paleta
SKIN = "#efe4f1"
SKIN_SH = "#cdb9d8"
SKIN_SH2 = "#ad97c0"
SKIN_LINE = "#4a2a4a"
BLUSH = "#ff7d98"

HAIR = "#2c2333"
HAIR_SH = "#1c1622"
HAIR_SH2 = "#130e18"
HAIR_LINE = "#07040a"
HAIR_SHINE = "#8c7aa8"

EYE_LINE = "#2a0a1c"
IRIS_TOP = "#3d0016"
IRIS_MID = "#b5122f"
IRIS_LOW = "#ff3d4a"
IRIS_GLOW = "#ff9a6e"
WHITE = "#ffffff"
EYE_WHITE_SH = "#ead6e2"

MOUTH_IN = "#6d0f2a"
TONGUE = "#ff7b8e"
FANG = "#ffffff"

RIBBON = "#d4173f"
RIBBON_SH = "#8e0b29"
CLIP_DARK = "#2a1a33"


def palette_low(c):
    """Pele mais pálida/azulada quando o sangue está acabando."""
    return mix(c, "#cfd6ea", 0.45)


# ------------------------------------------------------------------ olhos
def eye_shape(cx, cy, w, h, out):
    """Região branca do olho. out = -1 (canto externo à esquerda) ou +1."""
    inner = (cx - out * w / 2, cy - h * 0.12)
    outer = (cx + out * w / 2, cy - h * 0.22)
    top_c1 = (inner[0] + out * w * 0.18, cy - h * 0.58)
    top_c2 = (outer[0] - out * w * 0.25, cy - h * 0.62)
    p = P().M(*inner)
    p.C(*top_c1, *top_c2, *outer)
    p.C(outer[0] + out * w * 0.05, cy + h * 0.35, cx + out * w * 0.15, cy + h * 0.55, cx, cy + h * 0.5)
    p.C(cx - out * w * 0.35, cy + h * 0.45, inner[0], cy + h * 0.2, *inner)
    p.Z()
    return p, inner, outer, top_c1, top_c2


def draw_eye(pen, cx, cy, w, h, out, expr="open", look=(0.6, 0.0), glow=False, detail=False):
    """Olho anime. expr: open, half, closed (^ feliz), blink, wide, angry, frenzy, x, squeeze, tired."""
    lw = 0.55 if detail else 0.7
    if expr in ("closed", "blink", "x", "squeeze"):
        if expr == "closed":  # arco feliz ^
            pts = bezier_pts((cx - w / 2, cy + h * 0.1), (cx - w * 0.2, cy - h * 0.35), (cx + w * 0.2, cy - h * 0.35), (cx + w / 2, cy + h * 0.1), 10)
            pen.fill(tapered(pts, 0.6, 0.6, 1.6), EYE_LINE)
        elif expr == "blink":
            pts = bezier_pts((cx - w / 2, cy + h * 0.05), (cx - w * 0.2, cy + h * 0.28), (cx + w * 0.2, cy + h * 0.28), (cx + w / 2, cy + h * 0.02), 10)
            pen.fill(tapered(pts, 0.7, 0.7, 1.5), EYE_LINE)
            # cílio na ponta externa
            o = (cx + out * w / 2, cy + h * 0.03)
            pen.fill(tapered([o, add(o, (out * 1.4, -0.4)), add(o, (out * 2.2, -1.4))], 1.2, 0.2), EYE_LINE)
        elif expr == "x":
            s = min(w, h) * 0.38
            for a, b in (((-s, -s), (s, s)), ((-s, s), (s, -s))):
                pen.fill(tapered([add((cx, cy + 1), a), (cx, cy + 1), add((cx, cy + 1), b)], 0.9, 0.9, 1.4), EYE_LINE)
        else:  # squeeze  > <
            s = w * 0.42
            d = -out
            pts = [(cx + d * s, cy - h * 0.3), (cx - d * s * 0.7, cy + 0.2), (cx + d * s, cy + h * 0.32)]
            pen.fill(tapered(pts, 0.7, 0.7, 1.7), EYE_LINE)
        return

    shape, inner, outer, c1, c2 = eye_shape(cx, cy, w, h, out)
    lid = {"open": 0.0, "half": 0.38, "angry": 0.18, "frenzy": 0.12, "tired": 0.42, "wide": -0.05}.get(expr, 0.0)

    # branco + íris (recortados na forma do olho e abaixo da pálpebra)
    with pen.clip(shape):
        pen.fill(shape, WHITE)
        iris_r = (w * 0.37, h * 0.43)
        if expr == "wide":
            iris_r = (w * 0.24, h * 0.27)
        icx = cx + look[0] * w * 0.12
        icy = cy + h * 0.1 + look[1]
        iris = P().oval(icx, icy, *iris_r)
        top = IRIS_TOP if not glow else "#7a0010"
        low = IRIS_LOW if not glow else "#ffd36a"
        pen.grad(iris, (icx, icy - iris_r[1]), (icx, icy + iris_r[1]), [top, IRIS_MID if not glow else "#ff2030", low], [0.0, 0.55, 1.0])
        pen.stroke(iris, "#2a0010", 0.45 if detail else 0.5)
        # anel claro inferior
        pen.fill(P().oval(icx, icy + iris_r[1] * 0.55, iris_r[0] * 0.7, iris_r[1] * 0.3), IRIS_GLOW if not glow else "#fff2a0", alpha=150)
        # pupila (fenda de vampiro)
        pr = (iris_r[0] * (0.22 if expr != "frenzy" else 0.13), iris_r[1] * 0.55)
        pen.fill(P().oval(icx, icy - iris_r[1] * 0.05, *pr), "#16000a")
        # sombra da pálpebra superior no branco
        pen.fill(P().oval(cx, cy - h * 0.5, w * 0.7, h * 0.3), EYE_WHITE_SH, alpha=190)
        # brilhos
        if expr != "frenzy":
            pen.fill(P().oval(icx - iris_r[0] * 0.38, icy - iris_r[1] * 0.42, iris_r[0] * 0.36, iris_r[1] * 0.26), WHITE)
            pen.fill(P().circle(icx + iris_r[0] * 0.4, icy + iris_r[1] * 0.42, max(0.45, iris_r[0] * 0.16)), WHITE)
        else:
            pen.fill(P().circle(icx - iris_r[0] * 0.35, icy - iris_r[1] * 0.4, iris_r[0] * 0.22), "#fff3d0")
        # pálpebra baixando (meio fechado / cansado / bravo)
        if lid > 0:
            yl = cy - h * 0.5 + h * lid * 1.1
            if expr == "angry" or expr == "frenzy":
                lidp = P().poly([(inner[0], yl + h * 0.18), (outer[0], yl - h * 0.12), (outer[0] + out * 3, cy - h), (inner[0] - out * 3, cy - h)])
            elif expr == "tired":
                lidp = P().poly([(inner[0], yl - h * 0.05), (outer[0], yl + h * 0.12), (outer[0] + out * 3, cy - h), (inner[0] - out * 3, cy - h)])
            else:
                lidp = P().poly([(inner[0] - out, yl), (outer[0] + out, yl), (outer[0] + out * 3, cy - h), (inner[0] - out * 3, cy - h)])
            pen.fill(lidp, SKIN)
            pen.fill(lidp, SKIN_SH, alpha=120)
    if glow:
        pen.fill(P().oval(cx, cy + h * 0.1, w * 0.75, h * 0.6), "#ff2a3a", alpha=70, blur=1.4)

    # linha superior dos cílios (grossa, com ponta para fora)
    if lid > 0:
        yl = cy - h * 0.5 + h * lid * 1.1
        if expr in ("angry", "frenzy"):
            a, b = (inner[0], yl + h * 0.18), (outer[0], yl - h * 0.12)
        elif expr == "tired":
            a, b = (inner[0], yl - h * 0.05), (outer[0], yl + h * 0.12)
        else:
            a, b = (inner[0] - out * 0.3, yl), (outer[0], yl)
        lash = [a, lerp2(a, b, 0.5), b, add(b, (out * 1.6, 0.6)), add(b, (out * 2.4, 1.6))]
        pen.fill(tapered(lash, 0.6, 0.3, 1.9), EYE_LINE)
    else:
        lash = bezier_pts(inner, c1, c2, outer, 10)
        lash.append(add(outer, (out * 1.2, 0.2)))
        lash.append(add(outer, (out * 2.1, 1.3)))
        pen.fill(tapered(lash, 0.6, 0.35, 2.0 if not detail else 1.7), EYE_LINE)
        if detail:  # cílios extras
            for k in (0.25, 0.55):
                b0 = lerp2(outer, c2, k)
                pen.fill(tapered([b0, add(b0, (out * 0.8, -0.9)), add(b0, (out * 1.4, -1.3))], 0.6, 0.1), EYE_LINE)
    # linha inferior curta
    lo0 = (cx + out * w * 0.12, cy + h * 0.5)
    lo1 = (cx + out * w * 0.45, cy + h * 0.22)
    pen.stroke(P().M(*lo0).Q(cx + out * w * 0.38, cy + h * 0.47, *lo1), EYE_LINE, lw)


def draw_brow(pen, x0, y0, x1, y1, bend=0.6, w=0.75):
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2 - bend
    pts = bezier_pts((x0, y0), (mx, my), (mx, my), (x1, y1), 8)
    pen.fill(tapered(pts, w * 0.5, w * 0.5, w * 1.2), "#5b3e6a")


# ------------------------------------------------------------------ boca
def draw_mouth(pen, mx, my, expr="smile", s=1.0, detail=False):
    lw = 0.7 * s
    if expr == "smile":
        pen.stroke(P().M(mx - 2.3 * s, my - 0.2 * s).Q(mx, my + 1.2 * s, mx + 2.3 * s, my - 0.5 * s), SKIN_LINE, lw)
        fang = P().poly([(mx + 0.7 * s, my + 0.35 * s), (mx + 1.9 * s, my + 0.2 * s), (mx + 1.35 * s, my + 2.0 * s)])
        pen.shape(fang, FANG, SKIN_LINE, 0.35 * s)
    elif expr == "smirk":
        pen.stroke(P().M(mx - 2.0 * s, my + 0.2 * s).Q(mx + 0.2 * s, my + 1.0 * s, mx + 2.6 * s, my - 0.9 * s), SKIN_LINE, lw)
        fang = P().poly([(mx + 1.0 * s, my + 0.15 * s), (mx + 2.1 * s, my - 0.2 * s), (mx + 1.7 * s, my + 1.8 * s)])
        pen.shape(fang, FANG, SKIN_LINE, 0.35 * s)
    elif expr == "flat":
        pen.stroke(P().M(mx - 1.6 * s, my).Q(mx, my + 0.4 * s, mx + 1.8 * s, my - 0.1 * s), SKIN_LINE, lw)
    elif expr == "wobble":  # preocupada / cansada
        pen.stroke(P().M(mx - 2.2 * s, my + 0.4 * s).C(mx - 1.2 * s, my - 0.6 * s, mx - 0.2 * s, my + 0.9 * s, mx + 0.6 * s, my + 0.1 * s)
                   .C(mx + 1.2 * s, my - 0.5 * s, mx + 1.8 * s, my + 0.6 * s, mx + 2.4 * s, my + 0.1 * s), SKIN_LINE, lw)
    elif expr in ("open", "pant", "spit", "chomp", "grin", "dead", "shout"):
        if expr == "open" or expr == "pant":
            m = P().M(mx - 2.0 * s, my - 0.3 * s).C(mx - 1.6 * s, my + 2.6 * s, mx + 1.8 * s, my + 2.6 * s, mx + 2.2 * s, my - 0.4 * s).Q(mx, my + 0.3 * s, mx - 2.0 * s, my - 0.3 * s).Z()
        elif expr == "spit":  # biquinho bem aberto para cuspir
            m = P().oval(mx + 0.4 * s, my + 0.9 * s, 1.9 * s, 2.1 * s)
        elif expr == "chomp":  # bocão aberto (parry)
            m = P().M(mx - 4.0 * s, my - 1.6 * s).C(mx - 3.6 * s, my + 5.5 * s, mx + 4.0 * s, my + 5.5 * s, mx + 4.2 * s, my - 1.8 * s).Q(mx, my - 0.6 * s, mx - 4.0 * s, my - 1.6 * s).Z()
        elif expr == "grin":  # sorriso largo de frenesi
            m = P().M(mx - 3.4 * s, my - 1.2 * s).C(mx - 2.0 * s, my + 2.4 * s, mx + 2.4 * s, my + 2.6 * s, mx + 3.6 * s, my - 1.6 * s).Q(mx, my - 0.2 * s, mx - 3.4 * s, my - 1.2 * s).Z()
        elif expr == "shout":
            m = P().M(mx - 2.6 * s, my - 0.8 * s).C(mx - 2.4 * s, my + 3.8 * s, mx + 2.6 * s, my + 3.8 * s, mx + 2.8 * s, my - 0.9 * s).Q(mx, my - 0.2 * s, mx - 2.6 * s, my - 0.8 * s).Z()
        else:  # dead: boca mole com a língua de fora
            m = P().M(mx - 2.4 * s, my - 0.1 * s).C(mx - 1.6 * s, my + 1.8 * s, mx + 1.6 * s, my + 1.8 * s, mx + 2.4 * s, my - 0.4 * s).Q(mx, my + 0.4 * s, mx - 2.4 * s, my - 0.1 * s).Z()
        pen.fill(m, MOUTH_IN)
        with pen.clip(m):
            # língua
            pen.fill(P().oval(mx + 0.3 * s, my + 3.0 * s, 2.4 * s, 1.6 * s), TONGUE)
            if expr in ("grin", "chomp", "shout", "open", "pant"):
                # dentes de cima e presas
                pen.fill(P().M(mx - 5 * s, my - 3 * s).L(mx + 5 * s, my - 3 * s).L(mx + 5 * s, my + 0.15 * s).L(mx - 5 * s, my + 0.45 * s).Z(), FANG)
                for fx in ((-1.6, 1.4), (1.9, 1.3)) if expr != "open" else ((1.5, 1.1),):
                    fxp = mx + fx[0] * s
                    pen.fill(P().poly([(fxp - 0.75 * s, my), (fxp + 0.75 * s, my - 0.2 * s), (fxp + 0.05 * s, my + fx[1] * s + 0.8 * s)]), FANG)
            if expr == "chomp":
                pen.fill(P().M(mx - 5 * s, my + 6 * s).L(mx + 5 * s, my + 6 * s).L(mx + 5 * s, my + 3.3 * s).L(mx - 5 * s, my + 3.4 * s).Z(), FANG)
        pen.stroke(m, SKIN_LINE, lw * 0.8)
        if expr == "dead":
            t = P().M(mx + 0.2 * s, my + 0.9 * s).C(mx + 0.4 * s, my + 3.6 * s, mx + 2.8 * s, my + 3.8 * s, mx + 2.6 * s, my + 0.8 * s).Z()
            pen.shape(t, TONGUE, SKIN_LINE, 0.4 * s)
    elif expr == "puff":  # bochecha cheia antes de cuspir
        pen.stroke(P().M(mx - 1.0 * s, my + 0.3 * s).Q(mx + 0.2 * s, my - 0.4 * s, mx + 1.3 * s, my + 0.3 * s), SKIN_LINE, lw)


# ------------------------------------------------------------------ cabelo
def locks_path(pts, close_with=None):
    """Borda de franja: alterna entalhes e pontas com curvas levemente arqueadas."""
    p = P().M(*pts[0])
    for a, b in zip(pts, pts[1:]):
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        dx, dy = b[0] - a[0], b[1] - a[1]
        # arqueia cada mecha para o lado de onde vem o penteado (para a direita)
        k = 0.22
        p.Q(mx + dy * k, my - dx * k * 0.2, *b)
    return p


def twin_tail(root, ang, length, sway=0.0, flip=1, curl=1.0):
    """Maria-chiquinha: sai da raiz um pouco para fora e cai, com cacho na ponta.

    sway > 0 joga a ponta para +x (vento/movimento), < 0 para -x.
    """
    p0 = (0.0, 0.0)
    p1 = (flip * 8.0, -1.5)
    p2 = (flip * 9.5 + sway * 4.0, length * 0.5)
    p3 = (flip * 4.0 + sway * 9.0, length - sway * abs(sway) * 2.0)
    pts = bezier_pts(p0, p1, p2, p3, 10)
    # cacho: a ponta vira para dentro
    tip = pts[-1]
    pts.append((tip[0] - flip * 2.2 * curl + sway * 0.6, tip[1] + 1.4))
    pts.append((tip[0] - flip * 4.0 * curl + sway * 0.8, tip[1] + 0.6))
    out = []
    for x, y in pts:
        x, y = rot((x, y), ang)
        out.append((root[0] + x, root[1] + y))
    return out


def draw_twin_tail(pen, root, length, flip, sway=0.0, ang=0.0, shade_side=1):
    pts = twin_tail(root, ang, length, sway, flip)
    body = tapered(pts, 6.0, 1.2, 10.0)
    pen.fill(body, HAIR)
    with pen.clip(body):
        # sombra do lado de dentro e base perto da cabeça
        sh = [(x - flip * 2.8 * shade_side, y + 0.8) for x, y in pts]
        pen.fill(tapered(sh, 5.0, 0.6, 7.5), HAIR_SH)
        pen.fill(P().circle(root[0], root[1] + 1, 5.5), HAIR_SH2, alpha=150)
        # mechas internas
        for off in (-1.8, 1.6):
            q = [(x + flip * off, y) for x, y in pts[1:-2]]
            pen.stroke(P().smooth(q, close=False), HAIR_SH2, 0.45, alpha=200)
        # brilho
        hl = [(x + flip * 2.2, y) for x, y in pts[2:6]]
        pen.fill(tapered(hl, 0.4, 0.3, 1.6), HAIR_SHINE, alpha=170)
    pen.stroke(body, HAIR_LINE, 0.8)


def bat_clip(pen, x, y, s=1.0, flip=1, ang=0.0):
    """Presilha em forma de asinha de morcego com joia vermelha."""
    with pen.at(x, y, ang, s):
        w = P().M(0, 0).C(flip * 2, -3.2, flip * 5.5, -3.8, flip * 6.8, -2.0) \
            .Q(flip * 5.4, -1.2, flip * 5.6, 0.2).Q(flip * 4.2, -0.6, flip * 3.6, 0.9).Q(flip * 2.4, 0.0, flip * 1.6, 1.4).Z()
        w2 = P().M(0, 0).C(-flip * 1.4, -2.2, -flip * 3.6, -2.6, -flip * 4.6, -1.3).Q(-flip * 3.5, -0.8, -flip * 3.4, 0.3).Q(-flip * 2.2, -0.2, -flip * 1.4, 1.0).Z()
        pen.shape(w2, CLIP_DARK, "#120a18", 0.45)
        pen.shape(w, CLIP_DARK, "#120a18", 0.45)
        pen.fill(P().circle(0, 0.2, 1.25), RIBBON)
        pen.fill(P().circle(-0.35, -0.2, 0.45), "#ffb3c0")


def draw_bow(pen, x, y, s=1.0):
    """Laço vermelho (visto nas costas, preso no cabelo)."""
    with pen.at(x, y, 0.0, s):
        for f in (-1, 1):
            loop = P().M(0, 0).C(f * 2.5, -4.2, f * 7.8, -4.6, f * 8.2, -1.0).C(f * 8.4, 2.4, f * 4.0, 2.6, 0, 0.6).Z()
            pen.fill(loop, RIBBON)
            with pen.clip(loop):
                pen.fill(P().oval(f * 4.6, 1.2, 4.0, 1.8), RIBBON_SH)
                pen.fill(P().oval(f * 3.6, -2.2, 2.4, 0.9), "#ff7a90", alpha=200)
            pen.stroke(loop, "#4a0818", 0.6)
            tail = P().M(f * 0.6, 0.8).L(f * 3.6, 7.6).L(f * 2.0, 6.6).L(f * 1.0, 8.2).L(-f * 0.4, 1.2).Z()
            pen.shape(tail, RIBBON_SH, "#4a0818", 0.5)
        knot = P().oval(0, 0.3, 1.8, 1.5)
        pen.shape(knot, RIBBON, "#4a0818", 0.55)


# ------------------------------------------------------------------ cabeça de frente (3/4)
FACE = (P().M(-15.6, -3)
        .C(-15.6, 5.5, -12.2, 11.6, -4.4, 15.0)
        .C(-1.2, 16.3, 1.4, 16.9, 3.3, 16.7)
        .C(7.6, 14.7, 12.6, 9.6, 14.7, 3.6)
        .C(15.6, 0.6, 15.8, -2.6, 15.4, -5.2)
        .C(14.0, -14.2, 6.0, -17.6, -1.0, -17.6)
        .C(-9.0, -17.6, -15.6, -12.0, -15.6, -3.0).Z())


def front_hair_path():
    """Contorno do cabelo da frente: calota + franja + mechas laterais."""
    p = P().M(-14.2, 17.0)
    p.C(-17.8, 10.0, -19.2, 1.5, -18.4, -6.0)
    p.C(-17.6, -16.5, -10.0, -22.6, 0.6, -22.6)
    p.C(10.6, -22.6, 18.4, -16.2, 18.4, -5.4)
    p.C(18.6, 2.6, 17.2, 9.0, 14.6, 13.6)
    p.C(14.2, 9.0, 13.6, 4.6, 12.4, 1.8)
    # franja (direita -> esquerda): entalhes e pontas
    edge = [(12.4, 1.8), (11.0, -3.6), (9.8, -0.2), (8.4, -4.4), (6.2, 2.6), (4.6, -2.4), (2.8, 0.2),
            (1.0, -5.0), (-1.0, 3.0), (-2.9, -3.0), (-5.4, -0.2), (-7.4, -4.8), (-9.8, 1.2), (-11.5, -2.8), (-12.6, 3.4)]
    for a, b in zip(edge, edge[1:]):
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        going_down = b[1] > a[1]
        # pontas viradas levemente para a direita (penteado)
        cx = mx + (1.0 if going_down else -0.2)
        cy = my - (0.6 if going_down else 1.2)
        p.Q(cx, cy, *b)
    # mecha lateral perto (esquerda) descendo até a ponta
    p.C(-12.8, 7.0, -13.0, 12.0, -14.2, 17.0)
    p.Z()
    return p


def skin_tones(pale):
    if not pale:
        return SKIN, SKIN_SH
    return mix(SKIN, "#d8def0", pale), mix(SKIN_SH, "#aeb6d4", pale)


def draw_head_front(pen, expr=None, sway=0.0, detail=False, pale=0.0, ear=True, tails=False, glow=False,
                    tail_sway=0.0, ahoge=0.0, part="all"):
    """Desenha a cabeça (3/4 de frente) com centro em (0, 0).

    expr: dict com eyes, brows, mouth, blush.
    part: "all", "back" (só cabelo de trás), "neck" ou "front" (rosto + cabelo da frente).
    """
    expr = expr or {}
    skin, skin_sh = skin_tones(pale)
    if part in ("all", "back"):
        _back_hair(pen)
    if part in ("all", "neck"):
        _neck(pen, skin, skin_sh)
    if part in ("all", "front"):
        _face_front(pen, expr, detail, pale, ear, tails, glow, ahoge, skin, skin_sh)


def _back_hair(pen):
    back = P().M(-17.5, -6).C(-21.5, 10, -22, 26, -18, 40).L(-12, 35).L(-7, 42).L(-1.5, 36).L(4, 42.5).L(9, 35.5).L(14, 40) \
        .C(19, 26, 20.5, 8, 18, -6).C(16, -20, -15, -21, -17.5, -6).Z()
    pen.shape(back, HAIR_SH, HAIR_LINE, 0.8)
    with pen.clip(back):
        pen.fill(P().oval(0, 22, 17, 9), HAIR_SH2, alpha=200)


def _neck(pen, skin, skin_sh):
    neck = P().M(-3.6, 11).L(4.0, 11).L(4.4, 24).L(-3.4, 24).Z()
    pen.fill(neck, skin)
    with pen.clip(neck):
        pen.fill(P().oval(1, 13.5, 6, 4.5), skin_sh)
    pen.stroke(P().M(-3.6, 12).L(-3.4, 24), SKIN_LINE, 0.6)
    pen.stroke(P().M(4.0, 13).L(4.4, 24), SKIN_LINE, 0.6)


def _face_front(pen, expr, detail, pale, ear, tails, glow, ahoge, skin, skin_sh):
    eyes = expr.get("eyes", "open")
    brows = expr.get("brows", "normal")
    mouth = expr.get("mouth", "smile")
    # orelha pontuda (lado de perto)
    if ear:
        e = P().M(-14.4, -2.5).C(-17.5, -4.0, -21.0, -7.6, -23.4, -10.6).C(-21.8, -5.0, -19.6, 0.6, -15.6, 5.4).Z()
        pen.shape(e, skin, SKIN_LINE, 0.7)
        pen.fill(P().M(-16.0, -1.5).C(-18.2, -3.2, -20.2, -5.8, -21.4, -7.8).C(-20.2, -3.8, -18.6, -0.4, -16.4, 2.8).Z(), skin_sh)

    # rosto
    pen.fill(FACE, skin)
    with pen.clip(FACE):
        # sombra da franja na testa e lado de longe do rosto
        pen.fill(P().M(-18, -8).C(-8, -1.5, 6, -3.5, 18, -6).L(18, -20).L(-18, -20).Z(), skin_sh)
        pen.fill(P().M(12.8, -6).C(14.8, 2, 12.6, 9, 6.5, 15.6).L(18, 18).L(18, -6).Z(), skin_sh, alpha=200)
        # bochechas
        if expr.get("blush", True):
            pen.fill(P().oval(-6.8, 8.6, 3.4, 1.6), BLUSH, alpha=110, blur=0.9)
            pen.fill(P().oval(8.9, 8.2, 2.3, 1.4), BLUSH, alpha=100, blur=0.8)
            if detail:
                for i in range(3):
                    x = -8.6 + i * 1.5
                    pen.stroke(P().M(x, 9.4).L(x + 0.9, 7.8), "#ff5f80", 0.35, alpha=200)
        if pale:
            pen.fill(P().oval(-6, 11, 6, 3), "#9fb0e0", alpha=int(60 * pale), blur=1.5)
        if expr.get("shadow"):  # sombra "assustadora" sobre os olhos (frenesi)
            pen.grad(P().M(-20, -20).L(20, -20).L(20, 10).L(-20, 10).Z(), (0, -14), (0, 6),
                     ["#3a0420", "#3a0420"], alphas=[200, 0])
    pen.stroke(FACE, SKIN_LINE, 0.85)

    # feições
    look = expr.get("look", (0.7, 0.0))
    draw_eye(pen, -5.8, 3.6, 8.8, 10.8, -1, eyes, look, glow, detail)
    draw_eye(pen, 7.5, 3.5, 6.3, 10.3, +1, eyes, look, glow, detail)
    # nariz
    pen.stroke(P().M(6.6, 7.6).Q(7.4, 8.4, 6.6, 8.9), SKIN_SH2, 0.55)
    draw_mouth(pen, 4.2, 11.4, mouth, 1.0, detail)

    # cabelo da frente
    hair = front_hair_path()
    pen.fill(hair, HAIR)
    with pen.clip(hair):
        # sombra do lado de longe (luz vem da esquerda-cima)
        pen.fill(P().M(9, -24).C(16, -16, 19, -6, 16, 15).L(24, 15).L(24, -24).Z(), HAIR_SH)
        # sombra perto das pontas da franja
        pen.fill(P().M(-20, -1).C(-8, -6.5, 6, -7, 20, -3).L(20, 20).L(-20, 20).Z(), HAIR_SH, alpha=230)
        # entalhes escuros entre mechas
        for x0 in (-11.5, -7.4, -2.9, 1.0, 4.6, 8.4, 11.0):
            pen.fill(tapered([(x0 + 0.6, -9.5), (x0 + 0.2, -6.5), (x0, -3.5)], 0.2, 1.1, 0.9), HAIR_SH2, alpha=210)
        # mecha lateral perto: sombra interna
        pen.fill(tapered([(-14.6, -3), (-14.0, 6), (-13.8, 14)], 2.4, 0.8, 2.8), HAIR_SH)
        # brilho (anel de anjo) em zigue-zague
        band = []
        n = 12
        for i in range(n + 1):
            t = i / n
            ang = math.pi * (1.08 + 0.84 * t)
            band.append((math.cos(ang) * 15.5 + 0.8, math.sin(ang) * 9.5 - 6.5))
        lower = []
        for i in range(n, -1, -1):
            t = i / n
            ang = math.pi * (1.08 + 0.84 * t)
            r = 13.0 if i % 2 else 11.6
            lower.append((math.cos(ang) * r * 1.12 + 0.8, math.sin(ang) * r * 0.62 - 6.0))
        shine = P().poly(band + lower)
        pen.fill(shine, HAIR_SHINE, alpha=230)
        pen.fill(P().oval(-6, -16, 6, 2.6), HAIR_SHINE, alpha=120, blur=1.0)
        # fios finos
        for (x0, y0, x1, y1) in ((-10, -16, -12.5, -3), (-4, -19, -5.5, -5), (3, -19, 4.5, -5), (9, -17, 10.8, -4)):
            pen.stroke(P().M(x0, y0).Q((x0 + x1) / 2 - 1, (y0 + y1) / 2, x1, y1), HAIR_SH2, 0.4, alpha=160)
    pen.stroke(hair, HAIR_LINE, 0.95)

    if expr.get("sweat"):
        with pen.at(15.6, -9.0, 0.25, 1.15):
            d = P().M(0, -4.2).C(1.6, -1.4, 2.6, 0.4, 1.8, 1.8).C(0.9, 3.0, -1.4, 2.8, -1.7, 1.0).C(-1.9, -0.6, -1.0, -2.2, 0, -4.2).Z()
            pen.shape(d, "#c8ecff", "#3d78b0", 0.5)
            pen.fill(P().oval(-0.4, 0.4, 0.5, 0.9), WHITE)

    # sobrancelhas por cima da franja (convenção anime)
    by = {"normal": 0.0, "up": -0.8, "angry": 0.6, "worried": 0.2, "frenzy": 0.9, "dead": 0.0, "hurt": 0.4}.get(brows, 0.0)
    if brows in ("angry", "frenzy"):
        draw_brow(pen, -9.6, -6.4 + by, -2.6, -4.6 + by, 0.3)
        draw_brow(pen, 4.8, -4.9 + by, 10.4, -6.6 + by, 0.3)
    elif brows in ("worried", "hurt"):
        draw_brow(pen, -9.6, -4.9 + by, -2.6, -7.0 + by, 0.5)
        draw_brow(pen, 4.8, -7.2 + by, 10.4, -5.2 + by, 0.5)
    elif brows != "none":
        draw_brow(pen, -9.6, -6.1 + by, -2.8, -6.6 + by, 0.9)
        draw_brow(pen, 4.9, -6.8 + by, 10.4, -6.2 + by, 0.9)

    # ahoge (mecha rebelde)
    a = [(0.6, -21.8), (1.8 + ahoge * 0.4, -25.2), (4.6 + ahoge, -27.6), (7.6 + ahoge, -27.0), (8.4 + ahoge, -25.2)]
    ah = tapered(a, 3.0, 0.5, 2.0)
    pen.shape(ah, HAIR, HAIR_LINE, 0.7)

    # presilhas de asinha nas raízes das mariachiquinhas
    if tails:
        bat_clip(pen, -15.8, -11.2, 1.0, -1, -0.35)
        bat_clip(pen, 16.4, -12.0, 0.8, 1, 0.3)


def long_lock(pen, root, length, flip, sway=0.0):
    """Mecha comprida e solta caindo do lado da cabeça (cabelo preto da referência)."""
    pts = bezier_pts(root, (root[0] + flip * 5.0, root[1] + length * 0.3), (root[0] + flip * 6.0 + sway * 4, root[1] + length * 0.7),
                     (root[0] + flip * 3.0 + sway * 8, root[1] + length), 12)
    body = tapered(pts, 9.0, 1.0, 11.0)
    pen.fill(body, HAIR)
    with pen.clip(body):
        pen.fill(tapered([(x - flip * 2.6, y) for x, y in pts], 6.0, 0.6, 7.0), HAIR_SH)
        for off in (-2.0, 1.8):
            pen.stroke(P().smooth([(x + flip * off, y) for x, y in pts[1:-2]], close=False), HAIR_SH2, 0.5, alpha=220)
        pen.fill(tapered([(x + flip * 2.0, y) for x, y in pts[2:6]], 0.4, 0.3, 1.5), HAIR_SHINE, alpha=200)
    pen.stroke(body, HAIR_LINE, 0.8)


def draw_tails_front(pen, sway=0.0, length=34.0):
    """Cabelo comprido solto dos dois lados (desenhado atrás do corpo)."""
    long_lock(pen, (14.0, -6.0), length * 1.25, +1, sway * 0.8)
    long_lock(pen, (-14.0, -5.0), length * 1.32, -1, sway)


# ------------------------------------------------------------------ cabeça de costas (3/4)
def draw_head_back(pen, sway=0.0, ear=True, ahoge=0.0, part="all", pale=0.0):
    """Nuca: massa de cabelo vista de trás (olhando para cima-direita)."""
    skin, skin_sh = skin_tones(pale)
    if part in ("all", "neck"):
        neck = P().M(-4.2, 11).L(3.6, 11).L(4.0, 24).L(-3.8, 24).Z()
        pen.shape(neck, skin_sh, SKIN_LINE, 0.6)
    if part == "neck":
        return
    # orelha aparecendo à direita
    if ear:
        e = P().M(13.8, -3.5).C(17.0, -5.0, 20.6, -8.6, 22.8, -11.2).C(21.4, -5.6, 19.0, -0.4, 14.8, 4.2).Z()
        pen.shape(e, skin, SKIN_LINE, 0.7)
    hair = P().M(-17.8, -4).C(-18.6, -17, -8, -22.8, 1, -22.8).C(11, -22.8, 18.6, -15.5, 18.2, -4) \
        .C(18.4, 8, 16.5, 18.5, 13, 26.5).L(9.4, 22.6).L(5.6, 28).L(1.8, 23.2).L(-2.2, 28.4).L(-5.8, 23.2).L(-9.6, 27.4).L(-12.6, 22.4) \
        .C(-16.6, 16.5, -17.8, 6.0, -17.8, -4).Z()
    pen.fill(hair, HAIR)
    with pen.clip(hair):
        pen.fill(P().M(-20, 2).C(-6, 8, 8, 6, 20, -1).L(20, 30).L(-20, 30).Z(), HAIR_SH)
        pen.fill(P().M(8, -24).C(17, -14, 19, -2, 14, 22).L(24, 22).L(24, -24).Z(), HAIR_SH, alpha=180)
        # mechas
        for (x0, y0, x1, y1) in ((-12, -10, -12.5, 20), (-6, -14, -6.5, 24), (0, -16, 0.5, 23), (6, -14, 7, 24), (11.5, -9, 11.5, 20)):
            pen.stroke(P().M(x0, y0).Q((x0 + x1) / 2 + 1.2, (y0 + y1) / 2, x1, y1), HAIR_SH2, 0.5, alpha=200)
        band = []
        for i in range(13):
            t = i / 12
            ang = math.pi * (1.1 + 0.8 * t)
            band.append((math.cos(ang) * 15.5, math.sin(ang) * 9 - 5))
        for i in range(12, -1, -1):
            t = i / 12
            ang = math.pi * (1.1 + 0.8 * t)
            r = 13.2 if i % 2 else 11.8
            band.append((math.cos(ang) * r * 1.1, math.sin(ang) * r * 0.6 - 4.6))
        pen.fill(P().poly(band), HAIR_SHINE, alpha=220)
    pen.stroke(hair, HAIR_LINE, 0.95)
    a = [(-0.4, -21.8), (0.8 + ahoge * 0.4, -25.2), (3.6 + ahoge, -27.6), (6.6 + ahoge, -27.0), (7.4 + ahoge, -25.2)]
    pen.shape(tapered(a, 3.0, 0.5, 2.0), HAIR, HAIR_LINE, 0.7)
    draw_bow(pen, 0.6, 8.5, 1.0)
    bat_clip(pen, -15.6, -10.0, 0.9, -1, -0.3)
    bat_clip(pen, 15.8, -10.0, 1.0, 1, 0.3)


def draw_tails_back(pen, sway=0.0, length=34.0):
    long_lock(pen, (-14.0, -5.0), length * 1.3, -1, sway)
    long_lock(pen, (14.0, -5.0), length * 1.3, +1, sway * 0.9)


# ------------------------------------------------------------------ expressões prontas
EXPR = {
    "normal": {"eyes": "open", "brows": "normal", "mouth": "smile"},
    "smug": {"eyes": "half", "brows": "normal", "mouth": "smirk"},
    "blink": {"eyes": "blink", "brows": "normal", "mouth": "smile"},
    "frenzy": {"eyes": "frenzy", "brows": "frenzy", "mouth": "grin"},
    "low": {"eyes": "tired", "brows": "worried", "mouth": "wobble", "sweat": True},
    "low_blink": {"eyes": "blink", "brows": "worried", "mouth": "wobble", "sweat": True},
    "hurt": {"eyes": "squeeze", "brows": "hurt", "mouth": "shout"},
    "dead": {"eyes": "x", "brows": "none", "mouth": "dead", "blush": False},
    "spit": {"eyes": "closed", "brows": "angry", "mouth": "spit"},
    "puff": {"eyes": "squeeze", "brows": "angry", "mouth": "puff"},
    "chomp": {"eyes": "wide", "brows": "up", "mouth": "chomp"},
    "attack": {"eyes": "angry", "brows": "angry", "mouth": "shout"},
    "focus": {"eyes": "angry", "brows": "angry", "mouth": "flat"},
    # retrato do HUD
    "p_normal": {"eyes": "open", "brows": "normal", "mouth": "smile"},
    "p_normal_blink": {"eyes": "blink", "brows": "normal", "mouth": "smile"},
    "p_normal_spit": {"eyes": "closed", "brows": "angry", "mouth": "spit"},
    "p_frenzy": {"eyes": "frenzy", "brows": "frenzy", "mouth": "grin", "shadow": True},
    "p_frenzy_blink": {"eyes": "frenzy", "brows": "frenzy", "mouth": "grin", "shadow": True},
    "p_frenzy_spit": {"eyes": "frenzy", "brows": "frenzy", "mouth": "spit", "shadow": True},
    "p_low": {"eyes": "tired", "brows": "worried", "mouth": "wobble", "sweat": True},
    "p_low_blink": {"eyes": "blink", "brows": "worried", "mouth": "wobble", "sweat": True},
    "p_low_spit": {"eyes": "squeeze", "brows": "worried", "mouth": "spit", "sweat": True},
    "p_hurt": {"eyes": "squeeze", "brows": "hurt", "mouth": "shout"},
    "p_dead": {"eyes": "x", "brows": "none", "mouth": "dead", "blush": False},
}
