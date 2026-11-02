"""Tout ce qui touche à Windows : fenêtres, capture d'écran, envoi de touches.

Les touches sont envoyées avec PostMessage directement à la fenêtre du
navigateur du prêtre : pas besoin qu'elle ait le focus, tu gardes la main
sur ton perso principal.
"""
from __future__ import annotations

import ctypes
import time

import mss
import win32api
import win32con
import win32gui

from .keys import VK_MENU, Key, make_lparam

GA_ROOT = 2
RENDER_CLASS = "Chrome_RenderWidgetHostHWND"  # Chrome, Opera, Edge...


def enable_dpi_awareness() -> None:
    """Sans ça, avec un zoom Windows à 125 %/150 %, les coordonnées de la
    souris et celles de la capture ne correspondent pas."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def cursor_pos() -> tuple[int, int]:
    return win32api.GetCursorPos()


def window_under_cursor() -> int:
    hwnd = win32gui.WindowFromPoint(win32api.GetCursorPos())
    return win32gui.GetAncestor(hwnd, GA_ROOT)


def is_key_down(vk: int) -> bool:
    """État physique d'une touche, quelle que soit la fenêtre active."""
    return bool(win32api.GetAsyncKeyState(vk) & 0x8000)


def _find_child(hwnd: int, cls: str) -> int | None:
    found: list[int] = []

    def cb(child, _):
        if win32gui.GetClassName(child) == cls:
            found.append(child)
            return False
        return True

    try:
        win32gui.EnumChildWindows(hwnd, cb, None)
    except Exception:
        pass  # EnumChildWindows lève une erreur quand le callback renvoie False
    return found[0] if found else None


class GameWindow:
    def __init__(self, hwnd: int, input_mode: str = "top"):
        self.hwnd = hwnd
        self.input_mode = input_mode  # "top" ou "render"

    @property
    def title(self) -> str:
        return win32gui.GetWindowText(self.hwnd)

    def alive(self) -> bool:
        return bool(win32gui.IsWindow(self.hwnd))

    def screen_to_client(self, x: int, y: int) -> tuple[int, int]:
        return win32gui.ScreenToClient(self.hwnd, (x, y))

    def client_to_screen(self, x: int, y: int) -> tuple[int, int]:
        return win32gui.ClientToScreen(self.hwnd, (x, y))

    def _input_hwnd(self) -> int:
        if self.input_mode == "render":
            child = _find_child(self.hwnd, RENDER_CLASS)
            if child:
                return child
        return self.hwnd

    def press(self, key: Key, hold_s: float = 0.04) -> None:
        h = self._input_hwnd()
        scan = win32api.MapVirtualKey(key.vk, 0)
        if key.alt:
            alt_scan = win32api.MapVirtualKey(VK_MENU, 0)
            win32api.PostMessage(h, win32con.WM_SYSKEYDOWN, VK_MENU, make_lparam(alt_scan, up=False, alt=True))
            win32api.PostMessage(h, win32con.WM_SYSKEYDOWN, key.vk, make_lparam(scan, up=False, alt=True))
            time.sleep(hold_s)
            win32api.PostMessage(h, win32con.WM_SYSKEYUP, key.vk, make_lparam(scan, up=True, alt=True))
            win32api.PostMessage(h, win32con.WM_KEYUP, VK_MENU, make_lparam(alt_scan, up=True, alt=False))
        else:
            win32api.PostMessage(h, win32con.WM_KEYDOWN, key.vk, make_lparam(scan, up=False, alt=False))
            time.sleep(hold_s)
            win32api.PostMessage(h, win32con.WM_KEYUP, key.vk, make_lparam(scan, up=True, alt=False))


class ScreenReader:
    """Lit des pixels à l'écran. La fenêtre du prêtre doit être visible
    (pas réduite, pas cachée derrière une autre) : mets les deux fenêtres
    côte à côte. Un ScreenReader par thread (mss n'est pas thread-safe)."""

    def __init__(self):
        self._sct = mss.mss()

    def pixel(self, x: int, y: int) -> tuple[int, int, int]:
        img = self._sct.grab({"left": x, "top": y, "width": 1, "height": 1})
        r, g, b = img.rgb[0:3]
        return (r, g, b)

    def row(self, x1: int, x2: int, y: int) -> list[tuple[int, int, int]]:
        width = x2 - x1 + 1
        img = self._sct.grab({"left": x1, "top": y, "width": width, "height": 1})
        data = img.rgb
        return [(data[i], data[i + 1], data[i + 2]) for i in range(0, len(data), 3)]
