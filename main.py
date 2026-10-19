#!/usr/bin/env python3
"""Vampirinha - jogo de ação top-down para desktop (Linux/pygame).

Controles e combos: veja o README.md.
"""
import math
import random
import sys

import pygame
from pygame.math import Vector2 as V2

import sounds as SFX
import sprites as SP

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
PROJ_Z = 32                    # altura (px) em que os projéteis voam, para a vista 3/4
AIM_Z = 28                     # o cursor aponta para a altura do corpo: o alvo no chão fica 28 px abaixo dele
FOLLOW_STOP = 30               # cursor a menos disso (do alvo no chão) dela: ela fica parada
FOLLOW_RAMP = 60               # depois dessa faixa ela já anda na velocidade máxima
KEY_ELEMENTS = {pygame.K_q: ARM, pygame.K_w: LEG, pygame.K_e: TOOTH}
PORTRAIT_POS = (6, 2)          # canto do retrato no HUD
BAR_POS = (138, 72)            # moldura da barra de sangue

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
        self.spin += (20.0 if self.kind == "tooth" else 13.0) * dt
        self.life -= dt
        if self.life <= 0 or not (-60 < self.pos.x < WORLD_W + 60 and -60 < self.pos.y < WORLD_H + 60):
            self.dead = True

    BASE_R = {"tooth": 6.0, "leg": 9.0, "arm": 12.0}

    def draw(self, s, cam, A):
        sp = self.pos - cam
        if not (-60 < sp.x < W + 60 and -20 < sp.y < H + 80):
            return
        hp = (sp.x, sp.y - PROJ_Z)
        if self.kind in ("tooth", "leg", "arm"):
            k = self.r / self.BASE_R[self.kind]
            SP.shadow(s, sp, 6 * k + 4, 2.6 * k + 1.5, 90)
            if self.kind == "tooth" and self.vel.length() > 1:  # rastro de velocidade
                d = norm(self.vel)
                A.blit_fx(s, "streak", 0, (hp[0] - d.x * 13 * k, hp[1] - d.y * 13 * k), math.atan2(d.y, d.x), k)
            img = A.rot_frame(self.kind, self.spin)
            if abs(k - 1) > 0.05:
                img = pygame.transform.rotozoom(img, 0, k)
            s.blit(img, img.get_rect(center=(round(hp[0]), round(hp[1]))))
        elif self.kind == "bullet":  # tiro devolvido (embrulhado em sangue)
            SP.shadow(s, sp, 8, 3, 90)
            for i in range(1, 4):
                tp = V2(hp) - norm(self.vel) * i * 9
                pygame.draw.circle(s, (200, 30, 50), tp, max(1, 6 - i * 1.5))
            img = A.single("bullet_back", int(self.age * 18) % 2)
            s.blit(img, img.get_rect(center=(round(hp[0]), round(hp[1]))))
        else:  # tiro inimigo
            SP.shadow(s, sp, 6, 2.5, 90)
            for i in range(1, 4):
                tp = V2(hp) - norm(self.vel) * i * 7
                pygame.draw.circle(s, (255, 170 - i * 30, 60), tp, max(1, 4.5 - i * 1.2))
            img = A.single("bullet", int(self.age * 16) % 2)
            s.blit(img, img.get_rect(center=(round(hp[0]), round(hp[1]))))


def wrap_angle(a):
    return (a + math.pi) % math.tau - math.pi


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
        # animação
        self.hurt_t = 0.0
        self.slash_t = 0.0
        self.fired_t = 0.0
        self.anim_t = random.uniform(0, 1)
        self.flip = False
        self.speed_now = 0.0
        self.last_pos = V2(pos)

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
        self.hurt_t = max(0.0, self.hurt_t - dt)
        self.slash_t = max(0.0, self.slash_t - dt)
        self.fired_t = max(0.0, self.fired_t - dt)
        self.anim_t += dt
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
                g.add_vfx("fx_sword", self.pos, ang, 1.15, 0.2, 28, follow=self, flip=random.random() < 0.5)
                SFX.play("sword")
                if in_cone(self.pos, ang, p, 78, 130, g.player.r):
                    g.hurt_player(10, self.pos)
                self.cd = random.uniform(1.0, 1.4)
                self.slash_t = 0.24
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
                SFX.play("bark")
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
                SFX.play("gunshot")
                self.cd = random.uniform(1.8, 2.6)
                self.fired_t = 0.16
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
                SFX.play("aim")
                self.aim = norm(p + g.player.vel * 0.45 - self.pos)
                g.gun_cd = 0.8

    # ---- desenho
    SHEET = {"sword": "hunter", "gun": "gunner", "dog": "dog", "boss": "boss"}
    TOP = {"sword": 100, "gun": 100, "dog": 56, "boss": 196}
    _arm_cache = {}

    def face_side(self):
        c = math.cos(self.facing)
        if abs(c) > 0.2:
            self.flip = c < 0
        return self.flip

    def sprite_state(self, A):
        """(folha, índice do quadro) conforme o estado da IA."""
        if self.kind == "dog":
            if self.hurt_t > 0 or self.stun > 0:
                key, t, sp = "hurt", 0.0, 1.0
            elif self.state == "windup":
                key, t, sp = "crouch", self.anim_t, 1.0
            elif self.state == "lunge":
                key, t, sp = "lunge", 0.0, 1.0
            elif self.state == "recover":
                key, t, sp = "recover", 0.0, 1.0
            else:
                key, t, sp = "run", self.anim_t, max(0.45, min(1.4, self.speed_now / 170))
            return "dog", A.anim_frame("dog", key, t, sp)[0]
        if self.kind == "sword":
            if self.hurt_t > 0 or self.stun > 0:
                key, t = "hurt", 0.0
            elif self.windup > 0:
                key, t = "windup", 0.4 - self.windup
            elif self.slash_t > 0:
                key, t = "slash", 0.24 - self.slash_t
            elif self.speed_now > 10:
                return "hunter", A.anim_frame("hunter", "walk", self.anim_t, max(0.6, self.speed_now / 95))[0]
            else:
                key, t = "walk", 0.0
            return "hunter", A.anim_frame("hunter", key, t)[0]
        if self.hurt_t > 0 or self.stun > 0:
            return "gunner", A.anim_frame("gunner", "hurt", 0.0)[0]
        if self.windup > 0 or self.fired_t > 0:
            return "gunner", A.anim_frame("gunner", "aim", 0.0)[0]
        if self.speed_now > 10:
            return "gunner", A.anim_frame("gunner", "walk", self.anim_t, max(0.6, self.speed_now / 75))[0]
        return "gunner", A.anim_frame("gunner", "walk", 0.0)[0]

    def draw_gun_arm(self, s, A, sp, idx):
        aiming = self.windup > 0 or self.fired_t > 0
        aim = self.aim if aiming else V2(math.cos(self.facing), math.sin(self.facing))
        ang = math.atan2(aim.y, aim.x)
        sh = A.point("gunner", idx, "shoulder", self.flip)
        pivot = V2(sp.x + sh[0], sp.y + sh[1])
        frame = 1 if self.fired_t > 0.08 else 0
        vflip = math.cos(ang) < 0
        q = int(round(math.degrees(ang) / 4.0)) * 4
        key = (frame, vflip, q)
        cached = Enemy._arm_cache.get(key)
        if cached is None:
            img = A.single("gun_arm", frame)
            px, py = A.meta["gun_arm"]["anchor"]
            if vflip:
                img = pygame.transform.flip(img, False, True)
                py = img.get_height() - py
            rot = pygame.transform.rotozoom(img, -q, 1.0)
            off = V2(px - img.get_width() / 2, py - img.get_height() / 2).rotate(q)
            cached = (rot, off)
            Enemy._arm_cache[key] = cached
        rot, off = cached
        s.blit(rot, rot.get_rect(center=(round(pivot.x - off.x), round(pivot.y - off.y))))
        mz = A.meta["gun_arm"]["muzzle"]
        muzzle = pivot + V2(mz[0], -mz[1] if vflip else mz[1]).rotate(math.degrees(ang))
        if self.windup > 0:  # mira laser
            end = muzzle + aim * 620
            pygame.draw.line(s, (255, 60, 60), muzzle, end, 1)
            pygame.draw.circle(s, (255, 90, 90), muzzle, 2)
        if self.fired_t > 0.06:
            img = A.single("muzzle", int(self.fired_t * 40) % 2)
            img = pygame.transform.rotozoom(img, -math.degrees(ang), 1.0)
            s.blit(img, img.get_rect(center=(round(muzzle.x + aim.x * 8), round(muzzle.y + aim.y * 8))))

    def draw_shadow(self, s, cam):
        sp = self.pos - cam
        rx = {"sword": 17, "gun": 16, "dog": 22, "boss": 62}[self.kind]
        SP.shadow(s, (sp.x, sp.y + 1), rx, rx * 0.3)

    def draw(self, s, cam, A):
        sp = self.pos - cam
        if not (-90 < sp.x < W + 90 and -20 < sp.y < H + 130):
            return
        flip = self.face_side()
        name, idx = self.sprite_state(A)
        A.blit(s, name, idx, sp, flip, self.flash > 0)
        if self.kind == "gun" and not (self.hurt_t > 0 or self.stun > 0):
            self.draw_gun_arm(s, A, sp, idx)
        top = self.TOP[self.kind]
        warn = self.windup > 0 or (self.kind == "dog" and self.state == "windup")
        if warn:  # aviso de golpe "!"
            y = sp.y - top - 14 + math.sin(self.anim_t * 18) * 1.5
            pygame.draw.circle(s, (40, 0, 8), (sp.x, y), 10)
            pygame.draw.circle(s, (255, 60, 60), (sp.x, y), 8)
            draw_text(s, "!", 15, (255, 255, 255), (sp.x, y), "center", True, shadow=False)
        if self.hp < self.max_hp:
            w = 34
            y = sp.y - top - (30 if warn else 4)
            pygame.draw.rect(s, (30, 10, 14), (sp.x - w / 2 - 1, y - 1, w + 2, 6))
            pygame.draw.rect(s, (220, 40, 60), (sp.x - w / 2, y, w * max(0, self.hp) / self.max_hp, 4))


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
        SFX.play("slam" if a == "slam" else ("rain_warn" if a == "rain" else "boss_swing"))
        if a == "slam":
            g.add_vfx("fx_crack", self.pos + self.aim * 70, random.uniform(0, math.tau), 1.0, 3.2, 0, ground=True, fade=1.2,
                      frame=random.randrange(2))
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

    # ---- desenho 2.5D: corpo em sprite, braços e manoplas montados em tempo real
    ARM_L = 46.0
    _fist_cache = {}

    def arms_2d(self, A, sp):
        """Ombro, punho (tela), escala e se fica atrás do corpo, para cada braço."""
        sh = A.meta["boss"]["shoulders"]
        f = -1 if self.flip else 1
        shoulders = {1: sp + V2(sh["near"][0] * f, sh["near"][1]), -1: sp + V2(sh["far"][0] * f, sh["far"][1])}
        aim = V2(self.aim) if self.phase != "walk" else V2(math.cos(self.facing), math.sin(self.facing))
        if aim.length() < 1e-3:
            aim = V2(1, 0)
        perp = V2(-aim.y, aim.x)
        prog = smooth(self.phase_progress())
        ph, at = self.phase, self.attack

        def G(v, z):  # ponto no chão (relativo aos pés) erguido z px
            return sp + v - V2(0, z)

        out = []
        for side in (1, -1):
            shoulder = shoulders[side]
            outward = -f if side == 1 else f
            sway = math.sin(self.anim * 5 + (0 if side == 1 else math.pi)) * 4
            idle = shoulder + V2(outward * 7, 50 + sway)
            raised = shoulder + V2(outward * 6, -64)
            pos, sc, behind = idle, 1.0, False
            punching = side == self.punch_side
            if ph != "walk" and at == "jab" and punching:
                cocked = shoulder + V2(-aim.x * 16, -aim.y * 8 + 6)
                ext_v = aim * (BOSS_REACH - 22)
                ext = G(ext_v, 72)
                behind = ext_v.y < -20 and ph != "windup"
                pos = idle.lerp(cocked, prog) if ph == "windup" else (cocked.lerp(ext, prog) if ph == "strike" else ext.lerp(idle, prog))
            elif ph != "walk" and at == "hook" and punching:
                a0 = math.atan2(aim.y, aim.x)

                def arc(t, a0=a0, side=side):
                    ang = a0 - side * 1.75 + side * 3.5 * t
                    return V2(math.cos(ang), math.sin(ang)) * (120 + 25 * math.sin(math.pi * t))

                if ph == "windup":
                    v = arc(0)
                    pos = idle.lerp(G(v, 72), prog)
                elif ph == "strike":
                    v = arc(prog)
                    pos = G(v, 72)
                else:
                    v = arc(1)
                    pos = G(v, 72).lerp(idle, prog)
                behind = v.y < -20
            elif ph != "walk" and at in ("slam", "rain"):
                down_v = aim * (70 if at == "slam" else 58) + perp * side * (30 if at == "slam" else 26)
                down = G(down_v, 10)
                if ph == "windup":
                    pos, sc = idle.lerp(raised, prog), 1 + 0.35 * prog
                elif ph == "strike":
                    if at == "slam":
                        pos, sc = raised.lerp(down, prog), 1.35 - 0.35 * prog
                    else:
                        down_now = (int(self.anim * 3.6) % 2 == 0) == (side == 1)
                        pos, sc = (down, 1.0) if down_now else (raised, 1.35)
                    behind = down_v.y < -20 and pos == down
                else:
                    pos, sc = (down if at == "slam" else raised).lerp(idle, prog), (1.0 if at == "slam" else 1.35 - 0.35 * prog)
            elif ph != "walk" and at == "charge":
                fwd_v = aim * 95 + perp * side * 34
                fwd = G(fwd_v, 62)
                back = shoulder + V2(-aim.x * 18, 10)
                pos = idle.lerp(back, prog) if ph == "windup" else (fwd if ph == "strike" else fwd.lerp(idle, prog))
                behind = fwd_v.y < -20 and ph == "strike"
            out.append({"shoulder": shoulder, "fist": pos, "scale": sc, "behind": behind, "side": side})
        return out

    def draw_arm(self, s, A, arm, center):
        """Braço montado com discos sombreados (contorno contínuo, sem serrilhado) + manopla."""
        sh, fist, sc = arm["shoulder"], arm["fist"], arm["scale"]
        rage = self.enraged
        d = fist - sh
        dist = d.length() or 1.0
        dirv = d / dist
        L = self.ARM_L
        mid = sh + d * 0.5
        if dist < 2 * L - 2:
            h = math.sqrt(max(0.0, L * L - (dist / 2) ** 2))
            n = V2(-dirv.y, dirv.x)
            e1, e2 = mid + n * h, mid - n * h
            elbow = e1 if (e1 - center).length() > (e2 - center).length() else e2
        else:
            elbow = mid
        wrist = fist - (fist - elbow).normalize() * 12 * sc if (fist - elbow).length() > 1 else fist

        # tubo: fileira de discos lisos ao longo de ombro->cotovelo->pulso, em 4 passadas de cor
        # chapada (contorno, sombra, pele puxada para a luz do alto-esquerda, brilho)
        chain = []
        for a, b, r0, r1 in ((sh, elbow, 14.0, 12.0), (elbow, wrist, 12.0, 13.5)):
            steps = max(1, int((b - a).length() / 2.5))
            for i in range(steps + 1):
                t = i / steps
                chain.append((a.lerp(b, t), r0 + (r1 - r0) * t))
        line, shade, skin, light = (tuple(c) for c in A.meta["boss"]["arm_colors"]["rage" if rage else "skin"])
        if self.flash > 0:
            shade = skin = light = (255, 255, 255)
        for col, grow, k, ox, oy in ((line, 2.2, 1.0, 0.0, 0.0), (shade, 0.0, 1.0, 0.0, 0.0),
                                     (skin, 0.0, 0.78, -0.2, -0.24), (light, 0.0, 0.3, -0.42, -0.5)):
            for p, r in chain:
                img = A.disc(col, r * k + grow)
                s.blit(img, img.get_rect(center=(round(p.x + ox * r), round(p.y + oy * r))))
        # manopla girada na direção do soco
        ang = math.degrees(math.atan2(fist.y - elbow.y, fist.x - elbow.x)) if (fist - elbow).length() > 1 else 90
        q = int(round(ang / 5.0)) * 5
        key = (q, round(sc, 1), rage, self.flash > 0)
        img = Boss._fist_cache.get(key)
        if img is None:
            base = A.single("fist", 1 if rage else 0)
            if self.flash > 0:
                base = A.frame("fist", 1 if rage else 0, False, True)
            img = pygame.transform.rotozoom(base, -q, sc)
            Boss._fist_cache[key] = img
        s.blit(img, img.get_rect(center=(round(fist.x), round(fist.y))))

    def draw(self, s, cam, A):
        sp = self.pos - cam
        if not (-260 < sp.x < W + 260 and -40 < sp.y < H + 260):
            return
        c = math.cos(self.facing)
        if abs(c) > 0.15:
            self.flip = c < 0
        key = {"windup": "windup", "strike": "strike"}.get(self.phase, "walk")
        if self.enraged:
            key += "_rage"
        idx, _ = A.anim_frame("boss", key, self.anim)
        if self.attack == "rain" and self.phase != "recover":
            g = SP.glow(120, (255, 150, 60), 120)
            s.blit(g, g.get_rect(center=(sp.x, sp.y - 90)), special_flags=pygame.BLEND_ADD)
        elif self.enraged:
            g = SP.glow(110, (255, 40, 30), 70 + 10 * int(4 + 4 * math.sin(self.anim * 8)))
            s.blit(g, g.get_rect(center=(sp.x, sp.y - 90)), special_flags=pygame.BLEND_ADD)
        arms = self.arms_2d(A, sp)
        center = sp + V2(0, -80)
        for arm in arms:
            if arm["behind"]:
                self.draw_arm(s, A, arm, center)
        A.blit(s, "boss", idx, sp, self.flip, self.flash > 0)
        for arm in sorted((a for a in arms if not a["behind"]), key=lambda a: a["fist"].y):
            self.draw_arm(s, A, arm, center)


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
        # animação
        self.action = None       # animação de ataque/reação em curso
        self.action_t = 0.0
        self.anim_t = 0.0
        self.view = "front"
        self.flip = False
        self.ghosts = []         # rastro do dash
        self.claw_flip = False   # sentido do risco das garras (alterna a cada golpe)
        self.ghost_t = 0.0
        self.frame = ("vampire", 0)

    def play(self, action):
        self.action = action
        self.action_t = 0.0

    def add_blood(self, amount, g):
        if self.bat:
            return
        self.blood = min(BLOOD_MAX, self.blood + amount)
        if self.blood >= BLOOD_MAX and not self.frenzy:
            self.frenzy = True
            SFX.play("frenzy")
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
        self.anim_t += dt
        self.action_t += dt
        for gh in self.ghosts:
            gh[3] -= dt
        self.ghosts = [gh for gh in self.ghosts if gh[3] > 0]
        d = g.cursor_ground() - self.pos
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
        d["t"] = d.get("t", 0.0) + dt   # tempo desde o início (para a animação do dash)
        self.ghost_t -= dt
        if self.ghost_t <= 0:  # rastro de "fantasmas" da vampira
            self.ghost_t = 0.04
            self.ghosts.append([V2(self.pos), self.frame[1], self.flip, 0.22])
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
                g.add_vfx("fx_punch", self.pos, random.uniform(0, math.tau), 0.8, 0.28, 14)
                SFX.play("punch")
                g.aoe(self.pos, 75, 16 * POWER_DMG[d.get("power", 1) - 1], 320, 0.4, (110, 165, 255))
            return
        self.vel = d["dir"] * 80
        if d.get("burst"):
            g.tooth_ring(self.pos, d["burst"][0], d["burst"][1])
            self.play("spit")
            SFX.play("spit")
            g.hud_spit("tooth", 5)

    # ---- desenho
    def choose_view(self):
        sy, cx = math.sin(self.facing), math.cos(self.facing)
        if sy < -0.5:
            self.view = "back"
        elif sy > -0.3:
            self.view = "front"
        if abs(cx) > 0.12:
            self.flip = cx < 0
        return self.view, self.flip

    def anim_state(self, g, A):
        """Escolhe a animação: dash > ataque/reação > pulando sem perna > correndo > parada."""
        view, flip = self.choose_view()
        t, speed = self.anim_t, 1.0
        if self.dash:
            base = "dash_strike" if self.dash.get("dmg", 0) > 0 else "dash"
            t = self.dash.get("t", 0.0)
        else:
            base = None
            if self.action:
                a = A.anim("vampire", view + "/" + self.action)
                if self.action_t * a["fps"] < len(a["frames"]):
                    base, t = self.action, self.action_t
                else:
                    self.action = None
            if base is None:
                if g.leg_out():
                    base = "hop"
                elif self.vel.length() > 40:
                    base, speed = "run", max(0.6, self.vel.length() / 235)
                else:
                    base = "idle"
        if g.arm_out() and A.has_anim("vampire", view + "/" + base + "_na"):
            base += "_na"
        idx, _ = A.anim_frame("vampire", view + "/" + base, t, speed)
        self.frame = ("vampire", idx)
        return idx, flip

    def draw_shadow(self, s, cam):
        sp = self.pos - cam
        if self.bat:
            SP.shadow(s, sp, 11, 3.5, 80)
        else:
            SP.shadow(s, (sp.x, sp.y + 1), 19, 6)

    def draw_bat(self, s, sp, g, A):
        if g.state == "over":
            idx, _ = A.anim_frame("bat", "bat_die", g.over_t)
        elif 0.15 < self.cast_cd <= 0.4:
            idx, _ = A.anim_frame("bat", "bat_bite", 0.4 - self.cast_cd)
        else:
            idx, _ = A.anim_frame("bat", "bat_fly", g.time)
        flip = math.cos(self.facing) < 0
        blink = self.invuln > 0 and int(g.time * 30) % 2 == 0
        A.blit(s, "bat", idx, sp, flip, self.flash > 0, alpha=120 if blink else None)

    def draw(self, s, cam, g, A):
        sp = self.pos - cam
        if self.bat:
            self.draw_bat(s, sp, g, A)
            return
        idx, flip = self.anim_state(g, A)
        for gpos, gidx, gflip, gt in self.ghosts:  # rastro do dash
            img = A.tinted("vampire", gidx, gflip, (190, 110, 255))
            img = img.copy()
            img.set_alpha(int(95 * gt / 0.22))
            ax, ay = A.anchor("vampire")
            if gflip:
                ax = img.get_width() - ax
            gp = gpos - cam
            s.blit(img, (round(gp.x - ax), round(gp.y - ay)))
        if self.frenzy:
            pulse = 0.5 + 0.5 * math.sin(g.time * 12)
            gl = SP.glow(62, (255, 30, 50), 150 + 10 * int(pulse * 6))
            s.blit(gl, gl.get_rect(center=(sp.x, sp.y - 50)), special_flags=pygame.BLEND_ADD)
        blink = self.invuln > 0 and self.flash <= 0 and int(g.time * 30) % 2 == 0
        A.blit(s, "vampire", idx, sp, flip, self.flash > 0, alpha=110 if blink else None)
        if self.frenzy:  # olhos brilhando
            eyes = A.point("vampire", idx, "eyes", flip) or []
            for ex, ey in eyes:
                gl = SP.glow(7, (255, 40, 40), 220)
                s.blit(gl, gl.get_rect(center=(sp.x + ex, sp.y + ey)), special_flags=pygame.BLEND_ADD)
        for i, _ in enumerate(self.mouth):  # tiros guardados na boca orbitando
            a = g.time * 3 + i * 2.1
            pos = (sp.x + math.cos(a) * 26, sp.y - 58 + math.sin(a) * 9)
            img = A.single("bullet", 0)
            s.blit(img, img.get_rect(center=(round(pos[0]), round(pos[1]))))

    def mouth_screen(self, cam, A):
        idx = self.frame[1]
        m = A.point("vampire", idx, "mouth", self.flip) or (0, -52)
        return self.pos - cam + V2(m)


# --------------------------------------------------------------------- jogo
class Game:
    def __init__(self):
        self.ground = self.make_ground()
        self.props = self.make_props()
        self.vignette = self.make_vignette()
        self.fx_surf = pygame.Surface((W, H), pygame.SRCALPHA)
        self.mouse = V2(WORLD_W / 2 + 100, WORLD_H / 2)
        self.state = "menu"
        self.camera = V2()
        self.first_wave = 1
        self.hold_still = False  # botão esquerdo apertado: ela não sai do lugar
        self.reset()

    # ---- preparação
    def make_ground(self):
        """Piso de lajotas + manchas + decalques (grama, ossos, flores...) num Surface só."""
        A = SP.get()
        rnd = random.Random(7)
        g = pygame.Surface((WORLD_W, WORLD_H))
        tile = A.image("ground.png")
        tw, th = tile.get_size()
        for ty in range(0, WORLD_H, th):
            for tx in range(0, WORLD_W, tw):
                g.blit(tile, (tx, ty))
        blot = pygame.Surface((WORLD_W, WORLD_H), pygame.SRCALPHA)
        for _ in range(80):  # manchas grandes quebram a repetição da textura
            x, y = rnd.randint(0, WORLD_W), rnd.randint(0, WORLD_H)
            r = rnd.randint(90, 280)
            col = (8, 4, 16, rnd.randint(22, 46)) if rnd.random() < 0.6 else (110, 90, 150, rnd.randint(8, 16))
            pygame.draw.ellipse(blot, col, (x - r, y - r * 0.6, 2 * r, 1.2 * r))
        g.blit(blot, (0, 0))
        decals = A.frames("decals")
        weights = A.meta["decals"].get("weights")
        for _ in range(240):
            img = rnd.choices(decals, weights=weights)[0]
            g.blit(img, img.get_rect(center=(rnd.randint(50, WORLD_W - 50), rnd.randint(50, WORLD_H - 50))))
        shade = pygame.Surface((WORLD_W, WORLD_H), pygame.SRCALPHA)
        shade.fill((4, 0, 10, 60))  # escurece o piso para os personagens se destacarem
        g.blit(shade, (0, 0))
        wall = 40
        edge = pygame.Surface((WORLD_W, WORLD_H), pygame.SRCALPHA)
        pygame.draw.rect(edge, (6, 3, 10, 235), (0, 0, WORLD_W, WORLD_H), wall)
        g.blit(edge, (0, 0))
        pygame.draw.rect(g, (90, 20, 40), (wall, wall, WORLD_W - 2 * wall, WORLD_H - 2 * wall), 3)
        return g

    def make_props(self):
        """Túmulos, cruzes, velas e arbustos espalhados (desenhados junto com os personagens)."""
        A = SP.get()
        kinds = A.meta["props"]["kinds"]
        rnd = random.Random(21)
        props = []
        center = V2(WORLD_W / 2, WORLD_H / 2)
        tries = 0
        while len(props) < 46 and tries < 4000:
            tries += 1
            pos = V2(rnd.randint(110, WORLD_W - 110), rnd.randint(130, WORLD_H - 90))
            if (pos - center).length() < 260:
                continue
            if any((pos - q["pos"]).length() < 150 for q in props):
                continue
            k = rnd.randrange(len(kinds))
            props.append({"pos": pos, "idx": k, "kind": kinds[k], "flip": rnd.random() < 0.5, "seed": rnd.random() * 10})
        return props

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
        self.vfx = []            # efeitos desenhados: cortes, impactos, faíscas, rachaduras
        self.corpses = []        # inimigos derrotados caídos no chão (somem aos poucos)
        self.hud_parts = []      # dentes/perna/bala voando para fora da boca do retrato
        self.spit_t = 0.0        # retrato com a boca de cuspe
        self.phurt_t = 0.0       # retrato fazendo careta de dor
        self.over_t = 0.0

    def start(self):
        random.seed()
        self.reset()
        self.wave = self.first_wave - 1
        self.state = "play"

    def game_over(self):
        if self.state == "play":
            self.state = "over"
            self.shake = 14
            self.over_t = 0.0

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
        """Botão direito: lança já a fila (ou cospe o tiro guardado); na forma de morcego, morde."""
        self.cast()

    def space_action(self):
        """ESPAÇO: lança já a fila incompleta, ou cospe de volta o tiro guardado."""
        if not self.player.bat:
            self.cast()

    def clear_queue(self):
        self.player.queue.clear()

    def cursor_ground(self):
        """Ponto do chão "embaixo" do cursor: na vista 3/4 o cursor fica na altura do corpo
        (de quem ela mira, ou dela mesma), então o alvo no chão está um pouco abaixo dele."""
        return self.mouse + V2(0, AIM_Z)

    def aim(self):
        p = self.player
        return norm(self.cursor_ground() - p.pos, (math.cos(p.facing), math.sin(p.facing)))

    def follow_move(self):
        """Ela segue o mouse: anda até o cursor e para quando ele está em cima dela
        (ou enquanto o botão esquerdo está apertado, para mirar sem sair do lugar)."""
        if self.state != "play" or self.hold_still:
            return V2()
        d = self.cursor_ground() - self.player.pos
        dist = d.length()
        if dist <= FOLLOW_STOP:
            return V2()
        return d / dist * min(1.0, (dist - FOLLOW_STOP) / FOLLOW_RAMP)

    def handle_event(self, ev):
        """Teclado e mouse. Devolve "quit" quando o jogo deve fechar."""
        if ev.type == pygame.QUIT:
            return "quit"
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_F11:
                try:
                    pygame.display.toggle_fullscreen()
                except pygame.error:
                    pass
            elif self.state in ("menu", "over") and ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.start()
            elif ev.key in (pygame.K_p, pygame.K_ESCAPE):
                if self.state == "play":
                    self.state = "pause"
                elif self.state == "pause":
                    self.state = "play"
                elif ev.key == pygame.K_ESCAPE:
                    return "quit"
            elif ev.key == pygame.K_SPACE:
                self.space_action()
            elif ev.key in KEY_ELEMENTS:
                self.add_element(KEY_ELEMENTS[ev.key])
            elif ev.key in (pygame.K_r, pygame.K_BACKSPACE):
                self.clear_queue()
            elif ev.key == pygame.K_m:
                SFX.toggle_mute()
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if self.state in ("menu", "over") and ev.button == 1:
                self.start()
            elif ev.button == 3:
                self.right_click()
        return None

    # ---- efeitos visuais
    def add_fx(self, kind, pos, ang, radius, life, color, arc=90):
        self.fx.append({"k": kind, "pos": V2(pos), "ang": ang, "r": radius, "t": life, "max": life, "col": color, "arc": arc})

    def add_text(self, pos, txt, color, life=0.8, size=18):
        self.texts.append({"pos": V2(pos), "txt": txt, "col": color, "t": life, "max": life, "size": size})

    # alturas (px acima do chão) onde as faíscas de acerto aparecem em cada tipo
    SPARK_Z = {"sword": 38, "gun": 36, "dog": 18, "boss": 96}

    def add_vfx(self, name, pos, ang=0.0, scale=1.0, dur=0.25, z=0.0, follow=None, flip=False, ground=False, fade=0.0,
                frame=None):
        """Efeito desenhado (folha fx_*): gira para 'ang', pode acompanhar quem atacou.
        frame fixa um quadro (senão a animação avança com o tempo do efeito)."""
        v = {"name": name, "pos": V2(pos), "ang": ang, "scale": scale, "t": 0.0, "dur": dur, "z": z,
             "follow": follow, "off": V2(pos) - follow.pos if follow is not None else V2(), "flip": flip,
             "ground": ground, "fade": fade, "frame": frame}
        self.vfx.append(v)
        return v

    def hit_spark(self, pos, z, dmg, gold=False):
        self.add_vfx("fx_spark_w" if gold else "fx_spark", pos + V2(random.uniform(-6, 6), random.uniform(-4, 4)),
                     random.uniform(0, math.tau), 0.75 + min(0.8, dmg / 40.0), 0.2, z)

    def draw_vfx(self, s, cam, A, ground):
        for v in self.vfx:
            if v["ground"] != ground:
                continue
            base = v["follow"].pos + v["off"] if v["follow"] is not None else v["pos"]
            sp = base - cam
            if not (-200 < sp.x < W + 200 and -200 < sp.y < H + 260):
                continue
            n = A.meta[v["name"]]["count"]
            k = v["t"] / v["dur"]
            idx = v["frame"] if v["frame"] is not None else min(n - 1, int(k * n))
            alpha = None
            if v["fade"] and v["dur"] - v["t"] < v["fade"]:
                alpha = 255 * max(0.0, (v["dur"] - v["t"]) / v["fade"])
            A.blit_fx(s, v["name"], idx, (sp.x, sp.y - v["z"]), v["ang"], v["scale"], v["flip"], alpha)

    def blood_burst(self, pos, n, speed=180, z=34):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = V2(math.cos(a), math.sin(a)) * random.uniform(40, speed)
            life = random.uniform(0.25, 0.6)
            self.parts.append([V2(pos), v, life, life, random.choice([(170, 15, 35), (210, 30, 50), (120, 10, 25)]),
                               random.uniform(2, 5), z + random.uniform(-10, 10)])

    def dust(self, pos, n):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = V2(math.cos(a), math.sin(a)) * random.uniform(60, 260)
            life = random.uniform(0.3, 0.7)
            self.parts.append([V2(pos), v, life, life, random.choice([(120, 104, 96), (92, 80, 76), (150, 130, 118)]),
                               random.uniform(3, 7), random.uniform(0, 8)])

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
            SFX.play("death")
            self.game_over()
            return True
        p.blood -= dmg
        p.invuln = 0.45
        p.flash = 0.18
        self.hit_spark(p.pos, 34, dmg, gold=True)
        p.vel += norm(p.pos - src) * knock
        p.play("hurt")
        SFX.play("hurt")
        self.phurt_t = 0.35
        self.add_text(p.pos + V2(0, -30), "-%d" % dmg, (255, 90, 110), 0.7, 22)
        if p.blood <= 0 and not p.frenzy:
            self.become_bat()
        return True

    def leg_out(self):
        """A perna foi cuspida (ou ela está pulando até o inimigo)?"""
        if self.player.dash and self.player.dash.get("kind") == "leap":
            return True
        return any(pr.kind == "leg" for pr in self.projs)

    def arm_out(self):
        return any(pr.kind == "arm" for pr in self.projs)

    def portrait_state(self):
        p = self.player
        if self.state == "over":
            return "dead"
        if p.bat:
            return "bat"
        if self.phurt_t > 0:
            return "hurt"
        base = "frenzy" if p.frenzy else ("low" if p.blood < 25 else "normal")
        if self.spit_t > 0:
            return base + "_spit"
        if (self.time % 3.7) < 0.13:
            return base + "_blink"
        return base

    def hud_spit(self, kind="tooth", n=1):
        """Retrato faz cara de cuspe e o que ela cuspiu sai voando da boca no HUD."""
        self.spit_t = 0.3
        p = self.player
        base = "frenzy" if p.frenzy else ("low" if p.blood < 25 else "normal")
        m = SP.get().meta["portraits"]["mouth"].get(base + "_spit", (110, 128))
        mouth = V2(PORTRAIT_POS) + V2(m)
        for i in range(max(1, n)):
            self.hud_parts.append({
                "kind": kind, "pos": V2(mouth), "t": 1.8, "bounced": False,
                "vel": V2(random.uniform(150, 290) + i * 25, random.uniform(-330, -170)),
                "ang": random.uniform(0, math.tau), "spin": random.uniform(-16, 16)})

    def update_hud_parts(self, dt):
        floor = PORTRAIT_POS[1] + 168
        for h in self.hud_parts:
            h["vel"].y += 980 * dt
            h["pos"] += h["vel"] * dt
            h["ang"] += h["spin"] * dt
            h["t"] -= dt
            if h["pos"].y > floor and h["vel"].y > 0 and not h["bounced"]:
                h["pos"].y = floor
                h["vel"].y *= -0.42
                h["vel"].x *= 0.55
                h["spin"] *= 0.5
                h["bounced"] = True
        self.hud_parts = [h for h in self.hud_parts if h["t"] > 0 and h["pos"].y < H + 40]

    def resting(self):
        """Entre as ondas (nenhum inimigo vivo ou por nascer) o sangue não escorre."""
        return not self.enemies and not self.spawn_q

    def become_bat(self):
        p = self.player
        if p.bat or self.state != "play":
            return
        SFX.play("bat")
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
        SFX.play("revert")
        p.bat = False
        p.r = 14
        p.blood = BAT_REVERT_BLOOD
        p.invuln = 1.0
        self.add_fx("ring", p.pos, 0, 200, 0.5, (255, 90, 110))
        self.add_text(p.pos + V2(0, -42), "forma normal!", (255, 150, 160), 1.4, 24)

    def bite(self):
        p = self.player
        SFX.play("bite")
        a = self.aim()
        face = math.atan2(a.y, a.x)
        p.vel += a * 520  # bote para frente
        self.add_vfx("fx_bite", p.pos + a * 34, 0.0, 1.0, 0.22, 34, follow=p)
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
        e.hurt_t = 0.22
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
        self.hit_spark(e.pos, self.SPARK_Z.get(e.kind, 34), dmg, gold=self.player.frenzy)
        self.blood_burst(e.pos, 5)
        self.shake = max(self.shake, 3)
        SFX.play("hit")
        if e.hp <= 0:
            e.dead = True
            SFX.play("kill")
            self.kills += 1
            if self.player.bat:
                self.revert_human()
            self.blood_burst(e.pos, 20, 260)
            self.splat(e.pos)
            self.shake = max(self.shake, 6)
            life = 3.0 if e.kind == "boss" else 1.4
            self.corpses.append({"name": Enemy.SHEET[e.kind], "pos": V2(e.pos), "flip": e.flip, "t": life, "max": life})
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
        p.play("spit")
        SFX.play("spit_back")
        self.hud_spit("bullet", 1)
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
        self.add_text(p.pos + V2(0, -70), "PARRY!", (255, 225, 120), 1.0, 26)
        p.play("chomp")
        SFX.play("chomp")
        self.add_vfx("fx_bite", p.pos + self.aim() * 22, 0.0, 1.7, 0.32, 48, follow=p)
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
            p.play("spit")
            SFX.play("spit")
            self.hud_spit("tooth", power)
            return 0.28
        if key == "A":
            self.cone(p.pos, face, 82 * s, 130, 16 * m, 260, 0.15, ELEM_COLOR[ARM])
            p.play("punch")
            SFX.play("claw")
            p.claw_flip = not p.claw_flip  # alterna o sentido das garras a cada golpe
            self.add_vfx("fx_claw", p.pos, face, 1.1 * s, 0.24, 24, follow=p, flip=p.claw_flip)
            return 0.4
        if key == "L":
            SFX.play("dash")
            p.dash = {"kind": "dash", "dir": a, "left": 230 + 60 * (power - 1), "speed": 1300,
                      "dmg": 0, "knock": 0, "stun": 0, "hit": set()}
            return 0.65
        if key == "TL":  # cospe a perna; se acertar, pula até o inimigo
            pr = Proj("leg", p.pos + a * 22, a * 680, 14 * m, 9 * s, 0.55, knock=120)
            pr.leap = True
            self.projs.append(pr)
            p.leap_power = power
            p.play("spit")
            SFX.play("spit")
            self.hud_spit("leg", 1)
            return 0.8
        if key == "TA":  # braço bumerangue
            count = 1 if power == 1 else 2
            for i in range(count):
                off = 0 if count == 1 else (-0.18 if i == 0 else 0.18)
                v = V2(math.cos(face + off), math.sin(face + off))
                pr = Proj("arm", p.pos + v * 22, v * 640, 9 * m, 12 * s, 3, pierce=999, knock=140)
                pr.maxdist = 380 + 40 * power
                self.projs.append(pr)
            p.play("throw")
            SFX.play("throw")
            return 0.9
        if key == "LT":  # dash + chuva de dentes
            count = (8, 12, 16)[power - 1]
            SFX.play("dash")
            p.dash = {"kind": "dash", "dir": a, "left": 220 + 40 * (power - 1), "speed": 1300,
                      "dmg": 0, "knock": 0, "stun": 0, "hit": set(),
                      "burst": (count, 8 * (1 + 0.25 * (power - 1)))}
            return 0.9
        if key == "LA":  # dash com golpe à frente
            SFX.play("dash")
            SFX.play("kick")
            p.dash = {"kind": "dash", "dir": a, "left": 250 + 50 * (power - 1), "speed": 1350,
                      "dmg": 18 * m, "knock": 430, "stun": 0.35, "hit": set()}
            self.add_vfx("fx_kick", p.pos, face, 0.75, 0.24, 18, follow=p)
            return 0.85
        if key == "AL":  # chute
            self.cone(p.pos, face, 100 * s, 80, 14 * m, 720, 0.8, (255, 200, 120))
            p.play("kick")
            SFX.play("kick")
            self.add_vfx("fx_kick", p.pos, face, 1.05 * s, 0.26, 16, follow=p, flip=random.random() < 0.5)
            return 0.7
        if key == "AT":  # soco com dente em área
            p.play("punch")
            SFX.play("punch")
            center = p.pos + a * 62
            self.add_vfx("fx_punch", center, random.uniform(0, math.tau), 0.98 * s, 0.3, 20)
            self.aoe(center, 92 * s, 24 * m, 400, 0.3, (250, 235, 200))
            for _ in range(10):
                ang = random.uniform(0, math.tau)
                v = V2(math.cos(ang), math.sin(ang))
                self.parts.append([center + v * 10, v * random.uniform(160, 320), 0.35, 0.35, ELEM_COLOR[TOOTH], 4, 30])
            self.shake = max(self.shake, 7)
            return 0.8
        return 0.3

    # ---- atualização
    def start_wave(self, n):
        self.wave = n
        SFX.play("wave")
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
            SFX.play("roar")
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
                SFX.play("clear")
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
        self.update_hud_parts(dt)
        self.spit_t = max(0.0, self.spit_t - dt)
        self.phurt_t = max(0.0, self.phurt_t - dt)
        for c in self.corpses:
            c["t"] -= dt
        self.corpses = [c for c in self.corpses if c["t"] > 0]
        for v in self.vfx:
            v["t"] += dt
        self.vfx = [v for v in self.vfx if v["t"] < v["dur"]]
        if self.state == "over":
            self.over_t += dt

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
        for e in self.enemies:  # velocidade real (para o ritmo da animação de andar)
            e.speed_now += ((e.pos - e.last_pos).length() / max(dt, 1e-4) - e.speed_now) * min(1.0, 10 * dt)
            e.last_pos = V2(e.pos)

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
                SFX.play("slam", 0.55)
                self.add_fx("ring", h["pos"], 0, h["r"], 0.35, (255, 150, 60))
                self.add_fx("disc", h["pos"], 0, h["r"], 0.18, (255, 120, 50))
                self.add_vfx("fx_crack", h["pos"], random.uniform(0, math.tau), 0.6, 2.2, 0, ground=True, fade=0.9,
                             frame=random.randrange(2))
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
        A = SP.get()
        cam = V2(self.camera)
        if self.shake > 0:
            cam += V2(random.uniform(-1, 1), random.uniform(-1, 1)) * self.shake
        cam.x = max(0, min(WORLD_W - W, cam.x))
        cam.y = max(0, min(WORLD_H - H, cam.y))
        s.blit(self.ground, (0, 0), pygame.Rect(int(cam.x), int(cam.y), W, H))
        cam = V2(int(cam.x), int(cam.y))

        # inimigos derrotados caídos no chão
        for c in self.corpses:
            sp = c["pos"] - cam
            if -140 < sp.x < W + 140 and -40 < sp.y < H + 200:
                idx = A.anim(c["name"], "dead")["frames"][0]
                A.blit(s, c["name"], idx, sp, c["flip"], alpha=255 * min(1.0, c["t"] / 0.6))

        # efeitos no chão: golpes, ondas de choque e avisos do Gigante
        ov = self.fx_surf
        ov.fill((0, 0, 0, 0))
        for f in self.fx:
            k = f["t"] / f["max"]
            sp = f["pos"] - cam
            if f["k"] == "cone":  # área do golpe marcada de leve no chão (o corte desenhado vai por cima)
                reach = f["r"] * (0.65 + 0.35 * (1 - k))
                a0 = f["ang"] - math.radians(f["arc"]) / 2
                pts = [sp]
                for i in range(15):
                    a = a0 + math.radians(f["arc"]) * i / 14
                    pts.append(sp + V2(math.cos(a), math.sin(a)) * reach)
                pygame.draw.polygon(ov, (*f["col"], int(60 * k)), pts)
            elif f["k"] == "disc":
                pygame.draw.circle(ov, (*f["col"], int(110 * k)), sp, f["r"])
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
        self.draw_vfx(s, cam, A, ground=True)   # rachaduras no chão
        for f in self.fx:  # ondas de choque
            if f["k"] == "ring":
                k = f["t"] / f["max"]
                A.shock_ring(s, f["pos"] - cam, f["r"] * (0.35 + 0.65 * (1 - k)), f["col"], 255 * min(1.0, k * 1.6))

        # sombras, depois tudo que fica em pé ordenado pela profundidade (y no chão)
        visible_props = [q for q in self.props if -80 < q["pos"].x - cam.x < W + 80 and -10 < q["pos"].y - cam.y < H + 90]
        for q in visible_props:
            SP.shadow(s, q["pos"] - cam + V2(0, 1), 18, 5, 120)
        for e in self.enemies:
            e.draw_shadow(s, cam)
        self.player.draw_shadow(s, cam)
        items = [(q["pos"].y, -1, q) for q in visible_props]
        items += [(e.pos.y, 0, e) for e in self.enemies]
        items.append((self.player.pos.y, 0, self.player))
        items += [(pr.pos.y, 1, pr) for pr in self.projs]
        items += [(b.pos.y, 1, b) for b in self.ebullets]
        items.sort(key=lambda it: (it[0], it[1]))
        for _, _, obj in items:
            if obj is self.player:
                obj.draw(s, cam, self, A)
            elif isinstance(obj, dict):
                self.draw_prop(s, cam, A, obj)
            else:
                obj.draw(s, cam, A)
        self.draw_vfx(s, cam, A, ground=False)  # cortes, impactos e faíscas por cima de todos

        for pt in self.parts:
            k = pt[2] / pt[3]
            pygame.draw.circle(s, pt[4], pt[0] - cam - V2(0, pt[6]), max(1, pt[5] * (0.4 + 0.6 * k)))

        for tx in self.texts:
            k = tx["t"] / tx["max"]
            img = font(tx["size"], True).render(tx["txt"], True, tx["col"])
            img.set_alpha(int(255 * min(1.0, k * 2)))
            r = img.get_rect(center=(tx["pos"].x - cam.x, tx["pos"].y - cam.y - 46))
            s.blit(img, r)

        s.blit(self.vignette, (0, 0))
        if self.player.frenzy:
            tint = pygame.Surface((W, H), pygame.SRCALPHA)
            a = 28 + int(18 * math.sin(self.time * 10))
            tint.fill((200, 20, 30, a))
            s.blit(tint, (0, 0))
        self._cam_draw = cam

    def draw_prop(self, s, cam, A, q):
        sp = q["pos"] - cam
        A.blit(s, "props", q["idx"], sp, q["flip"])
        if q["kind"] == "candles":  # chama tremulando
            for fx, fy in A.meta["props"]["flames"]:
                fl = 0.75 + 0.25 * math.sin(self.time * 13 + q["seed"] + fx)
                gl = SP.glow(18, (255, 150, 60), 60 + 10 * int(fl * 8))
                x = sp.x + (-fx if q["flip"] else fx)
                s.blit(gl, gl.get_rect(center=(x, sp.y + fy)), special_flags=pygame.BLEND_ADD)

    def draw_crosshair(self, s, pos):
        x, y = pos
        pygame.draw.circle(s, (255, 255, 255), (x, y), 11, 2)
        pygame.draw.circle(s, (210, 30, 50), (x, y), 3)
        for dx, dy in ((14, 0), (-14, 0), (0, 14), (0, -14)):
            pygame.draw.line(s, (255, 255, 255), (x + dx * 0.6, y + dy * 0.6), (x + dx * 1.3, y + dy * 1.3), 2)

    # ---- HUD
    PBG = {"normal": ((86, 50, 118), (20, 10, 30)), "frenzy": ((190, 20, 46), (46, 0, 12)),
           "low": ((60, 78, 118), (12, 16, 28)), "dead": ((70, 70, 80), (14, 14, 18)),
           "bat": ((70, 46, 130), (14, 8, 34)), "hurt": ((235, 90, 100), (70, 10, 24))}
    _pbg = {}
    _scaled = {}

    def portrait_bg(self, state):
        key = state.split("_")[0]
        img = Game._pbg.get(key)
        if img is None:
            r = SP.get().meta["portraits"]["radius"]
            inner, outer = self.PBG.get(key, self.PBG["normal"])
            img = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            steps = 20
            for i in range(steps):
                t = i / (steps - 1)
                col = tuple(int(o + (n - o) * t) for o, n in zip(outer, inner))
                pygame.draw.circle(img, col + (255,), (r + 1, r + 1 + int(t * 10)), max(2, int(r * (1 - t * 0.85))))
            pygame.draw.circle(img, outer + (255,), (r + 1, r + 1), r, 4)
            Game._pbg[key] = img
        return img

    def scaled(self, surf, key, size):
        k = (key, size)
        img = Game._scaled.get(k)
        if img is None:
            img = pygame.transform.smoothscale(surf, size)
            Game._scaled[k] = img
        return img

    def draw_portrait(self, s, pos, state, scale=1.0, shake=0.0):
        A = SP.get()
        m = A.meta["portraits"]
        cx, cy = m["center"]
        jx = random.uniform(-shake, shake)
        jy = random.uniform(-shake, shake)
        x, y = pos
        if self.player.frenzy and state.startswith("frenzy"):
            gl = SP.glow(int(96 * scale), (255, 30, 50), 150 + 10 * int(3 + 3 * math.sin(self.time * 10)))
            s.blit(gl, gl.get_rect(center=(x + cx * scale, y + cy * scale)), special_flags=pygame.BLEND_ADD)
        bg = self.portrait_bg(state)
        back = A.image("portrait_frame_back.png")
        front = A.image("portrait_frame_front.png")
        face = A.portrait(state)
        if scale != 1.0:
            size = (int(face.get_width() * scale), int(face.get_height() * scale))
            bg = self.scaled(bg, "bg" + state.split("_")[0], (int(bg.get_width() * scale), int(bg.get_height() * scale)))
            back = self.scaled(back, "fb", size)
            front = self.scaled(front, "ff", size)
            face = self.scaled(face, "p" + state, size)
        s.blit(bg, bg.get_rect(center=(x + cx * scale, y + cy * scale)))
        s.blit(back, (x, y))
        s.blit(face, (x + jx, y + jy))
        s.blit(front, (x, y))

    def draw_blood_bar(self, s):
        A = SP.get()
        p = self.player
        bx, by = BAR_POS
        ix, iy, iw, ih = A.meta["bar"]["inner"]
        ix, iy = bx + ix, by + iy
        pygame.draw.rect(s, (22, 5, 12), (ix, iy, iw, ih))
        frac = max(0.0, min(1.0, p.blood / BLOOD_MAX))
        fw = int(iw * frac)
        if fw > 0:
            if p.frenzy:
                pulse = 0.5 + 0.5 * math.sin(self.time * 14)
                col, dark, light = (255, 46 + int(40 * pulse), 64), (170, 10, 36), (255, 170, 180)
            elif frac < 0.25:
                blink = 0.5 + 0.5 * math.sin(self.time * 8)
                col, dark, light = (150 + int(60 * blink), 16, 40), (90, 6, 22), (255, 120, 140)
            else:
                col, dark, light = (200, 20, 52), (120, 8, 30), (255, 120, 140)
            pygame.draw.rect(s, col, (ix, iy, fw, ih))
            pygame.draw.rect(s, dark, (ix, iy + int(ih * 0.62), fw, ih - int(ih * 0.62)))
            pygame.draw.rect(s, light, (ix + 2, iy + 3, max(0, fw - 4), 3))
            for k in range(7):  # bolhas subindo no sangue
                bxk = ix + ((k * 97 + self.time * (30 + k * 7)) % max(1, fw))
                byk = iy + ih - 3 - ((self.time * 18 + k * 11) % (ih - 4))
                pygame.draw.circle(s, light, (bxk, byk), 1 + (k % 2))
            pygame.draw.line(s, light, (ix + fw - 1, iy + 1), (ix + fw - 1, iy + ih - 2), 2)
        if p.bat:
            pygame.draw.rect(s, (40, 24, 70), (ix, iy, iw, ih))
        s.blit(A.single("bar"), (bx, by))
        if p.frenzy:
            label, lcol = "FRENESI!", (255, 200, 210)
        elif p.bat:
            label, lcol = "MORCEGO — mate um inimigo para voltar", (215, 185, 255)
        else:
            label, lcol = "SANGUE", (255, 236, 240)
        draw_text(s, label, 15, lcol, (ix + 36, iy + ih / 2), "midleft", True)
        if not p.bat:
            draw_text(s, "%d" % max(0, p.blood), 15, (255, 240, 240), (ix + iw - 10, iy + ih / 2), "midright", True)

    def draw_hud_parts(self, s):
        A = SP.get()
        if self.spit_t > 0.16 and self.state == "play":  # "pwah!" saindo da boca do retrato
            st = self.portrait_state()
            m = A.meta["portraits"]["mouth"].get(st)
            if m:
                mx, my = PORTRAIT_POS[0] + m[0], PORTRAIT_POS[1] + m[1]
                k = (self.spit_t - 0.16) / 0.14
                for ang in (-0.9, -0.35, 0.2):
                    d = V2(math.cos(ang), math.sin(ang))
                    a = V2(mx, my) + d * (8 + 6 * (1 - k))
                    b = a + d * 9 * k
                    pygame.draw.line(s, (40, 10, 30), a, b, 5)
                    pygame.draw.line(s, (255, 255, 255), a, b, 3)
        for h in self.hud_parts:
            alpha = 255 * min(1.0, h["t"] / 0.4)
            if h["kind"] == "tooth":
                A.blit_rot(s, "tooth_hud", h["ang"], h["pos"], alpha)
            elif h["kind"] == "leg":
                A.blit_rot(s, "leg_hud", h["ang"], h["pos"], alpha)
            else:
                img = A.single("bullet_back", 0)
                s.blit(img, img.get_rect(center=(round(h["pos"].x), round(h["pos"].y))))

    def draw_hud(self, s):
        A = SP.get()
        p = self.player
        st = self.portrait_state()
        self.draw_blood_bar(s)
        self.draw_portrait(s, PORTRAIT_POS, st, shake=3.0 if self.phurt_t > 0 else 0.0)
        self.draw_hud_parts(s)
        bx, by = BAR_POS
        if p.mouth:
            x0 = bx + 30
            draw_text(s, "Boca:", 14, (255, 200, 120), (x0, by + 52), "topleft")
            for i in range(len(p.mouth)):
                img = A.single("bullet", 0)
                s.blit(img, img.get_rect(center=(x0 + 56 + i * 20, by + 61)))
            draw_text(s, "ESPAÇO ou BOTÃO DIR. com a fila vazia: cuspir de volta", 13, (230, 200, 160), (x0 + 56 + 3 * 20, by + 53))
        elif self.resting() and self.state == "play" and not p.bat:
            draw_text(s, "sangue em pausa entre as ondas", 13, (205, 175, 190), (bx + 30, by + 52))

        # barra do chefe (vida + habilidade)
        for e in self.enemies:
            if e.kind != "boss":
                continue
            bw, bx0, by0 = 640, W / 2 - 320, H - 126
            draw_text(s, "GIGANTE", 18, (255, 225, 215), (W / 2, by0 - 6), "midbottom", True)
            pygame.draw.rect(s, (20, 6, 10), (bx0 - 4, by0 - 4, bw + 8, 24), border_radius=6)
            pygame.draw.rect(s, (64, 14, 22), (bx0, by0, bw, 16), border_radius=4)
            pygame.draw.rect(s, (214, 54, 62) if not e.enraged else (255, 90, 60), (bx0, by0, int(bw * max(0, e.hp) / e.max_hp), 16), border_radius=4)
            pygame.draw.rect(s, (255, 160, 170), (bx0 + 2, by0 + 2, max(0, int(bw * max(0, e.hp) / e.max_hp) - 4), 3), border_radius=2)
            pygame.draw.rect(s, (142, 127, 180), (bx0, by0, bw, 16), 2, border_radius=4)
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
        slot_img = A.single("slot")
        order = A.meta["icons"]["order"]
        size, gap = slot_img.get_width(), 6
        total = 3 * size + 2 * gap
        sx = W / 2 - total / 2
        sy = 12
        for i in range(0 if p.bat else 3):
            r = pygame.Rect(sx + i * (size + gap), sy, size, size)
            s.blit(slot_img, r)
            if i < len(p.queue):
                e = p.queue[i]
                glow_c = {TOOTH: (230, 220, 200), ARM: (255, 70, 90), LEG: (120, 170, 255)}[e]
                gl = SP.glow(30, glow_c, 90)
                s.blit(gl, gl.get_rect(center=r.center), special_flags=pygame.BLEND_ADD)
                icon = A.single("icons", order.index(e))
                s.blit(icon, icon.get_rect(center=r.center))
            if i == 0:
                draw_text(s, "1º", 12, (200, 180, 220), (r.left + 9, r.top + 6))
        name = combo_name(p.queue)
        if p.bat:
            draw_text(s, "BOTÃO DIR.: morder", 22, (200, 150, 255), (W / 2, sy + 10), "midtop", True)
            draw_text(s, "1 golpe e você morre", 16, (230, 190, 255), (W / 2, sy + 40), "midtop")
        elif name:
            draw_text(s, name, 20, (255, 235, 200), (W / 2, sy + size + 10), "midtop", True)
        elif p.mouth:
            draw_text(s, "Cuspir tiro de volta", 18, (255, 200, 120), (W / 2, sy + size + 10), "midtop", True)
        if p.cast_cd > 0 and not p.bat:
            pygame.draw.rect(s, (255, 235, 200), (sx + 6, sy + size + 3, (total - 12) * min(1, p.cast_cd / 0.9), 3))

        # legenda de teclas
        by = H - 48
        if p.bat:
            draw_text(s, "Ele segue o mouse   BOTÃO DIR.: morder   P: pausa", 14, (180, 165, 185), (W / 2, H - 12), "midbottom")
        else:
            items = [(ARM, "Q"), (LEG, "W"), (TOOTH, "E")]
            bx = W / 2 - 215
            for e, k in items:
                icon = self.scaled(A.single("icons", order.index(e)), "icon" + e, (30, 30))
                s.blit(icon, icon.get_rect(center=(bx + 14, by)))
                draw_text(s, "%s: %s" % (k, ELEM_LABEL[e]), 15, (225, 210, 220), (bx + 34, by), "midleft")
                bx += 150
            draw_text(s, "Ela segue o mouse (segure o BOTÃO ESQ. para ficar parada)   Barra cheia lança sozinha   "
                         "ESPAÇO ou BOTÃO DIR.: lançar já   R: limpar   M: som   P: pausa", 13, (180, 165, 185), (W / 2, H - 12), "midbottom")

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
        st = "normal_blink" if (pygame.time.get_ticks() / 1000.0) % 3.2 < 0.14 else "normal"
        self.draw_portrait(s, (18, 350), st, scale=1.55)
        draw_text(s, "VAMPIRINHA", 84, (210, 25, 50), (W / 2, 70), "midtop", True)
        draw_text(s, "O sangue é a sua vida — e o seu relógio. Cause dano para se manter de pé (ele pausa entre as ondas).", 20, (235, 215, 220), (W / 2, 168), "midtop")
        col1 = [
            "MOVER e MIRAR: ela segue o mouse (cursor em cima dela ou BOTÃO ESQUERDO segurado: fica parada)",
            "Q = braço     W = perna     E = dente",
            "Com 3 elementos a barra enche e a habilidade é lançada sozinha. ESPAÇO ou BOTÃO DIREITO lança antes (R limpa).",
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
            ("dente, dente, dente", "PARRY: come o tiro que vem (ESPAÇO ou BOTÃO DIR. p/ devolver)"),
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
        self.draw_portrait(s, (W / 2 - 176 * 0.75, 40), "dead", scale=1.5)
        title = "MORCEGO ABATIDO" if self.player.bat else "SEM SANGUE"
        draw_text(s, title, 76, (210, 25, 50), (W / 2, 330), "midtop", True)
        draw_text(s, "Chegou até a onda %d" % self.wave, 28, (240, 225, 230), (W / 2, 432), "midtop")
        draw_text(s, "Abates: %d     Tempo: %d:%02d" % (self.kills, int(self.time) // 60, int(self.time) % 60), 24, (240, 225, 230), (W / 2, 474), "midtop")
        draw_text(s, "ENTER ou clique para tentar de novo", 26, (255, 255, 255), (W / 2, 560), "midtop", True)

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
    pygame.mixer.pre_init(22050, -16, 1, 512)
    pygame.init()
    SFX.init()
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

    while True:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        for ev in pygame.event.get():
            if game.handle_event(ev) == "quit":
                pygame.quit()
                sys.exit()

        mx, my = pygame.mouse.get_pos()
        cam = game.camera
        game.mouse = V2(mx, my) + V2(int(cam.x), int(cam.y))
        game.hold_still = bool(pygame.mouse.get_pressed()[0])
        # ela segue o mouse (e para se o cursor sair da janela)
        move = game.follow_move() if pygame.mouse.get_focused() else V2()
        if game.state != "pause":
            game.update(dt, move)
        game.draw(screen, (mx, my))
        pygame.display.flip()


if __name__ == "__main__":
    main()
