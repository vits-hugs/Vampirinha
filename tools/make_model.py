#!/usr/bin/env python3
"""Modelo 3D da Vampirinha (models/vampirinha.glb), gerado por código.

Baseado na folha de referência (tools/ref/vampirinha_ref.png): cabelo preto comprido com franja,
pele pálida, olhos vermelhos grandes, orelhas pontudas, vestido preto com saia vermelha na frente,
mangas bufantes, capa preta forrada de vermelho com gola alta e botas.

Unidades em metros, Y para cima, ela olha para +Z. Precisa de: numpy, trimesh.

    python3 tools/make_model.py
"""
import math
import os

import numpy as np
import trimesh

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "models")

# ------------------------------------------------------------------ paleta (da folha de referência)
COL = {
    "skin": (236, 226, 238), "blush": (236, 170, 190), "hair": (30, 24, 36), "hair_hl": (70, 58, 90),
    "black": (28, 22, 30), "black_hl": (52, 40, 56), "red": (150, 18, 40), "red_dark": (95, 10, 28),
    "lining": (165, 20, 45), "white": (245, 242, 248), "iris": (200, 20, 40), "pupil": (25, 4, 10),
    "lash": (14, 10, 18), "lips": (150, 60, 80), "boot": (40, 26, 32), "gem": (220, 30, 60), "nail": (120, 12, 30),
}


def lin(c):
    """sRGB 0..255 -> linear 0..1 (o glTF guarda as cores em espaço linear)."""
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def material(name, col, rough=0.75, metal=0.0, emissive=None, double=False):
    m = trimesh.visual.material.PBRMaterial(
        name=name, baseColorFactor=[lin(c) for c in col] + [1.0], roughnessFactor=rough, metallicFactor=metal,
        doubleSided=double)
    if emissive:
        m.emissiveFactor = [lin(c) for c in emissive]
    return m


# ------------------------------------------------------------------ geometria
def grid_faces(rows, cols, wrap=False):
    """Faces de uma grade rows x cols de vértices (fecha em volta se wrap)."""
    f = []
    cc = cols if wrap else cols - 1
    for i in range(rows - 1):
        for j in range(cc):
            a = i * cols + j
            b = i * cols + (j + 1) % cols
            c = (i + 1) * cols + (j + 1) % cols
            d = (i + 1) * cols + j
            f += [(a, d, c), (a, c, b)]
    return f


def lathe(profile, seg=48, sx=1.0, sz=1.0, rmod=None, center=(0, 0, 0), a0=0.0, a1=math.tau, cap_top=False,
          cap_bottom=False):
    """Sólido de revolução em volta de Y. profile: [(raio, y)] de baixo para cima.
    rmod(theta, y, t) multiplica o raio (babados, busto...). Ângulo 90° = frente (+Z)."""
    full = abs(a1 - a0 - math.tau) < 1e-6
    n = seg if full else seg + 1
    verts = []
    for k, (r, y) in enumerate(profile):
        t = k / (len(profile) - 1)
        for j in range(n):
            th = a0 + (a1 - a0) * j / seg
            rr = r * (rmod(th, y, t) if rmod else 1.0)
            verts.append((center[0] + math.cos(th) * rr * sx, center[1] + y, center[2] + math.sin(th) * rr * sz))
    faces = grid_faces(len(profile), n, wrap=full)
    verts = np.array(verts)
    if cap_top or cap_bottom:
        for flag, row, y in ((cap_bottom, 0, profile[0][1]), (cap_top, len(profile) - 1, profile[-1][1])):
            if flag:
                ci = len(verts)
                verts = np.vstack([verts, [(center[0], center[1] + y, center[2])]])
                for j in range(n if full else n - 1):
                    a = row * n + j
                    b = row * n + (j + 1) % n
                    faces.append((ci, a, b) if row == 0 else (ci, b, a))
    return trimesh.Trimesh(verts, faces, process=False)


def ellipsoid(c, r, seg=32, rings=20, deform=None):
    prof = []
    for i in range(rings + 1):
        phi = -math.pi / 2 + math.pi * i / rings
        prof.append((max(1e-4, math.cos(phi)), math.sin(phi)))
    m = lathe(prof, seg)
    v = m.vertices * np.array(r)
    if deform:  # deform recebe o ponto relativo ao centro
        v = np.array([deform(p) for p in v])
    m.vertices = v + np.array(c)
    return m


def frames(path):
    """Referenciais (tangente, normal, binormal) por transporte paralelo ao longo do caminho."""
    path = np.asarray(path, float)
    T = np.gradient(path, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    up = np.array([0, 0, 1.0]) if abs(T[0][2]) < 0.9 else np.array([1.0, 0, 0])
    N = [np.cross(T[0], up)]
    N[0] /= np.linalg.norm(N[0])
    for i in range(1, len(path)):
        v = np.cross(T[i - 1], T[i])
        n = N[-1]
        if np.linalg.norm(v) > 1e-8:
            ax = v / np.linalg.norm(v)
            ang = math.acos(max(-1, min(1, float(np.dot(T[i - 1], T[i])))))
            n = n * math.cos(ang) + np.cross(ax, n) * math.sin(ang) + ax * np.dot(ax, n) * (1 - math.cos(ang))
        N.append(n / np.linalg.norm(n))
    N = np.array(N)
    B = np.cross(T, N)
    return T, N, B


def tube(path, radii, seg=16, flat=1.0, flat_dir=None, caps=True, twist=0.0):
    """Tubo ao longo de um caminho (lista de pontos 3D) com raio variável.
    flat < 1 achata a seção (mechas de cabelo); flat_dir escolhe a direção achatada."""
    path = np.asarray(path, float)
    radii = np.broadcast_to(np.asarray(radii, float), (len(path),))
    T, N, B = frames(path)
    if flat_dir is not None:  # alinha o lado achatado com uma direção dada (ex.: para fora da cabeça)
        fd = np.asarray(flat_dir, float)
        for i in range(len(path)):
            d = fd - T[i] * np.dot(fd, T[i])
            if np.linalg.norm(d) > 1e-6:
                N[i] = d / np.linalg.norm(d)
                B[i] = np.cross(T[i], N[i])
    verts = []
    for i, p in enumerate(path):
        for j in range(seg):
            a = math.tau * j / seg + twist * i / max(1, len(path) - 1)
            verts.append(p + (N[i] * math.cos(a) * flat + B[i] * math.sin(a)) * radii[i])
    faces = [(a, c, b) for a, b, c in grid_faces(len(path), seg, wrap=True)]  # normais para fora
    verts = np.array(verts)
    if caps:
        for row, sign in ((0, -1), (len(path) - 1, 1)):
            ci = len(verts)
            verts = np.vstack([verts, path[row]])
            for j in range(seg):
                a = row * seg + j
                b = row * seg + (j + 1) % seg
                faces.append((ci, b, a) if sign < 0 else (ci, a, b))
    m = trimesh.Trimesh(verts, faces, process=False)
    m.fix_normals() if False else None
    return m


def bezier(p0, p1, p2, p3, n=16):
    p0, p1, p2, p3 = (np.asarray(p, float) for p in (p0, p1, p2, p3))
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def sheet(fn, nu, nv, thick=0.004, flip=False):
    """Superfície dupla (frente/verso) definida por fn(u, v) -> (ponto, normal aproximada).
    Devolve (lado de fora, lado de dentro) para materiais diferentes (capa preta forrada de vermelho)."""
    P = np.zeros((nv, nu, 3))
    for i in range(nv):
        for j in range(nu):
            P[i, j] = fn(j / (nu - 1), i / (nv - 1))
    # normais pela grade
    du = np.gradient(P, axis=1)
    dv = np.gradient(P, axis=0)
    Nn = np.cross(dv, du)
    Nn /= np.maximum(np.linalg.norm(Nn, axis=2, keepdims=True), 1e-9)
    faces = grid_faces(nv, nu)
    if not flip:
        Nn = -Nn
        faces = [(a, c, b) for a, b, c in faces]
    outer = trimesh.Trimesh((P + Nn * thick / 2).reshape(-1, 3), faces, process=False)
    inner = trimesh.Trimesh((P - Nn * thick / 2).reshape(-1, 3), [(a, c, b) for a, b, c in faces], process=False)
    return outer, inner


def rot_y(m, ang, pivot=(0, 0, 0)):
    R = trimesh.transformations.rotation_matrix(ang, [0, 1, 0], pivot)
    m.apply_transform(R)
    return m


def mirror_x(m):
    m2 = m.copy()
    m2.vertices[:, 0] *= -1
    m2.faces = m2.faces[:, ::-1]
    return m2


# ------------------------------------------------------------------ medidas (altura ~1,62 m)
HEAD_C = np.array([0.0, 1.475, 0.0])
HEAD_R = np.array([0.084, 0.106, 0.092])


def head_surface(x, y):
    """z da superfície da frente da cabeça (aprox.) para colar olhos/boca no rosto."""
    dx = (x - HEAD_C[0]) / HEAD_R[0]
    dy = (y - HEAD_C[1]) / HEAD_R[1]
    taper = 1.0 if dy > 0 else 1 - 0.35 * dy * dy
    v = max(0.0, 1 - dx * dx / (taper * taper) - dy * dy)
    return HEAD_C[2] + HEAD_R[2] * taper * math.sqrt(v)


def build():
    parts = {k: [] for k in COL}

    def add(key, m):
        parts[key].append(m)

    # ---------------- cabeça (crânio + queixo afinado)
    def head_def(p):  # p relativo ao centro da cabeça (m): afina a parte de baixo até o queixo
        x, y, z = p
        dy = y / HEAD_R[1]
        if dy < 0:
            k = 1 - 0.35 * dy * dy
            x *= k
            z *= k
        return (x, y, z)
    add("skin", ellipsoid(HEAD_C, HEAD_R, 40, 28, head_def))
    add("skin", tube([(0, 1.30, -0.012), (0, 1.35, -0.014), (0, 1.39, -0.02)], [0.031, 0.027, 0.026], 20))   # pescoço

    # ---------------- olhos de anime (branco, íris vermelha, pupila, brilhos, cílios)
    for s in (-1, 1):
        ex, ey = s * 0.036, 1.462
        ez = head_surface(ex, ey) - 0.001
        yaw = math.atan2(ex, 0.09)

        def put(m, yaw=yaw):
            return rot_y(m, yaw, (ex, ey, ez))
        add("white", put(ellipsoid((ex, ey, ez), (0.021, 0.019, 0.0035), 20, 10)))
        add("iris", put(ellipsoid((ex, ey - 0.002, ez + 0.0015), (0.0135, 0.0175, 0.003), 20, 10)))
        add("pupil", put(ellipsoid((ex, ey - 0.002, ez + 0.003), (0.004, 0.011, 0.0018), 12, 8)))
        add("white", put(ellipsoid((ex - s * 0.005, ey + 0.006, ez + 0.0042), (0.0045, 0.0045, 0.0012), 10, 6)))
        add("white", put(ellipsoid((ex + s * 0.004, ey - 0.009, ez + 0.004), (0.002, 0.002, 0.001), 8, 5)))
        # cílio superior grosso, colado na superfície do rosto, com pontinha para fora
        lash2d = bezier((ex - s * 0.023, ey + 0.006), (ex - s * 0.008, ey + 0.022), (ex + s * 0.013, ey + 0.021),
                        (ex + s * 0.029, ey + 0.006), 14).tolist() + [(ex + s * 0.034, ey + 0.0)]
        lash = [(x, y, head_surface(x, y) + 0.0035) for x, y in lash2d]
        add("lash", tube(lash, np.linspace(0.0016, 0.0026, len(lash)), 8))
        low2d = bezier((ex + s * 0.004, ey - 0.019), (ex + s * 0.012, ey - 0.018), (ex + s * 0.018, ey - 0.014),
                       (ex + s * 0.021, ey - 0.01), 6)
        add("lash", tube([(x, y, head_surface(x, y) + 0.003) for x, y in low2d], 0.0009, 6))
        add("blush", put(ellipsoid((s * 0.046, 1.432, head_surface(s * 0.046, 1.432)), (0.012, 0.005, 0.002), 12, 6)))
    # nariz, boca e presinha
    add("skin", ellipsoid((0, 1.437, head_surface(0, 1.437) + 0.002), (0.004, 0.006, 0.004), 10, 6))
    mz = head_surface(0, 1.413) + 0.001
    add("lips", tube(bezier((-0.012, 1.415, mz - 0.003), (-0.004, 1.411, mz), (0.004, 1.411, mz), (0.012, 1.416, mz - 0.003), 10),
                     0.0014, 6))
    fang = trimesh.creation.cone(0.0022, 0.007, sections=10)
    fang.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
    fang.apply_translation((0.007, 1.4135, mz))
    add("white", fang)

    # ---------------- orelhas pontudas (saem para os lados e para trás, apontando para cima)
    for s in (-1, 1):
        base = np.array([s * 0.080, 1.465, -0.005])
        tip = base + np.array([s * 0.04, 0.032, -0.03])
        ear = tube(bezier(base, base + (tip - base) * 0.3 + (0, -0.01, 0), base + (tip - base) * 0.7, tip, 10),
                   [0.012, 0.013, 0.012, 0.011, 0.009, 0.008, 0.006, 0.0045, 0.003, 0.001], 12, flat=0.35,
                   flat_dir=(0, 0, 1))
        add("skin", ear)

    # ---------------- cabelo
    # calota: elipsoide um pouco maior, sem a região do rosto
    cap = ellipsoid(HEAD_C + (0, 0.008, -0.004), HEAD_R * (1.08, 1.06, 1.08), 40, 28)
    cen = cap.triangles_center
    rel = cen - HEAD_C
    keep = ~((rel[:, 2] > 0.02) & (rel[:, 1] < 0.045)) & (rel[:, 1] > -0.07)
    cap.update_faces(keep)
    cap.remove_unreferenced_vertices()
    add("hair", cap)

    def strand(p0, p1, p2, p3, w0, w1, n=16, flat=0.35, out=None, key="hair"):
        pts = bezier(p0, p1, p2, p3, n)
        radii = np.linspace(w0, w1, n) * np.sin(np.linspace(0.35, math.pi * 0.98, n)) ** 0.35
        add(key, tube(pts, radii, 10, flat=flat, flat_dir=out))

    # franja: mechas pontudas caindo sobre a testa até as sobrancelhas
    for k in range(9):
        u = (k - 4) / 4.0
        x0 = u * 0.06
        top = HEAD_C + (x0 * 0.6, 0.105, 0.04)
        z_end = head_surface(u * 0.07, 1.49) + 0.012
        end = (u * 0.072 + 0.006 * math.sin(k * 2.1), 1.488 - 0.012 * (1 - abs(u)) - 0.008 * (k % 2), z_end)
        mid1 = (x0 * 0.9, 1.585, 0.075)
        mid2 = (u * 0.072, 1.535, z_end + 0.012)
        strand(top, mid1, mid2, end, 0.020, 0.003, 14, 0.3, out=(0, 0.3, 1))
    # mechas laterais emoldurando o rosto, até o peito
    for s in (-1, 1):
        for k, (dx, ln) in enumerate(((0.0, 0.0), (0.012, 0.05))):
            p0 = (s * (0.072 - dx), 1.54, 0.045)
            strand(p0, (s * (0.092 - dx), 1.47, 0.07), (s * (0.09 - dx), 1.36, 0.06 - k * 0.02),
                   (s * (0.08 - dx), 1.25 - ln, 0.045 - k * 0.025), 0.019, 0.004, 18, 0.35, out=(s, 0, 0.4))
    # cabelo comprido de trás: muitas mechas até a cintura, abrindo um pouco
    for k in range(17):
        u = (k - 8) / 8.0
        ang = math.pi / 2 + u * 2.0           # em volta da nuca (frente = 90°)
        ang = -math.pi / 2 + u * 1.55         # lado de trás
        r0 = 0.07
        p0 = HEAD_C + (math.cos(ang) * r0, 0.07 - 0.03 * abs(u), math.sin(ang) * r0)
        spread = 1.0 + 0.6 * abs(u)
        p1 = HEAD_C + (math.cos(ang) * 0.115, -0.07, math.sin(ang) * 0.12)
        p2 = (math.cos(ang) * 0.17 * spread, 1.16, math.sin(ang) * 0.19 - 0.04)
        p3 = (math.cos(ang) * 0.19 * spread + 0.012 * math.sin(k * 1.7), 0.86 + 0.06 * abs(u) + 0.04 * (k % 3) / 2,
              math.sin(ang) * 0.17 - 0.12)
        strand(p0, p1, p2, p3, 0.034, 0.006, 22, 0.32, out=(math.cos(ang), 0, math.sin(ang)))
    # brilho frio no cabelo ("anel de anjo")

    # ---------------- tronco (corpete preto) com painel vermelho e broche
    def bust(th, y, t):
        front = max(0.0, math.sin(th))
        return 1 + 0.18 * front ** 3 * math.exp(-((y - 1.17) / 0.045) ** 2)
    torso = lathe([(0.088, 0.98), (0.086, 1.03), (0.096, 1.10), (0.112, 1.17), (0.118, 1.23), (0.112, 1.28),
                   (0.085, 1.315), (0.04, 1.335)], 44, sx=1.0, sz=0.72, rmod=bust)
    add("black", torso)
    panel = lathe([(0.0905, 0.985), (0.0885, 1.03), (0.0985, 1.10), (0.1135, 1.16)], 20, sz=0.735,
                  a0=math.radians(68), a1=math.radians(112))
    add("red", panel)
    for k in range(4):  # cordões do espartilho
        y = 1.0 + k * 0.035
        add("black_hl", tube([(-0.012, y, 0.07 + k * 0.002), (0.012, y + 0.02, 0.071 + k * 0.002)], 0.0016, 6))
    add("gem", ellipsoid((0, 1.255, 0.083), (0.012, 0.014, 0.008), 16, 10))
    # gola de babado no pescoço (preta, como na referência)
    add("black", lathe([(0.04, 1.30), (0.046, 1.318), (0.04, 1.336)], 24, center=(0, 0, -0.012),
                       rmod=lambda th, y, t: 1 + 0.08 * math.sin(th * 10)))

    # ---------------- saia: vermelha por baixo, sobressaia preta aberta na frente, babados na barra
    def ruffle(th, y, t):
        return 1 + 0.035 * math.sin(th * 18) * max(0.0, 1 - t * 4) + 0.02 * math.sin(th * 3 + 1)
    skirt_prof = [(0.36, 0.25), (0.34, 0.36), (0.30, 0.52), (0.24, 0.70), (0.17, 0.86), (0.115, 0.96), (0.09, 1.0)]
    add("red", lathe(skirt_prof, 72, sz=0.86, rmod=ruffle))
    add("red_dark", lathe([(0.37, 0.235), (0.365, 0.27)], 72, sz=0.87,
                          rmod=lambda th, y, t: 1 + 0.05 * math.sin(th * 26)))                      # anágua
    over = [(r * 1.035 + 0.004, y + (0.03 if y < 0.3 else 0)) for r, y in skirt_prof]
    add("black", lathe(over, 64, sz=0.88, rmod=ruffle, a0=math.radians(112), a1=math.radians(428)))
    add("black", lathe([(0.093, 0.985), (0.093, 1.015)], 40, sz=0.75))                              # cintura

    # ---------------- braços: ombro bufante, manga preta, punho vermelho, mão pálida com unhas vermelhas
    for s in (-1, 1):
        sh = np.array([s * 0.15, 1.27, -0.005])
        el = np.array([s * 0.205, 1.035, -0.02])
        wr = np.array([s * 0.225, 0.83, 0.035])
        add("black", ellipsoid(sh + (s * 0.012, 0.005, 0), (0.06, 0.055, 0.055), 24, 14))
        arm = np.vstack([bezier(sh, sh + (el - sh) * 0.5, el - (0, -0.03, 0), el, 8),
                         bezier(el, el + (wr - el) * 0.4, wr - (wr - el) * 0.2, wr, 8)[1:]])
        add("black", tube(arm, np.linspace(0.04, 0.03, len(arm)), 16))
        add("red", tube([wr + (0, 0.035, 0), wr - (0, 0.005, 0)], [0.034, 0.038], 16))                # punho
        hand_c = wr + (s * 0.004, -0.045, 0.005)
        add("skin", ellipsoid(hand_c, (0.019, 0.04, 0.03), 16, 10))
        for f in range(4):  # dedos com unhas pontudas
            fz = -0.015 + f * 0.011
            p0 = hand_c + (0, -0.03, fz)
            p3 = p0 + (s * 0.006, -0.042 + 0.004 * abs(f - 1.5), 0.012)
            pts = bezier(p0, p0 + (0, -0.015, 0.004), p3 + (0, 0.012, -0.004), p3, 8)
            add("skin", tube(pts, np.linspace(0.0065, 0.004, 8), 8))
            nail = trimesh.creation.cone(0.0045, 0.014, sections=8)
            nail.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1, 0, 0]))
            nail.apply_translation(p3 + (0, -0.001, 0))
            add("nail", nail)
        thumb = bezier(hand_c + (s * 0.012, -0.005, 0.02), hand_c + (s * 0.02, -0.025, 0.035),
                       hand_c + (s * 0.018, -0.045, 0.04), hand_c + (s * 0.012, -0.055, 0.04), 8)
        add("skin", tube(thumb, np.linspace(0.008, 0.0055, 8), 8))

    # ---------------- pernas (meia preta) e botas de cano alto com salto
    for s in (-1, 1):
        hip = (s * 0.07, 0.95, 0)
        knee = (s * 0.08, 0.52, 0.01)
        ank = (s * 0.085, 0.09, 0.0)
        leg = np.vstack([bezier(hip, (s * 0.075, 0.8, 0.01), (s * 0.08, 0.62, 0.02), knee, 8),
                         bezier(knee, (s * 0.082, 0.4, 0.0), (s * 0.085, 0.2, -0.005), ank, 8)[1:]])
        add("black", tube(leg, np.linspace(0.06, 0.034, len(leg)), 18))
        add("boot", tube([(s * 0.085, 0.055, 0.0), (s * 0.085, 0.2, -0.004), (s * 0.084, 0.33, 0.0)],
                         [0.042, 0.044, 0.05], 18))
        add("red_dark", tube([(s * 0.084, 0.315, 0.0), (s * 0.084, 0.335, 0.0)], 0.053, 18))      # borda da bota
        foot = ellipsoid((s * 0.085, 0.03, 0.05), (0.034, 0.03, 0.082), 20, 12,
                         deform=lambda p: (p[0] * (1 - 0.35 * max(0.0, p[2] / 0.082)), max(p[1], -0.026), p[2]))
        add("boot", foot)
        heel = trimesh.creation.box((0.034, 0.05, 0.035))
        heel.apply_translation((s * 0.085, 0.025, -0.035))
        add("boot", heel)

    # ---------------- capa: preta por fora, forrada de vermelho, barra rasgada em pontas
    def cape_fn(u, v):
        ang = -math.pi / 2 + (u - 0.5) * math.radians(250)          # em volta das costas
        y = 1.30 - v * 0.98
        r = 0.135 + v * 0.30 + 0.025 * math.sin(u * 9.0 + v * 2) * v
        # pontas rasgadas na barra
        jag = (abs(((u * 7) % 1) - 0.5) * 2) ** 1.5
        y -= v ** 4 * 0.10 * jag
        side = math.cos(ang)
        return (side * r * 1.15, y, math.sin(ang) * r * 0.95 - 0.03 * v)
    outer, inner = sheet(cape_fn, 56, 40, 0.006)
    add("black", outer)
    add("lining", inner)
    # gola alta: abre para trás e para cima, com pontas
    def collar_fn(u, v):
        ang = -math.pi / 2 + (u - 0.5) * math.radians(230)
        y = 1.30 + v * 0.17
        r = 0.072 + v * 0.065 + 0.02 * v * abs(math.cos(ang))
        y += v * 0.05 * (abs(((u * 4) % 1) - 0.5) * 2)                 # pontas
        return (math.cos(ang) * r * 1.2, y, math.sin(ang) * r - 0.01)
    outer, inner = sheet(collar_fn, 40, 10, 0.005, flip=True)
    add("black", outer)
    add("lining", inner)

    # ---------------- montar a cena com um material por cor
    scene = trimesh.Scene()
    emis = {"iris": (90, 0, 10), "gem": (60, 0, 10)}
    rough = {"hair": 0.45, "hair_hl": 0.3, "white": 0.3, "iris": 0.25, "gem": 0.2, "boot": 0.5, "nail": 0.3}
    double = {"hair", "red", "black", "lining", "red_dark"}
    for key, meshes in parts.items():
        if not meshes:
            continue
        m = trimesh.util.concatenate(meshes)
        m.merge_vertices()
        m.visual = trimesh.visual.TextureVisuals(material=material(key, COL[key], rough.get(key, 0.75), 0.0,
                                                                   emis.get(key), key in double))
        scene.add_geometry(m, node_name=key, geom_name=key)
    return scene


def main():
    os.makedirs(OUT, exist_ok=True)
    scene = build()
    path = os.path.join(OUT, "vampirinha.glb")
    scene.export(path, file_type="glb", include_normals=True)
    tris = sum(len(g.faces) for g in scene.geometry.values())
    print("modelo salvo em %s (%d triângulos, %.0f KB)" % (path, tris, os.path.getsize(path) / 1024))


if __name__ == "__main__":
    main()
