"""Efeitos de golpe (cortes, impactos, faíscas, rachaduras) e discos do braço do Gigante.

Os efeitos de golpe apontam para +x, com o pivô (quem ataca ou o ponto do impacto) no
centro da célula; o jogo gira cada quadro para a direção do golpe. Cada efeito tem
alguns quadros: o golpe acontecendo e depois sumindo.
"""
import math
import random

import skia

from . import enemies as en
from . import props as pr
from .kit import P, lerp, rgb

DEG = math.pi / 180


# ------------------------------------------------------------------ helpers
def crescent(c, r, a_tail, a_head, w, inward=True, p=1.5, n=40, full=0.6):
    """Lua crescente sobre um arco de raio r: nasce fina na cauda, engrossa perto da
    cabeça e termina em ponta (corte de anime). full < 1 deixa o corpo mais cheio."""
    outer, inner = [], []
    for i in range(n + 1):
        t = i / n
        a = lerp(a_tail, a_head, t)
        th = w * math.sin(math.pi * min(1.0, t ** p)) ** full
        ca, sa = math.cos(a), math.sin(a)
        rr = r - th if inward else r + th
        outer.append((c[0] + ca * r, c[1] + sa * r))
        inner.append((c[0] + ca * rr, c[1] + sa * rr))
    return P().poly(outer + inner[::-1])


def sweep_fill(pen, path, c, a_tail, a_head, colors, alphas, stops):
    """Preenche com gradiente angular: cor da cauda (a_tail) até a da cabeça (a_head)."""
    if a_head < a_tail:  # o gradiente angular do skia só gira no sentido horário
        a_tail, a_head = a_head, a_tail
        colors, alphas = colors[::-1], alphas[::-1]
        stops = [1.0 - s for s in stops[::-1]]
    frac = (a_head - a_tail) / math.tau
    pos = [s * frac for s in stops]
    cols = [rgb(col, a) for col, a in zip(colors, alphas)]
    # depois da cabeça mantém a cor da cabeça; antes da cauda, a da cauda
    pos += [frac + (1 - frac) * 0.5, 1.0]
    cols += [cols[-1], cols[0]]
    m = skia.Matrix()
    m.setRotate(math.degrees(a_tail), c[0], c[1])
    paint = skia.Paint(AntiAlias=True)
    paint.setShader(skia.GradientShader.MakeSweep(c[0], c[1], cols, pos, skia.TileMode.kClamp, 0, 360, 0, m))
    pen.c.drawPath(path.path if isinstance(path, P) else path, paint)


def star(c, r_out, r_in, n, rot=0.0, jitter=0.0, seed=0):
    rnd = random.Random(seed)
    pts = []
    for i in range(n * 2):
        a = rot + math.pi * i / n
        r = r_out if i % 2 == 0 else r_in
        if jitter and i % 2 == 0:
            r *= 1 + rnd.uniform(-jitter, jitter)
        pts.append((c[0] + math.cos(a) * r, c[1] + math.sin(a) * r))
    return P().poly(pts)


def streak(a, b, w):
    """Risco de velocidade: losango comprido de a até b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / d * w / 2, dx / d * w / 2
    m = (a[0] + dx * 0.35, a[1] + dy * 0.35)
    return P().poly([a, (m[0] + nx, m[1] + ny), b, (m[0] - nx, m[1] - ny)])


def slash(pen, c, r, a0, a1, head_t, tail_t, w, glow, body, core="#ffffff", alpha=1.0, glow_blur=4.0, core_k=0.42):
    """Um risco de corte entre os ângulos a0 (início) e a1 (fim) do golpe."""
    a_head = lerp(a0, a1, head_t)
    a_tail = lerp(a0, a1, tail_t)
    if abs(a_head - a_tail) < 1e-3:
        return
    shape = crescent(c, r, a_tail, a_head, w)
    glow_shape = crescent(c, r + w * 0.18, a_tail, a_head, w * 1.35)
    sweep_fill(pen, glow_shape, c, a_tail, a_head, [glow, glow, glow], [0, int(200 * alpha), int(230 * alpha)], [0.0, 0.3, 1.0])
    # o brilho difuso vem por baixo do corte (blur no próprio caminho)
    pen.fill(glow_shape, glow, alpha=int(120 * alpha), blur=glow_blur)
    sweep_fill(pen, shape, c, a_tail, a_head, [body, body, body], [0, int(235 * alpha), int(255 * alpha)], [0.0, 0.22, 1.0])
    inner = crescent(c, r - w * 0.1, a_tail + (a_head - a_tail) * 0.15, a_head, w * core_k)
    sweep_fill(pen, inner, c, a_tail, a_head, [core, core], [0, int(255 * alpha)], [0.15, 0.8])


# ------------------------------------------------------------------ garras (braço da vampira)
CLAW_FRAMES = [  # (cabeça, cauda, alfa, largura)
    (0.42, 0.00, 1.0, 0.85),
    (0.82, 0.08, 1.0, 1.0),
    (1.00, 0.38, 1.0, 1.0),
    (1.00, 0.70, 0.75, 0.8),
    (1.00, 0.90, 0.40, 0.6),
]


def draw_claw(k):
    """Três riscos de garra varrendo o arco do golpe (130°), em vermelho-sangue."""
    head, tail, alpha, wk = CLAW_FRAMES[k]

    def draw(pen):
        a0, a1 = -70 * DEG, 70 * DEG
        for i, (r, w) in enumerate(((72, 13), (59, 12), (46, 11))):
            lag = i * 0.06
            ht = max(0.0, min(1.0, head - lag))
            tt = max(0.0, min(ht, tail - lag * 0.5))
            slash(pen, (0, 0), r, a0 + i * 4 * DEG, a1 - i * 3 * DEG, ht, tt, w * wk,
                  "#ff1f4f", "#ff7d9c", "#fff4f7", alpha, glow_blur=3.6)
        if k in (1, 2):  # brilhos na ponta das garras
            for i, r in enumerate((70, 58, 46)):
                a = lerp(a0, a1, min(1.0, head - i * 0.06))
                p = (math.cos(a) * (r - 4), math.sin(a) * (r - 4))
                pen.fill(star(p, 6.5 - i, 1.4, 4, rot=0.3 * k), "#ffffff", alpha=230)
    return draw


# ------------------------------------------------------------------ chute
KICK_FRAMES = [(0.45, 0.0, 1.0), (0.9, 0.1, 1.0), (1.0, 0.45, 1.0), (1.0, 0.75, 0.7), (1.0, 0.93, 0.35)]


def draw_kick(k):
    """Arco grosso e dourado do chute + estrela de impacto na ponta."""
    head, tail, alpha = KICK_FRAMES[k]

    def draw(pen):
        a0, a1 = -46 * DEG, 46 * DEG
        r = 92
        slash(pen, (0, 0), r, a0, a1, head, tail, 30 * (1.0 if k < 3 else 0.8), "#ff9a1f", "#ffe39a", "#fffbe8", alpha,
              glow_blur=5.0, core_k=0.5)
        # linhas de velocidade acompanhando o arco
        for i, dr in enumerate((-30, -16, 8)):
            if k > 3:
                break
            a = lerp(a0, a1, max(0.0, head - 0.18 - i * 0.07))
            b = lerp(a0, a1, max(0.0, head - 0.42 - i * 0.07))
            rr = r + dr
            pen.fill(streak((math.cos(a) * rr, math.sin(a) * rr), (math.cos(b) * rr, math.sin(b) * rr), 3.0), "#fff3c4",
                     alpha=int(200 * alpha))
        if k in (1, 2, 3):  # pow!
            a = lerp(a0, a1, head)
            c = (math.cos(a) * (r - 8), math.sin(a) * (r - 8))
            s = (14, 22, 16)[k - 1]
            pen.fill(star(c, s * 1.25, s * 0.45, 8, rot=0.2 + k * 0.4), "#ff8a1c", alpha=int(170 * alpha), blur=3.0)
            pen.fill(star(c, s, s * 0.38, 8, rot=0.2 + k * 0.4, jitter=0.25, seed=k), "#ffe082", alpha=int(255 * alpha))
            pen.fill(star(c, s * 0.55, s * 0.24, 8, rot=0.2 + k * 0.4), "#ffffff", alpha=int(255 * alpha))
    return draw


# ------------------------------------------------------------------ soco com dente (impacto em área)
PUNCH_R = [26, 60, 80, 90, 94]
PUNCH_A = [1.0, 1.0, 0.9, 0.55, 0.25]


def draw_punch(k):
    """Explosão em estrela no ponto do soco, com anel de choque e dentes voando."""
    R, alpha = PUNCH_R[k], PUNCH_A[k]

    def draw(pen):
        c = (0, 0)
        rot = 0.15 + k * 0.08
        pen.fill(star(c, R * 1.08, R * 0.5, 12, rot, 0.3, 7), "#ff4a26", alpha=int(150 * alpha), blur=7.0)
        pen.fill(star(c, R, R * 0.44, 12, rot, 0.3, 7), "#ff9a3c", alpha=int(240 * alpha))
        pen.fill(star(c, R * 0.72, R * 0.34, 12, rot + 0.13, 0.25, 9), "#ffd986", alpha=int(255 * alpha))
        pen.fill(P().circle(0, 0, R * 0.3), "#fffbea", alpha=int(255 * alpha))
        if k >= 2:  # anel de choque
            rr = R * (1.02 + 0.1 * (k - 2))
            pen.stroke(P().circle(0, 0, rr), "#fff0c4", (5.0, 3.0, 2.0)[k - 2], alpha=int(230 * alpha))
        # dentes lascados voando para fora
        dist = [8, 46, 76, 96, 108][k]
        for i in range(8):
            a = i * math.tau / 8 + 0.2
            p = (math.cos(a) * dist, math.sin(a) * dist)
            with pen.layer(int(255 * min(1.0, alpha * 1.4))):
                with pen.at(p[0], p[1], a + k * 0.9):
                    pr.draw_tooth(pen, 0.85)
    return draw


# ------------------------------------------------------------------ espada do caçador
SWORD_FRAMES = [(0.5, 0.0, 1.0), (1.0, 0.25, 1.0), (1.0, 0.65, 0.7), (1.0, 0.9, 0.35)]


def draw_sword(k):
    head, tail, alpha = SWORD_FRAMES[k]

    def draw(pen):
        slash(pen, (0, 0), 68, -68 * DEG, 68 * DEG, head, tail, 17, "#7fb0ff", "#dceaff", "#ffffff", alpha, glow_blur=3.5,
              core_k=0.36)
        slash(pen, (0, 0), 54, -60 * DEG, 60 * DEG, max(0.0, head - 0.1), max(0.0, tail - 0.05), 5, "#7fb0ff", "#c8dcff",
              "#ffffff", alpha * 0.8, glow_blur=2.0)
    return draw


# ------------------------------------------------------------------ mordida do morcego
BITE_GAP = [15, 8, 1.5, 1.5]
BITE_A = [1.0, 1.0, 1.0, 0.45]


def _jaw(pen, gap, upper, alpha):
    s = -1 if upper else 1
    y = s * gap
    band = P().M(-22, y + s * 2).C(-14, y + s * 15, 14, y + s * 15, 22, y + s * 2).C(14, y + s * 9, -14, y + s * 9, -22, y + s * 2).Z()
    pen.fill(band, "#ff1f4f", alpha=int(150 * alpha), blur=2.5)
    pen.shape(band, "#ffffff", "#2a0a1c", 1.0, alpha=int(255 * alpha))
    for x, h in ((-11, 7.5), (0, 5.0), (11, 7.5)):  # presas apontando para a outra mandíbula
        yb = y + s * (5.0 if x else 7.0)
        fang = P().poly([(x - 3.2, yb + s * 1.0), (x + 3.2, yb + s * 1.0), (x, yb - s * h)])
        pen.shape(fang, "#ffffff", "#2a0a1c", 0.8, alpha=int(255 * alpha))


def draw_bite(k):
    def draw(pen):
        gap, alpha = BITE_GAP[k], BITE_A[k]
        if k == 2:
            pen.fill(star((0, 0), 26, 8, 6, 0.3), "#ff3355", alpha=150, blur=3.0)
            pen.fill(star((0, 0), 18, 6, 6, 0.3), "#ffd0da", alpha=230)
        _jaw(pen, gap, True, alpha)
        _jaw(pen, gap, False, alpha)
    return draw


# ------------------------------------------------------------------ faísca de acerto
SPARK_R = [11, 22, 17, 9]
SPARK_A = [1.0, 1.0, 0.8, 0.45]


def draw_spark(k, color="#ff2a4a"):
    def draw(pen):
        R, alpha = SPARK_R[k], SPARK_A[k]
        pen.fill(P().circle(0, 0, R * 0.9), color, alpha=int(120 * alpha), blur=5.0)
        pen.fill(star((0, 0), R * 1.25, R * 0.16, 4, 0.0), color, alpha=int(230 * alpha))
        pen.fill(star((0, 0), R * 0.7, R * 0.14, 4, math.pi / 4), color, alpha=int(230 * alpha))
        pen.fill(star((0, 0), R * 0.95, R * 0.1, 4, 0.0), "#ffffff", alpha=int(255 * alpha))
        pen.fill(P().circle(0, 0, R * 0.2), "#ffffff", alpha=int(255 * alpha))
        if k >= 1:  # gotinhas voando
            for i, a in enumerate((0.6, 2.3, 4.1, 5.4)):
                d = R * (1.1 + 0.35 * k)
                pen.fill(P().circle(math.cos(a) * d, math.sin(a) * d, max(1.0, 2.6 - k * 0.5)), color, alpha=int(255 * alpha))
    return draw


# ------------------------------------------------------------------ rachadura no chão (Gigante)
def draw_crack(seed=5):
    def draw(pen):
        rnd = random.Random(seed)
        # cratera
        pen.fill(P().oval(0, 0, 30, 24), "#000000", alpha=90, blur=6.0)
        pen.fill(P().oval(0, 1, 22, 17), "#120c18", alpha=230)
        pen.stroke(P().M(-20, -6).Q(0, -19, 20, -6), "#6a5d80", 1.6, alpha=170)
        # rachaduras irregulares saindo da cratera
        for i in range(10):
            a = i * math.tau / 10 + rnd.uniform(-0.2, 0.2)
            r = 18
            pts = [(math.cos(a) * r, math.sin(a) * r)]
            ln = rnd.uniform(70, 110)
            while r < ln:
                r += rnd.uniform(10, 18)
                a += rnd.uniform(-0.28, 0.28)
                pts.append((math.cos(a) * r, math.sin(a) * r))
            w0 = 5.0
            for j, (p, q) in enumerate(zip(pts, pts[1:])):
                w = w0 * (1 - j / len(pts))
                pen.stroke(P().M(*p).L(*q), "#0c0810", max(0.8, w), alpha=235)
                pen.stroke(P().M(p[0] + 1.2, p[1] + 1.2).L(q[0] + 1.2, q[1] + 1.2), "#5d5070", max(0.5, w * 0.35), alpha=150)
            if len(pts) > 3:  # galhinho
                p = pts[2]
                b = (p[0] + math.cos(a + 1.0) * 20, p[1] + math.sin(a + 1.0) * 20)
                pen.stroke(P().M(*p).L(*b), "#0c0810", 1.6, alpha=220)
        # pedrinhas
        for _ in range(14):
            a = rnd.uniform(0, math.tau)
            r = rnd.uniform(26, 80)
            c = (math.cos(a) * r, math.sin(a) * r)
            s = rnd.uniform(2.0, 4.5)
            pts = [(c[0] + math.cos(t) * s * rnd.uniform(0.7, 1.2), c[1] + math.sin(t) * s * rnd.uniform(0.7, 1.2))
                   for t in (0, 1.6, 3.1, 4.6)]
            pen.shape(P().poly(pts), "#4b4258", "#140e1a", 0.8)
    return draw


# ------------------------------------------------------------------ anel de choque (pintado na hora pelo jogo)
SHOCK_SIZE = 256


def draw_shock(pen):
    """Anel branco suave (o jogo multiplica pela cor e escala para o raio do efeito)."""
    c = SHOCK_SIZE / 2
    r = c - 10
    paint = skia.Paint(AntiAlias=True)
    cols = [rgb("#ffffff", a) for a in (0, 0, 60, 255, 120, 0)]
    pos = [0.0, (r - 22) / c, (r - 12) / c, (r - 3) / c, (r + 2) / c, (r + 6) / c]
    paint.setShader(skia.GradientShader.MakeRadial(skia.Point(c, c), c, cols, pos))
    pen.c.drawRect(skia.Rect.MakeXYWH(0, 0, SHOCK_SIZE, SHOCK_SIZE), paint)


# ------------------------------------------------------------------ discos do braço do Gigante
# Discos brancos lisos (antisserrilhados). O jogo pinta cada um com uma cor chapada e
# carimba uma fileira deles ao longo do braço em 4 passadas (contorno, sombra, pele
# puxada para a luz, brilho): a união de cada passada é uma faixa lisa, e o sombreado
# do "tubo" aparece pela sobreposição das faixas.
DISC_RADII = list(range(2, 19))  # raios (px) disponíveis
DISC_CELL = 40


def draw_disc(r):
    def draw(pen):
        pen.fill(P().circle(0, 0, r), "#ffffff")
    return draw

BOSS_ARM_COLORS = {  # (contorno, sombra, pele, brilho)
    "skin": (en.B_SKIN_LINE, en.B_SKIN_SH, en.B_SKIN, en.B_SKIN_HL),
    "rage": (en.B_SKIN_LINE, "#a8503f", en.B_RAGE, "#f2a08a"),
}
