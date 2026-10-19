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
    rgb = np.asarray(Image.open(REF).convert("RGB")).astype(int)
    bg, bg_loose = _bg_masks(rgb)
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
            sub = rgb[y0 + top:y0 + ground + 2, x0:x1]
            m = mask[top:ground + 2, x0:x1]
            sub = sub.copy()
            sub[..., 1] = np.minimum(sub[..., 1], np.maximum(sub[..., 0], sub[..., 2]))  # tira o verde do fundo
            crop[:m.shape[0], :, :3] = sub[:m.shape[0]]
            crop[:m.shape[0], :, 3] = np.where(m, 255, 0)
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
