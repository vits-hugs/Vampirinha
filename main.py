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
LIFESTEAL = 0.45               # fração do dano causado que vira sangue
FRENZY_SPEED = 1.35
FRENZY_DAMAGE = 1.5
PARRY_RADIUS = 230
MAX_ALIVE = 26

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


class Enemy:
    def __init__(self, kind, pos):
        self.kind = kind
        self.pos = V2(pos)
        self.vel = V2()
        if kind == "sword":
            self.hp = self.max_hp = 34
            self.speed = random.uniform(88, 112)
            self.r = 16
        else:
            self.hp = self.max_hp = 24
            self.speed = random.uniform(66, 80)
            self.r = 15
        self.stun = 0.0
        self.flash = 0.0
        self.cd = random.uniform(0.6, 1.6)
        self.windup = 0.0
        self.aim = V2(1, 0)
        self.facing = 0.0
        self.dead = False
        self.strafe = random.choice((-1, 1))

    def update(self, g, dt):
        self.flash = max(0.0, self.flash - dt)
        self.pos += self.vel * dt
        self.vel *= max(0.0, 1 - 8 * dt)
        self.pos.x = max(20, min(WORLD_W - 20, self.pos.x))
        self.pos.y = max(20, min(WORLD_H - 20, self.pos.y))
        if self.stun > 0:
            self.stun -= dt
            self.windup = 0
            return
        to = g.player.pos - self.pos
        d = to.length() or 0.001
        dirv = to / d
        self.facing = math.atan2(dirv.y, dirv.x)
        self.cd -= dt
        if self.kind == "sword":
            if self.windup > 0:
                self.windup -= dt
                if self.windup <= 0:
                    g.add_fx("cone", self.pos, math.atan2(self.aim.y, self.aim.x), 78, 0.16, (235, 235, 245), arc=130)
                    if in_cone(self.pos, math.atan2(self.aim.y, self.aim.x), g.player.pos, 78, 130, g.player.r):
                        g.hurt_player(10, self.pos)
                    self.cd = 1.1
            elif d > 52:
                self.pos += dirv * self.speed * dt
            elif self.cd <= 0:
                self.windup = 0.4
                self.aim = dirv
        else:
            if self.windup > 0:
                self.windup -= dt
                if self.windup > 0.15:
                    self.aim = dirv
                if self.windup <= 0:
                    b = Proj("ebullet", self.pos + self.aim * 22, self.aim * 360, 8, 6, 3.2, friendly=False)
                    g.ebullets.append(b)
                    self.cd = random.uniform(1.8, 2.6)
            else:
                if d > 360:
                    self.pos += dirv * self.speed * dt
                elif d < 250:
                    self.pos -= dirv * self.speed * 0.8 * dt
                else:
                    perp = V2(-dirv.y, dirv.x) * self.strafe
                    self.pos += perp * self.speed * 0.45 * dt
                if self.cd <= 0 and d < 640:
                    self.windup = 0.5
                    self.aim = dirv

    def draw(self, s, cam):
        sp = self.pos - cam
        if not (-60 < sp.x < W + 60 and -60 < sp.y < H + 60):
            return
        pygame.draw.ellipse(s, (8, 6, 12), (sp.x - self.r, sp.y + self.r * 0.5, self.r * 2, self.r * 0.9))
        fl = self.flash > 0
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
                end = sp + gun_dir * 600
                pygame.draw.line(s, (255, 70, 70), tip, end, 1)
                pygame.draw.circle(s, (255, 60, 60), sp + V2(0, -self.r - 14), 5)
        if self.hp < self.max_hp:
            w = 34
            pygame.draw.rect(s, (30, 10, 14), (sp.x - w / 2, sp.y - self.r - 10, w, 5))
            pygame.draw.rect(s, (200, 40, 50), (sp.x - w / 2, sp.y - self.r - 10, w * max(0, self.hp) / self.max_hp, 5))


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

    def add_blood(self, amount, g):
        self.blood = min(BLOOD_MAX, self.blood + amount)
        if self.blood >= BLOOD_MAX and not self.frenzy:
            self.frenzy = True
            g.add_text(self.pos + V2(0, -40), "FRENESI!", (255, 80, 80), 1.4, 28)
            g.add_fx("ring", self.pos, 0, 220, 0.5, (255, 60, 60))
            g.shake = max(g.shake, 10)

    def start_leap(self, enemy):
        self.dash = {"kind": "leap", "target": enemy, "speed": 1600, "time": 0.45}

    def update(self, g, dt, move):
        self.invuln = max(0.0, self.invuln - dt)
        self.flash = max(0.0, self.flash - dt)
        self.cast_cd = max(0.0, self.cast_cd - dt)
        d = g.mouse - self.pos
        if d.length() > 4:
            self.facing = math.atan2(d.y, d.x)
        if self.frenzy:
            self.blood -= FRENZY_DRAIN * dt
            if self.blood <= FRENZY_END:
                self.blood = FRENZY_END
                self.frenzy = False
                g.add_text(self.pos + V2(0, -40), "frenesi acabou", (220, 180, 190), 1.0, 20)
        else:
            self.blood -= BLOOD_DRAIN * dt
        if self.dash:
            self.update_dash(g, dt)
        else:
            speed = 235 * (FRENZY_SPEED if self.frenzy else 1.0)
            self.vel += (move * speed - self.vel) * min(1.0, 14 * dt)
            self.pos += self.vel * dt
        self.pos.x = max(22, min(WORLD_W - 22, self.pos.x))
        self.pos.y = max(22, min(WORLD_H - 22, self.pos.y))
        if self.blood <= 0 and not self.frenzy:
            g.game_over()

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

    def draw(self, s, cam, g):
        sp = self.pos - cam
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
        self.announced = True
        self.banner = ("", 0.0)
        self.camera = self.player.pos - V2(W / 2, H / 2)

    def start(self):
        random.seed()
        self.reset()
        self.state = "play"

    def game_over(self):
        if self.state == "play":
            self.state = "over"
            self.shake = 14

    # ---- input
    def add_element(self, e):
        if self.state == "play" and len(self.player.queue) < 3:
            self.player.queue.append(e)

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

    def splat(self, pos):
        for _ in range(random.randint(3, 6)):
            off = V2(random.uniform(-18, 18), random.uniform(-18, 18))
            pygame.draw.circle(self.ground, random.choice([(70, 8, 22), (88, 12, 28)]), pos + off, random.randint(3, 9))

    # ---- dano
    def hurt_player(self, dmg, src):
        p = self.player
        if self.state != "play" or p.invuln > 0 or p.dash:
            return False
        p.blood -= dmg
        p.invuln = 0.45
        p.flash = 0.18
        p.vel += norm(p.pos - src) * 260
        self.shake = max(self.shake, 9)
        self.blood_burst(p.pos, 8)
        self.add_text(p.pos + V2(0, -30), "-%d" % dmg, (255, 90, 110), 0.7, 22)
        if p.blood <= 0 and not p.frenzy:
            self.game_over()
        return True

    def damage_enemy(self, e, dmg, src, knock=0.0, stun=0.0):
        if e.dead:
            return
        if self.player.frenzy:
            dmg *= FRENZY_DAMAGE
        real = min(dmg, e.hp)
        e.hp -= dmg
        e.flash = 0.12
        self.player.add_blood(real * LIFESTEAL, self)
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
            self.blood_burst(e.pos, 20, 260)
            self.splat(e.pos)
            self.shake = max(self.shake, 6)

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
        self.spawn_q = ["sword"] * swords + ["gun"] * guns
        random.shuffle(self.spawn_q)
        self.spawn_t = 1.0
        self.announced = False
        self.banner = ("Onda %d" % n, 2.5)

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

        self.player.update(self, dt, move)
        self.update_waves(dt)
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

    def separate_enemies(self):
        es = self.enemies
        for i in range(len(es)):
            a = es[i]
            d = a.pos - self.player.pos
            dl = d.length()
            minimum = a.r + self.player.r + 4
            if 0 < dl < minimum:
                a.pos += d / dl * (minimum - dl)
            for j in range(i + 1, len(es)):
                b = es[j]
                dd = b.pos - a.pos
                dist = dd.length()
                lim = a.r + b.r
                if 0 < dist < lim:
                    push = dd / dist * (lim - dist) * 0.5
                    a.pos -= push
                    b.pos += push

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
        label = "FRENESI!" if p.frenzy else "SANGUE"
        draw_text(s, label, 16, (255, 240, 240), (x + 10, y + h / 2), "midleft", True)
        draw_text(s, "%d" % max(0, p.blood), 16, (255, 240, 240), (x + w - 10, y + h / 2), "midright", True)
        if p.mouth:
            draw_text(s, "Boca:", 15, (255, 200, 120), (x, y + h + 10))
            for i in range(len(p.mouth)):
                pygame.draw.circle(s, (255, 150, 40), (x + 62 + i * 20, y + h + 20), 7)
                pygame.draw.circle(s, (255, 235, 150), (x + 62 + i * 20, y + h + 20), 3)
            draw_text(s, "clique sem elementos p/ cuspir de volta", 14, (230, 200, 160), (x + 62 + 3 * 20 + 6, y + h + 12))

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
        for i in range(3):
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
        if name:
            draw_text(s, name, 20, (255, 235, 200), (W / 2, sy + slot + 12), "midtop", True)
        elif p.mouth:
            draw_text(s, "Cuspir tiro de volta", 18, (255, 200, 120), (W / 2, sy + slot + 12), "midtop", True)
        if p.cast_cd > 0:
            pygame.draw.rect(s, (255, 235, 200), (sx, sy + slot + 4, total * min(1, p.cast_cd / 0.9), 3))

        # legenda de teclas
        by = H - 48
        items = [(LEG, "SHIFT"), (ARM, "BOTÃO DIR."), (TOOTH, "ESPAÇO")]
        bx = W / 2 - 330
        for e, k in items:
            draw_icon(s, e, (bx + 14, by), 20)
            draw_text(s, "%s: %s" % (k, ELEM_LABEL[e]), 15, (225, 210, 220), (bx + 34, by), "midleft")
            bx += 190
        draw_text(s, "BOTÃO ESQ.: lançar   Q: limpar   P: pausa", 14, (180, 165, 185), (W / 2, H - 12), "midbottom")

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
        draw_text(s, "O sangue é a sua vida — e o seu relógio. Cause dano para se manter de pé.", 20, (235, 215, 220), (W / 2, 168), "midtop")
        col1 = [
            "MOVER: W A S D        MIRAR: mouse",
            "SHIFT = perna     BOTÃO DIREITO = braço     ESPAÇO = dente",
            "Empilhe até 3 elementos e lance com o BOTÃO ESQUERDO (Q limpa).",
            "O 1º elemento define a ação; repetir fortalece; misturar faz as duas coisas.",
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
            ("dente, dente, dente", "PARRY: come o tiro que vem (clique p/ devolver)"),
        ]
        y0 = 340
        for i, (k, d) in enumerate(combos):
            draw_text(s, k, 17, (255, 205, 150), (W / 2 - 20, y0 + i * 25), "topright", True)
            draw_text(s, d, 17, (230, 220, 225), (W / 2 + 0, y0 + i * 25), "topleft")
        draw_text(s, "Sangue em 100% = FRENESI: mais rápida e com mais dano. Sangue em 0 = fim.", 17, (255, 160, 170), (W / 2, 612), "midtop")
        blink = int(pygame.time.get_ticks() / 500) % 2 == 0
        if blink:
            draw_text(s, "ENTER, ESPAÇO ou clique para começar", 26, (255, 255, 255), (W / 2, 654), "midtop", True)

    def draw_over(self, s):
        self.draw_overlay_panel(s, 190)
        draw_text(s, "SEM SANGUE", 80, (210, 25, 50), (W / 2, 190), "midtop", True)
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
    elem_keys = {pygame.K_LSHIFT: LEG, pygame.K_RSHIFT: LEG, pygame.K_SPACE: TOOTH}

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
                elif ev.key in elem_keys:
                    game.add_element(elem_keys[ev.key])
                elif ev.key == pygame.K_q:
                    game.clear_queue()
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                if game.state in ("menu", "over") and ev.button == 1:
                    game.start()
                elif ev.button == 1:
                    game.cast()
                elif ev.button == 3:
                    game.add_element(ARM)

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
