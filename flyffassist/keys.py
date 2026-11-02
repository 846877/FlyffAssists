"""Parsing des touches ("1", "alt+3", "f5", "z") en codes virtuels Windows.

Ce module ne dépend pas de pywin32 pour pouvoir être testé partout.
"""
from __future__ import annotations

from dataclasses import dataclass

VK_MENU = 0x12  # Alt
VK_F1 = 0x70

_NAMED = {
    "space": 0x20,
    "enter": 0x0D,
    "esc": 0x1B,
    "tab": 0x09,
    "pause": 0x13,
}


@dataclass(frozen=True)
class Key:
    vk: int
    alt: bool = False

    def __str__(self) -> str:
        return ("alt+" if self.alt else "") + hex(self.vk)


def parse_key(text: str) -> Key:
    """Transforme "alt+3", "F1", "z", "0" en Key. Lève ValueError si invalide."""
    raw = text.strip().lower().replace(" ", "")
    if not raw:
        raise ValueError("touche vide")
    parts = raw.split("+")
    *mods, name = parts
    alt = False
    for m in mods:
        if m == "alt":
            alt = True
        else:
            # Ctrl/Shift ne peuvent pas être simulés de façon fiable sur une
            # fenêtre en arrière-plan (le navigateur lit l'état réel du clavier).
            raise ValueError(f"modificateur non supporté : {m!r} (seul alt l'est)")

    if len(name) == 1 and (name.isdigit() or "a" <= name <= "z"):
        vk = ord(name.upper())
    elif name.startswith("f") and name[1:].isdigit() and 1 <= int(name[1:]) <= 12:
        vk = VK_F1 + int(name[1:]) - 1
    elif name in _NAMED:
        vk = _NAMED[name]
    else:
        raise ValueError(f"touche inconnue : {name!r}")
    return Key(vk=vk, alt=alt)


def make_lparam(scan: int, *, up: bool, alt: bool) -> int:
    """Construit le lParam d'un WM_(SYS)KEYDOWN/UP.

    bits 0-15 : répétition (1), 16-23 : scan code, 29 : Alt enfoncé,
    30 : état précédent, 31 : transition (1 = relâchement).
    """
    lp = 1 | ((scan & 0xFF) << 16)
    if alt:
        lp |= 1 << 29
    if up:
        lp |= (1 << 30) | (1 << 31)
    return lp
