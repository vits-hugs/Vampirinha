#!/usr/bin/env python3
"""Gera toda a arte do jogo em assets/ (folhas PNG + assets/sprites.json).

A arte é vetorial e procedural (código em tools/art/). Para regerar:

    pip install -r tools/requirements.txt
    python3 tools/make_assets.py

O jogo só precisa do pygame e dos PNGs já gerados.
"""
import json
import math
import os
import sys
import time
import zlib

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from art import enemies as e  # noqa: E402
from art import fx  # noqa: E402
from art import ground as gr  # noqa: E402
from art import kit  # noqa: E402
from art import portrait as pt  # noqa: E402
from art import props as pr  # noqa: E402
from art import vampire as v  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets")
SS = 2  # supersampling


def cell_render(draw, cell, origin, ss=SS):
    """Renderiza um quadro (com supersampling) e devolve (rgba, âncoras)."""
    box = {}

    def wrapped(pen):
        r = draw(pen)
        if isinstance(r, dict):
            box.update(r)

    arr = kit.render(cell[0], cell[1], wrapped, scale=ss, origin=origin)
    if ss > 1:
        arr = kit.downsample(arr, ss)
    return arr, box


def rel(points):
    """Âncoras em relação ao ponto do pé (para espelhar é só trocar o sinal de x)."""
    out = {}
    for k, val in points.items():
        if isinstance(val, (list, tuple)) and val and isinstance(val[0], (list, tuple)):
            out[k] = [[round(p[0], 1), round(p[1], 1)] for p in val]
        elif isinstance(val, (list, tuple)) and len(val) == 2:
            out[k] = [round(val[0], 1), round(val[1], 1)]
    return out


# folhas que passam pelo filtro de pixel art (mesmo estilo da folha de referência da vampira);
# os efeitos de golpe (fx_*) continuam com brilho suave
PIXEL = {"bat", "hunter", "gunner", "gun_arm", "dog", "boss", "fist", "tooth", "tooth_hud", "leg", "leg_hud", "arm",
         "icons", "props", "bullet", "bullet_back", "muzzle"}


def styled(name, frames):
    if name in PIXEL:
        return [kit.pixelize(f) for f in frames]
    return frames


class Sheet:
    def __init__(self, name, cell, anchor, cols=16):
        self.name, self.cell, self.anchor, self.cols = name, cell, anchor, cols
        self.frames, self.points, self.anims = [], [], {}

    def add_anim(self, key, fps, loop, draws):
        idx = []
        for d in draws:
            arr, pts = cell_render(d, self.cell, self.anchor)
            idx.append(len(self.frames))
            self.frames.append(arr)
            self.points.append(rel(pts))
        self.anims[key] = {"fps": fps, "loop": loop, "frames": idx}

    def save(self, meta):
        rgba, cols = kit.sheet(styled(self.name, self.frames), cols=min(self.cols, len(self.frames)))
        kit.save_png(rgba, os.path.join(OUT, self.name + ".png"))
        meta[self.name] = {"sheet": self.name + ".png", "cell": list(self.cell), "anchor": list(self.anchor), "cols": cols,
                           "count": len(self.frames), "anims": self.anims, "points": self.points}
        print("  %-10s %3d quadros" % (self.name, len(self.frames)))


def rotations(name, draw_fn, size, n, meta, scale=1.0):
    """Gira um objeto em n ângulos (sentido horário a partir de +x)."""
    frames = []
    for i in range(n):
        ang = i / n * math.tau

        def d(pen, ang=ang):
            with pen.at(0, 0, ang, scale):
                draw_fn(pen)
        arr, _ = cell_render(d, size, (size[0] / 2, size[1] / 2))
        frames.append(arr)
    rgba, cols = kit.sheet(styled(name, frames), cols=n)
    kit.save_png(rgba, os.path.join(OUT, name + ".png"))
    meta[name] = {"sheet": name + ".png", "cell": list(size), "anchor": [size[0] / 2, size[1] / 2], "cols": cols, "count": n}
    print("  %-10s %3d rotações" % (name, n))


def single(name, draws, size, origin, meta, extra=None):
    frames = [cell_render(d, size, origin)[0] for d in draws]
    rgba, cols = kit.sheet(styled(name, frames), cols=len(frames))
    kit.save_png(rgba, os.path.join(OUT, name + ".png"))
    meta[name] = {"sheet": name + ".png", "cell": list(size), "anchor": list(origin), "cols": cols, "count": len(frames)}
    if extra:
        meta[name].update(extra)
    print("  %-10s %3d quadros" % (name, len(frames)))


VAMP_CELL, VAMP_ANCHOR = (160, 110), (82, 104)
# animação -> (faixa da folha de referência, quadros, fps, repete?)
VAMP_ANIMS = {
    "idle": ("walk", [0, 0], 3, True),
    "run": ("walk", list(range(9)), 14, True),
    "punch": ("claw", list(range(10)), 30, False),
    "throw": ("claw", [0, 2, 4, 5, 6, 8], 20, False),
    "spit": ("spit", list(range(7)), 24, False),
    "chomp": ("spit", [2, 3, 4, 5, 4, 3], 20, False),
    "kick": ("kick", list(range(6)), 18, False),
    "dash": ("dash", list(range(8)), 36, False),
    "dash_strike": ("dash", list(range(8)), 36, False),
    "hurt": ("walk", [0, 0], 10, False),
    "hop": ("walk", [0, 4], 8, True),
}


def build_vampire(meta):
    """Vampira: quadros recortados da folha de referência (tools/ref/vampirinha_ref.png).
    Ela foi desenhada de lado olhando para a direita; a esquerda é o espelho, feito no jogo."""
    from art import ref_sheet
    bands = ref_sheet.load_frames()
    cells = {k: ref_sheet.to_cells(fr, VAMP_CELL, VAMP_ANCHOR) for k, fr in bands.items()}
    frames, points, anims, index = [], [], {}, {}
    for band, lst in cells.items():
        for i, (img, pts) in enumerate(lst):
            index[(band, i)] = len(frames)
            frames.append(img)
            points.append(pts)
    # parada: o 2º quadro é o 1º descido 1 px (respiração)
    breath = np.zeros_like(frames[index[("walk", 0)]])
    breath[1:] = frames[index[("walk", 0)]][:-1]
    index[("breath", 0)] = len(frames)
    frames.append(breath)
    points.append(points[index[("walk", 0)]])
    for name, (band, ids, fps, loop) in VAMP_ANIMS.items():
        idx = [index[(band, i)] for i in ids]
        if name == "idle":
            idx = [index[("walk", 0)], index[("breath", 0)]]
        for view in ("front", "back"):  # só existe a vista de lado; as duas chaves apontam para ela
            anims[view + "/" + name] = {"fps": fps, "loop": loop, "frames": idx}
    rgba, cols = kit.sheet(frames, cols=16)
    kit.save_png(rgba, os.path.join(OUT, "vampire.png"))
    meta["vampire"] = {"sheet": "vampire.png", "cell": list(VAMP_CELL), "anchor": list(VAMP_ANCHOR), "cols": cols,
                       "count": len(frames), "anims": anims, "points": points}
    print("  vampire    %3d quadros (folha de referência)" % len(frames))


def build():
    os.makedirs(OUT, exist_ok=True)
    meta = {"version": 1}
    t0 = time.time()
    print("Gerando sprites em", OUT)

    # ---------------- vampira
    build_vampire(meta)

    # ---------------- morcego
    sb = Sheet("bat", (112, 104), (56, 96))
    for name, (fps, loop, frames) in v.bat_anims().items():
        sb.add_anim(name, fps, loop, [v.bat_draw(f) for f in frames])
    sb.save(meta)

    # ---------------- caçador (espada)
    sh = Sheet("hunter", (128, 128), (64, 118))
    for name, (fps, loop, poses) in e.hunter_anims().items():
        sh.add_anim(name, fps, loop, [lambda pen, ps=ps: e.draw_hunter(pen, ps) for ps in poses])
    sh.add_anim("dead", 1, False, [e.hunter_dead_draw()])
    sh.save(meta)

    # ---------------- atirador (o braço da arma é uma peça separada que gira)
    sg = Sheet("gunner", (128, 128), (64, 118))
    for name, (fps, loop, poses) in e.gunner_anims().items():
        with_arm = name == "hurt"
        sg.add_anim(name, fps, loop, [lambda pen, ps=ps, wa=with_arm: e.draw_gunner(pen, ps, with_arm=wa) for ps in poses])
    sg.add_anim("dead", 1, False, [e.gunner_dead_draw()])
    sg.save(meta)
    single("gun_arm", [lambda pen, r=r: e.draw_gun_arm(pen, r) for r in (0.0, 3.0)], e.GUN_SIZE, e.GUN_PIVOT, meta,
           {"muzzle": list(e.GUN_MUZZLE)})
    single("muzzle", [lambda pen, k=k: e.muzzle_flash(pen, k) for k in (1.0, 0.7)], (40, 40), (20, 20), meta)

    # ---------------- cão
    sd = Sheet("dog", (128, 96), (62, 90))
    for name, (fps, loop, poses) in e.dog_anims().items():
        sd.add_anim(name, fps, loop, [lambda pen, ps=ps: e.draw_dog(pen, ps) for ps in poses])
    sd.add_anim("dead", 1, False, [e.dog_dead_draw()])
    sd.save(meta)

    # ---------------- Gigante
    sbo = Sheet("boss", (224, 224), (112, 214), cols=7)
    for name, (fps, loop, poses) in e.boss_anims().items():
        sbo.add_anim(name, fps, loop, [lambda pen, ps=ps: e.draw_boss(pen, ps) for ps in poses])
    sbo.add_anim("dead", 1, False, [e.boss_dead_draw()])
    sbo.save(meta)
    meta["boss"]["shoulders"] = {"near": list(e.BOSS_SHOULDER_N), "far": list(e.BOSS_SHOULDER_F)}
    single("fist", [lambda pen: e.draw_fist(pen), lambda pen: e.draw_fist(pen, rage=True)], e.FIST_SIZE, (30, 32), meta)

    # ---------------- projéteis
    # no mundo os projéteis são desenhados maiores que no corpo dela, para ler bem em jogo
    rotations("tooth", lambda pen: pr.draw_tooth(pen, 1.6), (36, 36), 16, meta)
    rotations("tooth_hud", lambda pen: pr.draw_tooth(pen, 2.1), (44, 44), 16, meta)
    rotations("leg", lambda pen: pr.draw_leg_prop(pen, 1.45), (64, 64), 16, meta)
    rotations("leg_hud", lambda pen: pr.draw_leg_prop(pen, 1.7), (72, 72), 16, meta)
    rotations("arm", lambda pen: pr.draw_arm_prop(pen, 1.65), (64, 64), 16, meta)
    single("streak", [lambda pen: pr.draw_streak(pen)], (48, 16), (24, 8), meta)
    single("bullet", [lambda pen, k=k: pr.draw_bullet(pen, True, k) for k in (0, 1)], (28, 28), (14, 14), meta)
    single("bullet_back", [lambda pen, k=k: pr.draw_bullet(pen, False, k) for k in (0, 1)], (32, 32), (16, 16), meta)

    # ---------------- efeitos de golpe (o jogo gira cada quadro para a direção do golpe)
    single("fx_claw", [fx.draw_claw(k) for k in range(len(fx.CLAW_FRAMES))], (180, 180), (90, 90), meta)
    single("fx_kick", [fx.draw_kick(k) for k in range(len(fx.KICK_FRAMES))], (240, 240), (120, 120), meta)
    single("fx_punch", [fx.draw_punch(k) for k in range(len(fx.PUNCH_R))], (260, 260), (130, 130), meta)
    single("fx_sword", [fx.draw_sword(k) for k in range(len(fx.SWORD_FRAMES))], (170, 170), (85, 85), meta)
    single("fx_bite", [fx.draw_bite(k) for k in range(len(fx.BITE_GAP))], (72, 72), (36, 36), meta)
    single("fx_spark", [fx.draw_spark(k) for k in range(len(fx.SPARK_R))], (72, 72), (36, 36), meta)
    single("fx_spark_w", [fx.draw_spark(k, "#ffb648") for k in range(len(fx.SPARK_R))], (72, 72), (36, 36), meta)
    single("fx_crack", [fx.draw_crack(5), fx.draw_crack(9)], (240, 240), (120, 120), meta)
    single("fx_shock", [fx.draw_shock], (fx.SHOCK_SIZE, fx.SHOCK_SIZE), (0, 0), meta)
    single("disc", [fx.draw_disc(r) for r in fx.DISC_RADII], (fx.DISC_CELL, fx.DISC_CELL), (fx.DISC_CELL / 2, fx.DISC_CELL / 2),
           meta, {"radii": fx.DISC_RADII})
    meta["boss"]["arm_colors"] = {k: [list(int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) for c in cols]
                                  for k, cols in fx.BOSS_ARM_COLORS.items()}

    # ---------------- HUD
    single("icons", [lambda pen, el=el: pr.draw_icon(pen, el) for el in ("T", "A", "L")], (56, 56), (28, 28), meta,
           {"order": ["T", "A", "L"]})
    single("slot", [lambda pen: pr.draw_slot(pen)], (72, 72), (36, 36), meta)
    single("bar", [pr.draw_bar_frame], pr.BAR_SIZE, (0, 0), meta, {"inner": list(pr.BAR_INNER)})

    # ---------------- cenário
    import random as _r
    tile = kit.downsample(kit.render(512, 512, lambda pen: gr.draw_flagstones(pen, 512), scale=SS), SS)
    kit.save_png(tile, os.path.join(OUT, "ground.png"))
    dec = []
    for ki, kind in enumerate(gr.DECALS):
        for variant in range(2):
            # semente estável (hash() de str muda a cada execução do Python)
            seed = zlib.crc32(("%s:%d:%d" % (kind, ki, variant)).encode())
            dec.append(cell_render(lambda pen, k=kind, sd=seed: gr.decal(pen, k, _r.Random(sd)), (48, 32), (24, 16))[0])
    rgba, cols = kit.sheet([kit.pixelize(d, outline=None) for d in dec], cols=len(dec))
    kit.save_png(rgba, os.path.join(OUT, "decals.png"))
    meta["decals"] = {"sheet": "decals.png", "cell": [48, 32], "anchor": [24, 16], "cols": cols, "count": len(dec),
                      "weights": [w for w in gr.DECAL_WEIGHTS for _ in range(2)]}
    single("props", [lambda pen, k=k: gr.prop(pen, k) for k in gr.PROPS], (64, 72), (32, 66), meta,
           {"kinds": gr.PROPS, "flames": [list(f) for f in gr.PROP_CANDLE_FLAMES]})
    print("  ground     textura + %d decalques" % len(dec))

    # ---------------- retratos
    states = list(pt.STATES) + ["bat"]
    frames, mouths = [], {}
    for st in states:
        draw, mouth = pt.draw_bat_portrait() if st == "bat" else pt.draw_portrait(st)
        arr = kit.render(pt.SIZE / pt.SCALE, pt.SIZE / pt.SCALE, draw, scale=pt.SCALE * SS)
        arr = kit.downsample(arr, SS)
        frames.append(kit.pixelize(pt.mask_portrait(arr), colors=64, chunk=2))  # retrato em pixel art 2x2
        mouths[st] = [round(mouth[0], 1), round(mouth[1], 1)]
    rgba, cols = kit.sheet(frames, cols=len(frames))
    kit.save_png(rgba, os.path.join(OUT, "portraits.png"))
    for nm, front in (("frame_back", False), ("frame_front", True)):
        arr = kit.downsample(kit.render(pt.SIZE, pt.SIZE, pt.draw_frame(front), scale=SS), SS)
        kit.save_png(arr, os.path.join(OUT, "portrait_%s.png" % nm))
    meta["portraits"] = {"sheet": "portraits.png", "cell": [pt.SIZE, pt.SIZE], "cols": cols, "states": states,
                         "mouth": mouths, "center": list(pt.CENTER), "radius": pt.RADIUS}
    print("  portraits  %3d expressões" % len(states))

    with open(os.path.join(OUT, "sprites.json"), "w") as f:
        json.dump(meta, f, separators=(",", ":"))
    # apaga folhas antigas que esta versão do gerador não produz mais
    for fn in sorted(os.listdir(OUT)):
        full = os.path.join(OUT, fn)
        if fn.endswith(".png") and os.path.getmtime(full) < t0 - 1:
            os.remove(full)
            print("  removido   %s (não é mais gerado)" % fn)
    print("Pronto em %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    build()
