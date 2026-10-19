"""Leitura da malha base e dos ajustes (targets) do MakeHuman (assets CC0 1.0)."""
import gzip
import os

import numpy as np


def _open(path):
    return gzip.open(path, "rt") if path.endswith(".gz") else open(path)


def load_obj(path, groups=("body",)):
    """OBJ do MakeHuman: devolve (vértices, uvs, faces[(vi..), (ti..)] do(s) grupo(s) pedido(s))."""
    V, VT, faces = [], [], []
    cur = None
    with _open(path) as f:
        for line in f:
            if line.startswith("v "):
                V.append([float(x) for x in line.split()[1:4]])
            elif line.startswith("vt "):
                VT.append([float(x) for x in line.split()[1:3]])
            elif line.startswith("g "):
                cur = line.split()[1]
            elif line.startswith("f ") and (groups is None or cur in groups):
                vi, ti = [], []
                for tok in line.split()[1:]:
                    parts = tok.split("/")
                    vi.append(int(parts[0]) - 1)
                    ti.append(int(parts[1]) - 1 if len(parts) > 1 and parts[1] else -1)
                faces.append((vi, ti))
    return np.array(V, float), np.array(VT, float), faces


def load_target(path):
    idx, d = [], []
    with _open(path) as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            p = line.split()
            idx.append(int(p[0]))
            d.append([float(p[1]), float(p[2]), float(p[3])])
    return np.array(idx, int), np.array(d, float)


def apply_targets(V, folder, weights):
    V = V.copy()
    for rel, w in weights.items():
        if w == 0:
            continue
        idx, d = load_target(os.path.join(folder, rel))
        if len(idx):
            V[idx] += d * w
    return V


# ---------------------------------------------------------------- esqueleto e pose
def load_skeleton(skel_path, weights_path):
    import json
    with _open(skel_path) as f:
        skel = json.load(f)
    with _open(weights_path) as f:
        weights = json.load(f)["weights"]
    return skel, weights


def joint_pos(V, skel, name):
    return V[skel["joints"][name]].mean(0)


def descendants(skel, root):
    bones = skel["bones"]
    out = {root}
    changed = True
    while changed:
        changed = False
        for b, d in bones.items():
            if b not in out and d["parent"] in out:
                out.add(b)
                changed = True
    return out


def rot_matrix(axis, ang):
    axis = np.asarray(axis, float)
    axis = axis / np.linalg.norm(axis)
    x, y, z = axis
    c, s = np.cos(ang), np.sin(ang)
    C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])


def pose(V, skel, weights, rotations, body_idx):
    """Skinning linear. rotations: lista (osso, eixo, ângulo), aplicadas da raiz para as pontas.

    Vértices sem peso (ajudantes) herdam os pesos do vértice do corpo mais próximo."""
    from scipy.spatial import cKDTree

    bones = list(skel["bones"])
    bi = {b: i for i, b in enumerate(bones)}
    n = len(V)
    W = np.zeros((n, len(bones)))
    for b, lst in weights.items():
        if b in bi and lst:
            a = np.array(lst)
            W[a[:, 0].astype(int), bi[b]] = a[:, 1]
    tot = W.sum(1)
    body_w = np.zeros(n, bool)
    body_w[body_idx] = True
    have = (tot > 0) & body_w
    miss = np.where(~have)[0]
    src = np.where(have)[0]
    _, nn = cKDTree(V[src]).query(V[miss])
    W[miss] = W[src[nn]]
    W /= W.sum(1, keepdims=True)

    # transformações globais (4x4) por osso
    T = {b: np.eye(4) for b in bones}
    for bone, axis, ang in rotations:
        h = joint_pos(V, skel, skel["bones"][bone]["head"])
        h = T[bone][:3, :3] @ h + T[bone][:3, 3]          # cabeça já movida pelos pais
        R = rot_matrix(axis, ang)
        M = np.eye(4)
        M[:3, :3] = R
        M[:3, 3] = h - R @ h
        for d in descendants(skel, bone):
            T[d] = M @ T[d]
    out = np.zeros_like(V)
    for b, i in bi.items():
        w = W[:, i]
        nz = w > 0
        if not nz.any():
            continue
        M = T[b]
        out[nz] += w[nz, None] * (V[nz] @ M[:3, :3].T + M[:3, 3])
    return out


# ---------------------------------------------------------------- roupas/proxies (.mhclo)
def fit_mhclo(path, V):
    """Lê um .mhclo e devolve (vértices ajustados, uvs, faces) do obj associado."""
    folder = os.path.dirname(path)
    refs, scales, obj = [], {}, None
    with open(path) as f:
        lines = f.read().splitlines()
    i = 0
    while i < len(lines):
        p = lines[i].split()
        i += 1
        if not p or p[0].startswith("#"):
            continue
        if p[0] == "obj_file":
            obj = os.path.join(folder, p[1])
        elif p[0] in ("x_scale", "y_scale", "z_scale"):
            scales[p[0][0]] = (int(p[1]), int(p[2]), float(p[3]))
        elif p[0] == "verts":
            while i < len(lines) and lines[i].strip() and not lines[i].split()[0].isalpha():
                refs.append([float(x) for x in lines[i].split()])
                i += 1
    sc = np.ones(3)
    for k, ax in (("x", 0), ("y", 1), ("z", 2)):
        if k in scales:
            a, b, den = scales[k]
            sc[ax] = abs(V[a, ax] - V[b, ax]) / den
    out = []
    for r in refs:
        if len(r) == 1:
            out.append(V[int(r[0])])
        else:
            v = V[[int(r[0]), int(r[1]), int(r[2])]]
            out.append(r[3] * v[0] + r[4] * v[1] + r[5] * v[2] + np.array(r[6:9]) * sc)
    PV, PT, PF = load_obj(obj, groups=None)
    return np.array(out), PT, PF
