"""Utilidades de malha para o gerador do modelo 3D."""
import numpy as np


def vertex_normals(V, F):
    n = np.zeros_like(V)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    for k in range(3):
        np.add.at(n, F[:, k], fn)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    return n / ln


def split_uv(V, VT, faces):
    """Faces do OBJ (índices de vértice e de uv por canto) -> malha com 1 uv por vértice.

    Devolve (pos, uv, tris, origem) — origem é o índice do vértice original de cada novo vértice,
    para calcular normais suaves através das costuras de uv."""
    key = {}
    org, uvs = [], []
    tris = []
    for vi, ti in faces:
        ids = []
        for v, t in zip(vi, ti):
            k = (v, t)
            if k not in key:
                key[k] = len(org)
                org.append(v)
                uvs.append(VT[t] if t >= 0 else (0.0, 0.0))
            ids.append(key[k])
        if len(ids) == 4:
            tris += [[ids[0], ids[1], ids[2]], [ids[0], ids[2], ids[3]]]
        else:
            tris.append(ids[:3])
    org = np.array(org)
    return V[org], np.array(uvs, float), np.array(tris, int), org


def laplacian_smooth(V, F, iters=5, lam=0.5, fixed=None):
    n = len(V)
    import scipy.sparse as sp
    i = np.concatenate([F[:, 0], F[:, 1], F[:, 2], F[:, 1], F[:, 2], F[:, 0]])
    j = np.concatenate([F[:, 1], F[:, 2], F[:, 0], F[:, 0], F[:, 1], F[:, 2]])
    A = sp.coo_matrix((np.ones(len(i)), (i, j)), shape=(n, n)).tocsr()
    A.data[:] = 1
    deg = np.asarray(A.sum(1)).ravel()
    deg[deg == 0] = 1
    V = V.copy()
    for _ in range(iters):
        avg = (A @ V) / deg[:, None]
        nv = V + lam * (avg - V)
        if fixed is not None:
            nv[fixed] = V[fixed]
        V = nv
    return V


def boundary_vertices(F):
    from collections import Counter
    e = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1)
    c = Counter(map(tuple, e))
    return np.unique([v for k, n in c.items() if n == 1 for v in k])


def grid_faces(rows, cols, wrap=False):
    f = []
    cc = cols if wrap else cols - 1
    for r in range(rows - 1):
        for c in range(cc):
            a = r * cols + c
            b = r * cols + (c + 1) % cols
            f += [[a, a + cols, b], [b, a + cols, b + cols]]
    return np.array(f, int)


def ribbons(P, width, up):
    """Fitas para fios/mechas. P: (S, n, 3) caminhos; width: (S, n) larguras; up: (S, n, 3) normal desejada.

    Devolve (V, F, uv, N) — u atravessa a fita, v vai da raiz (0) à ponta (1)."""
    S, n, _ = P.shape
    T = np.gradient(P, axis=1)
    T /= np.linalg.norm(T, axis=2, keepdims=True) + 1e-12
    side = np.cross(T, up)
    side /= np.linalg.norm(side, axis=2, keepdims=True) + 1e-12
    nrm = np.cross(side, T)
    nrm /= np.linalg.norm(nrm, axis=2, keepdims=True) + 1e-12
    h = (width / 2)[..., None] * side
    V = np.stack([P - h, P + h], axis=2).reshape(-1, 3)              # (S, n, 2)
    N = np.repeat(nrm[:, :, None, :], 2, axis=2).reshape(-1, 3)
    v = np.linspace(0, 1, n)
    uv = np.zeros((S, n, 2, 2))
    uv[:, :, 0, 0] = 0.0
    uv[:, :, 1, 0] = 1.0
    uv[:, :, :, 1] = 1 - v[None, :, None]                            # textura: v=1 em cima (raiz)
    F = []
    base = (np.arange(S) * n * 2)[:, None]
    i = np.arange(n - 1)[None, :] * 2 + base
    a, b, c, d = i, i + 1, i + 2, i + 3
    F = np.concatenate([np.stack([a, c, b], -1).reshape(-1, 3), np.stack([b, c, d], -1).reshape(-1, 3)])
    return V, F, uv.reshape(-1, 2), N
