from flyffassist.config import Buff, Config
from flyffassist.engine import Brain
from flyffassist.hp import hp_percent
from flyffassist.keys import Key, make_lparam, parse_key

RED, GREY = (200, 30, 30), (40, 40, 40)


def test_parse_key():
    assert parse_key("1") == Key(ord("1"))
    assert parse_key("Alt+0") == Key(ord("0"), alt=True)
    assert parse_key("f8") == Key(0x77)
    assert parse_key("z") == Key(ord("Z"))


def test_parse_key_rejects_ctrl():
    import pytest
    with pytest.raises(ValueError):
        parse_key("ctrl+1")


def test_lparam_bits():
    assert make_lparam(0x02, up=False, alt=False) == 0x00020001
    assert make_lparam(0x02, up=True, alt=True) == 0xE0020001


def test_hp_percent():
    row = [RED] * 30 + [GREY] * 70
    assert hp_percent(row, RED, 40) == 30.0
    assert hp_percent([GREY] * 100, RED, 40) is None
    # texte blanc par-dessus la barre : on garde le pixel rouge le plus à droite
    row = [RED] * 10 + [(255, 255, 255)] * 5 + [RED] * 35 + [GREY] * 50
    assert hp_percent(row, RED, 40) == 50.0


class FakeBackend:
    def __init__(self):
        self.hp = 100.0
        self.pressed = []
        self.toggle = False

    def press(self, key):
        self.pressed.append(key)

    def read_hp(self):
        return self.hp

    def toggle_pressed(self):
        t, self.toggle = self.toggle, False
        return t


def make(**kw):
    cfg = Config(heal_key="1", follow_key="z", cast_delay_s=2, follow_interval_s=5, **kw)
    cfg.buffs = [Buff("2", 60, True), Buff("3", 120, True), Buff("", 10, True)]
    be = FakeBackend()
    return Brain(cfg, be, log=lambda m: None), be


def test_buffs_cast_in_sequence_then_follow():
    brain, be = make()
    for t in [0, 1, 2, 3, 4]:
        brain.step(t)
    assert be.pressed == [parse_key("2"), parse_key("3"), parse_key("z")]


def test_heal_has_priority_and_cooldown():
    brain, be = make(heal_threshold=70, heal_cooldown_s=1.5)
    be.hp = 50
    for t in [0, 1, 2]:
        brain.step(t)
    assert be.pressed == [parse_key("1"), parse_key("1")]


def test_unknown_hp_does_not_heal():
    brain, be = make()
    be.hp = None
    brain.step(0)
    assert parse_key("1") not in be.pressed


def test_buff_recast_after_interval():
    brain, be = make()
    for t in range(0, 70):
        brain.step(t)
    assert be.pressed.count(parse_key("2")) == 2


def test_pause():
    brain, be = make()
    be.toggle = True
    brain.step(0)
    assert brain.paused and be.pressed == []


def test_config_roundtrip(tmp_path):
    p = tmp_path / "c.json"
    c = Config(bar_color=(1, 2, 3), heal_key="alt+1")
    c.buffs[0] = Buff("2", 90, True)
    c.save(p)
    d = Config.load(p)
    assert d == c and len(d.buffs) == 8


def test_disabled_heal_and_follow():
    brain, be = make(heal_enabled=False, follow_enabled=False)
    brain.cfg.buffs = []
    brain.buffs, brain.last_buff = [], []
    be.hp = 10
    for t in range(10):
        brain.step(t)
    assert be.pressed == []
