"""Carrega a arte gerada (assets/sprites.json + PNGs) e oferece atalhos de desenho.

Os sprites foram desenhados olhando para a direita; a versão espelhada (esquerda) e
a silhueta branca (piscar ao tomar dano) são criadas sob demanda e guardadas em cache.
"""
import json
import math
import os

import pygame

ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

_assets = None


def get():
    """Instância única (carregada na primeira vez que alguém desenha)."""
    global _assets
    if _assets is None:
        _assets = Assets(ASSET_DIR)
    return _assets


def _prepare(surf):
    if pygame.display.get_surface() is not None:
        try:
            return surf.convert_alpha()
        except pygame.error:
            return surf
    return surf


class Assets:
    def __init__(self, folder):
        path = os.path.join(folder, "sprites.json")
        if not os.path.exists(path):
            raise SystemExit("Arte não encontrada em %s. Rode: python3 tools/make_assets.py" % folder)
        with open(path) as f:
            self.meta = json.load(f)
        self.folder = folder
        self._frames = {}
        self._flip = {}
        self._flash = {}
        self._tint = {}
        self._images = {}
        self._fx = {}
        self._shock = {}
        self._discs = {}

    # ---- carregamento
    def image(self, filename):
        if filename not in self._images:
            self._images[filename] = _prepare(pygame.image.load(os.path.join(self.folder, filename)))
        return self._images[filename]

    def frames(self, name):
        if name not in self._frames:
            m = self.meta[name]
            sheet = self.image(m["sheet"])
            cw, ch = m["cell"]
            cols = m["cols"]
            out = []
            for i in range(m["count"]):
                r, c = divmod(i, cols)
                out.append(sheet.subsurface(pygame.Rect(c * cw, r * ch, cw, ch)))
            self._frames[name] = out
        return self._frames[name]

    def frame(self, name, idx, flip=False, flash=False):
        key = (name, idx, flip)
        if flash:
            if key not in self._flash:
                src = self.frame(name, idx, flip)
                s = src.copy()
                s.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_MAX)
                self._flash[key] = s
            return self._flash[key]
        if not flip:
            return self.frames(name)[idx]
        if key not in self._flip:
            self._flip[key] = pygame.transform.flip(self.frames(name)[idx], True, False)
        return self._flip[key]

    def tinted(self, name, idx, flip, color):
        """Cópia multiplicada por uma cor (rastro do dash, fantasmas)."""
        key = (name, idx, flip, color)
        if key not in self._tint:
            s = self.frame(name, idx, flip).copy()
            s.fill(color + (255,), special_flags=pygame.BLEND_RGBA_MULT)
            self._tint[key] = s
        return self._tint[key]

    # ---- metadados
    def anim(self, name, key):
        return self.meta[name]["anims"][key]

    def has_anim(self, name, key):
        return key in self.meta[name].get("anims", {})

    def anchor(self, name):
        return self.meta[name]["anchor"]

    def point(self, name, idx, key, flip=False):
        """Ponto de referência do quadro (relativo aos pés), espelhado se preciso."""
        p = self.meta[name]["points"][idx].get(key)
        if p is None:
            return None
        if isinstance(p[0], list):
            return [((-q[0] if flip else q[0]), q[1]) for q in p]
        return ((-p[0] if flip else p[0]), p[1])

    def anim_frame(self, name, key, t, speed=1.0):
        """Índice do quadro de uma animação após t segundos. Devolve (idx, terminou)."""
        a = self.anim(name, key)
        n = len(a["frames"])
        k = max(0, int(t * a["fps"] * speed))
        if a["loop"]:
            return a["frames"][k % n], False
        return a["frames"][min(k, n - 1)], k >= n

    # ---- desenho
    def blit(self, surf, name, idx, pos, flip=False, flash=False, alpha=None, special=0):
        img = self.frame(name, idx, flip, flash)
        ax, ay = self.anchor(name)
        if flip:
            ax = img.get_width() - ax
        if alpha is not None and alpha < 255:
            img = img.copy()
            img.set_alpha(int(alpha))
        surf.blit(img, (round(pos[0] - ax), round(pos[1] - ay)), special_flags=special)

    def rot_frame(self, name, ang):
        """Quadro de um objeto pré-girado (ângulo em radianos, horário a partir de +x)."""
        n = self.meta[name]["count"]
        i = int(round((ang % math.tau) / math.tau * n)) % n
        return self.frames(name)[i]

    def blit_rot(self, surf, name, ang, pos, alpha=None):
        img = self.rot_frame(name, ang)
        if alpha is not None and alpha < 255:
            img = img.copy()
            img.set_alpha(int(alpha))
        surf.blit(img, img.get_rect(center=(round(pos[0]), round(pos[1]))))

    def single(self, name, idx=0):
        return self.frames(name)[idx]

    # ---- efeitos de golpe (desenhados apontando para +x, pivô no centro da célula)
    def fx_image(self, name, idx, ang, scale=1.0, flipv=False):
        """Quadro do efeito girado para 'ang' (radianos) e escalado; guardado em cache."""
        q = int(round(math.degrees(ang) / 4.0)) % 90
        sq = max(0.1, round(scale * 20) / 20)
        key = (name, idx, q, sq, flipv)
        img = self._fx.get(key)
        if img is None:
            src = self.frames(name)[idx]
            if flipv:
                src = pygame.transform.flip(src, False, True)
            img = pygame.transform.rotozoom(src, -q * 4.0, sq) if (q or sq != 1.0) else src
            if len(self._fx) > 220:  # cache pequeno: cada golpe usa poucos ângulos
                self._fx.clear()
            self._fx[key] = img
        return img

    def blit_fx(self, surf, name, idx, pos, ang=0.0, scale=1.0, flipv=False, alpha=None):
        img = self.fx_image(name, idx, ang, scale, flipv)
        if alpha is not None and alpha < 255:
            img = img.copy()
            img.set_alpha(int(alpha))
        surf.blit(img, img.get_rect(center=(round(pos[0]), round(pos[1]))))

    def disc(self, color, r):
        """Disco liso antisserrilhado de raio r (px) pintado com 'color' (cache por cor e raio)."""
        radii = self.meta["disc"]["radii"]
        ri = max(radii[0], min(radii[-1], int(round(r))))
        key = (color, ri)
        img = self._discs.get(key)
        if img is None:
            img = self.frames("disc")[ri - radii[0]].copy()
            img.fill(tuple(color) + (255,), special_flags=pygame.BLEND_RGBA_MULT)
            self._discs[key] = img
        return img

    def shock_ring(self, surf, center, radius, color, alpha=255):
        """Anel de choque suave (sprite branco tingido e escalado para o raio)."""
        if radius < 4:
            return
        base = self._shock.get(color)
        if base is None:
            base = self.single("fx_shock").copy()
            base.fill(tuple(color) + (255,), special_flags=pygame.BLEND_RGBA_MULT)
            self._shock[color] = base
        # o anel do sprite fica a 118/128 do raio da imagem
        size = max(8, int(radius * 2 * 128 / 118))
        img = pygame.transform.smoothscale(base, (size, size))
        if alpha < 255:
            img.set_alpha(int(alpha))
        surf.blit(img, img.get_rect(center=(round(center[0]), round(center[1]))))

    # ---- retratos
    def portrait(self, state):
        m = self.meta["portraits"]
        if "portraits" not in self._frames:
            sheet = self.image(m["sheet"])
            cw, ch = m["cell"]
            self._frames["portraits"] = {st: sheet.subsurface(pygame.Rect(i * cw, 0, cw, ch)) for i, st in enumerate(m["states"])}
        return self._frames["portraits"].get(state) or self._frames["portraits"]["normal"]


def shadow(surf, pos, rx, ry, alpha=110):
    """Sombra elíptica suave no chão."""
    key = (int(rx), int(ry), alpha)
    img = _SHADOWS.get(key)
    if img is None:
        img = pygame.Surface((int(rx * 2 + 4), int(ry * 2 + 4)), pygame.SRCALPHA)
        for k in range(4):
            f = 1 - k * 0.18
            pygame.draw.ellipse(img, (6, 2, 10, int(alpha * 0.32)),
                                pygame.Rect(2 + rx * (1 - f), 2 + ry * (1 - f), rx * 2 * f, ry * 2 * f))
        _SHADOWS[key] = img
    surf.blit(img, img.get_rect(center=(round(pos[0]), round(pos[1]))))


_SHADOWS = {}


def glow(radius, color, alpha=160):
    """Brilho radial com cor pré-multiplicada (para usar com special_flags=BLEND_ADD)."""
    key = (int(radius), color, alpha)
    img = _GLOWS.get(key)
    if img is None:
        r = int(radius)
        img = pygame.Surface((r * 2, r * 2))
        img.fill((0, 0, 0))
        steps = 24
        for k in range(steps):
            t = k / (steps - 1)
            inten = (alpha / 255.0) * (t ** 1.8)
            col = tuple(min(255, int(c * inten)) for c in color)
            pygame.draw.circle(img, col, (r, r), max(1, int(r * (1 - t * 0.96))))
        _GLOWS[key] = img
    return img


_GLOWS = {}
