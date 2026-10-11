"""Teste de fumaça sem janela: simula entradas e confere as mecânicas principais.

Uso: python tests/test_smoke.py
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame  # noqa: E402
from pygame.math import Vector2 as V2  # noqa: E402

import main as vamp  # noqa: E402
from main import ARM, LEG, TOOTH, Enemy, Game  # noqa: E402

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
    g.mouse = g.player.pos + V2(300, 0)
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
    g.player.pos = V2(WORLD_CENTER := vamp.WORLD_W / 2, vamp.WORLD_H / 2)
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
