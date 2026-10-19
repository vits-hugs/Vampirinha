"""Recorta a folha de sprites de referência da Vampirinha (tools/ref/vampirinha_ref.png).

A folha tem 5 faixas (andar, ataque com garras, cuspir dentes, chutar, dash) sobre fundo
cinza/verde. Cada quadro é um bloco conectado de pixels; o fundo vira transparente, os
pedacinhos soltos (dentes voando, morceguinhos) são descartados ou grudados no quadro
mais próximo, e todos os quadros de uma faixa ficam alinhados pelo chão e pelo tronco.
"""
import os

import numpy as np
from PIL import Image
from scipy import ndimage as nd

REF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ref", "vampirinha_ref.png")

# (nome, y0, y1, grudar pedacinhos soltos no quadro mais próximo?)
BANDS = [("walk", 18, 113, False), ("claw", 139, 235, True), ("spit", 250, 347, False),
         ("kick", 362, 471, False), ("dash", 486, 572, True)]


def _bg_masks(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    gray = (abs(r - g) < 14) & (abs(g - b) < 14) & (r > 100) & (r < 165)
    green = (g - r > 25) & (g - b > 20) & (g > 90) & (g < 170)
    # versão mais solta, só para limpar a franja da borda
    gray_l = (abs(r - g) < 24) & (abs(g - b) < 24) & (r > 88) & (r < 178)
    green_l = (g - r > 14) & (g - b > 10) & (g > 80)
    return gray | green, gray_l | green_l


def load_frames():
    """Devolve {faixa: [(rgba recortado, (âncora_x, âncora_y))...]} com âncora nos pés."""
    raw = np.asarray(Image.open(REF).convert("RGB"))
    rgb = raw.astype(int)
    bg, bg_loose = _bg_masks(rgb)
    # cores levemente desruidadas (a imagem tem ruído/compressão); a máscara usa a original
    import cv2
    smooth = cv2.bilateralFilter(np.ascontiguousarray(raw), 5, 22, 3).astype(float)
    out = {}
    for name, y0, y1, attach in BANDS:
        fg = ~bg[y0:y1]
        clean = nd.binary_opening(fg, iterations=1)
        lab, n = nd.label(clean, structure=np.ones((3, 3)))
        sizes = nd.sum(clean, lab, range(1, n + 1))
        objs = nd.find_objects(lab)
        big = sorted([i for i in range(n) if sizes[i] > 1500], key=lambda i: objs[i][1].start)
        groups = {i: [i] for i in big}
        if attach:  # morceguinhos/fumaça do dash, rastro das garras: vão para o quadro mais perto
            for i in range(n):
                if i in groups or sizes[i] < 25:
                    continue
                sy, sx = objs[i]
                cx = (sx.start + sx.stop) / 2
                best = min(big, key=lambda j: abs(cx - (objs[j][1].start + objs[j][1].stop) / 2))
                bx = objs[best][1]
                if bx.start - 30 <= cx <= bx.stop + 30:
                    groups[best].append(i)
        frames = []
        ground = 0
        for i in big:
            mask = np.isin(lab, [k + 1 for k in groups[i]])
            mask = nd.binary_dilation(mask, iterations=1) & fg          # recupera contornos finos
            mask &= ~(bg_loose[y0:y1] & ~nd.binary_erosion(mask, iterations=1))  # tira a franja cinza
            mask = mask | (nd.binary_fill_holes(mask) & ~bg[y0:y1])      # buracos internos que não são fundo
            ys, xs = np.nonzero(mask)
            ground = max(ground, ys.max())
            frames.append((i, mask))
        res = []
        for i, mask in frames:
            ys, xs = np.nonzero(mask)
            top, bot = ys.min(), ys.max()
            # âncora x: centro do tronco (faixa do meio da altura do corpo, só o pedaço principal)
            body = lab == i + 1
            h = bot - top
            band = body[int(top + h * 0.35):int(top + h * 0.7)]
            bys, bxs = np.nonzero(band)
            ax = float(np.median(bxs)) if len(bxs) else float(xs.mean())
            x0, x1 = xs.min(), xs.max() + 1
            crop = np.zeros((ground + 1 - top + 1, x1 - x0, 4), np.uint8)
            sub = smooth[y0 + top:y0 + ground + 2, x0:x1].copy()
            m = mask[top:ground + 2, x0:x1]
            sub = sub[:m.shape[0]]
            # transparência suave na borda: proporcional à distância da cor do fundo da faixa,
            # e a cor da borda "desmisturada" do fundo (sem franja cinza/verde)
            bgcol = np.median(rgb[y0:y1][bg[y0:y1]], axis=0)
            dist = np.sqrt(((sub - bgcol) ** 2).sum(axis=2))
            core = nd.binary_erosion(m, iterations=1)
            ring = nd.binary_dilation(m, iterations=1) & ~core
            alpha = np.where(core, 1.0, 0.0)
            alpha = np.where(ring, np.clip((dist - 18.0) / 70.0, 0.0, 1.0), alpha)
            alpha = np.maximum(nd.gaussian_filter(alpha, 0.55), nd.binary_erosion(m, iterations=2))
            alpha[alpha < 0.06] = 0
            unmix = bgcol + (sub - bgcol) / np.maximum(alpha, 0.35)[..., None]
            col = np.where(ring[..., None], unmix, sub)
            col[..., 1] = np.minimum(col[..., 1], np.maximum(col[..., 0], col[..., 2]))  # tira o verde do fundo
            crop[:m.shape[0], :, :3] = np.clip(col, 0, 255).astype(np.uint8)
            crop[:m.shape[0], :, 3] = (alpha * 255).astype(np.uint8)
            # pontos úteis (rosto olhando para a direita): topo da cabeça, olhos, boca
            head = body[top:top + 24]
            hys, hxs = np.nonzero(head)
            hx = float(np.median(hxs)) if len(hxs) else ax
            pts = {"head": (hx - x0, 12.0), "eyes": [(hx - x0 + 7.0, 15.0)], "mouth": (hx - x0 + 8.0, 21.0)}
            res.append((crop, (ax - x0, ground - top), pts))
        out[name] = res
    return out


def to_cells(frames, cell, anchor):
    """Cola cada quadro numa célula (cell) com a âncora (pés) em 'anchor'; devolve (rgba, pontos)."""
    cells = []
    for crop, (ax, ay), pts in frames:
        c = np.zeros((cell[1], cell[0], 4), np.uint8)
        ox = int(round(anchor[0] - ax))
        oy = int(round(anchor[1] - ay))
        h, w = crop.shape[:2]
        sx0, sy0 = max(0, -ox), max(0, -oy)
        dx0, dy0 = max(0, ox), max(0, oy)
        w2 = min(w - sx0, cell[0] - dx0)
        h2 = min(h - sy0, cell[1] - dy0)
        c[dy0:dy0 + h2, dx0:dx0 + w2] = crop[sy0:sy0 + h2, sx0:sx0 + w2]
        # pontos relativos aos pés
        def rel(p):
            return [round(p[0] - ax, 1), round(p[1] - ay, 1)]
        cells.append((c, {"head": rel(pts["head"]), "eyes": [rel(e) for e in pts["eyes"]], "mouth": rel(pts["mouth"])}))
    return cells


def inbetween(a, b, t=0.5):
    """Quadro intermediário entre a e b (RGBA alinhados pelos pés) por fluxo óptico:
    estima o movimento de cada pixel e desenha a pose "no meio do caminho"."""
    import cv2

    def pm(img):
        f = img.astype(np.float32) / 255.0
        f[..., :3] *= f[..., 3:4]
        return f

    def gray(img):
        g = cv2.cvtColor(img[..., :3], cv2.COLOR_RGB2GRAY).astype(np.float32)
        g = g * (img[..., 3].astype(np.float32) / 255.0) + (255 - img[..., 3].astype(np.float32)) * 0.35
        return np.clip(g, 0, 255).astype(np.uint8)

    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    ga, gb = gray(a), gray(b)
    f_ab = dis.calc(ga, gb, None)
    f_ba = dis.calc(gb, ga, None)
    h, w = ga.shape
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    pa, pb = pm(a), pm(b)
    # amostra a recuando t do caminho (fluxo b->a) e b avançando (1-t) (fluxo a->b)
    wa = cv2.remap(pa, gx + f_ba[..., 0] * t, gy + f_ba[..., 1] * t, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    wb = cv2.remap(pb, gx + f_ab[..., 0] * (1 - t), gy + f_ab[..., 1] * (1 - t), cv2.INTER_LINEAR,
                   borderMode=cv2.BORDER_CONSTANT)
    mid = wa * (1 - t) + wb * t
    al = mid[..., 3:4]
    out = np.zeros_like(a)
    out[..., :3] = np.clip(np.where(al > 1e-3, mid[..., :3] / np.maximum(al, 1e-3), 0) * 255, 0, 255).astype(np.uint8)
    out[..., 3] = np.clip(al[..., 0] * 255, 0, 255).astype(np.uint8)
    return out
