"""Calcul du % de PV à partir d'une ligne de pixels de la barre de vie.

Pure Python : pas de dépendance Windows, testable partout.
"""
from __future__ import annotations

from typing import Sequence

RGB = tuple[int, int, int]


def color_distance(a: RGB, b: RGB) -> int:
    """Distance simple (somme des écarts absolus) entre deux couleurs."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def hp_percent(row: Sequence[RGB], ref: RGB, tolerance: int) -> float | None:
    """Renvoie le % de PV (0-100) d'après une ligne de pixels.

    La barre se remplit de gauche à droite : on prend le pixel « plein » le
    plus à droite. Les pixels isolés (texte « 1234/5678 » posé sur la barre)
    sont gérés car on regarde la position, pas le nombre.

    Renvoie None si aucun pixel ne correspond : fenêtre masquée, groupe
    absent, mauvais calibrage... Dans ce cas on ne soigne pas à l'aveugle.
    """
    if not row:
        return None
    last = -1
    for i, px in enumerate(row):
        if color_distance(px, ref) <= tolerance:
            last = i
    if last < 0:
        return None
    return round(100.0 * (last + 1) / len(row), 1)
