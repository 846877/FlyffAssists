"""FlyffAssist.exe

Ouvre la fenêtre du perso soutien dans Chrome (ou Edge) avec un profil dédié,
et la pilote via le protocole DevTools de Chrome :
  - injecte l'assistant (flyffassist.js) dans la page du jeu : panneau
    d'options, lecture des PV, envoi des touches au jeu ;
  - surveille la touche pause (F8 par défaut) dans tout Windows.

Les touches partent depuis la page elle-même, donc la fenêtre du soutien
n'a pas besoin d'être au premier plan.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.request
from pathlib import Path

import websocket  # websocket-client

GAME_URL = os.environ.get("FLYFFASSIST_URL", "https://universe.flyff.com/play")
IS_WIN = sys.platform == "win32"


# ------------------------------------------------------------------ chemins
def resource(name: str) -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / name  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent / "extension" / name


def profile_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    d = Path(base) / "FlyffAssist" / "profile"
    d.mkdir(parents=True, exist_ok=True)
    return d


def find_browser() -> str | None:
    override = os.environ.get("FLYFFASSIST_BROWSER")
    if override:
        return override
    if not IS_WIN:
        return None
    candidates = []
    for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        root = os.environ.get(env)
        if root:
            candidates.append(Path(root) / "Google/Chrome/Application/chrome.exe")
    for env in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
        root = os.environ.get(env)
        if root:
            candidates.append(Path(root) / "Microsoft/Edge/Application/msedge.exe")
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ------------------------------------------------------------------ DevTools
class Cdp:
    """Client minimal du protocole DevTools (un seul onglet)."""

    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, suppress_origin=True, timeout=10)
        self.lock = threading.Lock()
        self.next_id = 0

    def call(self, method: str, **params):
        with self.lock:
            self.next_id += 1
            mid = self.next_id
            self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
            while True:
                msg = json.loads(self.ws.recv())
                if msg.get("id") == mid:
                    if "error" in msg:
                        raise RuntimeError(msg["error"].get("message", msg["error"]))
                    return msg.get("result", {})

    def evaluate(self, expr: str):
        r = self.call("Runtime.evaluate", expression=expr, returnByValue=True)
        return r.get("result", {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def wait_for_page(port: int, timeout: float = 30) -> str:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=2) as r:
                pages = [t for t in json.load(r) if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
                # On veut l'onglet du jeu, pas un onglet vide ouvert au démarrage
                game_host = GAME_URL.split("/")[2] if "://" in GAME_URL and GAME_URL.split("/")[2] else None
                for t in pages:
                    url = t.get("url", "")
                    if url.startswith(GAME_URL) or (game_host and game_host in url):
                        return t["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(0.5)
    raise TimeoutError("La fenêtre du jeu ne répond pas")


# ------------------------------------------------------------------ touche pause globale
def vk_from_name(name: str) -> int | None:
    n = (name or "").strip().upper()
    if len(n) == 1 and n.isalnum():
        return ord(n)
    if n.startswith("F") and n[1:].isdigit() and 1 <= int(n[1:]) <= 12:
        return 0x70 + int(n[1:]) - 1
    return None


def key_down(vk: int) -> bool:
    if not IS_WIN:
        return False
    import ctypes

    return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)


# ------------------------------------------------------------------ session
class Session:
    """Une fenêtre de soutien pilotée."""

    def __init__(self, on_status):
        self.on_status = on_status
        self.proc: subprocess.Popen | None = None
        self.cdp: Cdp | None = None
        self.alive = False

    def start(self, browser: str) -> None:
        port = free_port()
        args = [
            browser,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile_dir()}",
            f"--app={GAME_URL}",
            "--window-size=1280,800",
            "--no-first-run",
            "--no-default-browser-check",
            # Le jeu doit continuer à tourner même si sa fenêtre est derrière une autre
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
        ] + os.environ.get("FLYFFASSIST_EXTRA_ARGS", "").split()
        self.proc = subprocess.Popen(args)
        self.on_status("Ouverture de la fenêtre du jeu…")
        self.cdp = Cdp(wait_for_page(port))
        script = resource("flyffassist.js").read_text(encoding="utf-8")
        self.cdp.call("Page.enable")
        self.cdp.call("Page.addScriptToEvaluateOnNewDocument", source="window.__flyffAssistExe = true;\n" + script)
        self.cdp.call("Page.reload", ignoreCache=False)
        self.alive = True
        self.on_status("Fenêtre du soutien prête. Règle l'assistant dans le panneau du jeu.")
        threading.Thread(target=self._watch, daemon=True).start()

    def _watch(self) -> None:
        toggle_vk = 0x77  # F8
        was_down = False
        last_cfg = 0.0
        while self.alive:
            try:
                now = time.time()
                if now - last_cfg > 3:
                    last_cfg = now
                    name = self.cdp.evaluate(
                        "(() => { try { return JSON.parse(localStorage.getItem('flyffassist.config.v1') || '{}').toggleKey || 'F8' } catch (e) { return 'F8' } })()"
                    )
                    toggle_vk = vk_from_name(name) or 0x77
                down = key_down(toggle_vk)
                if down and not was_down:
                    self.cdp.evaluate("window.__flyffAssistToggle && window.__flyffAssistToggle()")
                was_down = down
            except Exception:
                if self.proc and self.proc.poll() is not None:
                    self.alive = False
                    self.on_status("La fenêtre du soutien a été fermée.")
                    return
                time.sleep(1)
            time.sleep(0.05)

    def stop(self) -> None:
        self.alive = False
        if self.cdp:
            self.cdp.close()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()


# ------------------------------------------------------------------ fenêtre
BG, FG, GOLD, MUTED, PANEL = "#1b150d", "#f3ead2", "#f0c766", "#a89c82", "#2a2117"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FlyffAssist")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.session: Session | None = None

        tk.Label(self, text="⚜ FlyffAssist", font=("Segoe UI", 16, "bold"), fg=GOLD, bg=BG).pack(padx=24, pady=(18, 2))
        tk.Label(self, text="Suivi, buffs et soin pour ton perso soutien", font=("Segoe UI", 10), fg=MUTED, bg=BG).pack()

        box = tk.Frame(self, bg=PANEL, highlightbackground="#5a4a30", highlightthickness=1)
        box.pack(padx=20, pady=14, fill="x")
        steps = (
            "1. Clique sur « Ouvrir la fenêtre du soutien ».",
            "2. Connecte-toi avec ton soutien (la connexion est mémorisée).",
            "3. Cible ton perso principal, calibre la barre de PV",
            "    et règle soin, buffs et suivi dans le panneau du jeu.",
            "4. Clique sur « Activer sur ce perso ».",
            "F8 met en pause ou relance, depuis n'importe quelle fenêtre.",
        )
        for s in steps:
            tk.Label(box, text=s, font=("Segoe UI", 10), fg=FG, bg=PANEL, anchor="w", justify="left").pack(fill="x", padx=12, pady=1)

        self.btn = tk.Button(
            self, text="▶  Ouvrir la fenêtre du soutien", font=("Segoe UI", 11, "bold"),
            fg="#1b150d", bg=GOLD, activebackground="#ffd97e", relief="flat", padx=16, pady=8,
            cursor="hand2", command=self.open_window,
        )
        self.btn.pack(pady=(0, 10))
        self.status = tk.Label(self, text="Prêt.", font=("Segoe UI", 9), fg=MUTED, bg=BG, wraplength=380)
        self.status.pack(padx=20, pady=(0, 16))
        self.protocol("WM_DELETE_WINDOW", self.quit_app)

    def set_status(self, text: str) -> None:
        self.after(0, lambda: self.status.config(text=text))
        if "fermée" in text:
            self.after(0, lambda: self.btn.config(state="normal"))

    def open_window(self) -> None:
        browser = find_browser()
        if not browser:
            self.set_status("Chrome ou Edge introuvable. Installe Google Chrome puis relance FlyffAssist.")
            return
        self.btn.config(state="disabled")
        self.session = Session(self.set_status)

        def run():
            try:
                self.session.start(browser)
            except Exception as exc:
                self.set_status(f"Erreur : {exc}")
                self.after(0, lambda: self.btn.config(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    def quit_app(self) -> None:
        if self.session:
            self.session.stop()
        self.destroy()


def main() -> None:
    if IS_WIN:
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    App().mainloop()


if __name__ == "__main__":
    main()
