#!/usr/bin/env python3
"""Vampirinha - jogo de ação top-down para desktop (Linux/pygame).

Controles e combos: veja o README.md.
"""
import math
import random
import sys

import pygame
from pygame.math import Vector2 as V2

# ---------------------------------------------------------------- constantes
W, H = 1280, 720
WORLD_W, WORLD_H = 2600, 1800
FPS = 60

TOOTH, ARM, LEG = "T", "A", "L"
ELEM_COLOR = {TOOTH: (245, 240, 220), ARM: (225, 70, 80), LEG: (110, 165, 255)}
ELEM_LABEL = {TOOTH: "dente", ARM: "braço", LEG: "perna"}

POWER_DMG = (1.0, 1.6, 2.3)    # repetir elemento fortalece
POWER_SIZE = (1.0, 1.3, 1.7)

BLOOD_MAX = 100.0
BLOOD_START = 50.0
BLOOD_DRAIN = 2.2              # sangue perdido por segundo
FRENZY_DRAIN = 10.0            # no frenesi a barra vira um cronômetro
FRENZY_END = 30.0              # o frenesi acaba quando a barra cai até aqui
BAT_REVERT_BLOOD = 35.0        # sangue ao voltar da forma de morcego
BAT_BITE_DAMAGE = 16
LIFESTEAL = 0.45              # fração do dano causado que vira sangue
FRENZY_SPEED = 1.35
FRENZY_DAMAGE = 1.5
PARRY_RADIUS = 230
MAX_ALIVE = 30

TOOTH_PTS = [(-0.5, -0.5), (0.5, -0.5), (0.45, 0.1), (0.2, 0.6), (0, 0.15), (-0.2, 0.6), (-0.45, 0.1)]
ARM_PTS = [(-0.6, -0.18), (0.2, -0.18), (0.2, -0.32), (0.62, -0.32), (0.62, 0.32), (0.2, 0.32), (0.2, 0.18), (-0.6, 0.18)]
LEG_PTS = [(-0.6, -0.16), (0.0, -0.16), (0.0, -0.32), (0.62, -0.32), (0.62, 0.16), (-0.6, 0.16)]

COMBO_NAMES = {
    "T": "Cuspe de dente", "A": "Golpe de braço", "L": "Dash",
    "TL": "Perna saltadora", "TA": "Braço bumerangue", "LT": "Dash + chuva de dentes",
    "LA": "Voadora", "AL": "Chute", "AT": "Soco com dente",
}
ROMAN = {1: "", 2: " II", 3: " III"}


# ------------------------------------------------------------------ helpers
def norm(v, default=(1, 0)):
    n = v.length()
    if n < 1e-6:
        return V2(default)
    return v / n


def rot_pts(pts, center, ang, scale):
    c, s = math.cos(ang), math.sin(ang)
    return [(center[0] + (x * c - y * s) * scale, center[1] + (x * s + y * c) * scale) for x, y in pts]


def in_cone(origin, facing, point, reach, arc_deg, pad=0.0):
    d = point - origin
    dist = d.length()
    if dist > reach + pad:
        return False
    if dist < 1e-6:
        return True
    diff = abs((math.degrees(math.atan2(d.y, d.x) - facing) + 180) % 360 - 180)
    slack = math.degrees(math.asin(min(1.0, pad / dist))) if pad else 0.0
    return diff <= arc_deg / 2 + slack


def parse_queue(q):
    order, counts = [], {}
    for e in q:
        if e not in counts:
            order.append(e)
            counts[e] = 0
        counts[e] += 1
    if len(order) == 1:
        power = counts[order[0]]
    else:
        power = min(3, counts[order[0]] + counts[order[1]] - 1)
    return order, max(1, min(3, power))


def combo_name(q):
    if not q:
        return ""
    order, power = parse_queue(q)
    key = order[0] if len(order) == 1 else order[0] + order[1]
    name = COMBO_NAMES[key]
    if list(q) == [TOOTH] * 3:
        name = "Dentão (ou PARRY se vier tiro)"
    else:
        name += ROMAN[power]
    if len(order) == 3:
        name += " + " + COMBO_NAMES[order[2]]
    return name


_fonts = {}


def font(size, bold=False):
    k = (size, bold)
    if k not in _fonts:
        _fonts[k] = pygame.font.SysFont("dejavusans,liberationsans,arial,helvetica", size, bold=bold)
    return _fonts[k]


def draw_text(surf, txt, size, color, pos, anchor="topleft", bold=False, shadow=True):
    f = font(size, bold)
    img = f.render(txt, True, color)
    r = img.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    if shadow:
        sh = f.render(txt, True, (0, 0, 0))
        surf.blit(sh, r.move(2, 2))
    surf.blit(img, r)
    return r


def draw_icon(surf, elem, center, size):
    col = ELEM_COLOR[elem]
    if elem == TOOTH:
        pts = rot_pts(TOOTH_PTS, center, 0, size)
    elif elem == ARM:
        pts = rot_pts(ARM_PTS, center, -0.7, size)
    else:
        pts = rot_pts(LEG_PTS, center, -1.1, size)
    pygame.draw.polygon(surf, col, pts)
    pygame.draw.polygon(surf, (20, 10, 20), pts, 2)


# ----------------------------------------------------------------- entidades
class Proj:
    """Projétil (dente, perna, braço bumerangue, tiro devolvido...)."""

    def __init__(self, kind, pos, vel, dmg, r, life, pierce=0, knock=60, friendly=True):
        self.kind = kind
        self.pos = V2(pos)
        self.vel = V2(vel)
        self.dmg = dmg
        self.r = r
        self.life = life
        self.pierce = pierce
        self.knock = knock
        self.friendly = friendly
        self.hit = set()
        self.dead = False
        self.age = 0.0
        self.leap = False
        # bumerangue
        self.origin = V2(pos)
        self.maxdist = 400
        self.speed = vel.length() if vel.length() else 1
        self.returning = False
        self.spin = random.uniform(0, 6)

    def update(self, g, dt):
        self.age += dt
        if self.kind == "arm":
            self.spin += 16 * dt
            if not self.returning:
                self.pos += self.vel * dt
                if (self.pos - self.origin).length() >= self.maxdist or self.age > 1.6:
                    self.returning = True
                    self.hit.clear()
            else:
                to = g.player.pos - self.pos
                d = to.length()
                if d < 28 or self.age > 4:
                    self.dead = True
                    return
                self.vel = to / d * self.speed * 1.1
                self.pos += self.vel * dt
            return
        self.pos += self.vel * dt
        self.life -= dt
        if self.life <= 0 or not (-60 < self.pos.x < WORLD_W + 60 and -60 < self.pos.y < WORLD_H + 60):
            self.dead = True

    def draw(self, s, cam):
        sp = self.pos - cam
        if not (-40 < sp.x < W + 40 and -40 < sp.y < H + 40):
            return
        ang = math.atan2(self.vel.y, self.vel.x) if self.vel.length() else 0
        if self.kind == "tooth":
            pts = rot_pts(TOOTH_PTS, sp, ang - math.pi / 2, self.r * 2.1)
            pygame.draw.polygon(s, ELEM_COLOR[TOOTH], pts)
            pygame.draw.polygon(s, (60, 50, 50), pts, 1)
        elif self.kind == "leg":
            pts = rot_pts(LEG_PTS, sp, ang, self.r * 2.2)
            pygame.draw.polygon(s, ELEM_COLOR[LEG], pts)
            pygame.draw.polygon(s, (10, 20, 50), pts, 2)
        elif self.kind == "arm":
            pts = rot_pts(ARM_PTS, sp, self.spin, self.r * 2.4)
            pygame.draw.polygon(s, ELEM_COLOR[ARM], pts)
            pygame.draw.polygon(s, (60, 10, 20), pts, 2)
        elif self.kind == "bullet":  # tiro devolvido
            pygame.draw.circle(s, (255, 150, 40), sp, self.r + 4)
            pygame.draw.circle(s, (255, 235, 150), sp, self.r)
        else:  # tiro inimigo
            pygame.draw.circle(s, (120, 20, 20), sp, self.r + 3)
            pygame.draw.circle(s, (255, 210, 90), sp, self.r)


def wrap_angle(a):
    return (a + math.pi) % math.tau - math.pi


def ellipse_pts(center, rx, ry, ang, n=16):
    c, s = math.cos(ang), math.sin(ang)
    pts = []
    for i in range(n):
        t = math.tau * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        pts.append((center[0] + x * c - y * s, center[1] + x * s + y * c))
    return pts


class Enemy:
    """Inimigos: 'sword' (espadachim), 'gun' (atirador) e 'dog' (cachorro).

    O papel (role) e a posição desejada (slot_angle / ring_r) são decididos pelo
    coordenador Game.plan_ai; aqui cada inimigo só executa o comportamento.
    """

    def __init__(self, kind, pos):
        self.kind = kind
        self.pos = V2(pos)
        self.vel = V2()
        if kind == "sword":
            self.hp = self.max_hp = 34
            self.speed = random.uniform(88, 112)
            self.r = 16
        elif kind == "dog":
            self.hp = self.max_hp = 18
            self.speed = random.uniform(190, 215)
            self.r = 12
        elif kind == "boss":
            self.hp = self.max_hp = 700
            self.speed = 70
            self.r = 52
        else:
            self.hp = self.max_hp = 24
            self.speed = random.uniform(66, 80)
            self.r = 15
        self.mass = 10.0 if kind == "boss" else 1.0
        self.knock_resist = 0.12 if kind == "boss" else 1.0
        self.stun_resist = 0.0 if kind == "boss" else 1.0
        self.lifesteal_mult = 0.6 if kind == "boss" else 1.0
        self.special = 0.0
        self.stun = 0.0
        self.flash = 0.0
        self.cd = random.uniform(0.6, 1.6)
        self.windup = 0.0
        self.aim = V2(1, 0)
        self.facing = 0.0
        self.dead = False
        self.strafe = random.choice((-1, 1))
        # tática
        self.role = "ring"          # sword: engage | flank | ring ; dog/gun: ring
        self.slot_angle = random.uniform(0, math.tau)
        self.ring_r = 240.0
        self.state = "circle"       # cachorro: circle | windup | lunge | recover
        self.t = 0.0
        self.hit_done = False

    # ---- movimento tático
    def steer(self, g, target, speed, dt, sep_r=70):
        """Anda até target mantendo distância dos outros inimigos."""
        to = target - self.pos
        d = to.length()
        v = to / d if d > 1e-3 else V2()
        push = V2()
        for o in g.enemies:
            if o is self or o.dead:
                continue
            dd = self.pos - o.pos
            dl = dd.length()
            rad = sep_r if o.kind == self.kind else min(sep_r, 60)
            if o.kind == "boss":
                rad = o.r + 45
            if 0 < dl < rad:
                push += dd / dl * (1 - dl / rad)
        v += push * 1.6
        n = v.length()
        if n > 1e-3:
            slow = min(1.0, d / 25) if d < 25 else 1.0
            self.pos += v / n * speed * slow * dt

    def orbit_target(self, g, target_angle, ring_r, final_r):
        """Contorna o jogador em arco (sem passar pela frente dele) até o ângulo desejado."""
        p = g.player.pos
        rel = self.pos - p
        cur = math.atan2(rel.y, rel.x)
        diff = wrap_angle(target_angle - cur)
        if abs(diff) > 0.55:
            a = cur + (0.45 if diff > 0 else -0.45)
            return p + V2(math.cos(a), math.sin(a)) * ring_r
        return p + V2(math.cos(target_angle), math.sin(target_angle)) * final_r

    # ---- atualização
    def update(self, g, dt):
        self.flash = max(0.0, self.flash - dt)
        self.pos += self.vel * dt
        self.vel *= max(0.0, 1 - 8 * dt)
        self.pos.x = max(20, min(WORLD_W - 20, self.pos.x))
        self.pos.y = max(20, min(WORLD_H - 20, self.pos.y))
        if self.stun > 0:
            self.stun -= dt
            self.windup = 0
            if self.kind == "dog":
                self.state = "circle"
                self.cd = max(self.cd, 0.5)
            return
        to = g.player.pos - self.pos
        d = to.length() or 0.001
        dirv = to / d
        if not (self.kind == "dog" and self.state == "lunge"):
            self.facing = math.atan2(dirv.y, dirv.x)
        self.cd -= dt
        if self.kind == "sword":
            self.ai_sword(g, dt, d, dirv)
        elif self.kind == "dog":
            self.ai_dog(g, dt, d, dirv)
        else:
            self.ai_gun(g, dt, d, dirv)

    def ai_sword(self, g, dt, d, dirv):
        p = g.player.pos
        if self.windup > 0:
            self.windup -= dt
            if self.windup <= 0:
                ang = math.atan2(self.aim.y, self.aim.x)
                g.add_fx("cone", self.pos, ang, 78, 0.16, (235, 235, 245), arc=130)
                if in_cone(self.pos, ang, p, 78, 130, g.player.r):
                    g.hurt_player(10, self.pos)
                self.cd = random.uniform(1.0, 1.4)
            return
        if self.role == "ring":
            tgt = p + V2(math.cos(self.slot_angle), math.sin(self.slot_angle)) * self.ring_r
            self.steer(g, tgt, self.speed * 0.9, dt, 80)
        elif self.role == "flank":
            tgt = self.orbit_target(g, self.slot_angle, 240, 54)
            self.steer(g, tgt, self.speed * 1.05, dt, 55)
        elif d > 50:
            self.steer(g, p, self.speed, dt, 70)
        if self.role != "ring" and d < 56 and self.cd <= 0:
            self.windup = 0.4
            self.aim = dirv

    def ai_dog(self, g, dt, d, dirv):
        p = g.player.pos
        if self.state == "windup":
            self.windup -= dt
            if self.windup > 0.1:
                self.aim = dirv
            if self.windup <= 0:
                self.state = "lunge"
                self.t = 0.45
                self.hit_done = False
                self.aim = norm(p + g.player.vel * 0.2 - self.pos)
            return
        if self.state == "lunge":
            self.pos += self.aim * 560 * dt
            self.facing = math.atan2(self.aim.y, self.aim.x)
            self.t -= dt
            if not self.hit_done and d < self.r + g.player.r + 12:
                self.hit_done = True
                g.hurt_player(9, self.pos)
            if self.t <= 0:
                self.state = "recover"
                self.t = 0.7
                self.cd = random.uniform(1.2, 2.0)
            return
        if self.state == "recover":
            self.t -= dt
            self.pos -= dirv * self.speed * 0.5 * dt
            if self.t <= 0:
                self.state = "circle"
            return
        tgt = self.orbit_target(g, self.slot_angle, 230, 190)
        self.steer(g, tgt, self.speed, dt, 60)
        if self.cd <= 0 and 90 < d < 260:
            busy = sum(1 for e in g.enemies if e is not self and e.kind == "dog" and e.state in ("windup", "lunge"))
            if busy < 2:
                self.state = "windup"
                self.windup = 0.4
                self.aim = dirv

    def ai_gun(self, g, dt, d, dirv):
        p = g.player.pos
        if self.windup > 0:
            self.windup -= dt
            if self.windup > 0.15:  # mira com um pouco de antecipação do movimento
                self.aim = norm(p + g.player.vel * 0.45 - self.pos)
            if self.windup <= 0:
                g.ebullets.append(Proj("ebullet", self.pos + self.aim * 22, self.aim * 360, 8, 6, 3.2, friendly=False))
                self.cd = random.uniform(1.8, 2.6)
            return
        perp = V2(-dirv.y, dirv.x) * self.strafe
        tgt = p + V2(math.cos(self.slot_angle), math.sin(self.slot_angle)) * self.ring_r
        tgt.x = max(90, min(WORLD_W - 90, tgt.x))
        tgt.y = max(90, min(WORLD_H - 90, tgt.y))
        if d < 230:  # recua em diagonal
            self.steer(g, self.pos + (-dirv + perp * 0.6) * 100, self.speed * 1.1, dt, 120)
        elif (tgt - self.pos).length() > 30:
            self.steer(g, tgt, self.speed, dt, 120)
        else:
            self.steer(g, self.pos + perp * 60, self.speed * 0.35, dt, 120)
        if self.cd <= 0 and d < 650 and g.gun_cd <= 0:
            if g.line_blocked(self):
                self.strafe = -self.strafe  # aliado na frente: muda de posição em vez de atirar
                self.cd = 0.35
            else:
                self.windup = 0.5
                self.aim = norm(p + g.player.vel * 0.45 - self.pos)
                g.gun_cd = 0.8

    # ---- desenho
    def draw(self, s, cam):
        sp = self.pos - cam
        if not (-60 < sp.x < W + 60 and -60 < sp.y < H + 60):
            return
        pygame.draw.ellipse(s, (8, 6, 12), (sp.x - self.r, sp.y + self.r * 0.5, self.r * 2, self.r * 0.9))
        fl = self.flash > 0
        if self.kind == "dog":
            self.draw_dog(s, sp, fl)
        else:
            if self.kind == "sword":
                body, trim = ((255, 255, 255) if fl else (96, 110, 140)), (40, 48, 70)
            else:
                body, trim = ((255, 255, 255) if fl else (140, 100, 70)), (60, 40, 25)
            pygame.draw.circle(s, trim, sp, self.r + 2)
            pygame.draw.circle(s, body, sp, self.r)
            fv = V2(math.cos(self.facing), math.sin(self.facing))
            pygame.draw.circle(s, (230, 200, 170), sp + fv * 5, 8)
            pygame.draw.circle(s, (20, 20, 20), sp + fv * 9 + V2(-fv.y, fv.x) * 3, 2)
            pygame.draw.circle(s, (20, 20, 20), sp + fv * 9 - V2(-fv.y, fv.x) * 3, 2)
            if self.kind == "sword":
                ang = math.atan2(self.aim.y, self.aim.x) if self.windup > 0 else self.facing
                raise_ = 0.9 if self.windup > 0 else 0.0
                base = sp + V2(math.cos(ang), math.sin(ang)) * 12
                tip = sp + V2(math.cos(ang + raise_ * 0.6), math.sin(ang + raise_ * 0.6)) * 42
                pygame.draw.line(s, (210, 215, 225), base, tip, 4)
                if self.windup > 0:
                    pygame.draw.circle(s, (255, 60, 60), sp + V2(0, -self.r - 14), 5)
            else:
                gun_dir = self.aim if self.windup > 0 else fv
                tip = sp + gun_dir * 30
                pygame.draw.line(s, (40, 40, 45), sp + gun_dir * 8, tip, 6)
                if self.windup > 0:
                    pygame.draw.line(s, (255, 70, 70), tip, sp + gun_dir * 600, 1)
                    pygame.draw.circle(s, (255, 60, 60), sp + V2(0, -self.r - 14), 5)
        if self.hp < self.max_hp:
            w = 34
            pygame.draw.rect(s, (30, 10, 14), (sp.x - w / 2, sp.y - self.r - 10, w, 5))
            pygame.draw.rect(s, (200, 40, 50), (sp.x - w / 2, sp.y - self.r - 10, w * max(0, self.hp) / self.max_hp, 5))

    def draw_dog(self, s, sp, fl):
        fv = V2(math.cos(self.facing), math.sin(self.facing))
        perp = V2(-fv.y, fv.x)
        stretch = 1.3 if self.state == "lunge" else (0.82 if self.state == "windup" else 1.0)
        body = (255, 255, 255) if fl else (156, 110, 66)
        dark = (88, 56, 34)
        phase = pygame.time.get_ticks() / 70.0
        for i, (fo, side) in enumerate(((9, 1), (9, -1), (-9, 1), (-9, -1))):
            sw = math.sin(phase + i * 1.6) * 4 if self.state in ("circle", "lunge") else 0
            pygame.draw.circle(s, dark, sp + fv * (fo * stretch + sw) + perp * side * 6, 3)
        pygame.draw.polygon(s, dark, ellipse_pts(sp, 17 * stretch, 9.5, self.facing))
        pygame.draw.polygon(s, body, ellipse_pts(sp, 15 * stretch, 7.5, self.facing))
        tail_end = sp - fv * 24 * stretch + perp * math.sin(phase * 0.7) * 5
        pygame.draw.line(s, dark, sp - fv * 13 * stretch, tail_end, 3)
        head = sp + fv * 15 * stretch
        pygame.draw.circle(s, dark, head, 8)
        pygame.draw.circle(s, body, head, 6.5)
        pygame.draw.circle(s, dark, head + fv * 6, 3)
        for side in (1, -1):
            pygame.draw.polygon(s, dark, [head - fv * 2 + perp * side * 4, head - fv * 7 + perp * side * 8, head - fv * 5 + perp * side * 1])
            pygame.draw.circle(s, (20, 14, 10), head + fv * 2 + perp * side * 3, 1.5)
        if self.state == "windup":
            pygame.draw.circle(s, (255, 60, 60), sp + V2(0, -self.r - 14), 5)


BOSS_ATTACKS = {  # (aviso, golpe, recuperação) em segundos
    "jab": (0.50, 0.15, 0.40),
    "hook": (0.75, 0.25, 0.55),
    "slam": (1.00, 0.12, 0.80),
    "charge": (0.60, 0.50, 0.70),
    "rain": (1.10, 2.40, 0.90),
}
BOSS_REACH = 175           # alcance do soco/gancho a partir do centro do gigante
BOSS_SLAM_R = 200          # raio do soco no chão
BOSS_RAIN_TELEGRAPH = 0.85  # tempo de aviso de cada impacto da Chuva de Socos
BOSS_SPECIAL_RATE = 4.5    # % da barra de habilidade por segundo


def seg_dist(p, a, b):
    ab = b - a
    L2 = ab.length_squared()
    if L2 < 1e-6:
        return (p - a).length()
    t = max(0.0, min(1.0, (p - a).dot(ab) / L2))
    return (p - (a + ab * t)).length()


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


class Boss(Enemy):
    """Gigante: golpes de soco telegrafados e uma habilidade especial (Chuva de Socos)
    liberada quando a barra de habilidade enche."""

    def __init__(self, pos, hp):
        super().__init__("boss", pos)
        self.hp = self.max_hp = hp
        self.phase = "walk"        # walk | windup | strike | recover
        self.attack = None
        self.pt = 0.0              # tempo restante da fase
        self.pdur = 1.0            # duração da fase atual (aviso/recuperação)
        self.sdur = 0.1            # duração do golpe
        self.special = 0.0         # barra de habilidade (0..100)
        self.punch_side = 1
        self.anim = 0.0
        self.cd = 1.2
        self.charge_dir = V2(1, 0)

    @property
    def enraged(self):
        return self.hp < self.max_hp * 0.5

    # ---- comportamento
    def update(self, g, dt):
        self.flash = max(0.0, self.flash - dt)
        self.pos += self.vel * dt
        self.vel *= max(0.0, 1 - 8 * dt)
        self.anim += dt
        to = g.player.pos - self.pos
        d = to.length() or 0.001
        dirv = to / d
        self.cd -= dt
        rate = 0.8 if self.enraged else 1.0
        if self.phase == "walk":
            self.facing = math.atan2(dirv.y, dirv.x)
            self.special = min(100.0, self.special + dt * BOSS_SPECIAL_RATE * (1.5 if self.enraged else 1.0))
            if d > 125:
                self.pos += dirv * self.speed * (1.25 if self.enraged else 1.0) * dt
            if self.special >= 100:
                self.start("rain", dirv, rate)
            elif self.cd <= 0 and d < 440:
                self.start(self.pick_attack(d), dirv, rate)
        else:
            self.pt -= dt
            if self.phase == "windup":
                if self.attack != "rain" and self.pt > 0.12:  # acompanha o alvo até o último instante
                    self.aim = dirv
                    self.facing = math.atan2(dirv.y, dirv.x)
                if self.pt <= 0:
                    self.phase = "strike"
                    self.pt = self.sdur
                    self.on_strike(g, d)
            elif self.phase == "strike":
                self.strike(g, dt, d)
                if self.pt <= 0:
                    self.phase = "recover"
                    self.pdur = self.pt = BOSS_ATTACKS[self.attack][2] * rate
            elif self.pt <= 0:
                self.phase = "walk"
                self.attack = None
                self.cd = random.uniform(0.4, 0.9) * rate
        self.pos.x = max(self.r, min(WORLD_W - self.r, self.pos.x))
        self.pos.y = max(self.r, min(WORLD_H - self.r, self.pos.y))

    def pick_attack(self, d):
        if d < 190:
            return random.choice(["jab", "jab", "hook", "hook", "slam"])
        return random.choice(["charge", "charge", "slam" if d < 260 else "charge"])

    def start(self, attack, dirv, rate):
        self.attack = attack
        self.phase = "windup"
        self.pdur = self.pt = BOSS_ATTACKS[attack][0] * rate
        self.sdur = BOSS_ATTACKS[attack][1]
        self.aim = V2(dirv)
        self.facing = math.atan2(dirv.y, dirv.x)
        self.hit_done = False
        self.punch_side = -self.punch_side
        if attack == "rain":
            self.special = 0.0

    def on_strike(self, g, d):
        p = g.player
        a = self.attack
        if a == "slam":
            g.add_fx("ring", self.pos, 0, BOSS_SLAM_R, 0.45, (255, 140, 60))
            g.add_fx("disc", self.pos, 0, BOSS_SLAM_R, 0.2, (255, 120, 50))
            g.dust(self.pos + self.aim * 70, 20)
            g.shake = max(g.shake, 16)
            if d < BOSS_SLAM_R + p.r:
                g.hurt_player(20, self.pos, knock=520)
        elif a == "hook":
            g.add_fx("cone", self.pos, math.atan2(self.aim.y, self.aim.x), BOSS_REACH, 0.25, (255, 200, 150), arc=200)
        elif a == "charge":
            self.charge_dir = V2(self.aim)
        elif a == "rain":
            g.add_text(self.pos + V2(0, -90), "CHUVA DE SOCOS!", (255, 200, 120), 1.4, 30)
            for i in range(12):
                if i < 3:
                    off = V2(random.uniform(-45, 45), random.uniform(-45, 45))
                else:
                    ang = random.uniform(0, math.tau)
                    off = V2(math.cos(ang), math.sin(ang)) * random.uniform(80, 330)
                pos = p.pos + off
                pos.x = max(60, min(WORLD_W - 60, pos.x))
                pos.y = max(60, min(WORLD_H - 60, pos.y))
                delay = BOSS_RAIN_TELEGRAPH + i * 0.17
                g.hazards.append({"pos": pos, "r": 95, "t": delay, "dmg": 16, "done": False})

    def strike(self, g, dt, d):
        p = g.player
        a = self.attack
        if a == "jab":
            if not self.hit_done and seg_dist(p.pos, self.pos, self.pos + self.aim * BOSS_REACH) < 26 + p.r:
                self.hit_done = True
                g.hurt_player(14, self.pos, knock=420)
        elif a == "hook":
            e = 1 - self.pt / self.sdur
            if not self.hit_done and e > 0.2 and in_cone(self.pos, math.atan2(self.aim.y, self.aim.x), p.pos, BOSS_REACH, 200, p.r):
                self.hit_done = True
                g.hurt_player(16, self.pos, knock=450)
        elif a == "charge":
            self.pos += self.charge_dir * 480 * dt
            self.facing = math.atan2(self.charge_dir.y, self.charge_dir.x)
            if not self.hit_done and d < self.r + p.r + 12:
                self.hit_done = True
                g.hurt_player(18, self.pos, knock=560)

    # ---- desenho
    def phase_progress(self):
        if self.phase == "windup":
            return 1 - max(0.0, self.pt) / self.pdur
        if self.phase == "strike":
            return 1 - max(0.0, self.pt) / self.sdur
        if self.phase == "recover":
            return 1 - max(0.0, self.pt) / self.pdur
        return 0.0

    def fists(self, fv, perp):
        """Posição (relativa ao centro) e escala de cada punho, conforme a animação do golpe."""
        ph, at = self.phase, self.attack
        prog = smooth(self.phase_progress())
        out = []
        for side in (1, -1):
            idle = perp * side * 54 + fv * (28 + 9 * math.sin(self.anim * 5) * side)
            pos, sc = idle, 1.0
            punching = side == self.punch_side
            if ph != "walk" and at == "jab" and punching:
                back = perp * side * 46 - fv * 30
                ext = fv * (BOSS_REACH - 25) + perp * side * 10
                pos = idle.lerp(back, prog) if ph == "windup" else (back.lerp(ext, prog) if ph == "strike" else ext.lerp(idle, prog))
            elif ph != "walk" and at == "hook" and punching:
                a0 = math.atan2(fv.y, fv.x)

                def arc(t, a0=a0, side=side):
                    ang = a0 - side * 1.75 + side * 3.5 * t
                    r = 125 + 25 * math.sin(math.pi * t)
                    return V2(math.cos(ang), math.sin(ang)) * r

                if ph == "windup":
                    pos = idle.lerp(arc(0), prog)
                elif ph == "strike":
                    pos = arc(prog)
                else:
                    pos = arc(1).lerp(idle, prog)
            elif ph != "walk" and at == "slam":
                up = perp * side * 38 + fv * 4
                down = fv * 78 + perp * side * 30
                if ph == "windup":
                    pos, sc = idle.lerp(up, prog), 1 + 0.55 * prog
                elif ph == "strike":
                    pos, sc = up.lerp(down, prog), 1.55 - 0.55 * prog
                else:
                    pos = down.lerp(idle, prog)
            elif ph != "walk" and at == "charge":
                back = perp * side * 50 - fv * 22
                fwd = fv * 100 + perp * side * 34
                pos = idle.lerp(back, prog) if ph == "windup" else (fwd if ph == "strike" else fwd.lerp(idle, prog))
            elif ph != "walk" and at == "rain":
                up = perp * side * 38 + fv * 4
                if ph == "windup":
                    pos, sc = idle.lerp(up, prog), 1 + 0.55 * prog
                elif ph == "strike":
                    down_now = (int(self.anim * 3.6) % 2 == 0) == (side == 1)
                    pos, sc = (fv * 58 + perp * side * 22, 1.0) if down_now else (up, 1.55)
                else:
                    pos, sc = up.lerp(idle, prog), 1.55 - 0.55 * prog
            out.append((pos, sc))
        return out

    def draw_telegraph(self, ov, cam):
        if self.phase != "windup":
            return
        prog = 1 - max(0.0, self.pt) / self.pdur
        alpha = int(30 + 110 * prog)
        col = (255, 60, 50, alpha)
        sp = self.pos - cam
        a = self.attack
        ang = math.atan2(self.aim.y, self.aim.x)
        fwd = V2(math.cos(ang), math.sin(ang))
        side = V2(-fwd.y, fwd.x)
        if a == "slam":
            pygame.draw.circle(ov, col, sp, BOSS_SLAM_R)
            pygame.draw.circle(ov, (255, 210, 140, 220), sp, max(4, int(BOSS_SLAM_R * prog)), 3)
        elif a == "jab":
            half = 26
            pts = [sp + side * half, sp - side * half, sp - side * half + fwd * BOSS_REACH, sp + side * half + fwd * BOSS_REACH]
            pygame.draw.polygon(ov, col, pts)
        elif a == "hook":
            pts = [sp]
            for i in range(17):
                t = ang - math.radians(100) + math.radians(200) * i / 16
                pts.append(sp + V2(math.cos(t), math.sin(t)) * BOSS_REACH)
            pygame.draw.polygon(ov, col, pts)
        elif a == "charge":
            half = 45
            length = 480 * BOSS_ATTACKS["charge"][1]
            pts = [sp + side * half, sp - side * half, sp - side * half + fwd * length, sp + side * half + fwd * length]
            pygame.draw.polygon(ov, col, pts)

    def draw(self, s, cam):
        sp = self.pos - cam
        if not (-170 < sp.x < W + 170 and -170 < sp.y < H + 170):
            return
        r = self.r
        pygame.draw.ellipse(s, (8, 6, 12), (sp.x - r * 1.05, sp.y + r * 0.45, r * 2.1, r * 0.95))
        fv = V2(math.cos(self.facing), math.sin(self.facing))
        perp = V2(-fv.y, fv.x)
        enr = self.enraged
        fl = self.flash > 0
        skin = (255, 255, 255) if fl else ((170, 88, 78) if enr else (150, 108, 88))
        vest = (255, 255, 255) if fl else (92, 26, 40)
        dark = (48, 22, 26)
        lean = fv * 10 if (self.attack == "charge" and self.phase == "strike") else V2()
        crouch = 0.92 if (self.attack == "charge" and self.phase == "windup") else 1.0
        c = sp + lean
        if enr:
            pulse = 0.5 + 0.5 * math.sin(self.anim * 9)
            pygame.draw.circle(s, (150, 20, 30), c, r + 8 + int(5 * pulse), 3)
        if self.attack == "rain" and self.phase != "recover":
            pygame.draw.circle(s, (255, 180, 70), c, r + 10 + int(4 * math.sin(self.anim * 14)), 3)
        pygame.draw.circle(s, dark, c, int(r * crouch) + 3)
        pygame.draw.circle(s, vest, c, int(r * crouch))
        pygame.draw.circle(s, (176, 134, 44), c, int(r * 0.55), 4)
        head = c + fv * 18
        pygame.draw.circle(s, dark, head, 22)
        pygame.draw.circle(s, skin, head, 19)
        for sd in (1, -1):  # chifres
            base = head + perp * sd * 13 - fv * 4
            pygame.draw.polygon(s, (214, 204, 182), [base + perp * sd * 3, base - perp * sd * 3, base + perp * sd * 12 - fv * 10])
            eye = head + fv * 8 + perp * sd * 6
            pygame.draw.circle(s, (255, 70, 70) if enr else (250, 220, 120), eye, 3)
        pygame.draw.line(s, dark, head + fv * 5 + perp * 10, head + fv * 10 - perp * 10, 3)
        pygame.draw.line(s, (240, 235, 215), head + fv * 14 + perp * 5, head + fv * 18 + perp * 5, 3)
        pygame.draw.line(s, (240, 235, 215), head + fv * 14 - perp * 5, head + fv * 18 - perp * 5, 3)
        for side, (fpos, sc) in zip((1, -1), self.fists(fv, perp)):
            shoulder = c + perp * side * 42
            fist = c + fpos
            pygame.draw.line(s, dark, shoulder, fist, 25)
            pygame.draw.line(s, skin, shoulder, fist, 19)
            fr = int(21 * sc)
            pygame.draw.circle(s, dark, fist, fr + 3)
            pygame.draw.circle(s, skin, fist, fr)
            fd = V2(fpos).normalize() if fpos.length() > 1 else fv
            fp = V2(-fd.y, fd.x)
            for k in (-1, 0, 1):
                pygame.draw.line(s, dark, fist + fd * fr * 0.55 + fp * k * fr * 0.45, fist + fd * fr * 0.95 + fp * k * fr * 0.45, 2)


class Player:
    def __init__(self, pos):
        self.pos = V2(pos)
        self.vel = V2()
        self.r = 14
        self.blood = BLOOD_START
        self.frenzy = False
        self.invuln = 0.0
        self.flash = 0.0
        self.cast_cd = 0.0
        self.queue = []
        self.mouth = []          # tiros "comidos" no parry
        self.dash = None
        self.facing = 0.0
        self.bat = False         # sem sangue: vira morcego (só morde, morre com 1 golpe)

    def add_blood(self, amount, g):
        if self.bat:
            return
        self.blood = min(BLOOD_MAX, self.blood + amount)
        if self.blood >= BLOOD_MAX and not self.frenzy:
            self.frenzy = True
            g.add_text(self.pos + V2(0, -40), "FRENESI!", (255, 80, 80), 1.4, 28)
            g.add_fx("ring", self.pos, 0, 220, 0.5, (255, 60, 60))
            g.shake = max(g.shake, 10)

    def start_leap(self, enemy):
        if self.bat:
            return
        self.dash = {"kind": "leap", "target": enemy, "speed": 1600, "time": 0.45}

    def update(self, g, dt, move):
        self.invuln = max(0.0, self.invuln - dt)
        self.flash = max(0.0, self.flash - dt)
        self.cast_cd = max(0.0, self.cast_cd - dt)
        d = g.mouse - self.pos
        if d.length() > 4:
            self.facing = math.atan2(d.y, d.x)
        resting = g.resting()    # entre as ondas o sangue (e o frenesi) não escorrem
        if self.bat:
            pass
        elif self.frenzy:
            if not resting:
                self.blood -= FRENZY_DRAIN * dt
            if self.blood <= FRENZY_END:
                self.blood = FRENZY_END
                self.frenzy = False
                g.add_text(self.pos + V2(0, -40), "frenesi acabou", (220, 180, 190), 1.0, 20)
        elif not resting:
            self.blood -= BLOOD_DRAIN * dt
        if self.dash:
            self.update_dash(g, dt)
        else:
            if self.bat:
                speed = 310
            else:
                speed = 235 * (FRENZY_SPEED if self.frenzy else 1.0)
            self.vel += (move * speed - self.vel) * min(1.0, 14 * dt)
            self.pos += self.vel * dt
        self.pos.x = max(22, min(WORLD_W - 22, self.pos.x))
        self.pos.y = max(22, min(WORLD_H - 22, self.pos.y))
        if self.blood <= 0 and not self.frenzy and not self.bat:
            g.become_bat()

    def update_dash(self, g, dt):
        d = self.dash
        g.add_trail(self.pos)
        if d["kind"] == "leap":
            t = d["target"]
            if t.dead:
                self.end_dash(g, False)
                return
            to = t.pos - self.pos
            dist = to.length()
            if dist <= self.r + t.r + 6 or d["time"] <= 0:
                self.end_dash(g, True)
                return
            self.pos += to / dist * min(d["speed"] * dt, dist)
            d["time"] -= dt
            return
        step = min(d["speed"] * dt, d["left"])
        self.pos += d["dir"] * step
        d["left"] -= step
        if d["dmg"] > 0:
            for e in g.enemies:
                if not e.dead and id(e) not in d["hit"] and (e.pos - self.pos).length() < self.r + e.r + 24:
                    d["hit"].add(id(e))
                    g.damage_enemy(e, d["dmg"], self.pos, knock=d["knock"], stun=d["stun"])
        if d["left"] <= 1e-3:
            self.end_dash(g, False)

    def end_dash(self, g, landed):
        d = self.dash
        self.dash = None
        self.invuln = max(self.invuln, 0.12)
        if d["kind"] == "leap":
            if landed:
                g.aoe(self.pos, 75, 16 * POWER_DMG[d.get("power", 1) - 1], 320, 0.4, (110, 165, 255))
            return
        self.vel = d["dir"] * 80
        if d.get("burst"):
            g.tooth_ring(self.pos, d["burst"][0], d["burst"][1])

    def draw_bat(self, s, sp, g):
        pygame.draw.ellipse(s, (8, 6, 12), (sp.x - 12, sp.y + 12, 24, 9))
        fv = V2(math.cos(self.facing), math.sin(self.facing))
        perp = V2(-fv.y, fv.x)
        flap = math.sin(g.time * 22)
        body = (255, 255, 255) if (self.flash > 0 or (self.invuln > 0 and int(g.time * 30) % 2 == 0)) else (58, 18, 52)
        for side in (1, -1):
            tip = sp + perp * side * (26 + 6 * flap) + fv * (-4 + 6 * flap)
            mid = sp + perp * side * 14 - fv * 12
            pts = [sp + perp * side * 4, sp + perp * side * 12 + fv * 9, tip,
                   mid + perp * side * 4, sp - fv * 10]
            pygame.draw.polygon(s, (88, 24, 70), pts)
            pygame.draw.polygon(s, (24, 6, 22), pts, 2)
        pygame.draw.circle(s, body, sp, 9)
        pygame.draw.polygon(s, body, [sp + fv * 4 + perp * 7, sp + fv * 14 + perp * 5, sp + fv * 8 + perp * 2])
        pygame.draw.polygon(s, body, [sp + fv * 4 - perp * 7, sp + fv * 14 - perp * 5, sp + fv * 8 - perp * 2])
        pygame.draw.circle(s, (255, 50, 70), sp + fv * 5 + perp * 3, 2)
        pygame.draw.circle(s, (255, 50, 70), sp + fv * 5 - perp * 3, 2)
        if self.cast_cd > 0.3:  # mordida
            pygame.draw.line(s, (255, 255, 255), sp + fv * 9 + perp * 2, sp + fv * 14 + perp * 2, 2)
            pygame.draw.line(s, (255, 255, 255), sp + fv * 9 - perp * 2, sp + fv * 14 - perp * 2, 2)

    def draw(self, s, cam, g):
        sp = self.pos - cam
        if self.bat:
            self.draw_bat(s, sp, g)
            return
        pygame.draw.ellipse(s, (8, 6, 12), (sp.x - 17, sp.y + 8, 34, 13))
        if self.frenzy:
            pulse = 0.5 + 0.5 * math.sin(g.time * 14)
            pygame.draw.circle(s, (150, 20, 30), sp, 30 + int(5 * pulse), 3)
            pygame.draw.circle(s, (255, 60, 60), sp, 24 + int(4 * pulse), 2)
        fv = V2(math.cos(self.facing), math.sin(self.facing))
        blink = self.invuln > 0 and int(g.time * 30) % 2 == 0
        cape = (255, 255, 255) if (self.flash > 0 or blink) else (95, 22, 62)
        back = -fv
        perp = V2(-fv.y, fv.x)
        tri = [sp + back * 26 + perp * 6, sp + perp * 14, sp - perp * 14, sp + back * 26 - perp * 6]
        pygame.draw.polygon(s, (60, 12, 40), [sp + perp * 13, sp - perp * 13, sp + back * 30])
        pygame.draw.circle(s, cape, sp, self.r)
        pygame.draw.circle(s, (30, 8, 25), sp, self.r, 2)
        head = sp + fv * 3
        pygame.draw.polygon(s, (30, 12, 30), [head + perp * 8 + fv * 1, head + perp * 10 + back * 9, head + perp * 3 + back * 3])
        pygame.draw.polygon(s, (30, 12, 30), [head - perp * 8 + fv * 1, head - perp * 10 + back * 9, head - perp * 3 + back * 3])
        pygame.draw.circle(s, (238, 224, 228), head, 9)
        pygame.draw.circle(s, (210, 20, 40), head + fv * 4 + perp * 3.5, 2)
        pygame.draw.circle(s, (210, 20, 40), head + fv * 4 - perp * 3.5, 2)
        pygame.draw.line(s, (255, 255, 255), head + fv * 7 + perp * 2, head + fv * 10 + perp * 2, 2)
        pygame.draw.line(s, (255, 255, 255), head + fv * 7 - perp * 2, head + fv * 10 - perp * 2, 2)
        for i, _ in enumerate(self.mouth):
            a = g.time * 3 + i * 2.1
            pos = sp + V2(math.cos(a), math.sin(a)) * 24
            pygame.draw.circle(s, (255, 150, 40), pos, 6)
            pygame.draw.circle(s, (255, 235, 150), pos, 3)


# --------------------------------------------------------------------- jogo
class Game:
    def __init__(self):
        self.ground = self.make_ground()
        self.vignette = self.make_vignette()
        self.fx_surf = pygame.Surface((W, H), pygame.SRCALPHA)
        self.mouse = V2(WORLD_W / 2 + 100, WORLD_H / 2)
        self.state = "menu"
        self.camera = V2()
        self.first_wave = 1
        self.reset()

    # ---- preparação
    def make_ground(self):
        rnd = random.Random(7)
        g = pygame.Surface((WORLD_W, WORLD_H))
        g.fill((34, 27, 42))
        tile = 100
        for ty in range(0, WORLD_H, tile):
            for tx in range(0, WORLD_W, tile):
                shade = rnd.randint(-5, 6)
                col = (44 + shade, 36 + shade, 56 + shade)
                pygame.draw.rect(g, col, (tx + 2, ty + 2, tile - 4, tile - 4))
                if rnd.random() < 0.18:
                    x1, y1 = tx + rnd.randint(10, 90), ty + rnd.randint(10, 90)
                    pygame.draw.line(g, (16, 12, 22), (x1, y1), (x1 + rnd.randint(-25, 25), y1 + rnd.randint(-25, 25)), 2)
        for _ in range(60):  # túmulos decorativos
            x, y = rnd.randint(100, WORLD_W - 100), rnd.randint(100, WORLD_H - 100)
            pygame.draw.rect(g, (44, 40, 56), (x - 10, y - 8, 20, 26), border_radius=8)
            pygame.draw.rect(g, (30, 27, 40), (x - 10, y - 8, 20, 26), 2, border_radius=8)
            pygame.draw.line(g, (30, 27, 40), (x, y - 2), (x, y + 8), 2)
        wall = 40
        pygame.draw.rect(g, (10, 6, 14), (0, 0, WORLD_W, WORLD_H), wall)
        pygame.draw.rect(g, (90, 20, 40), (wall, wall, WORLD_W - 2 * wall, WORLD_H - 2 * wall), 3)
        return g

    def make_vignette(self):
        v = pygame.Surface((W, H), pygame.SRCALPHA)
        steps = 18
        for i in range(steps):
            t = i / steps
            alpha = int(120 * (1 - t) ** 2.2)
            rect = pygame.Rect(0, 0, W, H).inflate(-int(W * 0.5 * t), -int(H * 0.5 * t))
            pygame.draw.rect(v, (10, 0, 10, alpha), rect, 18, border_radius=60)
        return v

    def reset(self):
        self.player = Player(V2(WORLD_W / 2, WORLD_H / 2))
        self.enemies, self.projs, self.ebullets = [], [], []
        self.fx, self.parts, self.texts, self.timers = [], [], [], []
        self.wave = 0
        self.kills = 0
        self.time = 0.0
        self.shake = 0.0
        self.spawn_q = []
        self.spawn_t = 0.0
        self.break_t = 1.5
        self.ai_t = 0.0
        self.hazards = []
        self.ai_aim = 0.0
        self.gun_cd = 0.0
        self.announced = True
        self.banner = ("", 0.0)
        self.camera = self.player.pos - V2(W / 2, H / 2)

    def start(self):
        random.seed()
        self.reset()
        self.wave = self.first_wave - 1
        self.state = "play"

    def game_over(self):
        if self.state == "play":
            self.state = "over"
            self.shake = 14

    # ---- input
    def add_element(self, e):
        if self.state == "play" and not self.player.bat and len(self.player.queue) < 3:
            self.player.queue.append(e)
            self.try_auto_cast()

    def try_auto_cast(self):
        """Barra de habilidades cheia (3 elementos): a habilidade é lançada sozinha."""
        p = self.player
        if self.state == "play" and not p.bat and len(p.queue) >= 3 and p.cast_cd <= 0 and not p.dash:
            self.cast()

    def right_click(self):
        """Botão direito: elemento perna; na forma de morcego, morder."""
        if self.player.bat:
            self.cast()
        else:
            self.add_element(LEG)

    def space_action(self):
        """ESPAÇO: lança já a fila incompleta, ou cospe de volta o tiro guardado."""
        if not self.player.bat:
            self.cast()

    def clear_queue(self):
        self.player.queue.clear()

    def aim(self):
        p = self.player
        return norm(self.mouse - p.pos, (math.cos(p.facing), math.sin(p.facing)))

    # ---- efeitos visuais
    def add_fx(self, kind, pos, ang, radius, life, color, arc=90):
        self.fx.append({"k": kind, "pos": V2(pos), "ang": ang, "r": radius, "t": life, "max": life, "col": color, "arc": arc})

    def add_text(self, pos, txt, color, life=0.8, size=18):
        self.texts.append({"pos": V2(pos), "txt": txt, "col": color, "t": life, "max": life, "size": size})

    def add_trail(self, pos):
        self.parts.append([V2(pos), V2(), 0.28, 0.28, (170, 30, 70), 11])

    def blood_burst(self, pos, n, speed=180):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = V2(math.cos(a), math.sin(a)) * random.uniform(40, speed)
            life = random.uniform(0.25, 0.6)
            self.parts.append([V2(pos), v, life, life, random.choice([(170, 15, 35), (210, 30, 50), (120, 10, 25)]), random.uniform(2, 5)])

    def dust(self, pos, n):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = V2(math.cos(a), math.sin(a)) * random.uniform(60, 260)
            life = random.uniform(0.3, 0.7)
            self.parts.append([V2(pos), v, life, life, random.choice([(120, 104, 96), (92, 80, 76), (150, 130, 118)]), random.uniform(3, 7)])

    def splat(self, pos):
        for _ in range(random.randint(3, 6)):
            off = V2(random.uniform(-18, 18), random.uniform(-18, 18))
            pygame.draw.circle(self.ground, random.choice([(70, 8, 22), (88, 12, 28)]), pos + off, random.randint(3, 9))

    # ---- dano
    def hurt_player(self, dmg, src, knock=260.0):
        p = self.player
        if self.state != "play" or p.invuln > 0 or p.dash:
            return False
        self.shake = max(self.shake, 9)
        self.blood_burst(p.pos, 8)
        if p.bat:  # morcego morre com 1 golpe
            self.blood_burst(p.pos, 24, 260)
            self.game_over()
            return True
        p.blood -= dmg
        p.invuln = 0.45
        p.flash = 0.18
        p.vel += norm(p.pos - src) * knock
        self.add_text(p.pos + V2(0, -30), "-%d" % dmg, (255, 90, 110), 0.7, 22)
        if p.blood <= 0 and not p.frenzy:
            self.become_bat()
        return True

    def resting(self):
        """Entre as ondas (nenhum inimigo vivo ou por nascer) o sangue não escorre."""
        return not self.enemies and not self.spawn_q

    def become_bat(self):
        p = self.player
        if p.bat or self.state != "play":
            return
        p.bat = True
        p.blood = 0.0
        p.r = 10
        p.frenzy = False
        p.queue.clear()
        p.mouth.clear()
        p.dash = None
        p.invuln = 0.6   # um respiro curto ao se transformar
        self.timers.clear()
        self.add_fx("ring", p.pos, 0, 160, 0.5, (150, 60, 200))
        self.add_text(p.pos + V2(0, -42), "MORCEGO! mate um inimigo para voltar", (200, 150, 255), 2.0, 22)
        self.shake = max(self.shake, 10)

    def revert_human(self):
        p = self.player
        p.bat = False
        p.r = 14
        p.blood = BAT_REVERT_BLOOD
        p.invuln = 1.0
        self.add_fx("ring", p.pos, 0, 200, 0.5, (255, 90, 110))
        self.add_text(p.pos + V2(0, -42), "forma normal!", (255, 150, 160), 1.4, 24)

    def bite(self):
        p = self.player
        a = self.aim()
        face = math.atan2(a.y, a.x)
        p.vel += a * 520  # bote para frente
        self.cone(p.pos, face, 66, 120, BAT_BITE_DAMAGE, 120, 0.1, (255, 255, 255))
        p.cast_cd = 0.4

    def damage_enemy(self, e, dmg, src, knock=0.0, stun=0.0):
        if e.dead:
            return
        if self.player.frenzy:
            dmg *= FRENZY_DAMAGE
        real = min(dmg, e.hp)
        e.hp -= dmg
        e.flash = 0.12
        self.player.add_blood(real * LIFESTEAL * e.lifesteal_mult, self)
        if e.kind == "boss":  # apanhar também enche a barra de habilidade dele
            e.special = min(100.0, e.special + real * 0.25)
        knock *= e.knock_resist
        stun *= e.stun_resist
        if knock:
            e.vel += norm(e.pos - src) * knock
        if stun:
            e.stun = max(e.stun, stun)
        self.add_text(e.pos + V2(random.uniform(-6, 6), -e.r - 8), str(int(dmg)), (255, 230, 200), 0.6, 18)
        self.blood_burst(e.pos, 5)
        self.shake = max(self.shake, 3)
        if e.hp <= 0:
            e.dead = True
            self.kills += 1
            if self.player.bat:
                self.revert_human()
            self.blood_burst(e.pos, 20, 260)
            self.splat(e.pos)
            self.shake = max(self.shake, 6)
            if e.kind == "boss":
                self.hazards.clear()
                self.blood_burst(e.pos, 90, 420)
                for _ in range(4):
                    self.splat(e.pos + V2(random.uniform(-40, 40), random.uniform(-40, 40)))
                self.shake = 20
                self.banner = ("Chefe derrotado!", 3.0)

    def aoe(self, center, radius, dmg, knock, stun, color):
        self.add_fx("ring", center, 0, radius, 0.3, color)
        self.add_fx("disc", center, 0, radius, 0.15, color)
        for e in self.enemies:
            if not e.dead and (e.pos - center).length() < radius + e.r:
                self.damage_enemy(e, dmg, center, knock, stun)

    def cone(self, origin, facing, reach, arc, dmg, knock, stun, color):
        self.add_fx("cone", origin, facing, reach, 0.2, color, arc)
        for e in self.enemies:
            if not e.dead and in_cone(origin, facing, e.pos, reach, arc, e.r):
                self.damage_enemy(e, dmg, origin, knock, stun)

    def tooth_ring(self, pos, count, dmg):
        off = random.uniform(0, math.tau)
        for i in range(count):
            a = off + math.tau * i / count
            v = V2(math.cos(a), math.sin(a))
            self.projs.append(Proj("tooth", pos + v * 18, v * 540, dmg, 6, 0.55, knock=90))
        self.add_fx("ring", pos, 0, 120, 0.25, ELEM_COLOR[TOOTH])

    # ---- ações do jogador
    def cast(self):
        p = self.player
        if self.state != "play" or p.cast_cd > 0 or p.dash:
            return
        if p.bat:
            self.bite()
            return
        q = list(p.queue)
        if not q:
            if p.mouth:
                self.spit_back()
            return
        p.queue.clear()
        order, power = parse_queue(q)
        a = self.aim()
        cd = self.run_combo(order[0], order[1] if len(order) > 1 else None, power, a, q)
        if len(order) == 3:
            third = order[2]
            self.timers.append([0.3, lambda: self.run_combo(third, None, 1, self.aim(), None)])
        p.cast_cd = cd * (0.7 if p.frenzy else 1.0)

    def spit_back(self):
        p = self.player
        p.mouth.pop()
        a = self.aim()
        self.projs.append(Proj("bullet", p.pos + a * 22, a * 950, 34, 8, 1.4, pierce=1, knock=220))
        self.add_fx("ring", p.pos + a * 20, 0, 40, 0.15, (255, 170, 60))
        p.cast_cd = 0.22

    def try_parry(self):
        p = self.player
        caught = []
        for b in self.ebullets:
            d = b.pos - p.pos
            if d.length() < PARRY_RADIUS and b.vel.dot(-d) > 0:
                caught.append(b)
        if not caught:
            return False
        for b in caught:
            b.dead = True
            if len(p.mouth) < 3:
                p.mouth.append(1)
            p.add_blood(8, self)
        self.add_fx("ring", p.pos, 0, PARRY_RADIUS, 0.35, (255, 220, 120))
        self.add_text(p.pos + V2(0, -40), "PARRY!", (255, 225, 120), 1.0, 26)
        self.shake = max(self.shake, 6)
        return True

    def run_combo(self, first, second, power, a, q):
        p = self.player
        m, s = POWER_DMG[power - 1], POWER_SIZE[power - 1]
        key = first + (second or "")
        face = math.atan2(a.y, a.x)
        if key == "T":
            if q == [TOOTH] * 3 and self.try_parry():
                return 0.4
            self.projs.append(Proj("tooth", p.pos + a * 20, a * 740, 12 * m, 6 * s, 1.0, pierce=power - 1))
            return 0.28
        if key == "A":
            self.cone(p.pos, face, 82 * s, 130, 16 * m, 260, 0.15, ELEM_COLOR[ARM])
            return 0.4
        if key == "L":
            p.dash = {"kind": "dash", "dir": a, "left": 230 + 60 * (power - 1), "speed": 1300,
                      "dmg": 0, "knock": 0, "stun": 0, "hit": set()}
            return 0.65
        if key == "TL":  # cospe a perna; se acertar, pula até o inimigo
            pr = Proj("leg", p.pos + a * 22, a * 680, 14 * m, 9 * s, 0.55, knock=120)
            pr.leap = True
            self.projs.append(pr)
            p.leap_power = power
            return 0.8
        if key == "TA":  # braço bumerangue
            count = 1 if power == 1 else 2
            for i in range(count):
                off = 0 if count == 1 else (-0.18 if i == 0 else 0.18)
                v = V2(math.cos(face + off), math.sin(face + off))
                pr = Proj("arm", p.pos + v * 22, v * 640, 9 * m, 12 * s, 3, pierce=999, knock=140)
                pr.maxdist = 380 + 40 * power
                self.projs.append(pr)
            return 0.9
        if key == "LT":  # dash + chuva de dentes
            count = (8, 12, 16)[power - 1]
            p.dash = {"kind": "dash", "dir": a, "left": 220 + 40 * (power - 1), "speed": 1300,
                      "dmg": 0, "knock": 0, "stun": 0, "hit": set(),
                      "burst": (count, 8 * (1 + 0.25 * (power - 1)))}
            return 0.9
        if key == "LA":  # dash com golpe à frente
            p.dash = {"kind": "dash", "dir": a, "left": 250 + 50 * (power - 1), "speed": 1350,
                      "dmg": 18 * m, "knock": 430, "stun": 0.35, "hit": set()}
            return 0.85
        if key == "AL":  # chute
            self.cone(p.pos, face, 100 * s, 80, 14 * m, 720, 0.8, (255, 200, 120))
            return 0.7
        if key == "AT":  # soco com dente em área
            center = p.pos + a * 62
            self.aoe(center, 92 * s, 24 * m, 400, 0.3, (250, 235, 200))
            for _ in range(10):
                ang = random.uniform(0, math.tau)
                v = V2(math.cos(ang), math.sin(ang))
                self.parts.append([center + v * 10, v * random.uniform(160, 320), 0.35, 0.35, ELEM_COLOR[TOOTH], 4])
            self.shake = max(self.shake, 7)
            return 0.8
        return 0.3

    # ---- atualização
    def start_wave(self, n):
        self.wave = n
        swords = 3 + 3 * n
        guns = 0 if n == 1 else min(10, n + 1)
        dogs = 0 if n == 1 else min(8, n)
        self.spawn_q = ["sword"] * swords + ["gun"] * guns + ["dog"] * dogs
        random.shuffle(self.spawn_q)
        if n % 5 == 0:  # onda de chefe: o gigante entra primeiro, com poucos acompanhantes
            k = n // 5
            escort = ["sword"] * (2 + 2 * k) + ["gun"] * (1 + k) + ["dog"] * (2 * k)
            random.shuffle(escort)
            self.spawn_q = ["boss"] + escort
        self.spawn_t = 1.0
        self.announced = False
        self.banner = (("Onda %d — CHEFE!" % n) if n % 5 == 0 else ("Onda %d" % n), 3.0 if n % 5 == 0 else 2.5)

    def spawn_enemy(self, kind):
        p = self.player.pos
        pos = None
        for _ in range(40):
            c = V2(random.randint(90, WORLD_W - 90), random.randint(90, WORLD_H - 90))
            if (c - p).length() > 560:
                pos = c
                break
        if pos is None:
            pos = V2(120, 120)
        if kind == "boss":
            self.enemies.append(Boss(pos, 450 + 40 * self.wave))
        else:
            self.enemies.append(Enemy(kind, pos))

    def update_waves(self, dt):
        if self.spawn_q:
            self.spawn_t -= dt
            if self.spawn_t <= 0 and len(self.enemies) < MAX_ALIVE:
                self.spawn_enemy(self.spawn_q.pop(0))
                self.spawn_t = 0.35
        elif not self.enemies:
            if not self.announced and self.wave > 0:
                self.announced = True
                self.banner = ("Onda %d concluída!" % self.wave, 2.0)
                self.break_t = 3.0
            self.break_t -= dt
            if self.break_t <= 0:
                self.start_wave(self.wave + 1)

    def update(self, dt, move):
        self.shake = max(0.0, self.shake - 30 * dt)
        for f in self.fx:
            f["t"] -= dt
        self.fx = [f for f in self.fx if f["t"] > 0]
        for pt in self.parts:
            pt[0] += pt[1] * dt
            pt[1] *= max(0.0, 1 - 5 * dt)
            pt[2] -= dt
        self.parts = [pt for pt in self.parts if pt[2] > 0]
        for tx in self.texts:
            tx["t"] -= dt
            tx["pos"].y -= 40 * dt
        self.texts = [t for t in self.texts if t["t"] > 0]
        if self.banner[1] > 0:
            self.banner = (self.banner[0], self.banner[1] - dt)

        if self.state != "play":
            self.follow_camera(dt)
            return
        self.time += dt
        for t in self.timers:
            t[0] -= dt
        due = [t for t in self.timers if t[0] <= 0]
        self.timers = [t for t in self.timers if t[0] > 0]
        for t in due:
            t[1]()

        self.update_hazards(dt)
        self.player.update(self, dt, move)
        self.try_auto_cast()
        self.update_waves(dt)
        self.plan_ai(dt)
        for e in self.enemies:
            e.update(self, dt)
        self.separate_enemies()

        for pr in self.projs:
            pr.update(self, dt)
            if pr.dead:
                continue
            for e in self.enemies:
                if e.dead or id(e) in pr.hit:
                    continue
                if (e.pos - pr.pos).length() < pr.r + e.r:
                    pr.hit.add(id(e))
                    src = pr.pos - norm(pr.vel) * 10
                    self.damage_enemy(e, pr.dmg, src, pr.knock)
                    if pr.leap:
                        self.player.start_leap(e)
                        self.player.dash["power"] = getattr(self.player, "leap_power", 1)
                        pr.dead = True
                        break
                    if pr.pierce <= 0:
                        pr.dead = True
                        break
                    pr.pierce -= 1
        for b in self.ebullets:
            b.update(self, dt)
            if b.dead:
                continue
            if (b.pos - self.player.pos).length() < b.r + self.player.r and not self.player.dash:
                if self.hurt_player(b.dmg, b.pos):
                    b.dead = True
        self.projs = [p for p in self.projs if not p.dead]
        self.ebullets = [b for b in self.ebullets if not b.dead]
        self.enemies = [e for e in self.enemies if not e.dead]
        self.follow_camera(dt)


    # ---- IA tática (coordena os papéis; cada Enemy executa o seu)
    def line_blocked(self, shooter):
        """Há um aliado no caminho entre o atirador e o jogador?"""
        a = shooter.pos
        ab = self.player.pos - a
        L2 = ab.length_squared()
        if L2 < 1:
            return False
        for o in self.enemies:
            if o is shooter or o.dead:
                continue
            t = (o.pos - a).dot(ab) / L2
            if 0 < t < 1 and (o.pos - (a + ab * t)).length() < o.r + 10:
                return True
        return False

    def plan_ai(self, dt):
        self.gun_cd = max(0.0, self.gun_cd - dt)
        self.ai_t -= dt
        if self.ai_t > 0:
            return
        self.ai_t = 0.25
        p = self.player.pos
        # "frente" do jogador (para onde ele mira), suavizada para a formação não tremer
        self.ai_aim += wrap_angle(self.player.facing - self.ai_aim) * 0.35
        front = self.ai_aim

        def rel(e):
            d = e.pos - p
            return (math.atan2(d.y, d.x) - front) % math.tau

        def dist(e):
            return (e.pos - p).length()

        live = [e for e in self.enemies if not e.dead]
        swords = sorted((e for e in live if e.kind == "sword"), key=dist)
        n = len(swords)
        if n:
            max_att = min(4, 2 + self.wave // 3)
            n_flank = min(2, max(0, n - 2))
            n_engage = max(1, min(n - n_flank, max_att - n_flank))
            engage, rest = swords[:n_engage], swords[n_engage:]
            for e in engage:
                e.role = "engage"
            # os flanqueadores são os que já estão mais perto de "atrás" do jogador
            rest.sort(key=lambda e: abs(wrap_angle(rel(e) - math.pi)))
            flankers, ring = rest[:n_flank], rest[n_flank:]
            flankers.sort(key=rel)
            for i, e in enumerate(flankers):
                e.role = "flank"
                off = 0.0 if len(flankers) == 1 else (-0.95 if i == 0 else 0.95)
                e.slot_angle = front + math.pi + off
            ring.sort(key=rel)
            if ring:
                base = front + rel(ring[0]) + self.time * 0.15
                for k, e in enumerate(ring):
                    e.role = "ring"
                    e.slot_angle = base + math.tau * k / len(ring)
                    e.ring_r = 235 + 35 * (k % 2)

        dogs = sorted((e for e in live if e.kind == "dog"), key=rel)
        for k, e in enumerate(dogs):  # cachorros espalhados pela retaguarda
            e.slot_angle = front + math.radians(100 + 160 * (k + 0.5) / len(dogs))

        guns = sorted((e for e in live if e.kind == "gun"), key=rel)
        for k, e in enumerate(guns):  # atiradores abrem fogo cruzado pelos lados e por trás
            e.slot_angle = front + math.radians(60 + 240 * (k + 0.5) / len(guns))
            e.ring_r = 340 + 45 * (k % 2)

    def update_hazards(self, dt):
        for h in self.hazards:
            h["t"] -= dt
            if h["t"] <= 0 and not h["done"]:
                h["done"] = True
                self.add_fx("ring", h["pos"], 0, h["r"], 0.35, (255, 150, 60))
                self.add_fx("disc", h["pos"], 0, h["r"], 0.18, (255, 120, 50))
                self.dust(h["pos"], 10)
                self.shake = max(self.shake, 9)
                pl = self.player
                if (pl.pos - h["pos"]).length() < h["r"] + pl.r:
                    self.hurt_player(h["dmg"], h["pos"], knock=380)
        self.hazards = [h for h in self.hazards if not h["done"]]

    def separate_enemies(self):
        es = self.enemies
        for i in range(len(es)):
            a = es[i]
            d = a.pos - self.player.pos
            dl = d.length()
            minimum = a.r + self.player.r + 4
            if 0 < dl < minimum:
                if a.kind == "boss":
                    self.player.pos -= d / dl * (minimum - dl)
                else:
                    a.pos += d / dl * (minimum - dl)
            for j in range(i + 1, len(es)):
                b = es[j]
                dd = b.pos - a.pos
                dist = dd.length()
                lim = a.r + b.r
                if 0 < dist < lim:
                    push = dd / dist * (lim - dist)
                    total = a.mass + b.mass
                    a.pos -= push * (b.mass / total)
                    b.pos += push * (a.mass / total)

    def follow_camera(self, dt):
        target = self.player.pos - V2(W / 2, H / 2)
        target.x = max(0, min(WORLD_W - W, target.x))
        target.y = max(0, min(WORLD_H - H, target.y))
        self.camera += (target - self.camera) * min(1.0, 8 * dt)

    # ---- desenho
    def draw_world(self, s):
        cam = V2(self.camera)
        if self.shake > 0:
            cam += V2(random.uniform(-1, 1), random.uniform(-1, 1)) * self.shake
        cam.x = max(0, min(WORLD_W - W, cam.x))
        cam.y = max(0, min(WORLD_H - H, cam.y))
        s.blit(self.ground, (0, 0), pygame.Rect(int(cam.x), int(cam.y), W, H))
        cam = V2(int(cam.x), int(cam.y))

        for pt in self.parts:
            k = pt[2] / pt[3]
            pygame.draw.circle(s, pt[4], pt[0] - cam, max(1, pt[5] * (0.4 + 0.6 * k)))
        for e in sorted(self.enemies, key=lambda e: e.pos.y):
            e.draw(s, cam)
        self.player.draw(s, cam, self)
        for pr in self.projs:
            pr.draw(s, cam)
        for b in self.ebullets:
            b.draw(s, cam)

        ov = self.fx_surf
        ov.fill((0, 0, 0, 0))
        for f in self.fx:
            k = f["t"] / f["max"]
            alpha = int(210 * k)
            col = (*f["col"], alpha)
            sp = f["pos"] - cam
            if f["k"] == "cone":
                reach = f["r"] * (0.65 + 0.35 * (1 - k))
                a0 = f["ang"] - math.radians(f["arc"]) / 2
                pts = [sp]
                for i in range(15):
                    a = a0 + math.radians(f["arc"]) * i / 14
                    pts.append(sp + V2(math.cos(a), math.sin(a)) * reach)
                pygame.draw.polygon(ov, col, pts)
            elif f["k"] == "ring":
                r = f["r"] * (0.35 + 0.65 * (1 - k))
                pygame.draw.circle(ov, col, sp, r, 5)
            elif f["k"] == "disc":
                pygame.draw.circle(ov, (*f["col"], int(120 * k)), sp, f["r"])
        for h in self.hazards:
            if h["t"] <= BOSS_RAIN_TELEGRAPH:
                k = 1 - max(0.0, h["t"]) / BOSS_RAIN_TELEGRAPH
                sp = h["pos"] - cam
                pygame.draw.circle(ov, (255, 50, 40, 40 + int(100 * k)), sp, h["r"])
                pygame.draw.circle(ov, (255, 90, 60, 220), sp, h["r"], 3)
                pygame.draw.circle(ov, (255, 220, 150, 220), sp, max(4, int(h["r"] * k)), 3)
        for e in self.enemies:
            if e.kind == "boss":
                e.draw_telegraph(ov, cam)
        s.blit(ov, (0, 0))

        for tx in self.texts:
            k = tx["t"] / tx["max"]
            img = font(tx["size"], True).render(tx["txt"], True, tx["col"])
            img.set_alpha(int(255 * min(1.0, k * 2)))
            r = img.get_rect(center=(tx["pos"].x - cam.x, tx["pos"].y - cam.y))
            s.blit(img, r)

        s.blit(self.vignette, (0, 0))
        if self.player.frenzy:
            tint = pygame.Surface((W, H), pygame.SRCALPHA)
            a = 28 + int(18 * math.sin(self.time * 10))
            tint.fill((200, 20, 30, a))
            s.blit(tint, (0, 0))
        self._cam_draw = cam

    def draw_crosshair(self, s, pos):
        x, y = pos
        pygame.draw.circle(s, (255, 255, 255), (x, y), 11, 2)
        pygame.draw.circle(s, (210, 30, 50), (x, y), 3)
        for dx, dy in ((14, 0), (-14, 0), (0, 14), (0, -14)):
            pygame.draw.line(s, (255, 255, 255), (x + dx * 0.6, y + dy * 0.6), (x + dx * 1.3, y + dy * 1.3), 2)

    def draw_hud(self, s):
        p = self.player
        # barra de sangue
        x, y, w, h = 24, 22, 400, 28
        pygame.draw.rect(s, (20, 6, 12), (x - 4, y - 4, w + 8, h + 8), border_radius=8)
        frac = max(0.0, min(1.0, p.blood / BLOOD_MAX))
        if p.frenzy:
            pulse = 0.5 + 0.5 * math.sin(self.time * 14)
            col = (255, 50 + int(40 * pulse), 50)
            pygame.draw.rect(s, (255, 60, 60), (x - 6, y - 6, w + 12, h + 12), 3, border_radius=10)
        else:
            col = (176, 14, 40)
        pygame.draw.rect(s, (50, 10, 20), (x, y, w, h), border_radius=6)
        if frac > 0:
            pygame.draw.rect(s, col, (x, y, int(w * frac), h), border_radius=6)
            pygame.draw.rect(s, (255, 130, 140), (x + 4, y + 3, max(0, int(w * frac) - 8), 5), border_radius=3)
        pygame.draw.rect(s, (230, 200, 205), (x, y, w, h), 2, border_radius=6)
        label = "FRENESI!" if p.frenzy else ("MORCEGO — mate um inimigo para voltar" if p.bat else "SANGUE")
        draw_text(s, label, 16, (255, 240, 240), (x + 10, y + h / 2), "midleft", True)
        draw_text(s, "%d" % max(0, p.blood), 16, (255, 240, 240), (x + w - 10, y + h / 2), "midright", True)
        if p.mouth:
            draw_text(s, "Boca:", 15, (255, 200, 120), (x, y + h + 10))
            for i in range(len(p.mouth)):
                pygame.draw.circle(s, (255, 150, 40), (x + 62 + i * 20, y + h + 20), 7)
                pygame.draw.circle(s, (255, 235, 150), (x + 62 + i * 20, y + h + 20), 3)
            draw_text(s, "ESPAÇO com a fila vazia: cuspir de volta", 14, (230, 200, 160), (x + 62 + 3 * 20 + 6, y + h + 12))

        # barra do chefe (vida + habilidade)
        for e in self.enemies:
            if e.kind != "boss":
                continue
            bw, bx0, by0 = 640, W / 2 - 320, H - 126
            draw_text(s, "GIGANTE", 18, (255, 225, 215), (W / 2, by0 - 6), "midbottom", True)
            pygame.draw.rect(s, (20, 6, 10), (bx0 - 3, by0 - 3, bw + 6, 22), border_radius=6)
            pygame.draw.rect(s, (64, 14, 22), (bx0, by0, bw, 16), border_radius=4)
            pygame.draw.rect(s, (214, 54, 62) if not e.enraged else (255, 90, 60), (bx0, by0, int(bw * max(0, e.hp) / e.max_hp), 16), border_radius=4)
            pygame.draw.rect(s, (230, 200, 205), (bx0, by0, bw, 16), 2, border_radius=4)
            sy0 = by0 + 24
            full = e.special >= 99.5 or e.attack == "rain"
            pygame.draw.rect(s, (30, 20, 48), (bx0, sy0, bw, 10), border_radius=4)
            fill = 1.0 if full else e.special / 100
            scol = (255, 200, 90) if full and int(self.time * 8) % 2 == 0 else (170, 110, 240)
            pygame.draw.rect(s, scol, (bx0, sy0, int(bw * fill), 10), border_radius=4)
            pygame.draw.rect(s, (200, 180, 230), (bx0, sy0, bw, 10), 1, border_radius=4)
            draw_text(s, "HABILIDADE: Chuva de Socos", 13, (215, 195, 245), (bx0 + bw, sy0 + 12), "topright")
            break

        # info da onda
        draw_text(s, "Onda %d" % self.wave, 22, (255, 235, 235), (W - 24, 20), "topright", True)
        left = len(self.enemies) + len(self.spawn_q)
        draw_text(s, "Inimigos: %d" % left, 16, (230, 210, 215), (W - 24, 50), "topright")
        draw_text(s, "Abates: %d" % self.kills, 16, (230, 210, 215), (W - 24, 72), "topright")
        draw_text(s, "Tempo: %d:%02d" % (int(self.time) // 60, int(self.time) % 60), 16, (230, 210, 215), (W - 24, 94), "topright")

        # fila de elementos
        slot, gap = 64, 12
        total = 3 * slot + 2 * gap
        sx = W / 2 - total / 2
        sy = 18
        for i in range(0 if p.bat else 3):
            r = pygame.Rect(sx + i * (slot + gap), sy, slot, slot)
            pygame.draw.rect(s, (18, 10, 22), r, border_radius=10)
            if i < len(p.queue):
                e = p.queue[i]
                pygame.draw.rect(s, ELEM_COLOR[e], r, 3, border_radius=10)
                draw_icon(s, e, r.center, 34)
            else:
                pygame.draw.rect(s, (70, 50, 80), r, 2, border_radius=10)
            if i == 0:
                draw_text(s, "1º", 12, (200, 180, 200), (r.left + 5, r.top + 3))
        name = combo_name(p.queue)
        if p.bat:
            draw_text(s, "BOTÃO DIR.: morder", 22, (200, 150, 255), (W / 2, sy + 10), "midtop", True)
            draw_text(s, "1 golpe e você morre", 16, (230, 190, 255), (W / 2, sy + 40), "midtop")
        elif name:
            draw_text(s, name, 20, (255, 235, 200), (W / 2, sy + slot + 12), "midtop", True)
        elif p.mouth:
            draw_text(s, "Cuspir tiro de volta", 18, (255, 200, 120), (W / 2, sy + slot + 12), "midtop", True)
        if p.cast_cd > 0 and not p.bat:
            pygame.draw.rect(s, (255, 235, 200), (sx, sy + slot + 4, total * min(1, p.cast_cd / 0.9), 3))
        if self.resting() and self.state == "play" and not p.bat:
            draw_text(s, "sangue em pausa entre as ondas", 14, (200, 170, 180), (24, 84))

        # legenda de teclas
        by = H - 48
        if p.bat:
            draw_text(s, "BOTÃO DIR.: morder   WASD: voar   P: pausa", 14, (180, 165, 185), (W / 2, H - 12), "midbottom")
        else:
            items = [(TOOTH, "SHIFT"), (ARM, "BOTÃO ESQ."), (LEG, "BOTÃO DIR.")]
            bx = W / 2 - 330
            for e, k in items:
                draw_icon(s, e, (bx + 14, by), 20)
                draw_text(s, "%s: %s" % (k, ELEM_LABEL[e]), 15, (225, 210, 220), (bx + 34, by), "midleft")
                bx += 190
            draw_text(s, "Barra cheia lança sozinha   ESPAÇO: lançar já   Q: limpar   P: pausa", 14, (180, 165, 185), (W / 2, H - 12), "midbottom")

        if self.banner[1] > 0:
            k = min(1.0, self.banner[1])
            img = font(54, True).render(self.banner[0], True, (240, 220, 225))
            img.set_alpha(int(255 * k))
            s.blit(img, img.get_rect(center=(W / 2, H * 0.3)))

    def draw_overlay_panel(self, s, alpha=170):
        shade = pygame.Surface((W, H), pygame.SRCALPHA)
        shade.fill((6, 0, 10, alpha))
        s.blit(shade, (0, 0))

    def draw_menu(self, s):
        self.draw_overlay_panel(s, 190)
        draw_text(s, "VAMPIRINHA", 84, (210, 25, 50), (W / 2, 70), "midtop", True)
        draw_text(s, "O sangue é a sua vida — e o seu relógio. Cause dano para se manter de pé (ele pausa entre as ondas).", 20, (235, 215, 220), (W / 2, 168), "midtop")
        col1 = [
            "MOVER: W A S D        MIRAR: mouse",
            "SHIFT = dente     BOTÃO ESQUERDO = braço     BOTÃO DIREITO = perna",
            "Com 3 elementos a barra enche e a habilidade é lançada sozinha. ESPAÇO lança antes (Q limpa).",
            "O 1º elemento define a ação; repetir fortalece; misturar faz as duas coisas.",
            "A cada 5 ondas surge um GIGANTE: fuja das áreas vermelhas no chão.",
        ]
        for i, t in enumerate(col1):
            draw_text(s, t, 18, (245, 235, 240), (W / 2, 218 + i * 26), "midtop")
        combos = [
            ("dente", "cospe um dente em linha reta"),
            ("braço", "golpe em arco à frente"),
            ("perna", "dash na direção do mouse"),
            ("perna + dente", "dash e chuva de dentes em área"),
            ("perna + braço", "dash que bate em quem estiver à frente"),
            ("braço + perna", "chute que arremessa e atordoa"),
            ("braço + dente", "soco com dente em área"),
            ("dente + perna", "cospe a perna; se acertar, pula até o inimigo"),
            ("dente + braço", "arremessa o braço como bumerangue"),
            ("dente, dente, dente", "PARRY: come o tiro que vem (ESPAÇO p/ devolver)"),
        ]
        y0 = 356
        for i, (k, d) in enumerate(combos):
            draw_text(s, k, 17, (255, 205, 150), (W / 2 - 20, y0 + i * 24), "topright", True)
            draw_text(s, d, 17, (230, 220, 225), (W / 2 + 0, y0 + i * 24), "topleft")
        draw_text(s, "Sangue cheio = FRENESI. Sangue zerado = MORCEGO (só morde; 1 golpe e acabou; mate um inimigo para voltar).", 17, (255, 160, 170), (W / 2, 612), "midtop")
        blink = int(pygame.time.get_ticks() / 500) % 2 == 0
        if blink:
            draw_text(s, "ENTER, ESPAÇO ou clique para começar", 26, (255, 255, 255), (W / 2, 654), "midtop", True)

    def draw_over(self, s):
        self.draw_overlay_panel(s, 190)
        title = "MORCEGO ABATIDO" if self.player.bat else "SEM SANGUE"
        draw_text(s, title, 80, (210, 25, 50), (W / 2, 190), "midtop", True)
        draw_text(s, "Chegou até a onda %d" % self.wave, 28, (240, 225, 230), (W / 2, 300), "midtop")
        draw_text(s, "Abates: %d     Tempo: %d:%02d" % (self.kills, int(self.time) // 60, int(self.time) % 60), 24, (240, 225, 230), (W / 2, 345), "midtop")
        draw_text(s, "ENTER ou clique para tentar de novo", 26, (255, 255, 255), (W / 2, 440), "midtop", True)

    def draw(self, s, mouse_screen):
        self.draw_world(s)
        if self.state == "play":
            self.draw_hud(s)
        elif self.state == "pause":
            self.draw_hud(s)
            self.draw_overlay_panel(s, 140)
            draw_text(s, "PAUSADO", 70, (255, 255, 255), (W / 2, 260), "midtop", True)
            draw_text(s, "P ou ESC para continuar", 22, (230, 220, 225), (W / 2, 350), "midtop")
        elif self.state == "menu":
            self.draw_menu(s)
        elif self.state == "over":
            self.draw_hud(s)
            self.draw_over(s)
        self.draw_crosshair(s, mouse_screen)


# --------------------------------------------------------------------- main
def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H), pygame.SCALED | pygame.RESIZABLE)
    pygame.display.set_caption("Vampirinha")
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()
    game = Game()
    if "--wave" in sys.argv:  # atalho para testar ondas altas / o chefe: python3 main.py --wave 5
        try:
            game.first_wave = max(1, int(sys.argv[sys.argv.index("--wave") + 1]))
        except (IndexError, ValueError):
            pass
    elem_keys = {pygame.K_LSHIFT: TOOTH, pygame.K_RSHIFT: TOOTH}

    while True:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_F11:
                    pygame.display.toggle_fullscreen()
                elif game.state in ("menu", "over") and ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    game.start()
                elif ev.key in (pygame.K_p, pygame.K_ESCAPE):
                    if game.state == "play":
                        game.state = "pause"
                    elif game.state == "pause":
                        game.state = "play"
                    elif ev.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit()
                elif ev.key == pygame.K_SPACE:
                    game.space_action()
                elif ev.key in elem_keys:
                    game.add_element(elem_keys[ev.key])
                elif ev.key == pygame.K_q:
                    game.clear_queue()
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                if game.state in ("menu", "over") and ev.button == 1:
                    game.start()
                elif ev.button == 1:
                    game.add_element(ARM)
                elif ev.button == 3:
                    game.right_click()

        keys = pygame.key.get_pressed()
        move = V2(keys[pygame.K_d] - keys[pygame.K_a], keys[pygame.K_s] - keys[pygame.K_w])
        if move.length() > 0:
            move = move.normalize()
        mx, my = pygame.mouse.get_pos()
        cam = game.camera
        game.mouse = V2(mx, my) + V2(int(cam.x), int(cam.y))
        if game.state != "pause":
            game.update(dt, move)
        game.draw(screen, (mx, my))
        pygame.display.flip()


if __name__ == "__main__":
    main()
