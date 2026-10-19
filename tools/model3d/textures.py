"""Texturas procedurais (pele, cabelo, tecido) e recoloração do olho."""
import numpy as np
from PIL import Image
from scipy import ndimage


def bake_vertex_colors(uv, tris, col, size=2048, pad=6):
    """Rasteriza cores por vértice no espaço uv (interpolação baricêntrica)."""
    img = np.zeros((size, size, col.shape[1]), np.float32)
    cov = np.zeros((size, size), bool)
    P = uv * (size - 1)
    P[:, 1] = (size - 1) - P[:, 1]          # v para cima
    for t in tris:
        p = P[t]
        x0, y0 = np.floor(p.min(0)).astype(int)
        x1, y1 = np.ceil(p.max(0)).astype(int)
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, size - 1), min(y1, size - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        a, b, c = p
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12:
            continue
        l0 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / d
        l1 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / d
        l2 = 1 - l0 - l1
        m = (l0 >= -0.02) & (l1 >= -0.02) & (l2 >= -0.02)
        if not m.any():
            continue
        cc = col[t]
        v = l0[..., None] * cc[0] + l1[..., None] * cc[1] + l2[..., None] * cc[2]
        sub = img[y0:y1 + 1, x0:x1 + 1]
        sub[m] = v[m]
        cov[y0:y1 + 1, x0:x1 + 1] |= m
    # dilata as bordas das ilhas para não aparecer costura
    if pad:
        _, (iy, ix) = ndimage.distance_transform_edt(~cov, return_indices=True)
        img = img[iy, ix]
    return img


def fbm(size, octaves=5, seed=0, base=8):
    rng = np.random.default_rng(seed)
    out = np.zeros((size, size), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        n = base * 2 ** o
        g = rng.standard_normal((n, n)).astype(np.float32)
        up = ndimage.zoom(g, size / n, order=3, mode="grid-wrap")[:size, :size]
        out += amp * up
        tot += amp
        amp *= 0.5
    out /= tot
    return (out - out.mean()) / (out.std() + 1e-6)


def to_image(arr, mode="RGB"):
    a = np.clip(arr * 255 + 0.5, 0, 255).astype(np.uint8)
    return Image.fromarray(a, mode)


def hair_texture(w=256, h=1024, seed=3):
    """Textura RGBA de mecha: fios finos, pontas afinando; a cor vem do baseColorFactor."""
    rng = np.random.default_rng(seed)
    x = np.arange(w)[None, :]
    y = np.linspace(0, 1, h)[:, None]
    alpha = np.zeros((h, w), np.float32)
    lum = np.zeros((h, w), np.float32)
    for _ in range(230):
        cx = rng.uniform(0.04, 0.96) * w
        wid = rng.uniform(0.6, 2.2)
        wob = rng.uniform(0, 6.28)
        cxy = cx + 3.5 * np.sin(y * rng.uniform(2, 7) + wob)
        tip = rng.uniform(0.72, 1.0)                # onde o fio acaba (v=1 é a ponta)
        prof = np.exp(-((x - cxy) / wid) ** 2)
        prof *= np.clip((tip - y) / 0.08, 0, 1)
        alpha = np.maximum(alpha, prof * rng.uniform(0.75, 1.0))
        lum = np.maximum(lum, prof * rng.uniform(0.55, 1.0))
    # o meio da mecha é mais denso; as bordas, ralas
    edge = np.sin(np.linspace(0, np.pi, w))[None, :] ** 0.5
    alpha = np.clip(alpha * 1.25 * (0.55 + 0.45 * edge), 0, 1)
    root = np.clip(y / 0.06, 0, 1)
    alpha = alpha * (0.6 + 0.4 * root)
    tone = rng.uniform(0.75, 1.0)
    rgb = np.repeat((tone * (0.5 + 0.5 * lum))[..., None], 3, 2)
    return to_image(np.dstack([rgb, alpha]), "RGBA")


def red_eye(src):
    """Leva a íris do olho castanho do MakeHuman para um vermelho-sangue vivo."""
    im = np.array(Image.open(src).convert("RGBA")).astype(np.float32) / 255
    rgb = im[..., :3]
    mx, mn = rgb.max(-1), rgb.min(-1)
    sat = (mx - mn) / (mx + 1e-6)
    iris = np.clip((sat - 0.35) / 0.25, 0, 1) * (im[..., 3] > 0.5)
    iris = ndimage.gaussian_filter(iris, 1.0)
    lum = rgb @ np.array([0.3, 0.55, 0.15])
    red = np.stack([np.clip(lum * 3.2 + 0.08, 0, 1), lum * 0.35, lum * 0.45], -1)
    out = rgb * (1 - iris[..., None]) + red * iris[..., None]
    return to_image(np.dstack([out, im[..., 3]]), "RGBA")
