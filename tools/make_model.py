"""Gera models/vampirinha.glb — a Vampirinha em 3D, num estilo realista.

O corpo parte da malha base do MakeHuman (assets CC0 1.0, em tools/model3d/makehuman/):
ajustes de mulher jovem, proporções ideais, orelhas pontudas e olhos um pouco maiores;
os braços são baixados com o esqueleto padrão do MakeHuman (skinning linear).
Por cima disso tudo é procedural: textura da pele, olhos vermelhos, cílios, sobrancelhas,
cabelo em mechas (cards com alfa) simulado com gravidade e colisão, vestido moldado ao corpo,
saia com pregas, botas, gargantilha e capa de gola alta.

    python3 tools/make_model.py                  # escreve models/vampirinha.glb (quantizado, se houver npx)
    python3 tools/make_model.py --sem-compactar  # sem passar pelo glTF-Transform
"""
import math
import os
import sys

import numpy as np
import trimesh
from scipy import ndimage
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from model3d import geom, mh, textures  # noqa: E402

MH = os.path.join(HERE, "model3d", "makehuman")
OUT = os.path.join(HERE, "..", "models", "vampirinha.glb")
HEIGHT = 1.62
SOLE = 0.022          # espessura da sola: o corpo sobe isso


def lin(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def material(name, col=(1, 1, 1), rough=0.7, metal=0.0, tex=None, alpha=None, double=False, emissive=None,
             alpha_mode=None, cutoff=0.5):
    rgba = list(lin(col[:3])) + [1.0 if alpha is None else alpha]
    kw = dict(name=name, baseColorFactor=rgba, roughnessFactor=rough, metallicFactor=metal, doubleSided=double)
    if tex is not None:
        kw["baseColorTexture"] = tex
    if alpha_mode:
        kw["alphaMode"] = alpha_mode
        if alpha_mode == "MASK":
            kw["alphaCutoff"] = cutoff
    if emissive is not None:
        kw["emissiveFactor"] = list(lin(emissive))
    return trimesh.visual.material.PBRMaterial(**kw)


class Scene:
    def __init__(self):
        self.parts = []

    def add(self, name, V, F, mat, uv=None, N=None):
        V = np.asarray(V, float)
        F = np.asarray(F, int)
        m = trimesh.Trimesh(V, F, process=False)
        if uv is None:
            uv = np.zeros((len(V), 2))
        m.visual = trimesh.visual.TextureVisuals(uv=uv, material=mat)
        if N is None:
            N = geom.vertex_normals(V, F)
        m.vertex_normals = N
        names = {n for n, _ in self.parts}
        base, k = name, 2
        while name in names:
            name = f"{base}_{k}"
            k += 1
        self.parts.append((name, m))
        return m

    def export(self, path):
        sc = trimesh.Scene()
        for name, m in self.parts:
            sc.add_geometry(m, node_name=name, geom_name=name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        sc.export(path, file_type="glb", include_normals=True)
        return sum(len(m.faces) for _, m in self.parts)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- corpo
TARGETS = {
    "caucasian-female-young": 0.7,
    "asian-female-young": 0.3,
    "female-young-averagemuscle-averageweight-idealproportions": 0.8,
    "female-young-averagemuscle-averageweight-minheight": 0.15,
    "female-young-averagemuscle-averageweight-maxcup-averagefirmness": 0.2,
    "l-ear-shape-pointed": 1.0,
    "r-ear-shape-pointed": 1.0,
    "l-eye-scale-incr": 0.35,
    "r-eye-scale-incr": 0.35,
}
ARM_DOWN = math.radians(28)
ELBOW = math.radians(-32)


class Body:
    """Malha base com ajustes, escala em metros e pose de braços baixados."""

    def __init__(self):
        base = os.path.join(MH, "base.obj.gz")
        V, self.VT, faces = mh.load_obj(base, groups=None)
        self.all_faces = self._groups(base)
        self.faces = [(vi, ti) for g, vi, ti in self.all_faces if g == "body"]
        tgt = {os.path.join(MH, "targets", k + ".target.gz"): w for k, w in TARGETS.items()}
        V = mh.apply_targets(V, "", tgt)
        self.body_idx = np.unique([i for f in self.faces for i in f[0]])
        lo, hi = V[self.body_idx, 1].min(), V[self.body_idx, 1].max()
        V = (V - [0, lo, 0]) * ((HEIGHT - SOLE) / (hi - lo))
        self.rest = V.copy()
        self.skel, self.weights = mh.load_skeleton(os.path.join(MH, "default.mhskel.gz"),
                                                   os.path.join(MH, "default_weights.mhw.gz"))
        rots = [("upperarm01.L", (0, 0, 1), -ARM_DOWN), ("upperarm01.R", (0, 0, 1), ARM_DOWN),
                ("lowerarm01.L", (1, 0, 0), -ELBOW), ("lowerarm01.R", (1, 0, 0), -ELBOW)]
        V = mh.pose(V, self.skel, self.weights, rots, self.body_idx)
        V[:, 1] += SOLE
        self.rest[:, 1] += SOLE
        self.V = V
        # malha do corpo com uv por vértice; normais suaves calculadas nos índices originais
        self.pos, self.uv, self.tris, self.org = geom.split_uv(V, self.VT, self.faces)
        self.otris = self.org[self.tris]
        self.N = geom.vertex_normals(V, self.otris)
        self.bone_w = {}
        for b, lst in self.weights.items():
            w = np.zeros(len(V))
            if lst:
                a = np.array(lst)
                w[a[:, 0].astype(int)] = a[:, 1]
            self.bone_w[b] = w

    @staticmethod
    def _groups(path):
        faces = []
        cur = None
        with mh._open(path) as f:
            for line in f:
                if line.startswith("g "):
                    cur = line.split()[1]
                elif line.startswith("f "):
                    vi, ti = [], []
                    for tok in line.split()[1:]:
                        p = tok.split("/")
                        vi.append(int(p[0]) - 1)
                        ti.append(int(p[1]) - 1 if len(p) > 1 and p[1] else -1)
                    faces.append((cur, vi, ti))
        return faces

    def group_verts(self, name):
        return np.unique([i for g, vi, _ in self.all_faces if g == name for i in vi])

    def group_faces(self, prefix):
        return [(vi, ti) for g, vi, ti in self.all_faces if g.startswith(prefix)]

    def joint(self, name):
        return self.V[self.group_verts("joint-" + name)].mean(0)

    def bone_head(self, bone):
        return self.V[self.skel["joints"][self.skel["bones"][bone]["head"]]].mean(0)

    def weight_of(self, prefixes):
        w = np.zeros(len(self.V))
        for b, ww in self.bone_w.items():
            if any(b.startswith(p) for p in prefixes):
                w += ww
        return w


# ---------------------------------------------------------------- pele
SKIN = np.array([0.93, 0.85, 0.86])
LIPS = np.array([0.52, 0.07, 0.15])
SHADOW = np.array([0.42, 0.27, 0.40])
BLUSH = np.array([0.92, 0.60, 0.65])


def skin_colors(body, hair_mask):
    V = body.V
    col = np.tile(SKIN, (len(V), 1))
    ly = body.joint("jaw")[1] + 0.023                       # fenda da boca
    bi = body.body_idx
    near = bi[(np.abs(V[bi, 0]) < 0.006) & (np.abs(V[bi, 1] - ly) < 0.012)]
    lz = V[near, 2].max()
    dx, dy = V[:, 0], V[:, 1] - ly
    front = smoothstep(lz - 0.028, lz - 0.014, V[:, 2])
    w = 0.025 - 0.006 * smoothstep(0, 0.01, np.abs(dy))
    lips = np.clip(1 - np.sqrt((dx / w) ** 2 + (dy / 0.0125) ** 2), 0, 1)
    lips = smoothstep(0.0, 0.3, lips) * (V[:, 2] > lz - 0.05)
    lip_col = LIPS * (0.35 + 0.65 * front[:, None])           # dentro da boca, mais escuro
    col = col * (1 - lips[:, None]) + lip_col * lips[:, None]
    inside = (np.abs(dx) < 0.024) & (np.abs(dy) < 0.006) & (body.N[:, 2] < 0.5) & (V[:, 2] < lz - 0.002) & (V[:, 2] > lz - 0.09)
    col[inside] = LIPS * 0.3
    for side in ("l", "r"):
        E = body.joint(side + "-eye")
        ex, ey = V[:, 0] - E[0], V[:, 1] - E[1]
        fr = smoothstep(E[2] - 0.01, E[2] + 0.004, V[:, 2])
        d = np.sqrt((ex / 0.03) ** 2 + ((ey - 0.003) / 0.02) ** 2)
        sh = np.clip(1 - d, 0, 1) ** 1.2 * fr * 0.32
        col = col * (1 - sh[:, None]) + SHADOW * sh[:, None]
        cx = V[:, 0] - E[0] * 1.15
        cy = V[:, 1] - (E[1] - 0.04)
        bl = np.clip(1 - np.sqrt((cx / 0.026) ** 2 + (cy / 0.02) ** 2), 0, 1) ** 1.5 * 0.3 * (V[:, 2] > E[2] - 0.03)
        col = col * (1 - bl[:, None]) + BLUSH * bl[:, None]
    # couro cabeludo escuro embaixo do cabelo
    col = col * (1 - hair_mask[:, None]) + np.array([0.05, 0.04, 0.05]) * hair_mask[:, None]
    return col


def skin_texture(body, hair_mask, size=2048):
    col = skin_colors(body, hair_mask)
    img = textures.bake_vertex_colors(body.uv, body.tris, col[body.org], size)
    n = textures.fbm(size, 6, seed=11, base=16)
    pores = textures.fbm(size, 2, seed=12, base=256)
    img = img * (1 + 0.018 * n[..., None] + 0.012 * pores[..., None])
    return jpeg(textures.to_image(np.clip(img, 0, 1)), 92)


# ---------------------------------------------------------------- cílios e sobrancelhas
LASH = (0.025, 0.018, 0.025)


def curl_path(root, tip, out, n, curl):
    """Fio da raiz até a ponta, curvando para 'out' (vetor unitário)."""
    t = np.linspace(0, 1, n)[:, None]
    return root + (tip - root) * t + out * curl * t ** 2


def lashes(sc, body):
    rng = np.random.default_rng(5)
    paths, widths, ups = [], [], []
    for side in ("l", "r"):
        E = body.joint(side + "-eye")
        for k, (count, length) in enumerate(((45, 0.55), (150, 1.35))):     # 1 = de baixo, 2 = de cima
            quads = [vi for g, vi, _ in body.all_faces if g == f"helper-{side}-eyelashes-{k + 1}"]
            for _ in range(count):
                q = quads[rng.integers(len(quads))]
                P = body.V[q]
                d = np.linalg.norm(P - E, axis=1)
                roots = sorted(np.argsort(d)[:2])
                a, b = roots
                if (b - a) % 4 == 1:          # arestas adjacentes: raiz a-b, pontas vizinhas
                    ta, tb = (a - 1) % 4, (b + 1) % 4
                else:
                    a, b = b, a
                    ta, tb = (a - 1) % 4, (b + 1) % 4
                s_ = rng.uniform(0, 1)
                root = P[a] * (1 - s_) + P[b] * s_
                tip = P[ta] * (1 - s_) + P[tb] * s_
                v = tip - root
                if k == 0:
                    root = root - v * 0.35            # de baixo: encosta a raiz na borda da pálpebra
                tip = root + v * length * rng.uniform(0.75, 1.15)
                out = tip - E
                out = out / np.linalg.norm(out)
                path = curl_path(root, tip, out, 6, 0.0022 * length)
                paths.append(path)
                widths.append(np.linspace(0.00028, 0.00005, 6))
                n = np.cross(v, P[b] - P[a])
                ups.append(np.tile(n / (np.linalg.norm(n) + 1e-12), (6, 1)))
    V, F, uv, N = geom.ribbons(np.array(paths), np.array(widths), np.array(ups))
    sc.add("cilios", V, F, material("cilios", LASH, rough=0.55, double=True), uv=uv, N=N)


def surface_point(body, p):
    """Ponto mais próximo na pele (aproximado pelo vértice mais próximo) e sua normal."""
    if not hasattr(body, "_kd"):
        body._kd = cKDTree(body.V[body.body_idx])
    _, i = body._kd.query(p)
    vi = body.body_idx[i]
    n = body.N[vi]
    # projeta p no plano tangente do vértice
    q = p - np.dot(p - body.V[vi], n) * n
    return q, n


def brows(sc, body):
    rng = np.random.default_rng(9)
    paths, widths, ups = [], [], []
    for sgn, side in ((1, "l"), (-1, "r")):
        E = body.joint(side + "-eye")
        for _ in range(360):
            t = 0.92 * rng.uniform(0, 1) ** 0.8                  # 0 = ponta interna, 1 = externa
            x = E[0] + sgn * (-0.021 + 0.05 * t)
            arch = 0.0175 + 0.006 * math.sin(math.pi * min(1.0, t * 1.25)) - 0.004 * t
            thick = 0.0042 * (1 - 0.7 * t)
            y = E[1] + arch + rng.uniform(-0.5, 0.5) * thick
            p, n = surface_point(body, np.array([x, y, E[2] + 0.03]))
            p, n = surface_point(body, p)
            # direção: na cabeça da sobrancelha sobe, depois deita para fora
            ang = math.radians(75 - 70 * min(1.0, t * 1.6)) + rng.normal(0, 0.12)
            d = np.array([sgn * math.cos(ang), math.sin(ang), 0.0])
            d = d - np.dot(d, n) * n
            d /= np.linalg.norm(d)
            L = rng.uniform(0.004, 0.0065)
            root = p + n * 0.0003
            path = root + np.outer(np.linspace(0, 1, 5), d * L) + np.outer(np.linspace(0, 1, 5) ** 2, n * 0.0006)
            paths.append(path)
            widths.append(np.linspace(0.00018, 0.00005, 5))
            ups.append(np.tile(n, (5, 1)))
    V, F, uv, N = geom.ribbons(np.array(paths), np.array(widths), np.array(ups))
    sc.add("sobrancelhas", V, F, material("sobrancelhas", (0.09, 0.065, 0.075), rough=0.6, double=True), uv=uv, N=N)


# ---------------------------------------------------------------- roupas moldadas ao corpo
def push_out(P, body, gap, iters=3):
    """Empurra pontos para fora da pele até ficarem a 'gap' dela (aprox. pelo vértice mais próximo)."""
    if not hasattr(body, "_kd"):
        body._kd = cKDTree(body.V[body.body_idx])
    P = P.copy()
    gap = np.broadcast_to(np.asarray(gap, float), (len(P),))
    for _ in range(iters):
        _, i = body._kd.query(P)
        vi = body.body_idx[i]
        d = np.einsum("ij,ij->i", P - body.V[vi], body.N[vi])
        k = d < gap
        P[k] += (gap[k] - d[k])[:, None] * body.N[vi[k]]
    return P


def shell(body, vmask, offset, smooth=6, extra=None, gap=None):
    """Casca que acompanha a pele numa região (máscara por vértice original), afastada 'offset'.

    Devolve (pos, uv, tris, N, org) já no espaço com uv do corpo."""
    fm = vmask[body.otris].all(1)
    ot = body.otris[fm]
    used = np.unique(ot)
    P = body.V.copy()
    off = np.full(len(P), offset) if extra is None else offset + extra
    P[used] += body.N[used] * off[used, None]
    if smooth:
        P = geom.laplacian_smooth(P, ot, iters=smooth, lam=0.5, fixed=geom.boundary_vertices(ot))
    P = smooth_boundary(P, ot, 12)
    P[used] = push_out(P[used], body, (gap if gap is not None else offset * 0.6) + (0 if extra is None else extra[used] * 0.6))
    tris = body.tris[fm]
    keep = np.unique(tris)
    remap = -np.ones(len(body.pos), int)
    remap[keep] = np.arange(len(keep))
    org = body.org[keep]
    pos = P[org]
    N = geom.vertex_normals(P, ot)[org]
    return pos, body.uv[keep], remap[tris], N, org


def smooth_boundary(P, F, iters):
    """Alisa as bordas abertas (decote, punhos) ao longo delas mesmas, sem o serrilhado da malha."""
    from collections import Counter, defaultdict
    e = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1)
    c = Counter(map(tuple, e))
    nb = defaultdict(list)
    for (a, b), n in c.items():
        if n == 1:
            nb[a].append(b)
            nb[b].append(a)
    idx = np.array([v for v, l in nb.items() if len(l) == 2])
    if not len(idx):
        return P
    n1 = np.array([nb[v][0] for v in idx])
    n2 = np.array([nb[v][1] for v in idx])
    P = P.copy()
    for _ in range(iters):
        P[idx] = 0.5 * P[idx] + 0.25 * (P[n1] + P[n2])
    return P


def cloth_masks(body):
    V = body.V
    y, x, z = V[:, 1], V[:, 0], V[:, 2]
    torso = body.weight_of(["spine", "breast", "clavicle", "shoulder01", "upperarm", "lowerarm", "root", "pelvis"])
    neck = body.weight_of(["neck", "head"])
    hand = body.weight_of(["wrist", "finger", "metacarpal"])
    leg = body.weight_of(["upperleg", "lowerleg", "foot", "toe"])
    front_line = 1.262 + 0.9 * x ** 2
    back_line = 1.315
    neckline = np.where(np.abs(x) < 0.088, np.where(z > -0.01, y < front_line, y < back_line), True)
    top = (torso > 0.5) & (neck < 0.25) & (hand < 0.12) & (y > 0.82) & neckline
    return dict(torso=torso, neck=neck, hand=hand, leg=leg, top=top)


def dress_top(sc, body, mk):
    V = body.V
    # babado no ombro e boca de manga levemente aberta
    extra = np.zeros(len(V))
    for side in ("L", "R"):
        sh = body.bone_head("upperarm01." + side)
        d = np.linalg.norm(V - (sh + [0, 0.01, 0]), axis=1)
        extra += 0.011 * np.exp(-(d / 0.055) ** 2)
        wr = body.bone_head("wrist." + side)
        d = np.linalg.norm(V - wr, axis=1)
        extra += 0.008 * smoothstep(0.075, 0.0, d)
    # o busto: tecido não entra no vão entre os seios
    extra += 0.004 * body.weight_of(["breast"])
    pos, uv, tris, N, org = shell(body, mk["top"], 0.0035, smooth=10, extra=extra)
    sc.add("vestido", pos, tris, dress_material(body, pos, uv, tris), uv=uv, N=N)
    top_pos = pos[body.weight_of(["upperarm", "lowerarm", "wrist"])[org] < 0.2]
    # cadarço cruzado no corpete, com ilhoses
    fz = height_field(pos[N[:, 2] > 0.3])
    lace = material("cadarco", (0.03, 0.02, 0.03), rough=0.6)
    ys = np.linspace(0.972, 1.15, 8)
    for i in range(len(ys) - 1):
        for sgn in (1, -1):
            t = np.linspace(0, 1, 10)
            x = -sgn * 0.021 + sgn * 0.042 * t
            y = ys[i] + (ys[i + 1] - ys[i]) * t
            z = fz(x, y) + 0.0022 + 0.0012 * np.sin(np.pi * t)
            tube_add(sc, "cadarco", np.c_[x, y, z], 0.0011, lace)
    gold = material("ilhos", (0.75, 0.6, 0.35), rough=0.3, metal=1.0)
    a = np.linspace(0, 2 * np.pi, 13)
    for yy in ys:
        for xx in (-0.021, 0.021):
            ring = np.c_[xx + 0.0026 * np.cos(a), yy + 0.0026 * np.sin(a), np.zeros_like(a)]
            ring[:, 2] = fz(ring[:, 0], ring[:, 1]) + 0.0012
            tube_add(sc, "ilhoses", ring, 0.0007, gold, seg=6)
    return top_pos


BOOT_TOP = 0.33


def legs(sc, body, mk):
    V = body.V
    y = V[:, 1]
    leg = mk["leg"] > 0.5
    # meia-calça escura (aparece entre a barra e a bota)
    m = leg & (y < 0.9) & (y > 0.08)
    pos, uv, tris, N, _ = shell(body, m, 0.0009, smooth=2)
    sc.add("meias", pos, tris, material("meias", (0.06, 0.05, 0.065), rough=0.68), uv=uv, N=N)
    # botas de couro: superfície implícita em volta do pé e da canela (funde os dedos), sola reta
    leather = material("couro", (0.045, 0.035, 0.04), rough=0.32)
    trim = material("borda", SATIN, rough=0.4)
    for side in (1, -1):
        bV, bF = boot_mesh(body, leg & (y < BOOT_TOP + 0.03) & (np.sign(V[:, 0]) == side))
        sc.add("botas", bV, bF, leather)
        top = bV[bV[:, 1] > BOOT_TOP - 0.008]
        c = top.mean(0)
        ring = []
        for ang in np.linspace(0, 2 * np.pi, 49):
            d = np.array([math.sin(ang), 0, math.cos(ang)])
            ring.append(c + d * ((top - c) @ d).max())
        ring = np.array(ring)
        ring[:, 1] = BOOT_TOP - 0.007
        tube_add(sc, "borda_bota", ring, 0.0055, trim, seg=10)


def ball(r):
    g = np.mgrid[-r:r + 1, -r:r + 1, -r:r + 1]
    return (g ** 2).sum(0) <= r * r


def boot_mesh(body, mask, h=0.0025, offset=0.007):
    from skimage import measure
    tri = body.otris[mask[body.otris].all(1)]
    sm = trimesh.Trimesh(body.V, tri, process=False)
    P, _ = trimesh.sample.sample_surface(sm, int(sm.area / (0.0015 ** 2)), seed=1)
    P = np.vstack([P, body.V[mask]])
    lo = P.min(0) - 0.02
    lo[1] = 0.0
    hi = P.max(0) + 0.02
    hi[1] = BOOT_TOP
    shape = np.ceil((hi - lo) / h).astype(int) + 1
    g = np.stack(np.meshgrid(*[lo[k] + np.arange(shape[k]) * h for k in range(3)], indexing="ij"), -1)
    d, _ = cKDTree(P).query(g.reshape(-1, 3), distance_upper_bound=0.05)
    occ = (d < offset).reshape(shape)
    for iy in range(shape[1]):
        occ[:, iy, :] = ndimage.binary_fill_holes(occ[:, iy, :])
    # sola: preenche cada coluna até o chão
    ground = occ[:, : int(0.045 / h), :].any(1)
    for iy in range(int(0.004 / h), int(0.045 / h)):
        occ[:, iy, :] |= ground
    occ[:, : int(0.004 / h), :] = False
    occ[:, -1, :] = False
    occ = ndimage.binary_closing(np.pad(occ, 6), structure=ball(5))[6:-6, 6:-6, 6:-6]
    lab, n = ndimage.label(occ)
    if n > 1:
        occ = lab == (np.argmax(np.bincount(lab.ravel())[1:]) + 1)
    vol = ndimage.gaussian_filter(np.pad(occ.astype(np.float32), 3), 2.0)
    v, f, _, _ = measure.marching_cubes(vol, 0.5, spacing=(h, h, h))
    m = trimesh.Trimesh(v + lo - 3 * h, f, process=True)
    trimesh.smoothing.filter_taubin(m, iterations=30)
    m = m.simplify_quadric_decimation(face_count=14000)
    m.fix_normals()
    if m.volume < 0:
        m.invert()
    return m.vertices, m.faces


def choker(sc, body):
    V = body.V[body.body_idx]
    nk = body.joint("neck")
    yc = nk[1] + 0.012
    sel = V[(np.abs(V[:, 1] - yc) < 0.02) & (np.hypot(V[:, 0], V[:, 2] - nk[2]) < 0.09)]
    env = Envelope(sel, nk[2], yc - 0.02, yc + 0.02, dy=0.004, nth=96)
    th = np.linspace(0, 2 * np.pi, 96, endpoint=False)
    ys = np.linspace(yc + 0.008, yc - 0.008, 5)
    G = surface_grid(env, env.R, th, ys, 0.0025, lambda Y: 0 * Y, lambda T, Y: 0 * T)
    Vb, Fb, uvb = sheet_mesh(G, True)
    sc.add("gargantilha", Vb, Fb[:, ::-1], material("gargantilha", (0.03, 0.02, 0.03), rough=0.7, double=True), uv=uvb)
    front = G[2, 0]
    g = trimesh.creation.icosphere(3)
    sc.add("pingente", g.vertices * [0.0065, 0.0085, 0.004] + front + [0, -0.016, 0.003], g.faces,
           material("gema", (0.7, 0.02, 0.08), rough=0.08, emissive=(0.12, 0.0, 0.02)))
    a = np.linspace(0, 2 * np.pi, 17)
    ring = np.c_[0.0045 * np.cos(a), -0.016 + 0.0058 * np.sin(a), np.zeros_like(a)] + front + [0, 0, 0.002]
    tube_add(sc, "ilhoses", ring, 0.0011, material("ilhos", (0.75, 0.6, 0.35), rough=0.3, metal=1.0), seg=6)
    tube_add(sc, "ilhoses", np.array([front + [0, -0.002, 0.001], front + [0, -0.0095, 0.002]]), 0.0008,
             material("ilhos", (0.75, 0.6, 0.35), rough=0.3, metal=1.0), seg=6)


def thick_sheet(sc, name, G, outer_mat, inner_mat, thick=0.003, wrap=False):
    """Pano com duas faces (fora e forro) e a borda fechada entre elas."""
    rows, cols = G.shape[:2]
    V, F, uv = sheet_mesh(G, wrap)
    N = geom.vertex_normals(V, F)
    sc.add(name, V, F, outer_mat, uv=uv, N=N)
    Vi = V - N * thick
    sc.add(name + "_forro", Vi, F[:, ::-1], inner_mat, uv=uv, N=-N)
    # borda: liga a casca de fora com o forro em todo o contorno
    idx = np.arange(rows * cols).reshape(rows, cols)
    loops = [idx[0], idx[-1]] + ([] if wrap else [idx[:, 0], idx[:, -1]])
    BV, BF = [], []
    for lp in loops:
        a, b = V[lp], Vi[lp]
        k = len(BV) and sum(len(x) for x in BV)
        n = len(lp)
        BV.append(np.vstack([a, b]))
        for i in range(n - 1):
            BF += [[k + i, k + i + 1, k + n + i], [k + i + 1, k + n + i + 1, k + n + i]]
    BV = np.vstack(BV)
    sc.add(name + "_borda", BV, np.array(BF), outer_mat)
    return V


def cape(sc, body, top_pos, skirt_pts):
    P = np.vstack([body.V[body.body_idx], top_pos, skirt_pts])
    P = P[P[:, 1] < 1.37]
    zc = 0.0
    env = Envelope(P, zc, 0.05, 1.40, dy=0.01, nth=180)
    y_top = 1.355
    Rd = env.drape(y_top)
    hem = 0.11
    rows, cols = 90, 160
    ys = np.linspace(y_top, hem, rows)
    rng = np.random.default_rng(7)
    ph = rng.uniform(0, 2 * np.pi, 4)
    drop = np.clip((1.27 - ys) / (1.27 - hem), 0, 1)
    span = np.radians(np.interp(ys, [hem, 1.25, 1.31, y_top], [112, 124, 150, 168]))
    u = np.linspace(-1, 1, cols)
    TH = np.pi + span[:, None] * u[None, :]
    Y = np.repeat(ys[:, None], cols, 1)
    D = drop[:, None]
    r = env.sample(Rd, TH, Y) + 0.012 + 0.012 * (1 - D) + 0.075 * D ** 1.2
    fold = (0.004 + 0.022 * D) * (0.5 + 0.5 * np.sin(11 * TH + ph[0] + 0.7 * np.sin(3 * TH + ph[1])))
    r = r + fold
    G = np.dstack([r * np.sin(TH), Y, zc + r * np.cos(TH)])
    # barra levemente irregular, mais comprida atrás
    G[-1, :, 1] += 0.012 * np.sin(5 * u * np.pi + ph[2]) - 0.02 * np.cos(u * np.pi / 2)
    G[-2, :, 1] = 0.5 * (G[-1, :, 1] + G[-3, :, 1])
    black = material("capa", VELVET, rough=0.78)
    lining = material("forro", SATIN, rough=0.36)
    thick_sheet(sc, "capa", G, black, lining, 0.004)
    # gola alta atrás da cabeça, abrindo para fora
    rows, cols = 24, 90
    yb = y_top - 0.012
    t = np.linspace(0, 1, rows)
    u = np.linspace(-1, 1, cols)
    span = np.radians(112)
    TH = np.pi + span * u[None, :] * np.ones((rows, 1))
    base_r = env.sample(env.drape(yb + 0.01, 15), TH[0], np.full(cols, yb)) + 0.03 + 0.012 * np.cos(u * np.pi / 2) ** 2
    height = 0.09 + 0.03 * np.cos(u * np.pi / 2) ** 2                # mais alta atrás
    Y = yb + height[None, :] * t[:, None]
    r = base_r[None, :] + 0.06 * t[:, None] ** 1.6 + 0.003 * np.sin(9 * TH)
    G2 = np.dstack([r * np.sin(TH), Y, zc + r * np.cos(TH)])
    thick_sheet(sc, "gola", G2[::-1], black, lining, 0.004)
    # broche que fecha a capa no pescoço
    g = trimesh.creation.icosphere(3)
    c = G[2, 0] * 0.5 + G[2, -1] * 0.5
    c[2] = max(G[2, 0, 2], G[2, -1, 2]) + 0.006
    sc.add("broche", g.vertices * [0.012, 0.014, 0.007] + c, g.faces,
           material("gema", (0.7, 0.02, 0.08), rough=0.08, emissive=(0.12, 0.0, 0.02)))
    for k in (0, -1):
        tube_add(sc, "corrente", np.linspace(G[2, k], c, 6) + [0, -0.004, 0.002], 0.0014,
                 material("ilhos", (0.75, 0.6, 0.35), rough=0.3, metal=1.0))
    return G.reshape(-1, 3)


# ---------------------------------------------------------------- cabelo
HAIR = (0.085, 0.07, 0.095)


def hair_atlas():
    from PIL import Image
    tiles = [textures.hair_texture(256, 1024, seed=k) for k in range(4)]
    im = Image.new("RGBA", (1024, 1024))
    for k, t in enumerate(tiles):
        im.paste(t, (256 * k, 0))
    return im


def hairline(body):
    """Altura da linha do cabelo em função do ângulo em volta da cabeça (0 = testa)."""
    E = body.joint("l-eye")
    front = E[1] + 0.062
    return lambda th: np.interp(np.abs(np.mod(th + np.pi, 2 * np.pi) - np.pi),
                                [0, 0.6, 1.15, 1.6, 2.2, np.pi], [front, front - 0.012, E[1] + 0.03, E[1] + 0.0,
                                                                 1.43, 1.415])


def scalp(body):
    V, N = body.V, body.N
    head = body.weight_of(["head", "neck"]) > 0.5
    hc = body.joint("head")
    th = np.arctan2(V[:, 0], V[:, 2] - hc[2])
    line = hairline(body)(th)
    m = head & (V[:, 1] > line) & (N[:, 1] > -0.4)
    m[np.setdiff1d(np.arange(len(V)), body.body_idx)] = False
    return m


def sample_tris(V, F, n, rng):
    a = np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)
    i = rng.choice(len(F), n, p=a / a.sum())
    r1, r2 = rng.random(n), rng.random(n)
    s = np.sqrt(r1)
    w = np.c_[1 - s, s * (1 - r2), s * r2]
    return (V[F[i]] * w[..., None]).sum(1), i


def hair(sc, body, cloth_pts):
    rng = np.random.default_rng(17)
    V = body.V
    m = scalp(body)
    F = body.otris[m[body.otris].all(1)]
    Fn = geom.vertex_normals(V, body.otris)
    hc = body.joint("head")
    E = body.joint("l-eye")
    brow_y = E[1] + 0.022
    # colisão: cabeça/pescoço/ombros pelo vértice mais próximo; corpo, roupa e capa como sólido cilíndrico
    near = body.body_idx[V[body.body_idx, 1] > 1.2]
    on_scalp = geom.laplacian_smooth(m.astype(float)[:, None], body.otris, iters=4)[:, 0] > 0.05
    kd = cKDTree(V[near])
    solid = Envelope(np.vstack([V[body.body_idx][V[body.body_idx, 1] < 1.39], cloth_pts]), 0.0, 0.6, 1.55,
                     dy=0.01, nth=180)
    # orelhas pontudas à mostra: as mechas passam por trás delas (ou pela frente, as que nascem na frente)
    ears = []
    for side in ("l", "r"):
        idx, _ = mh.load_target(os.path.join(MH, "targets", f"{side}-ear-shape-pointed.target.gz"))
        ev = V[idx]
        ears.append((ev.mean(0), ev.min(0), ev.max(0)))
    groups = [  # (quantidade, comprimento, largura, tipo)
        (2300, (0.50, 0.66), 0.016, "costas"),
        (650, (0.10, 0.14), 0.008, "franja"),
        (360, (0.36, 0.48), 0.012, "lado"),
    ]
    paths, widths, ups = [], [], []
    nseg = 26
    for count, (l0, l1), wid, kind in groups:
        roots, fi = sample_tris(V, F, count * 14, rng)
        th = np.arctan2(roots[:, 0], roots[:, 2] - hc[2])
        ath = np.abs(th)
        if kind == "franja":
            ok = (ath < 0.75) & (roots[:, 1] > hairline(body)(th) + 0.004) & (roots[:, 1] < hairline(body)(th) + 0.05)
        elif kind == "lado":
            ok = (ath > 0.75) & (ath < 1.05) & (roots[:, 1] > E[1] + 0.03)
        else:
            ok = ~((ath < 0.75) & (roots[:, 1] < hairline(body)(th) + 0.03))
        roots, fi, th = roots[ok][:count], fi[ok][:count], th[ok][:count]
        n = len(roots)
        nrm = Fn[F[fi]].mean(1)
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
        # direção de penteado: repartido no meio, caindo para trás/para os lados
        side = np.sign(roots[:, 0] + 1e-6)
        if kind == "franja":
            comb = np.c_[0.25 * np.sin(th), -0.6 * np.ones(n), np.ones(n)]
        elif kind == "lado":
            comb = np.c_[side * 0.5, -np.ones(n), 0.2 * np.ones(n)]
        else:
            back = np.c_[side * 0.55, -0.1 * np.ones(n), -np.ones(n)]
            down = np.c_[side * 0.3, -np.ones(n), -0.15 * np.ones(n)]
            k = np.clip((hc[1] + 0.06 - roots[:, 1]) / 0.08, 0, 1)[:, None]
            comb = back * (1 - k) + down * k
        d = comb - (comb * nrm).sum(1, keepdims=True) * nrm
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        L = rng.uniform(l0, l1, n)
        seg = L / nseg
        layer = rng.uniform(0.001, 0.008, n) ** 1.0      # camadas: umas mechas por cima das outras
        if kind == "franja":
            layer = rng.uniform(0.004, 0.009, n)
        p = roots + nrm * 0.0015
        in_front = np.zeros(n, bool)
        for ec, lo, hi in ears:
            in_front |= (np.sign(roots[:, 0]) == np.sign(ec[0])) & (roots[:, 2] > hi[2])
        P = [p.copy()]
        for k in range(nseg):
            t = (k + 1) / nseg
            if kind == "franja":
                g = np.array([0, -1.0, 0.25]) * (0.25 + 0.6 * t)
            elif kind == "lado":
                g = np.array([0, -1.0, 0.07]) * (0.18 + 0.5 * t)
            else:
                g = np.array([0, -1.0, -0.05]) * (0.1 + 0.55 * t)
            d = d + g[None, :]
            d /= np.linalg.norm(d, axis=1, keepdims=True)
            q = p + d * seg[:, None]
            # cabeça e ombros
            for _ in range(2):
                _, i = kd.query(q)
                vi = near[i]
                dist = np.einsum("ij,ij->i", q - V[vi], body.N[vi])
                off = np.where(on_scalp[vi], 0.0015 + 0.45 * layer, 0.002 + layer)
                hug = on_scalp[vi] & (dist < off + 0.03)                     # no crânio a mecha acompanha a cabeça
                hit = (dist < off) | hug
                q[hit] += (off[hit] - dist[hit])[:, None] * body.N[vi[hit]]
            # orelhas
            for ec, lo, hi in ears:
                near_ear = (np.sign(q[:, 0]) == np.sign(ec[0])) & (q[:, 1] > lo[1] - 0.012) & (q[:, 1] < hi[1] + 0.01) \
                    & (np.abs(q[:, 0]) < abs(ec[0]) + 0.04)
                fz = near_ear & in_front & (q[:, 2] < hi[2] + 0.004 + layer)
                q[fz, 2] = hi[2] + 0.004 + layer[fz]
                bz = near_ear & ~in_front & (q[:, 2] > lo[2] - 0.004 - layer)
                q[bz, 2] = lo[2] - 0.004 - layer[bz]
            # tronco, roupa e capa
            low = q[:, 1] < 1.52
            if low.any():
                thq = np.arctan2(q[low, 0], q[low, 2])
                rq = np.hypot(q[low, 0], q[low, 2])
                R = solid.sample(solid.R, thq, q[low, 1]) + 0.004 + layer[low]
                k2 = rq < R
                idx = np.where(low)[0][k2]
                scale = (R[k2] / np.maximum(rq[k2], 1e-6))
                q[idx, 0] *= scale
                q[idx, 2] *= scale
            d = q - p
            d /= np.linalg.norm(d, axis=1, keepdims=True)
            p = p + d * seg[:, None]
            P.append(p.copy())
        P = np.stack(P, 1)
        # descarta fios que escaparam (colisão ruim): nada pode ficar longe da cabeça/corpo
        rad = np.hypot(P[..., 0], P[..., 2])
        Rs = solid.sample(solid.R, np.arctan2(P[..., 0], P[..., 2]), np.clip(P[..., 1], 0.6, 1.39))
        far_body = ((P[..., 1] < 1.39) & (rad > Rs + 0.1)).any(1)
        far_head = ((P[..., 1] >= 1.39) & (np.linalg.norm(P - hc, axis=2) > 0.24)).any(1)
        keep = ~(far_body | far_head)
        P, n, layer, in_front = P[keep], keep.sum(), layer[keep], in_front[keep]
        if kind == "franja":
            # corta a franja na altura das sobrancelhas
            for j in range(n):
                below = np.where(P[j, :, 1] < brow_y + rng.uniform(-0.006, 0.01))[0]
                if len(below):
                    cut = max(below[0], 3)
                    tt = np.linspace(0, cut, nseg + 1)
                    P[j] = np.array([np.interp(tt, np.arange(nseg + 1), P[j, :, c]) for c in range(3)]).T
        # largura afinando e "up" = normal para fora (da cabeça em cima, do corpo embaixo)
        up_head = P - hc[None, None, :]
        up_body = P.copy()
        up_body[..., 1] = 0
        w = np.clip((hc[1] - P[..., 1]) / 0.12, 0, 1)[..., None]
        up = up_head * (1 - w) + up_body * w
        up /= np.linalg.norm(up, axis=2, keepdims=True)
        tt = np.linspace(0, 1, nseg + 1)
        W = wid * rng.uniform(0.7, 1.2, n)[:, None] * (1 - 0.55 * tt[None, :])
        paths.append(P)
        widths.append(W)
        ups.append(up)
    P = np.concatenate(paths)
    W = np.concatenate(widths)
    U = np.concatenate(ups)
    # touca de cabelo rente ao couro cabeludo: tapa as frestas entre as mechas
    pos, uv, tris, N, _ = shell(body, m, 0.0022, smooth=2)
    sc.add("cabelo_base", pos, tris, material("cabelo_base", np.array(HAIR) * 0.8, rough=0.6), uv=uv, N=N)
    HV, HF, Huv, HN = geom.ribbons(P, W, U)
    # cada mecha usa uma das 4 variações da textura (faixas em u)
    var = np.repeat(rng.integers(0, 4, len(P)), P.shape[1] * 2)
    Huv[:, 0] = (Huv[:, 0] * 0.96 + 0.02 + var) / 4
    mat = material("cabelo", HAIR, rough=0.3, tex=hair_atlas(), alpha_mode="MASK", cutoff=0.4, double=True)
    sc.add("cabelo", HV, HF, mat, uv=Huv, N=HN)


SKIRT_TOP = 1.0
HIP = 0.86


def hand_clear(G, body, gap=0.008):
    """Afunda o tecido onde as mãos encostam (a mão empurra o pano)."""
    hands = body.V[body.weight_of(["wrist", "finger", "metacarpal", "lowerarm"]) > 0.3]
    kd = cKDTree(hands)
    P = G.reshape(-1, 3)
    for _ in range(4):
        d, i = kd.query(P)
        k = d < gap
        if not k.any():
            break
        axis = np.c_[np.zeros(k.sum()), P[k, 1], np.full(k.sum(), 0.02)]
        dirn = P[k] - axis
        dirn /= np.linalg.norm(dirn, axis=1, keepdims=True)
        P[k] -= dirn * (gap - d[k])[:, None] * 1.2
    return P.reshape(G.shape)


def sheet_mesh(G, wrap):
    rows, cols = G.shape[:2]
    V = G.reshape(-1, 3)
    F = geom.grid_faces(rows, cols, wrap)
    uv = np.dstack(np.meshgrid(np.linspace(0, 6, cols), np.linspace(1, 0, rows))).reshape(-1, 2)
    return V, F, uv


def skirt(sc, body, mk, top_pos):
    V = body.V
    arms = body.weight_of(["upperarm", "lowerarm", "wrist", "finger", "metacarpal"]) > 0.2
    pts = np.vstack([V[body.body_idx][~arms[body.body_idx]], top_pos])
    env = Envelope(pts, 0.015, 0.2, 1.1)
    Rd = env.drape(SKIRT_TOP)
    rng = np.random.default_rng(4)
    # saia de baixo, vermelha, inteira (godê com pregas que abrem para a barra)
    hem = 0.30
    th = np.linspace(0, 2 * np.pi, 220, endpoint=False)
    ys = np.linspace(SKIRT_TOP, hem, 70)
    ph = rng.uniform(0, 2 * np.pi, 3)
    drop = lambda Y: np.clip((HIP - Y) / (HIP - hem), 0, 1)
    flare = lambda Y: 0.09 * drop(Y) ** 1.25
    folds = lambda TH, Y: (0.002 + 0.016 * drop(Y)) * (0.5 + 0.5 * np.sin(18 * TH + 0.6 * np.sin(3 * TH + ph[0])))
    G = surface_grid(env, Rd, th, ys, 0.006, flare, folds)
    G[-1, :, 1] += 0.006 * np.sin(5 * th + ph[1])
    G = hand_clear(G, body)
    Vs, Fs, uvs = sheet_mesh(G, True)
    sc.add("saia", Vs, Fs[:, ::-1], material("saia", SATIN, rough=0.42, double=True), uv=uvs)
    # sobressaia preta aberta na frente, com barra vermelha
    hem2 = 0.36
    ys2 = np.linspace(SKIRT_TOP + 0.004, hem2, 64)
    u = np.linspace(0, 1, 200)
    opening = lambda Y: np.radians(4 + 38 * drop(Y) ** 0.8)
    TH = opening(ys2)[:, None] + u[None, :] * (2 * np.pi - 2 * opening(ys2)[:, None])
    Y = np.repeat(ys2[:, None], len(u), 1)
    r = env.sample(Rd, TH, Y) + 0.013 + 0.11 * drop(Y) ** 1.2 + \
        (0.003 + 0.02 * drop(Y)) * (0.5 + 0.5 * np.sin(13 * TH + 0.8 * np.sin(2 * TH + ph[2])))
    G2 = np.dstack([r * np.sin(TH), Y, env.zc + r * np.cos(TH)])
    G2[-1, :, 1] += 0.008 * np.sin(4 * u * 2 * np.pi)
    G2 = hand_clear(G2, body, 0.012)
    Vo, Fo, uvo = sheet_mesh(G2, False)
    rows = len(ys2)
    trim_rows = 3
    fr = np.arange(len(Fo)) // (2 * (len(u) - 1))
    fc = (np.arange(len(Fo)) // 2) % (len(u) - 1)
    trim = (fr >= rows - 1 - trim_rows) | (fc < 2) | (fc >= len(u) - 3)
    sc.add("sobressaia", Vo, Fo[~trim][:, ::-1], material("sobressaia", VELVET, rough=0.8, double=True), uv=uvo)
    sc.add("barra", Vo, Fo[trim][:, ::-1], material("barra", SATIN, rough=0.4, double=True), uv=uvo)
    # cinto na cintura
    th3 = np.linspace(0, 2 * np.pi, 160, endpoint=False)
    ys3 = np.linspace(1.012, 0.978, 5)
    G3 = surface_grid(env, Rd, th3, ys3, 0.008, lambda Y: 0 * Y, lambda T, Y: 0 * T)
    Vb, Fb, uvb = sheet_mesh(G3, True)
    sc.add("cinto", Vb, Fb[:, ::-1], material("cinto", (0.03, 0.025, 0.03), rough=0.35, double=True), uv=uvb)
    fz = env.sample(Rd, np.array([0.0]), np.array([0.995]))[0] + 0.02
    m = trimesh.creation.icosphere(3)
    sc.add("gema", m.vertices * [0.011, 0.014, 0.006] + [0, 0.995, env.zc + fz], m.faces,
           material("gema", (0.7, 0.02, 0.08), rough=0.08, emissive=(0.12, 0.0, 0.02)))
    return np.vstack([Vs, Vo])


def height_field(P):
    """z(x, y) da superfície da frente, interpolada dos pontos P (inverso da distância)."""
    kd = cKDTree(P[:, :2])

    def f(x, y):
        q = np.c_[np.atleast_1d(x), np.atleast_1d(y)]
        d, i = kd.query(q, 8)
        w = 1 / (d + 1e-5) ** 2
        return (P[i, 2] * w).sum(1) / w.sum(1)
    return f


class Envelope:
    """Raio máximo r(θ, y) de uma nuvem de pontos em volta de um eixo vertical (x=0, z=zc).

    θ = 0 aponta para a frente (+z) e cresce para +x."""

    def __init__(self, P, zc, y0, y1, dy=0.01, nth=144):
        self.zc, self.y0, self.dy, self.nth = zc, y0, dy, nth
        ny = int(round((y1 - y0) / dy)) + 1
        self.ys = y0 + np.arange(ny) * dy
        x, z = P[:, 0], P[:, 2] - zc
        th = np.mod(np.arctan2(x, z), 2 * np.pi)
        r = np.hypot(x, z)
        iy = np.round((P[:, 1] - y0) / dy).astype(int)
        it = (th / (2 * np.pi) * nth).astype(int) % nth
        ok = (iy >= 0) & (iy < ny)
        R = np.zeros((ny, nth))
        np.maximum.at(R, (iy[ok], it[ok]), r[ok])
        # buracos (bins vazios) e serrilhado: máximo dos vizinhos em θ e suavização
        R = ndimage.maximum_filter(R, size=(3, 5), mode=("nearest", "wrap"))
        self.R = ndimage.gaussian_filter(R, (1.0, 1.5), mode=("nearest", "wrap"))

    def drape(self, y_top, bridge=9):
        """Pano caindo de y_top: em cada altura vale o maior raio daí para cima (até y_top).

        'bridge' faz o tecido passar reto por cima de vãos estreitos (entre as pernas, na coluna)."""
        R = ndimage.maximum_filter(self.R, size=(1, bridge), mode=("nearest", "wrap"))
        R = ndimage.gaussian_filter(R, (0, bridge / 3), mode=("nearest", "wrap"))
        top = int(round((y_top - self.y0) / self.dy))
        for i in range(top - 1, -1, -1):
            R[i] = np.maximum(R[i], R[i + 1])
        return R

    def sample(self, R, th, y):
        from scipy.ndimage import map_coordinates
        fy = (np.asarray(y) - self.y0) / self.dy
        ft = np.mod(np.asarray(th), 2 * np.pi) / (2 * np.pi) * self.nth - 0.5
        ext = np.concatenate([R, R[:, :1]], 1)
        return map_coordinates(ext, [fy.ravel(), np.mod(ft.ravel(), self.nth)], order=1, mode="nearest").reshape(np.shape(y))


def surface_grid(env, Rd, th, ys, ease, flare, folds):
    """Malha (len(ys) x len(th)) sobre o envelope: raio = drape + folga + godê + pregas."""
    TH, Y = np.meshgrid(th, ys)
    r = env.sample(Rd, TH, Y) + ease + flare(Y) + folds(TH, Y)
    x = r * np.sin(TH)
    z = env.zc + r * np.cos(TH)
    return np.dstack([x, Y, z])


def jpeg(img, q=90):
    import io
    from PIL import Image
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=q)
    buf.seek(0)
    return Image.open(buf)


def fabric_maps(uv, tris, pos, size, colfn, seed=0):
    """Pinta textura de cor e de rugosidade avaliando colfn(posição 3D) por pixel."""
    P = textures.bake_vertex_colors(uv, tris, pos, size)
    col, rough = colfn(P.reshape(-1, 3))
    col = col.reshape(size, size, 3)
    rough = rough.reshape(size, size)
    n = textures.fbm(size, 5, seed=seed, base=64)
    col = col * (1 + 0.05 * n[..., None])
    mr = np.dstack([np.zeros_like(rough), np.clip(rough + 0.03 * n, 0, 1), np.zeros_like(rough)])
    return jpeg(textures.to_image(np.clip(col, 0, 1))), jpeg(textures.to_image(mr))


def tex_material(name, col_img, mr_img, double=False):
    return trimesh.visual.material.PBRMaterial(name=name, baseColorTexture=col_img, metallicRoughnessTexture=mr_img,
                                                roughnessFactor=1.0, metallicFactor=1.0, doubleSided=double)


VELVET = np.array([0.075, 0.06, 0.08])
SATIN = np.array([0.55, 0.04, 0.10])


def dress_material(body, pos, uv, tris):
    wrists = [body.bone_head("wrist." + s) for s in ("L", "R")]

    def colfn(P):
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        # painel do corpete: mais largo em cima, ponta em V embaixo
        half = 0.036 + 0.16 * np.clip(y - 1.0, 0, None)
        bottom = 0.948 + 0.9 * np.abs(x)
        panel = (np.abs(x) < half) & (z > 0.04) & (y > bottom) & (y < 1.168)
        edge = (np.abs(np.abs(x) - half) < 0.0035) & panel             # debrum preto
        cuff = np.zeros(len(P), bool)
        for w in wrists:
            cuff |= np.linalg.norm(P - w, axis=1) < 0.065
        red = (panel & ~edge) | cuff
        col = np.where(red[:, None], SATIN, VELVET)
        rough = np.where(red, 0.35, 0.85)
        return col, rough

    c, mr = fabric_maps(uv, tris, pos, 2048, colfn, seed=21)
    return tex_material("vestido", c, mr)


def tube_add(sc, name, pts, r, mat, seg=8):
    pts = np.asarray(pts, float)
    T = np.gradient(pts, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    ref = np.eye(3)[np.argmin(np.abs(T).max(0))]          # eixo nunca paralelo ao caminho
    Nn = np.cross(T, ref)
    Nn /= np.linalg.norm(Nn, axis=1, keepdims=True)
    B = np.cross(T, Nn)
    a = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    rr = np.broadcast_to(np.asarray(r, float), (len(pts),))
    ring = (np.cos(a)[None, :, None] * Nn[:, None] + np.sin(a)[None, :, None] * B[:, None])
    V = (pts[:, None] + rr[:, None, None] * ring).reshape(-1, 3)
    F = geom.grid_faces(len(pts), seg, wrap=True)
    F = F[:, ::-1]
    N = ring.reshape(-1, 3)
    if name in getattr(sc, "_tubes", {}):
        pv, pf, pn, pm = sc._tubes[name]
        sc._tubes[name] = (np.vstack([pv, V]), np.vstack([pf, F + len(pv)]), np.vstack([pn, N]), pm)
    else:
        sc.__dict__.setdefault("_tubes", {})[name] = (V, F, N, mat)


def flush_tubes(sc):
    for name, (V, F, N, mat) in getattr(sc, "_tubes", {}).items():
        sc.add(name, V, F, mat, N=N)
    sc._tubes = {}


# ---------------------------------------------------------------- montagem
def build():
    body = Body()
    sc = Scene()
    hm = scalp(body).astype(float)
    hm = geom.laplacian_smooth(hm[:, None], body.otris, iters=3, lam=0.5)[:, 0]
    hair_mask = np.clip(hm * 1.3, 0, 1)
    skin = material("pele", rough=0.52, tex=skin_texture(body, hair_mask))
    sc.add("corpo", body.pos, body.tris, skin, uv=body.uv, N=body.N[body.org])

    # olhos (proxy do MakeHuman), íris recolorida de vermelho; córnea transparente e brilhante
    EV, ET, EF = mh.fit_mhclo(os.path.join(MH, "eyes", "high-poly.mhclo"), body.rest)
    pos, uv, tris, org = geom.split_uv(EV, ET, EF)
    En = geom.vertex_normals(EV, org[tris])[org]
    eye_tex = jpeg(textures.red_eye(os.path.join(MH, "eyes", "brown_eye.png")), 92)
    c = uv[tris].mean(1)
    corner = (c[:, 0] > 0.85) & (c[:, 1] < 0.15)
    sc.add("olhos", pos, tris[~corner], material("olho", rough=0.25, tex=eye_tex), uv=uv, N=En)
    sc.add("cornea", pos, tris[corner], material("cornea", (1, 1, 1), rough=0.02, alpha=0.08, alpha_mode="BLEND"),
           uv=uv, N=En)
    # boca: um miolo escuro atrás dos lábios (a malha base tem a boca aberta para dentro da cabeça)
    ly = body.joint("jaw")[1] + 0.023
    bi = body.body_idx
    lz = body.V[bi[(np.abs(body.V[bi, 0]) < 0.006) & (np.abs(body.V[bi, 1] - ly) < 0.012)], 2].max()
    m = trimesh.creation.icosphere(3)
    MV = m.vertices * [0.024, 0.006, 0.012] + [0, ly, lz - 0.027]
    sc.add("boca", MV, m.faces, material("boca", (0.12, 0.02, 0.03), rough=0.5))
    lashes(sc, body)
    brows(sc, body)
    mk = cloth_masks(body)
    top = dress_top(sc, body, mk)
    skirt_pts = skirt(sc, body, mk, top)
    legs(sc, body, mk)
    choker(sc, body)
    cape_pts = cape(sc, body, top, skirt_pts)
    hair(sc, body, np.vstack([top, skirt_pts, cape_pts]))
    flush_tubes(sc)
    return sc, body


def compact(path):
    """Quantiza posições/normais/uvs (KHR_mesh_quantization) com o glTF-Transform, se houver Node.

    O arquivo fica ~35% menor e continua abrindo no Blender, three.js, Godot etc."""
    import shutil
    import subprocess
    if not shutil.which("npx"):
        print("(sem npx: o .glb fica sem quantização)")
        return
    tmp = path + ".tmp.glb"
    r = subprocess.run(["npx", "--yes", "@gltf-transform/cli@4", "quantize", path, tmp], capture_output=True, text=True)
    if r.returncode == 0 and os.path.exists(tmp):
        os.replace(tmp, path)
    else:
        print("(quantização falhou, mantendo o .glb completo)", r.stderr[-300:])


def main():
    sc, _ = build()
    tris = sc.export(OUT)
    if "--sem-compactar" not in sys.argv:
        compact(OUT)
    print(f"{OUT}: {tris} triângulos, {len(sc.parts)} partes, {os.path.getsize(OUT) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
