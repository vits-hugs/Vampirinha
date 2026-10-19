"""Kit de desenho vetorial (skia) usado para gerar os sprites do jogo.

Tudo é desenhado em "unidades" que valem 1 px no tamanho final do sprite; o
gerador pode renderizar em escala maior (pré-visualização) só mudando a escala.
"""
import math
from contextlib import contextmanager

import numpy as np
import skia


# ------------------------------------------------------------------ cores
def rgb(h, a=255):
    """'#rrggbb' -> skia.Color4f (com alfa 0..255)."""
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return skia.Color(r, g, b, a)


def mix(c1, c2, t):
    """Mistura duas cores hex ('#rrggbb') -> hex."""
    a = [int(c1.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(c2.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def lerp(a, b, t):
    return a + (b - a) * t


def lerp2(p, q, t):
    return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)


def rot(p, ang, about=(0.0, 0.0)):
    c, s = math.cos(ang), math.sin(ang)
    x, y = p[0] - about[0], p[1] - about[1]
    return (about[0] + x * c - y * s, about[1] + x * s + y * c)


def add(p, q, k=1.0):
    return (p[0] + q[0] * k, p[1] + q[1] * k)


def polar(ang, r):
    return (math.cos(ang) * r, math.sin(ang) * r)


# ------------------------------------------------------------------ caminhos
class P:
    """Construtor de caminhos encadeável: P().M(x, y).C(...).Z()"""

    def __init__(self):
        self.p = skia.Path()

    def M(self, x, y=None):
        if y is None:
            x, y = x
        self.p.moveTo(x, y)
        return self

    def L(self, x, y=None):
        if y is None:
            x, y = x
        self.p.lineTo(x, y)
        return self

    def Q(self, x1, y1, x, y):
        self.p.quadTo(x1, y1, x, y)
        return self

    def C(self, x1, y1, x2, y2, x, y):
        self.p.cubicTo(x1, y1, x2, y2, x, y)
        return self

    def Z(self):
        self.p.close()
        return self

    def circle(self, x, y, r):
        self.p.addCircle(x, y, r)
        return self

    def oval(self, x, y, rx, ry):
        self.p.addOval(skia.Rect.MakeLTRB(x - rx, y - ry, x + rx, y + ry))
        return self

    def poly(self, pts, close=True):
        self.p.moveTo(*pts[0])
        for q in pts[1:]:
            self.p.lineTo(*q)
        if close:
            self.p.close()
        return self

    def smooth(self, pts, close=True, k=0.5):
        """Curva suave (Catmull-Rom) passando pelos pontos."""
        n = len(pts)
        if n < 3:
            return self.poly(pts, close)
        self.p.moveTo(*pts[0])
        rng = range(n) if close else range(n - 1)
        for i in rng:
            p0 = pts[(i - 1) % n] if (close or i > 0) else pts[i]
            p1 = pts[i]
            p2 = pts[(i + 1) % n]
            p3 = pts[(i + 2) % n] if (close or i + 2 < n) else p2
            c1 = (p1[0] + (p2[0] - p0[0]) * k / 3, p1[1] + (p2[1] - p0[1]) * k / 3)
            c2 = (p2[0] - (p3[0] - p1[0]) * k / 3, p2[1] - (p3[1] - p1[1]) * k / 3)
            self.p.cubicTo(*c1, *c2, *p2)
        if close:
            self.p.close()
        return self

    @property
    def path(self):
        return self.p


def union(*paths):
    out = paths[0].path if isinstance(paths[0], P) else paths[0]
    for q in paths[1:]:
        q = q.path if isinstance(q, P) else q
        out = skia.Op(out, q, skia.PathOp.kUnion_PathOp)
    return out


def subtract(a, b):
    a = a.path if isinstance(a, P) else a
    b = b.path if isinstance(b, P) else b
    return skia.Op(a, b, skia.PathOp.kDifference_PathOp)


def intersect(a, b):
    a = a.path if isinstance(a, P) else a
    b = b.path if isinstance(b, P) else b
    return skia.Op(a, b, skia.PathOp.kIntersect_PathOp)


def _path(p):
    return p.path if isinstance(p, P) else p


def tapered(pts, w0, w1, wmid=None):
    """Traço afilado (pincel) ao longo de pontos: devolve um caminho preenchível."""
    n = len(pts)
    if wmid is None:
        wmid = max(w0, w1)
    left, right = [], []
    for i, p in enumerate(pts):
        a = pts[max(0, i - 1)]
        b = pts[min(n - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        d = math.hypot(dx, dy) or 1
        nx, ny = -dy / d, dx / d
        t = i / (n - 1)
        w = (lerp(w0, wmid, t * 2) if t < 0.5 else lerp(wmid, w1, (t - 0.5) * 2)) / 2
        left.append((p[0] + nx * w, p[1] + ny * w))
        right.append((p[0] - nx * w, p[1] - ny * w))
    return P().smooth(left + right[::-1], close=True, k=0.35)


def bezier_pts(p0, p1, p2, p3, n=12):
    out = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        out.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return out


# ------------------------------------------------------------------ pintura
class Pen:
    """Envolve um skia.Canvas com atalhos de preenchimento, traço e sombreado."""

    def __init__(self, canvas, line_scale=1.0):
        self.c = canvas
        self.ls = line_scale  # multiplica espessuras de linha (detalhe no retrato)

    def fill(self, p, color, alpha=255, blur=0.0, blend=None):
        paint = skia.Paint(AntiAlias=True, Color=rgb(color, alpha) if isinstance(color, str) else color)
        if blur:
            paint.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
        if blend is not None:
            paint.setBlendMode(blend)
        self.c.drawPath(_path(p), paint)

    def grad(self, p, p0, p1, colors, pos=None, alpha=255, alphas=None):
        paint = skia.Paint(AntiAlias=True)
        if alphas is None:
            alphas = [alpha] * len(colors)
        cols = [rgb(c, a) for c, a in zip(colors, alphas)]
        paint.setShader(skia.GradientShader.MakeLinear([skia.Point(*p0), skia.Point(*p1)], cols, pos))
        self.c.drawPath(_path(p), paint)

    def radial(self, p, center, radius, colors, pos=None, alphas=None):
        paint = skia.Paint(AntiAlias=True)
        if alphas is None:
            alphas = [255] * len(colors)
        cols = [rgb(c, a) for c, a in zip(colors, alphas)]
        paint.setShader(skia.GradientShader.MakeRadial(skia.Point(*center), radius, cols, pos))
        self.c.drawPath(_path(p), paint)

    def stroke(self, p, color, w=1.0, alpha=255, cap="round"):
        paint = skia.Paint(AntiAlias=True, Color=rgb(color, alpha), Style=skia.Paint.kStroke_Style,
                           StrokeWidth=w * self.ls, StrokeJoin=skia.Paint.kRound_Join,
                           StrokeCap=skia.Paint.kRound_Cap if cap == "round" else skia.Paint.kButt_Cap)
        self.c.drawPath(_path(p), paint)

    def shape(self, p, fill, line, w=1.2, alpha=255):
        """Preenche e contorna (estilo anime: linha colorida escura)."""
        self.fill(p, fill, alpha)
        if line:
            self.stroke(p, line, w)

    @contextmanager
    def clip(self, p):
        self.c.save()
        self.c.clipPath(_path(p), skia.ClipOp.kIntersect, True)
        try:
            yield
        finally:
            self.c.restore()

    @contextmanager
    def at(self, x=0.0, y=0.0, ang=0.0, sx=1.0, sy=None):
        """Transforma o sistema de coordenadas (ângulo em radianos)."""
        self.c.save()
        self.c.translate(x, y)
        if ang:
            self.c.rotate(math.degrees(ang))
        if sx != 1.0 or (sy is not None and sy != 1.0):
            self.c.scale(sx, sx if sy is None else sy)
        try:
            yield
        finally:
            self.c.restore()

    @contextmanager
    def layer(self, alpha=255):
        paint = skia.Paint(Alphaf=alpha / 255.0)
        self.c.saveLayer(None, paint)
        try:
            yield
        finally:
            self.c.restore()


# ------------------------------------------------------------------ superfícies
def new_surface(w, h):
    s = skia.Surface(int(w), int(h))
    s.getCanvas().clear(skia.ColorTRANSPARENT)
    return s


def to_rgba(surface):
    """Snapshot -> np.uint8 RGBA (alfa não pré-multiplicado)."""
    img = surface.makeImageSnapshot()
    info = skia.ImageInfo.Make(img.width(), img.height(), skia.kRGBA_8888_ColorType, skia.kUnpremul_AlphaType)
    arr = np.zeros((img.height(), img.width(), 4), np.uint8)
    img.readPixels(info, arr, img.width() * 4, 0, 0)
    return arr


def outline_rgba(arr, color="#1a0d1c", radius=1.0, alpha=255):
    """Contorno externo de 'adesivo' em volta da silhueta (dilata o alfa)."""
    h, w = arr.shape[:2]
    a = arr[:, :, 3].astype(np.float32) / 255.0
    out = np.zeros_like(a)
    r = int(math.ceil(radius))
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            d = math.hypot(dx, dy)
            if d > radius + 0.5:
                continue
            k = 1.0 if d <= radius - 0.5 else (radius + 0.5 - d)
            sh = np.zeros_like(a)
            ys = slice(max(0, dy), h + min(0, dy))
            yd = slice(max(0, -dy), h + min(0, -dy))
            xs = slice(max(0, dx), w + min(0, dx))
            xd = slice(max(0, -dx), w + min(0, -dx))
            sh[ys, xs] = a[yd, xd]
            out = np.maximum(out, sh * k)
    col = [int(color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    base = np.zeros_like(arr, dtype=np.float32)
    base[:, :, 0], base[:, :, 1], base[:, :, 2] = col
    base[:, :, 3] = out * (alpha / 255.0)
    # composição "por cima": sprite sobre o contorno
    fa = a[..., None]
    ba = base[:, :, 3:4]
    oa = fa + ba * (1 - fa)
    rgbv = (arr[:, :, :3].astype(np.float32) * fa + base[:, :, :3] * ba * (1 - fa)) / np.maximum(oa, 1e-6)
    res = np.zeros_like(arr)
    res[:, :, :3] = np.clip(rgbv, 0, 255).astype(np.uint8)
    res[:, :, 3] = np.clip(oa[..., 0] * 255, 0, 255).astype(np.uint8)
    return res


def save_png(arr, path):
    from PIL import Image
    Image.fromarray(arr, "RGBA").save(path, optimize=True)


def render(w, h, draw, scale=1.0, origin=(0, 0), outline=None):
    """Renderiza draw(pen) numa superfície w x h (px finais) e devolve RGBA.

    origin: onde fica o (0, 0) do desenho (em px finais). outline: (cor, raio) do
    contorno externo opcional, em px finais.
    """
    s = new_surface(w * scale, h * scale)
    c = s.getCanvas()
    c.scale(scale, scale)
    c.translate(*origin)
    draw(Pen(c))
    arr = to_rgba(s)
    if outline:
        arr = outline_rgba(arr, outline[0], outline[1] * scale)
    return arr


def downsample(arr, factor):
    from PIL import Image
    if factor == 1:
        return arr
    im = Image.fromarray(arr, "RGBA")
    # pré-multiplica para não sangrar cor das bordas transparentes
    a = arr[:, :, 3:4].astype(np.float32) / 255.0
    pm = arr.astype(np.float32)
    pm[:, :, :3] *= a
    im = Image.fromarray(np.clip(pm, 0, 255).astype(np.uint8), "RGBA")
    im = im.resize((arr.shape[1] // factor, arr.shape[0] // factor), Image.LANCZOS)
    out = np.asarray(im).astype(np.float32)
    aa = out[:, :, 3:4] / 255.0
    out[:, :, :3] = np.where(aa > 0.004, out[:, :, :3] / np.maximum(aa, 1e-6), 0)
    return np.clip(out, 0, 255).astype(np.uint8)


def sheet(frames, cols=None, pad=0):
    """Junta frames (mesmo tamanho) numa grade; devolve (rgba, cols)."""
    n = len(frames)
    fh, fw = frames[0].shape[:2]
    cols = cols or min(n, 8)
    rows = (n + cols - 1) // cols
    out = np.zeros((rows * (fh + pad), cols * (fw + pad), 4), np.uint8)
    for i, f in enumerate(frames):
        r, c = divmod(i, cols)
        out[r * (fh + pad):r * (fh + pad) + fh, c * (fw + pad):c * (fw + pad) + fw] = f
    return out, cols
