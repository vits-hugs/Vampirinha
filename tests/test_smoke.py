"""Teste de fumaça sem janela: simula entradas e confere as mecânicas principais.

Uso: python tests/test_smoke.py
"""
import math
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame  # noqa: E402
from pygame.math import Vector2 as V2  # noqa: E402

import main as vamp  # noqa: E402
from main import ARM, LEG, TOOTH, Boss, Enemy, Game  # noqa: E402
import sprites as SP  # noqa: E402

pygame.init()
screen = pygame.display.set_mode((vamp.W, vamp.H))
DT = 1 / 60


def fresh():
    g = Game()
    g.start()
    g.spawn_q = []
    g.break_t = 999
    g.enemies.clear()
    g.player.blood = 60
    g.mouse = g.player.pos + V2(300, -vamp.AIM_Z)
    return g


def step(g, n=1, move=None):
    for _ in range(n):
        g.update(DT, move or V2())


def cast(g, *elems):
    g.player.cast_cd = 0
    g.player.queue = list(elems)
    g.cast()


def test_blood_drain_and_hit_heals():
    g = fresh()
    g.enemies.append(Enemy("sword", g.player.pos + V2(900, 900)))  # com inimigos vivos o sangue escorre
    b0 = g.player.blood
    step(g, 60)
    assert g.player.blood < b0, "sangue deve cair com o tempo"
    e = Enemy("sword", g.player.pos + V2(150, 0))
    g.enemies.append(e)
    before = g.player.blood
    g.damage_enemy(e, 10, g.player.pos)
    assert g.player.blood > before, "causar dano deve recuperar sangue"


def test_damage_lowers_blood():
    g = fresh()
    b = g.player.blood
    assert g.hurt_player(10, g.player.pos + V2(30, 0))
    assert g.player.blood == b - 10


def test_frenzy():
    g = fresh()
    g.player.add_blood(100, g)
    assert g.player.frenzy
    e = Enemy("sword", g.player.pos + V2(200, 0))
    g.enemies.append(e)
    hp = e.hp
    g.damage_enemy(e, 10, g.player.pos)
    assert hp - e.hp == 10 * vamp.FRENZY_DAMAGE
    step(g, 60 * 10)
    assert not g.player.frenzy, "frenesi deve acabar"


def test_tooth_projectile_hits():
    g = fresh()
    e = Enemy("sword", g.player.pos + V2(250, 0))
    g.enemies.append(e)
    cast(g, TOOTH)
    assert g.projs and g.projs[0].kind == "tooth"
    step(g, 40)
    assert e.hp < e.max_hp


def test_dash_moves_toward_mouse():
    g = fresh()
    x0 = g.player.pos.x
    cast(g, LEG)
    step(g, 30)
    assert g.player.pos.x > x0 + 150


def test_leg_arm_dash_damages():
    g = fresh()
    e = Enemy("sword", g.player.pos + V2(120, 0))
    g.enemies.append(e)
    cast(g, LEG, ARM)
    step(g, 30)
    assert e.hp < e.max_hp


def test_leg_tooth_burst():
    g = fresh()
    cast(g, LEG, TOOTH)
    step(g, 30)
    assert sum(1 for p in g.projs if p.kind == "tooth") >= 8


def test_kick_and_punch():
    g = fresh()
    e1 = Enemy("sword", g.player.pos + V2(70, 0))
    g.enemies.append(e1)
    cast(g, ARM, LEG)
    assert e1.hp < e1.max_hp and e1.stun > 0
    g2 = fresh()
    e2 = Enemy("sword", g2.player.pos + V2(70, 0))
    g2.enemies.append(e2)
    cast(g2, ARM, TOOTH)
    assert e2.hp < e2.max_hp


def test_leg_spit_leaps():
    g = fresh()
    e = Enemy("sword", g.player.pos + V2(250, 0))
    g.enemies.append(e)
    x0 = g.player.pos.x
    cast(g, TOOTH, LEG)
    step(g, 60)
    assert g.player.pos.x > x0 + 150, "deve pular até o inimigo"
    assert e.hp < e.max_hp


def test_boomerang_returns():
    g = fresh()
    e = Enemy("sword", g.player.pos + V2(200, 0))
    g.enemies.append(e)
    cast(g, TOOTH, ARM)
    arm = [p for p in g.projs if p.kind == "arm"]
    assert arm
    step(g, 20)
    assert e.hp < e.max_hp
    step(g, 60 * 4)
    assert not [p for p in g.projs if p.kind == "arm"], "braço deve voltar e sumir"


def test_parry_and_spit_back():
    g = fresh()
    gun = Enemy("gun", g.player.pos + V2(400, 0))
    g.enemies.append(gun)
    far = Enemy("sword", g.player.pos + V2(900, 0))
    g.enemies.append(far)
    from main import Proj
    g.ebullets.append(Proj("ebullet", g.player.pos + V2(150, 0), V2(-360, 0), 8, 6, 3, friendly=False))
    blood = g.player.blood
    cast(g, TOOTH, TOOTH, TOOTH)
    assert all(b.dead for b in g.ebullets) and g.player.mouth, "tiro deve ser comido"
    assert g.player.blood > blood
    g.player.cast_cd = 0
    g.cast()
    assert any(p.kind == "bullet" for p in g.projs), "deve devolver o tiro"
    step(g, 60)
    assert gun.hp < gun.max_hp or far.hp < far.max_hp or gun.dead


def test_triple_tooth_without_bullet_is_strong_shot():
    g = fresh()
    cast(g, TOOTH, TOOTH, TOOTH)
    assert g.projs and g.projs[0].pierce == 2


def test_waves_and_enemies_attack():
    g = Game()
    g.start()
    step(g, 60 * 12)
    assert g.wave >= 1 and g.enemies
    g.player.pos = V2(vamp.WORLD_W / 2, vamp.WORLD_H / 2)
    for _ in range(60 * 30):
        g.update(DT, V2())
        if g.state != "play":
            break
    assert g.state == "over" or g.player.blood < vamp.BLOOD_START


def test_blood_paused_between_waves():
    g = Game()
    g.start()
    g.break_t = 999
    g.enemies.clear()
    g.spawn_q = []
    assert g.resting()
    b = g.player.blood
    step(g, 120)
    assert g.player.blood == b, "sangue nao deve cair entre as ondas"
    g.enemies.append(Enemy("sword", g.player.pos + V2(900, 0)))
    step(g, 60)
    assert g.player.blood < b, "sangue volta a cair com inimigos vivos"


def test_bat_form_and_bite_revert():
    g = fresh()
    far = Enemy("sword", g.player.pos + V2(900, 900))
    e = Enemy("sword", g.player.pos + V2(45, 0))
    e.hp = 10
    g.enemies += [far, e]
    g.player.blood = 0.5
    g.player.queue = [TOOTH]
    step(g, 60)
    p = g.player
    assert p.bat and g.state == "play", "sem sangue vira morcego"
    assert not p.queue
    g.add_element(ARM)
    assert not p.queue, "morcego nao usa elementos"
    b = p.blood
    g.cast()  # morder
    assert not p.bat, "matar com a mordida volta a forma normal"
    assert p.blood > b and e.dead


def test_bat_dies_in_one_hit():
    g = fresh()
    g.enemies.append(Enemy("sword", g.player.pos + V2(900, 900)))
    g.become_bat()
    g.player.invuln = 0
    g.hurt_player(8, g.player.pos + V2(30, 0))
    assert g.state == "over"


def test_human_hit_to_zero_becomes_bat():
    g = fresh()
    g.player.blood = 5
    g.hurt_player(10, g.player.pos + V2(30, 0))
    assert g.player.bat and g.state == "play"


def test_bat_blood_does_not_drain_or_heal():
    g = fresh()
    g.enemies.append(Enemy("sword", g.player.pos + V2(900, 900)))
    g.become_bat()
    g.player.add_blood(50, g)
    step(g, 60)
    assert g.player.blood == 0 and g.player.bat


def _no_damage(g):
    g.player.invuln = 99


def test_swords_hold_ring_and_keep_spacing():
    g = fresh()
    g.wave = 1
    for i in range(8):
        ang = i * 0.7
        g.enemies.append(Enemy("sword", g.player.pos + V2(500, 0).rotate_rad(ang)))
    for _ in range(60 * 7):
        _no_damage(g)
        g.update(DT, V2())
    near = [e for e in g.enemies if (e.pos - g.player.pos).length() < 75]
    assert len(near) <= 4, "so poucos espadachins atacam ao mesmo tempo (%d)" % len(near)
    assert any(e.role == "ring" for e in g.enemies), "o resto fica rondando em anel"
    es = g.enemies
    closest = min((a.pos - b.pos).length() for i, a in enumerate(es) for b in es[i + 1:])
    assert closest > 24, "inimigos nao devem se amontoar (%.1f)" % closest


def test_swords_flank_behind_player():
    g = fresh()  # a vampira mira para a direita (+x)
    g.wave = 1
    for i in range(6):
        g.enemies.append(Enemy("sword", g.player.pos + V2(420, -150 + i * 60)))
    for _ in range(60 * 9):
        _no_damage(g)
        g.update(DT, V2())
    assert any(e.role == "flank" for e in g.enemies)
    behind = [e for e in g.enemies if e.pos.x < g.player.pos.x - 20]
    assert behind, "alguem deve ter contornado e chegado por tras"


def test_dog_lunges_and_hits():
    g = fresh()
    dog = Enemy("dog", g.player.pos + V2(-230, 0))
    dog.cd = 0
    g.enemies.append(dog)
    hits = []
    orig = g.hurt_player
    g.hurt_player = lambda dmg, src: (hits.append(dmg), orig(dmg, src))[1]
    seen = set()
    for _ in range(60 * 6):
        g.player.blood = 60
        g.update(DT, V2())
        seen.add(dog.state)
        if hits:
            break
    assert {"windup", "lunge"} <= seen, "cachorro avisa e avanca em bote (%s)" % seen
    assert hits and hits[0] == 9


def test_dog_lunge_can_be_dodged_with_dash():
    g = fresh()
    dog = Enemy("dog", g.player.pos + V2(-200, 0))
    dog.cd = 0
    g.enemies.append(dog)
    hits = []
    g.hurt_player = lambda dmg, src: hits.append(dmg)
    g.mouse = g.player.pos + V2(0, 300)
    for _ in range(60 * 3):
        g.player.blood = 60
        g.update(DT, V2())
        if dog.state == "lunge":
            cast(g, LEG)
            break
    step(g, 40)
    # o dash tirou a vampira da linha do bote (a trajetoria era travada no inicio do bote)
    assert not hits, "o dash tira a vampira da linha do bote"


def test_gunner_line_of_fire_and_slots():
    g = fresh()
    gun = Enemy("gun", g.player.pos + V2(400, 0))
    ally = Enemy("sword", g.player.pos + V2(200, 4))
    g.enemies += [gun, ally]
    assert g.line_blocked(gun), "aliado no meio bloqueia o tiro"
    ally.pos = g.player.pos + V2(200, 120)
    assert not g.line_blocked(gun)
    guns = [Enemy("gun", g.player.pos + V2(500, i * 40)) for i in range(3)]
    g.enemies += guns
    g.ai_t = 0
    g.plan_ai(DT)
    angles = sorted(round(e.slot_angle % math.tau, 2) for e in guns + [gun])
    assert len(set(angles)) == len(angles), "atiradores ocupam posicoes diferentes"


def test_gunners_do_not_fire_all_at_once():
    g = fresh()
    guns = [Enemy("gun", g.player.pos + V2(380, i * 90 - 135)) for i in range(4)]
    for e in guns:
        e.cd = 0
    g.enemies += guns
    g.ai_t = 0
    for _ in range(int(0.45 / DT)):
        _no_damage(g)
        g.update(DT, V2())
    assert sum(1 for e in guns if e.windup > 0) <= 1, "tiros escalonados, nao uma salva"


# ------------------------------------------------------------------ controles
def test_full_bar_casts_by_itself():
    g = fresh()
    g.add_element(TOOTH)
    g.add_element(TOOTH)
    assert len(g.player.queue) == 2 and not g.projs, "com 2 elementos ainda nao lanca"
    g.add_element(TOOTH)
    assert not g.player.queue and g.projs, "barra cheia lanca sozinha"


def test_space_casts_partial_queue_and_spits_back():
    g = fresh()
    g.add_element(TOOTH)
    g.add_element(LEG)
    assert not g.projs
    g.space_action()
    assert any(p.kind == "leg" for p in g.projs), "ESPACO lanca a fila incompleta"
    g2 = fresh()
    g2.player.mouth = [1]
    g2.space_action()
    assert any(p.kind == "bullet" for p in g2.projs), "ESPACO com fila vazia cospe o tiro de volta"


def test_full_bar_waits_for_cooldown():
    g = fresh()
    g.player.cast_cd = 0.4
    for _ in range(3):
        g.add_element(ARM)
    assert len(g.player.queue) == 3, "espera o fim da recarga"
    step(g, 40)
    assert not g.player.queue, "lanca assim que a recarga termina"


def key(g, k):
    return g.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))


def click(g, button):
    return g.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=button, pos=(0, 0)))


def test_q_w_e_are_arm_leg_tooth_and_r_clears():
    g = fresh()
    g.enemies.append(Enemy("sword", g.player.pos + V2(900, 900)))
    key(g, pygame.K_q)
    key(g, pygame.K_w)
    assert g.player.queue == [ARM, LEG], "Q = braço, W = perna"
    key(g, pygame.K_r)
    assert not g.player.queue, "R limpa a fila"
    key(g, pygame.K_e)
    key(g, pygame.K_e)
    assert g.player.queue == [TOOTH, TOOTH], "E = dente"
    key(g, pygame.K_e)
    assert not g.player.queue and g.projs, "o terceiro enche a barra e lança sozinho"
    for k in (pygame.K_a, pygame.K_s, pygame.K_d, pygame.K_LSHIFT):
        key(g, k)
    assert not g.player.queue, "as teclas antigas não fazem mais nada"
    click(g, 1)
    assert not g.player.queue, "botão esquerdo não põe elemento"


def test_mouse_buttons_and_quit():
    g = fresh()
    g.enemies.append(Enemy("sword", g.player.pos + V2(900, 900)))
    key(g, pygame.K_e)
    click(g, 3)
    assert not g.player.queue and any(pr.kind == "tooth" for pr in g.projs), "botão direito lança já"
    g2 = Game()
    assert key(g2, pygame.K_ESCAPE) == "quit"
    assert g2.handle_event(pygame.event.Event(pygame.QUIT)) == "quit"
    click(g2, 1)
    assert g2.state == "play", "clique começa o jogo"
    key(g2, pygame.K_p)
    assert g2.state == "pause"
    key(g2, pygame.K_ESCAPE)
    assert g2.state == "play"


def test_follows_the_mouse():
    g = fresh()
    g.enemies.append(Enemy("sword", g.player.pos + V2(900, 900)))
    p = g.player
    g.mouse = p.pos + V2(0, -vamp.AIM_Z)  # cursor em cima dela: parada
    assert g.follow_move().length() == 0
    g.mouse = p.pos + V2(10, -vamp.AIM_Z - 15)
    assert g.follow_move().length() == 0, "zona morta em volta dela"
    g.mouse = p.pos + V2(400, -vamp.AIM_Z)
    mv = g.follow_move()
    assert abs(mv.length() - 1) < 1e-6 and mv.x > 0.99, "longe: velocidade máxima na direção do cursor"
    g.mouse = p.pos + V2(vamp.FOLLOW_STOP + vamp.FOLLOW_RAMP / 2, -vamp.AIM_Z)
    assert 0.3 < g.follow_move().length() < 0.7, "perto: desacelera"
    g.hold_still = True
    g.mouse = p.pos + V2(400, -vamp.AIM_Z)
    assert g.follow_move().length() == 0, "botão esquerdo segurado: fica parada"
    g.hold_still = False
    # andando de verdade: chega até o cursor e para
    target = p.pos + V2(250, 120)
    g.mouse = target - V2(0, vamp.AIM_Z)
    for _ in range(60 * 3):
        g.player.blood = 60
        g.update(DT, g.follow_move())
    assert (p.pos - target).length() <= vamp.FOLLOW_STOP + 4, "parou em cima do cursor"
    assert p.vel.length() < 40
    g.state = "pause"
    assert g.follow_move().length() == 0


def test_aim_points_where_the_cursor_shows():
    """Com o cursor no corpo de um inimigo (acima dos pés dele), o dente vai nele."""
    g = fresh()
    e = Enemy("sword", g.player.pos + V2(180, 0))
    g.enemies.append(e)
    g.mouse = e.pos - V2(0, vamp.AIM_Z)
    a = g.aim()
    assert abs(a.y) < 1e-6 and a.x > 0.99
    cast(g, TOOTH)
    step(g, 30)
    assert e.hp < e.max_hp


def test_right_click_casts_and_bat_bites():
    g = fresh()
    g.player.mouth = [1]
    g.right_click()
    assert any(pr.kind == "bullet" for pr in g.projs), "fila vazia: cospe o tiro de volta"
    g.enemies.append(Enemy("sword", g.player.pos + V2(900, 900)))
    e = Enemy("sword", g.player.pos + V2(45, 0))
    e.hp = 5
    g.enemies.append(e)
    g.become_bat()
    g.player.invuln = 0
    g.player.cast_cd = 0  # o cuspe de volta tem uma recarga curta
    g.right_click()
    assert e.dead and not g.player.bat, "no morcego o botao direito morde"


# ---------------------------------------------------------------------- chefe
def boss_fresh(dist=150):
    g = fresh()
    b = Boss(g.player.pos + V2(dist, 0), 700)
    b.cd = 99
    g.enemies.append(b)
    g.player.blood = 80
    hits = []
    orig = g.hurt_player

    def spy(dmg, src, knock=260.0):
        r = orig(dmg, src, knock)
        if r:
            hits.append(dmg)
        return r

    g.hurt_player = spy
    return g, b, hits


def run_attack(g, b, name, seconds):
    b.start(name, norm_dir(g, b), 1.0)
    for _ in range(int(seconds * 60)):
        g.player.blood = 80
        g.update(DT, V2())


def norm_dir(g, b):
    return (g.player.pos - b.pos).normalize()


def test_boss_jab_hits_in_reach():
    g, b, hits = boss_fresh(150)
    run_attack(g, b, "jab", 0.8)
    assert hits == [14]


def test_boss_hook_slam_charge_hit():
    g, b, hits = boss_fresh(110)
    run_attack(g, b, "hook", 1.2)
    assert hits == [16], hits
    g, b, hits = boss_fresh(120)
    run_attack(g, b, "slam", 1.6)
    assert hits == [20], hits
    g, b, hits = boss_fresh(200)
    run_attack(g, b, "charge", 1.5)
    assert hits == [18], hits


def test_boss_attacks_have_a_telegraph_and_can_be_dodged():
    g, b, hits = boss_fresh(150)
    b.start("jab", norm_dir(g, b), 1.0)
    assert b.phase == "windup", "todo golpe comeca com um aviso"
    g.player.pos = V2(g.player.pos.x, g.player.pos.y + 220)  # fora do alcance
    for _ in range(60):
        g.player.blood = 80
        g.player.pos.y = b.pos.y + 220
        g.update(DT, V2())
    assert not hits


def test_boss_special_bar_fills_and_releases_rain():
    g, b, hits = boss_fresh(400)
    b.cd = 99
    step(g, 60 * 5)
    assert 15 < b.special < 40, "a barra enche com o tempo (%.1f)" % b.special
    before = b.special
    g.damage_enemy(b, 40, g.player.pos)
    assert b.special > before + 8, "apanhar tambem enche"
    b.special = 100
    g.player.pos = V2(g.player.pos.x, g.player.pos.y)
    seen_hazards = 0
    for _ in range(60 * 6):
        g.player.blood = 80
        g.update(DT, V2())
        seen_hazards = max(seen_hazards, len(g.hazards))
    assert seen_hazards >= 10, "a habilidade solta varios impactos"
    assert 16 in hits, "quem fica parado leva a Chuva de Socos"
    assert b.special < 30 and not g.hazards, "barra zera depois de soltar"


def test_boss_resists_knockback_and_stun_and_heals_less():
    g, b, hits = boss_fresh(300)
    g.damage_enemy(b, 10, g.player.pos, knock=600, stun=1.0)
    assert b.vel.length() < 100 and b.stun == 0
    g2 = fresh()
    e = Enemy("sword", g2.player.pos + V2(300, 0))
    e.hp = 500
    g2.enemies.append(e)
    g2.player.blood = 40
    g2.damage_enemy(e, 20, g2.player.pos)
    normal = g2.player.blood - 40
    g.player.blood = 40
    g.damage_enemy(b, 20, g.player.pos)
    assert g.player.blood - 40 < normal


def test_boss_death_and_boss_waves():
    g, b, hits = boss_fresh(300)
    b.hp = 1
    g.hazards.append({"pos": V2(0, 0), "r": 50, "t": 5, "dmg": 16, "done": False})
    g.damage_enemy(b, 5, g.player.pos)
    assert b.dead and not g.hazards and "derrotado" in g.banner[0]
    g2 = Game()
    g2.start()
    g2.start_wave(5)
    assert g2.spawn_q[0] == "boss" and "CHEFE" in g2.banner[0]
    g3 = Game()
    g3.first_wave = 5
    g3.start()
    assert g3.wave == 4


def test_boss_pushes_player_instead_of_being_pushed():
    g, b, hits = boss_fresh(40)
    pos = V2(b.pos)
    step(g, 5)
    assert (b.pos - pos).length() < 5 and (g.player.pos - b.pos).length() >= 60


def test_boss_render_all_phases():
    g, b, hits = boss_fresh(200)
    for name in ("jab", "hook", "slam", "charge", "rain"):
        b.phase, b.attack = "walk", None
        b.start(name, norm_dir(g, b), 1.0)
        for i in range(60 * 4):
            g.player.blood = 80
            g.player.invuln = 99
            g.update(DT, V2())
            if i % 6 == 0:
                g.draw(screen, (640, 360))
            if b.phase == "walk":
                break
    b.enraged
    g.draw(screen, (640, 360))


# ------------------------------------------------------------------ arte e HUD
def test_assets_complete():
    A = SP.get()
    for name in ("vampire", "bat", "hunter", "gunner", "dog", "boss", "tooth", "tooth_hud", "leg", "leg_hud", "arm",
                 "bullet", "bullet_back", "icons", "slot", "bar", "fist", "gun_arm", "muzzle", "props", "decals",
                 "fx_claw", "fx_kick", "fx_punch", "fx_sword", "fx_bite", "fx_spark", "fx_spark_w", "fx_crack",
                 "fx_shock", "disc", "streak"):
        assert len(A.frames(name)) == A.meta[name]["count"], name
    for view in ("front", "back"):
        for anim in ("idle", "run", "punch", "kick", "spit", "throw", "dash", "dash_strike", "hurt", "chomp", "hop"):
            assert A.has_anim("vampire", view + "/" + anim), (view, anim)
    for st in ("normal", "normal_blink", "normal_spit", "frenzy", "frenzy_blink", "frenzy_spit", "low", "low_blink",
               "low_spit", "hurt", "dead", "bat"):
        assert A.portrait(st) is not None and st in A.meta["portraits"]["mouth"], st
    for n, keys in (("hunter", ("walk", "windup", "slash", "hurt", "dead")), ("gunner", ("walk", "aim", "hurt", "dead")),
                    ("dog", ("run", "crouch", "lunge", "recover", "hurt", "dead")),
                    ("boss", ("walk", "windup", "strike", "walk_rage", "windup_rage", "strike_rage", "dead")),
                    ("bat", ("bat_fly", "bat_bite", "bat_die"))):
        for k in keys:
            assert A.has_anim(n, k), (n, k)


def test_player_animation_follows_actions():
    A = SP.get()
    g = fresh()
    cast(g, ARM)
    assert g.player.action == "punch"
    idx, flip = g.player.anim_state(g, A)
    assert idx in A.anim("vampire", "front/punch")["frames"] and not flip
    g.mouse = g.player.pos + V2(-100, -200)  # mirando para cima-esquerda: de costas e espelhada
    step(g, 1)
    g.player.anim_state(g, A)
    assert g.player.view == "back" and g.player.flip
    g2 = fresh()
    g2.enemies.append(Enemy("sword", g2.player.pos + V2(900, 900)))
    cast(g2, TOOTH, ARM)
    assert g2.player.action == "throw"
    step(g2, 30)  # arremesso terminou: volta a ficar parada
    idx, _ = g2.player.anim_state(g2, A)
    assert idx in A.anim("vampire", "front/idle")["frames"] + A.anim("vampire", "front/run")["frames"]
    g3 = fresh()
    cast(g3, TOOTH, LEG)
    step(g3, 20)  # perna voando: ela pula num pé só
    idx, _ = g3.player.anim_state(g3, A)
    assert idx in A.anim("vampire", "front/hop")["frames"]
    g4 = fresh()
    cast(g4, LEG)
    step(g4, 2)
    idx, _ = g4.player.anim_state(g4, A)
    assert idx in A.anim("vampire", "front/dash")["frames"]
    assert g4.player.ghosts, "dash deixa rastro"


def test_hud_portrait_states_and_spit_particles():
    import main
    g = fresh()
    g.enemies.append(Enemy("sword", g.player.pos + V2(900, 900)))
    g.time = 1.0
    assert g.portrait_state() == "normal"
    cast(g, TOOTH)
    assert g.portrait_state() == "normal_spit"
    assert g.hud_parts and g.hud_parts[0]["kind"] == "tooth"
    mouth = V2(main.PORTRAIT_POS) + V2(SP.get().meta["portraits"]["mouth"]["normal_spit"])
    assert (g.hud_parts[0]["pos"] - mouth).length() < 1, "o dente sai da boca do retrato"
    step(g, 5)
    assert g.hud_parts[0]["pos"].x > mouth.x, "e voa para fora"
    step(g, 60 * 2)
    assert not g.hud_parts
    g.spit_t = 0
    g.player.blood = 10
    assert g.portrait_state() in ("low", "low_blink")
    g.player.add_blood(100, g)
    assert g.portrait_state().startswith("frenzy")
    g.player.frenzy = False
    g.player.blood = 50
    g.player.invuln = 0
    g.hurt_player(5, g.player.pos + V2(10, 0))
    assert g.portrait_state() == "hurt"
    g.become_bat()
    assert g.portrait_state() == "bat"
    g.game_over()
    assert g.portrait_state() == "dead"


def test_leg_and_bullet_fly_out_of_portrait():
    g = fresh()
    cast(g, TOOTH, LEG)
    assert any(h["kind"] == "leg" for h in g.hud_parts)
    g2 = fresh()
    g2.player.mouth = [1]
    g2.space_action()
    assert any(h["kind"] == "bullet" for h in g2.hud_parts)


def test_corpse_left_on_death_then_fades():
    g = fresh()
    e = Enemy("dog", g.player.pos + V2(100, 0))
    e.hp = 1
    g.enemies.append(e)
    g.damage_enemy(e, 5, g.player.pos)
    assert g.corpses and g.corpses[0]["name"] == "dog"
    step(g, 60 * 2)
    assert not g.corpses


def test_boss_fist_reaches_toward_target():
    A = SP.get()
    g, b, hits = boss_fresh(150)
    b.start("jab", (g.player.pos - b.pos).normalize(), 1.0)
    b.phase, b.pt = "strike", 0.0
    sp = b.pos - g.camera
    arms = b.arms_2d(A, sp)
    punch = [a for a in arms if a["side"] == b.punch_side][0]
    assert punch["fist"].x < sp.x - 100, "o punho vai na direção da vampira"
    b.phase, b.attack = "walk", None
    b.start("slam", (g.player.pos - b.pos).normalize(), 1.0)
    b.pt = 0.0  # fim do aviso: punhos lá no alto
    for a in b.arms_2d(A, sp):
        assert a["fist"].y < sp.y - 150 and a["scale"] > 1.2


# ------------------------------------------------------------------ efeitos de golpe
def _vfx(g, name):
    return [v for v in g.vfx if v["name"] == name]


def test_attacks_spawn_drawn_effects():
    g = fresh()
    e = Enemy("sword", g.player.pos + V2(60, 0))
    e.hp = 999
    e.cd = 99
    g.enemies.append(e)
    cast(g, ARM)
    claw = _vfx(g, "fx_claw")
    assert claw and claw[0]["follow"] is g.player, "garras acompanham a vampira"
    assert abs(claw[0]["ang"]) < 0.2, "na direção da mira"
    assert _vfx(g, "fx_spark"), "acerto solta faísca"
    flip0 = claw[0]["flip"]
    cast(g, ARM)
    assert _vfx(g, "fx_claw")[-1]["flip"] != flip0, "o sentido das garras alterna"
    cast(g, ARM, LEG)
    assert _vfx(g, "fx_kick")
    cast(g, ARM, TOOTH)
    punch = _vfx(g, "fx_punch")
    assert punch and (punch[0]["pos"] - (g.player.pos + V2(62, 0))).length() < 2
    cast(g, LEG, ARM)
    assert len(_vfx(g, "fx_kick")) == 2, "voadora também tem o arco"
    step(g, 60)
    assert not g.vfx, "efeitos somem sozinhos"


def test_frenzy_hits_spark_gold():
    g = fresh()
    e = Enemy("sword", g.player.pos + V2(60, 0))
    e.hp = 999
    g.enemies.append(e)
    g.player.add_blood(100, g)
    cast(g, ARM)
    assert _vfx(g, "fx_spark_w") and not _vfx(g, "fx_spark")


def test_enemy_and_boss_effects():
    g = fresh()
    h = Enemy("sword", g.player.pos + V2(50, 0))
    h.cd = 0
    h.role = "engage"
    g.enemies.append(h)
    for _ in range(40):
        g.player.blood = 60
        g.update(DT, V2())
        if _vfx(g, "fx_sword"):
            break
    sw = _vfx(g, "fx_sword")
    assert sw and sw[0]["follow"] is h
    g2, b, hits = boss_fresh(150)
    b.start("slam", (g2.player.pos - b.pos).normalize(), 1.0)
    for _ in range(80):
        g2.player.blood = 80
        g2.update(DT, V2())
    crack = _vfx(g2, "fx_crack")
    assert crack and crack[0]["ground"] and crack[0]["frame"] in (0, 1)


def test_parry_and_bat_bite_effects():
    g = fresh()
    g.enemies.append(Enemy("sword", g.player.pos + V2(900, 900)))
    g.ebullets.append(vamp.Proj("ebullet", g.player.pos + V2(140, 0), V2(-360, 0), 8, 6, 3, friendly=False))
    cast(g, TOOTH, TOOTH, TOOTH)
    assert _vfx(g, "fx_bite"), "parry abre a bocona"
    g2 = fresh()
    g2.enemies.append(Enemy("sword", g2.player.pos + V2(900, 900)))
    g2.become_bat()
    g2.player.cast_cd = 0
    g2.right_click()
    assert _vfx(g2, "fx_bite")


def test_effects_render_rotated_and_cached():
    A = SP.get()
    g = fresh()
    g.enemies.append(Enemy("sword", g.player.pos + V2(900, 900)))
    for ang in (0.0, 1.0, 2.5, -2.0):
        g.mouse = g.player.pos + V2(math.cos(ang), math.sin(ang)) * 200
        cast(g, ARM)
        cast(g, ARM, LEG)
        cast(g, TOOTH)
        for _ in range(3):
            g.update(DT, V2())
            g.draw(screen, (640, 360))
    assert A._fx, "quadros girados ficam em cache"
    a = A.fx_image("fx_claw", 1, 0.0)
    b = A.fx_image("fx_claw", 1, math.pi / 4)
    assert b.get_width() > a.get_width(), "girar 45 graus alarga a imagem"
    A.shock_ring(screen, (300, 300), 120, (255, 60, 60), 200)
    assert A.disc((10, 20, 30), 12).get_at((20, 20))[:3] == (10, 20, 30)


# ------------------------------------------------------------------ sons
def test_sounds_load_and_play_on_events():
    import sounds
    assert len({f.split(".")[0] for f in os.listdir(sounds.SFX_DIR) if f.endswith(".ogg")}) >= 25
    sounds.init()  # com SDL_AUDIODRIVER=dummy o mixer abre; sem áudio, tudo vira silêncio
    heard = []
    orig = sounds.play
    sounds.play = lambda name, volume=1.0: heard.append(name)
    try:
        g = fresh()
        e = Enemy("sword", g.player.pos + V2(60, 0))
        e.hp = 1
        g.enemies.append(e)
        g.enemies.append(Enemy("sword", g.player.pos + V2(900, 900)))
        cast(g, ARM)
        cast(g, TOOTH)
        cast(g, ARM, LEG)
        cast(g, ARM, TOOTH)
        cast(g, LEG)
        g.player.dash = None  # no dash ela não toma dano
        g.player.invuln = 0
        g.hurt_player(5, g.player.pos + V2(10, 0))
        for name in ("claw", "hit", "kill", "spit", "kick", "punch", "dash", "hurt"):
            assert name in heard, name
        g.start_wave(5)
        assert "wave" in heard
    finally:
        sounds.play = orig
    sounds.play("claw")
    assert sounds.toggle_mute() is True and sounds.play("claw") is None
    sounds.toggle_mute()


def test_render_all_states():
    g = Game()
    for st in ("menu", "play", "pause", "over"):
        g.state = st
        if st == "play":
            g.start()
            step(g, 120)
            cast(g, ARM, TOOTH)
            cast(g, LEG, TOOTH)
            g.become_bat()
            g.draw(screen, (600, 300))
        g.state = st
        g.draw(screen, (600, 300))
    pygame.image.save(screen, os.path.join(os.path.dirname(__file__), "_last_frame.png"))


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print("ok  ", t.__name__)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            import traceback
            print("FAIL", t.__name__, "->", repr(exc))
            traceback.print_exc()
    print("\n%d/%d testes passaram" % (len(tests) - failed, len(tests)))
    sys.exit(1 if failed else 0)
