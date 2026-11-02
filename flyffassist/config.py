"""Configuration persistée dans config.json à côté du programme."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


@dataclass
class Buff:
    key: str = ""
    interval_s: float = 300.0
    enabled: bool = False


@dataclass
class Config:
    # Soin
    heal_key: str = "1"
    heal_threshold: float = 70.0  # % de PV sous lequel on soigne
    heal_cooldown_s: float = 1.5  # délai mini entre deux soins

    # Barre de PV du perso principal (dans la fenêtre de groupe du prêtre),
    # en coordonnées relatives à la zone client de la fenêtre du prêtre.
    bar_x1: int = 0
    bar_x2: int = 0
    bar_y: int = 0
    bar_color: tuple[int, int, int] = (0, 0, 0)
    bar_tolerance: int = 60

    # Buffs : enchaînés avec cast_delay_s entre chaque.
    buffs: list[Buff] = field(default_factory=lambda: [Buff() for _ in range(8)])
    cast_delay_s: float = 1.8

    # Suivi
    follow_key: str = ""
    follow_interval_s: float = 5.0

    # Raccourci global pour mettre en pause / reprendre
    toggle_key: str = "f8"

    tick_s: float = 0.1

    @property
    def calibrated(self) -> bool:
        return self.bar_x2 > self.bar_x1

    def save(self, path: Path = CONFIG_PATH) -> None:
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "Config":
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        buffs = [Buff(**b) for b in data.pop("buffs", [])]
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        if "bar_color" in known:
            known["bar_color"] = tuple(known["bar_color"])
        cfg = cls(**known)
        if buffs:
            cfg.buffs = (buffs + [Buff() for _ in range(8)])[:8]
        return cfg
