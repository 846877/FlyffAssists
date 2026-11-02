"""Interface graphique (tkinter) de FlyffAssist."""
from __future__ import annotations

import queue
import tkinter as tk
from tkinter import messagebox, ttk

from . import winapi
from .config import Config
from .engine import Brain, Engine
from .hp import hp_percent
from .keys import Key, parse_key

COUNTDOWN_S = 3


class WindowsBackend:
    """Relie la logique (Brain) à la vraie fenêtre du prêtre."""

    def __init__(self, cfg: Config, window: winapi.GameWindow):
        self.cfg = cfg
        self.window = window
        self.toggle_vk = parse_key(cfg.toggle_key).vk if cfg.toggle_key else None
        self._was_down = False
        self._reader: winapi.ScreenReader | None = None  # créé dans le thread qui lit

    def press(self, key: Key) -> None:
        self.window.press(key)

    def read_hp(self) -> float | None:
        if not self.cfg.calibrated or not self.window.alive():
            return None
        if self._reader is None:
            self._reader = winapi.ScreenReader()
        return read_hp(self._reader, self.cfg, self.window)

    def toggle_pressed(self) -> bool:
        if self.toggle_vk is None:
            return False
        down = winapi.is_key_down(self.toggle_vk)
        pressed = down and not self._was_down
        self._was_down = down
        return pressed


def read_hp(reader: winapi.ScreenReader, cfg: Config, window: winapi.GameWindow) -> float | None:
    x1, y = window.client_to_screen(cfg.bar_x1, cfg.bar_y)
    x2, _ = window.client_to_screen(cfg.bar_x2, cfg.bar_y)
    return hp_percent(reader.row(x1, x2, y), cfg.bar_color, cfg.bar_tolerance)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FlyffAssist")
        self.resizable(False, False)
        self.cfg = Config.load()
        self.window: winapi.GameWindow | None = None
        self.engine: Engine | None = None
        self.brain: Brain | None = None
        self.logs: queue.Queue[str] = queue.Queue()
        self.reader = winapi.ScreenReader()  # pour l'aperçu, dans le thread de l'UI
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(300, self._tick)

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        pad = {"padx": 6, "pady": 3}
        root = ttk.Frame(self, padding=8)
        root.grid()

        # Fenêtre du prêtre
        f = ttk.LabelFrame(root, text="1. Fenêtre du prêtre", padding=6)
        f.grid(row=0, column=0, sticky="ew", **pad)
        ttk.Button(f, text=f"Choisir (survole-la pendant {COUNTDOWN_S} s)", command=self._pick_window).grid(row=0, column=0, **pad)
        self.win_label = ttk.Label(f, text="Aucune fenêtre", width=42)
        self.win_label.grid(row=0, column=1, **pad)
        ttk.Label(f, text="Envoi des touches :").grid(row=1, column=0, sticky="e", **pad)
        self.input_mode = tk.StringVar(value="top")
        ttk.Combobox(f, textvariable=self.input_mode, values=["top", "render"], width=8, state="readonly").grid(row=1, column=1, sticky="w", **pad)
        self.test_key = tk.StringVar(value=self.cfg.heal_key)
        ttk.Entry(f, textvariable=self.test_key, width=8).grid(row=2, column=0, sticky="e", **pad)
        ttk.Button(f, text="Tester cette touche", command=self._test_key).grid(row=2, column=1, sticky="w", **pad)

        # Barre de PV
        f = ttk.LabelFrame(root, text="2. Barre de PV du perso principal (fenêtre de groupe du prêtre)", padding=6)
        f.grid(row=1, column=0, sticky="ew", **pad)
        ttk.Button(f, text="Bord gauche", command=lambda: self._calibrate("left")).grid(row=0, column=0, **pad)
        ttk.Button(f, text="Bord droit", command=lambda: self._calibrate("right")).grid(row=0, column=1, **pad)
        ttk.Label(f, text="Tolérance couleur").grid(row=0, column=2, **pad)
        self.tolerance = tk.IntVar(value=self.cfg.bar_tolerance)
        ttk.Spinbox(f, from_=5, to=300, textvariable=self.tolerance, width=5).grid(row=0, column=3, **pad)
        self.hp_label = ttk.Label(f, text="PV lus : -", font=("Segoe UI", 11, "bold"))
        self.hp_label.grid(row=1, column=0, columnspan=4, **pad)
        ttk.Label(f, text="Le perso principal doit être à 100 % PV pendant le calibrage.").grid(row=2, column=0, columnspan=4, **pad)

        # Soin
        f = ttk.LabelFrame(root, text="3. Soin", padding=6)
        f.grid(row=2, column=0, sticky="ew", **pad)
        self.heal_key = tk.StringVar(value=self.cfg.heal_key)
        self.heal_threshold = tk.DoubleVar(value=self.cfg.heal_threshold)
        self.heal_cd = tk.DoubleVar(value=self.cfg.heal_cooldown_s)
        for col, (label, var, w) in enumerate([("Touche", self.heal_key, 8), ("Seuil PV %", self.heal_threshold, 6), ("Délai entre soins (s)", self.heal_cd, 6)]):
            ttk.Label(f, text=label).grid(row=0, column=col * 2, **pad)
            ttk.Entry(f, textvariable=var, width=w).grid(row=0, column=col * 2 + 1, **pad)

        # Buffs
        f = ttk.LabelFrame(root, text="4. Buffs (relancés automatiquement)", padding=6)
        f.grid(row=3, column=0, sticky="ew", **pad)
        ttk.Label(f, text="Actif").grid(row=0, column=0)
        ttk.Label(f, text="Touche").grid(row=0, column=1)
        ttk.Label(f, text="Toutes les (s)").grid(row=0, column=2)
        ttk.Label(f, text="Actif").grid(row=0, column=3)
        ttk.Label(f, text="Touche").grid(row=0, column=4)
        ttk.Label(f, text="Toutes les (s)").grid(row=0, column=5)
        self.buff_vars = []
        for i, b in enumerate(self.cfg.buffs):
            r, c = 1 + i % 4, (i // 4) * 3
            en, key, itv = tk.BooleanVar(value=b.enabled), tk.StringVar(value=b.key), tk.DoubleVar(value=b.interval_s)
            ttk.Checkbutton(f, variable=en).grid(row=r, column=c, **pad)
            ttk.Entry(f, textvariable=key, width=8).grid(row=r, column=c + 1, **pad)
            ttk.Entry(f, textvariable=itv, width=6).grid(row=r, column=c + 2, **pad)
            self.buff_vars.append((en, key, itv))
        ttk.Label(f, text="Durée d'un sort (s)").grid(row=5, column=0, columnspan=2, **pad)
        self.cast_delay = tk.DoubleVar(value=self.cfg.cast_delay_s)
        ttk.Entry(f, textvariable=self.cast_delay, width=6).grid(row=5, column=2, **pad)

        # Suivi
        f = ttk.LabelFrame(root, text="5. Suivi", padding=6)
        f.grid(row=4, column=0, sticky="ew", **pad)
        self.follow_key = tk.StringVar(value=self.cfg.follow_key)
        self.follow_itv = tk.DoubleVar(value=self.cfg.follow_interval_s)
        self.toggle_key = tk.StringVar(value=self.cfg.toggle_key)
        for col, (label, var) in enumerate([("Touche suivre", self.follow_key), ("Toutes les (s)", self.follow_itv), ("Pause/reprise", self.toggle_key)]):
            ttk.Label(f, text=label).grid(row=0, column=col * 2, **pad)
            ttk.Entry(f, textvariable=var, width=7).grid(row=0, column=col * 2 + 1, **pad)

        # Démarrage + journal
        f = ttk.Frame(root)
        f.grid(row=5, column=0, sticky="ew", **pad)
        self.start_btn = ttk.Button(f, text="▶ Démarrer", command=self._toggle_engine)
        self.start_btn.grid(row=0, column=0, **pad)
        ttk.Button(f, text="Enregistrer", command=self._save).grid(row=0, column=1, **pad)
        self.status = ttk.Label(f, text="Arrêté")
        self.status.grid(row=0, column=2, **pad)
        self.log_box = tk.Text(root, height=8, width=70, state="disabled")
        self.log_box.grid(row=6, column=0, **pad)

    # ------------------------------------------------------------ actions
    def log(self, msg: str) -> None:
        self.logs.put(msg)  # appelable depuis n'importe quel thread

    def _countdown(self, label: str, then) -> None:
        def step(n: int):
            if n == 0:
                then()
            else:
                self.status.config(text=f"{label} dans {n}…")
                self.after(1000, step, n - 1)
        step(COUNTDOWN_S)

    def _pick_window(self) -> None:
        def done():
            hwnd = winapi.window_under_cursor()
            if hwnd == self.winfo_id() or winapi.win32gui.GetAncestor(self.winfo_id(), winapi.GA_ROOT) == hwnd:
                self.log("C'est la fenêtre de FlyffAssist, recommence sur celle du prêtre.")
                return
            self.window = winapi.GameWindow(hwnd, self.input_mode.get())
            self.win_label.config(text=f"{self.window.title[:40]}  (#{hwnd})")
            self.log(f"Fenêtre choisie : {self.window.title}")
            self.status.config(text="Arrêté")
        self._countdown("Capture de la fenêtre", done)

    def _need_window(self) -> bool:
        if self.window is None or not self.window.alive():
            messagebox.showwarning("FlyffAssist", "Choisis d'abord la fenêtre du prêtre.")
            return False
        self.window.input_mode = self.input_mode.get()
        return True

    def _test_key(self) -> None:
        if not self._need_window():
            return
        try:
            key = parse_key(self.test_key.get())
        except ValueError as exc:
            messagebox.showerror("FlyffAssist", str(exc))
            return
        self.window.press(key)
        self.log(f"Touche {self.test_key.get()} envoyée (mode {self.input_mode.get()})")

    def _calibrate(self, side: str) -> None:
        if not self._need_window():
            return
        if side == "right" and self.cfg.bar_y == 0:
            messagebox.showinfo("FlyffAssist", "Commence par le bord gauche.")
            return

        def done():
            sx, sy = winapi.cursor_pos()
            cx, cy = self.window.screen_to_client(sx, sy)
            if side == "left":
                self.cfg.bar_x1, self.cfg.bar_y = cx, cy
                # on échantillonne un peu à droite du bord pour éviter le contour
                self.cfg.bar_color = self.reader.pixel(sx + 2, sy)
                self.log(f"Bord gauche ({cx},{cy}), couleur {self.cfg.bar_color}")
            else:
                self.cfg.bar_x2 = cx
                self.log(f"Bord droit ({cx},{self.cfg.bar_y})")
            self.status.config(text="Arrêté")
        self._countdown(f"Pointe le bord {'gauche' if side == 'left' else 'droit'} de la barre", done)

    def _read_form(self) -> Config:
        c = self.cfg
        c.bar_tolerance = int(self.tolerance.get())
        c.heal_key = self.heal_key.get().strip()
        c.heal_threshold = float(self.heal_threshold.get())
        c.heal_cooldown_s = float(self.heal_cd.get())
        for b, (en, key, itv) in zip(c.buffs, self.buff_vars):
            b.enabled, b.key, b.interval_s = en.get(), key.get().strip(), float(itv.get())
        c.cast_delay_s = float(self.cast_delay.get())
        c.follow_key = self.follow_key.get().strip()
        c.follow_interval_s = float(self.follow_itv.get())
        c.toggle_key = self.toggle_key.get().strip()
        return c

    def _save(self) -> None:
        try:
            self._read_form().save()
            self.log("Configuration enregistrée")
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("FlyffAssist", f"Valeur invalide : {exc}")

    def _toggle_engine(self) -> None:
        if self.engine:
            self.engine.stop()
            self.engine = self.brain = None
            self.start_btn.config(text="▶ Démarrer")
            return
        if not self._need_window():
            return
        try:
            cfg = self._read_form()
            self.brain = Brain(cfg, WindowsBackend(cfg, self.window), self.log)
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("FlyffAssist", f"Réglage invalide : {exc}")
            return
        if not cfg.calibrated:
            self.log("⚠ Barre de PV non calibrée : pas de soin, seulement buffs et suivi.")
        cfg.save()
        self.engine = Engine(self.brain, cfg.tick_s)
        self.engine.start()
        self.start_btn.config(text="■ Arrêter")

    # --------------------------------------------------------------- boucle UI
    def _tick(self) -> None:
        while not self.logs.empty():
            self.log_box.config(state="normal")
            self.log_box.insert("end", self.logs.get() + "\n")
            self.log_box.see("end")
            self.log_box.config(state="disabled")

        hp = None
        if self.brain:
            hp = self.brain.hp
            self.status.config(text="En pause" if self.brain.paused else "En marche")
        elif self.window and self.window.alive() and self.cfg.calibrated:
            try:
                self.cfg.bar_tolerance = int(self.tolerance.get())
                hp = read_hp(self.reader, self.cfg, self.window)
            except Exception:
                hp = None
        self.hp_label.config(text=f"PV lus : {hp:.0f} %" if hp is not None else "PV lus : -")
        self.after(300, self._tick)

    def _on_close(self) -> None:
        if self.engine:
            self.engine.stop()
        try:
            self._read_form().save()
        except Exception:
            pass
        self.destroy()


def main() -> None:
    winapi.enable_dpi_awareness()
    App().mainloop()
