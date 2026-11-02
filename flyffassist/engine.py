"""Boucle principale : soin prioritaire, puis buffs, puis suivi.

La logique ne connaît Windows qu'à travers un « backend » (press, read_hp,
toggle_pressed), ce qui permet de la tester sans le jeu.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Protocol

from .config import Config
from .keys import Key, parse_key


class Backend(Protocol):
    def press(self, key: Key) -> None: ...
    def read_hp(self) -> float | None: ...
    def toggle_pressed(self) -> bool: ...
    def click_target(self) -> None: ...


class Brain:
    """Décide quoi faire à un instant donné. Aucune attente ici."""

    def __init__(self, cfg: Config, backend: Backend, log: Callable[[str], None] = print):
        self.cfg = cfg
        self.backend = backend
        self.log = log
        self.heal_key = parse_key(cfg.heal_key) if cfg.heal_enabled and cfg.heal_key else None
        self.follow_key = parse_key(cfg.follow_key) if cfg.follow_enabled and cfg.follow_key else None
        self.buffs = [(parse_key(b.key), b.interval_s, b.key) for b in cfg.buffs if b.enabled and b.key]
        self.last_buff = [float("-inf")] * len(self.buffs)  # tout est lancé au démarrage
        self.queue: list[int] = []
        self.busy_until = 0.0  # on attend la fin d'une incantation
        self.last_heal = float("-inf")
        self.last_follow = float("-inf")
        self.last_target = float("-inf")
        self.paused = False
        self.hp: float | None = None

    def step(self, now: float) -> None:
        if self.backend.toggle_pressed():
            self.paused = not self.paused
            self.log("⏸ Pause" if self.paused else "▶ Reprise")
        if self.paused:
            return

        # 0. Re-cibler le perso principal (clic dans la fenêtre de groupe)
        if self.cfg.retarget_enabled and now - self.last_target >= self.cfg.follow_interval_s:
            self.backend.click_target()
            self.last_target = now

        self.hp = self.backend.read_hp()

        # 1. Soin, toujours prioritaire
        low = self.heal_key is not None and self.hp is not None and self.hp < self.cfg.heal_threshold
        if low and now - self.last_heal >= self.cfg.heal_cooldown_s:
            self.backend.press(self.heal_key)
            self.last_heal = now
            self.busy_until = now + self.cfg.cast_delay_s
            self.log(f"Soin (PV {self.hp:.0f} %)")
            return
        if low:
            return  # on garde le mana et le temps pour le prochain soin

        # 2. Buffs arrivés à échéance
        for i, (_, interval, _name) in enumerate(self.buffs):
            if i not in self.queue and now - self.last_buff[i] >= interval:
                self.queue.append(i)
        if self.queue and now >= self.busy_until:
            i = self.queue.pop(0)
            key, _, name = self.buffs[i]
            self.backend.press(key)
            self.last_buff[i] = now
            self.busy_until = now + self.cfg.cast_delay_s
            self.log(f"Buff {name}")
            return

        # 3. Suivi, seulement hors incantation (bouger annule un sort)
        if (
            self.follow_key
            and not self.queue
            and now >= self.busy_until
            and now - self.last_follow >= self.cfg.follow_interval_s
        ):
            self.backend.press(self.follow_key)
            self.last_follow = now


class Engine(threading.Thread):
    def __init__(self, brain: Brain, tick_s: float = 0.1):
        super().__init__(daemon=True)
        self.brain = brain
        self.tick_s = tick_s
        self._stop_evt = threading.Event()

    def stop(self) -> None:
        self._stop_evt.set()

    def run(self) -> None:
        self.brain.log("Assistant démarré")
        while not self._stop_evt.is_set():
            try:
                self.brain.step(time.monotonic())
            except Exception as exc:  # on log et on continue
                self.brain.log(f"Erreur : {exc}")
                time.sleep(1)
            self._stop_evt.wait(self.tick_s)
        self.brain.log("Assistant arrêté")
