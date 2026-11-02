/*
 * FlyffAssist : extension Chrome pour Flyff Universe.
 *
 * Le script tourne dans la page du jeu (monde MAIN). Il envoie les touches
 * directement au canvas du jeu, comme le font les extensions Flyff existantes,
 * donc ça marche même quand la fenêtre du soutien n'a pas le focus.
 * Les PV sont lus sur la barre de la cible, en haut de l'écran.
 */
(() => {
  "use strict";
  if (window.__flyffAssistLoaded) return;
  window.__flyffAssistLoaded = true;

  // ---------------------------------------------------------------- canvas
  // Sans preserveDrawingBuffer, l'image WebGL est effacée après chaque rendu
  // et on ne peut pas relire les pixels de la barre de PV.
  const origGetContext = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (type, attrs) {
    if (/webgl/i.test(String(type))) {
      attrs = Object.assign({}, attrs || {}, { preserveDrawingBuffer: true });
    }
    return origGetContext.call(this, type, attrs);
  };

  const STORE_KEY = "flyffassist.config.v1";
  const ACTIVE_KEY = "flyffassist.active"; // par onglet (sessionStorage)
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  const DEFAULTS = {
    heal: { enabled: true, key: "1", threshold: 70, cooldown: 1.5 },
    buffs: Array.from({ length: 8 }, () => ({ enabled: false, key: "", interval: 300 })),
    castDelay: 1.8,
    follow: { enabled: true, key: "z", interval: 3 },
    bar: null, // { x1, x2, y, color: [r,g,b], cw, ch } en pixels du canvas
    tolerance: 60,
    toggleKey: "F8",
    panel: { x: 16, y: 140, collapsed: false },
  };

  function loadConfig() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORE_KEY) || "{}");
      const cfg = structuredClone(DEFAULTS);
      for (const k of Object.keys(saved)) {
        if (cfg[k] && typeof cfg[k] === "object" && !Array.isArray(cfg[k]) && saved[k]) Object.assign(cfg[k], saved[k]);
        else cfg[k] = saved[k];
      }
      while (cfg.buffs.length < 8) cfg.buffs.push({ enabled: false, key: "", interval: 300 });
      return cfg;
    } catch {
      return structuredClone(DEFAULTS);
    }
  }
  const cfg = loadConfig();
  const saveConfig = () => {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(cfg)); } catch {}
  };

  // ---------------------------------------------------------------- touches
  function parseKey(text) {
    let s = String(text || "").trim();
    if (!s) return null;
    let alt = false;
    const m = s.match(/^alt\s*\+\s*(.+)$/i);
    if (m) { alt = true; s = m[1].trim(); }
    let key, code;
    if (/^[0-9]$/.test(s)) { key = s; code = "Digit" + s; }
    else if (/^[a-z]$/i.test(s)) { key = s.toLowerCase(); code = "Key" + s.toUpperCase(); }
    else if (/^f([1-9]|1[0-2])$/i.test(s)) { key = s.toUpperCase(); code = key; }
    else if (/^tab$/i.test(s)) { key = "Tab"; code = "Tab"; }
    else if (/^(space|espace)$/i.test(s)) { key = " "; code = "Space"; }
    else return null;
    return { key, code, alt, label: (alt ? "Alt+" : "") + (key === " " ? "Espace" : key.toUpperCase()) };
  }

  let gameCanvas = null;

  async function press(k) {
    if (!gameCanvas || !k) return;
    const ev = { key: k.key, code: k.code, altKey: k.alt };
    if (k.alt) gameCanvas.dispatchEvent(new KeyboardEvent("keydown", { key: "Alt", code: "AltLeft", altKey: true }));
    gameCanvas.dispatchEvent(new KeyboardEvent("keydown", ev));
    await sleep(60);
    gameCanvas.dispatchEvent(new KeyboardEvent("keyup", ev));
    if (k.alt) gameCanvas.dispatchEvent(new KeyboardEvent("keyup", { key: "Alt", code: "AltLeft", altKey: false }));
  }

  // ---------------------------------------------------------------- PV
  const probe = document.createElement("canvas");
  const probeCtx = probe.getContext("2d", { willReadFrequently: true });

  function readPixels(x, y, w) {
    probe.width = w;
    probe.height = 1;
    probeCtx.clearRect(0, 0, w, 1);
    probeCtx.drawImage(gameCanvas, x, y, w, 1, 0, 0, w, 1);
    return probeCtx.getImageData(0, 0, w, 1).data;
  }

  const dist = (d, i, c) => Math.abs(d[i] - c[0]) + Math.abs(d[i + 1] - c[1]) + Math.abs(d[i + 2] - c[2]);

  function readHp() {
    const b = cfg.bar;
    if (!gameCanvas || !b || b.x2 <= b.x1) return null;
    if (b.cw !== gameCanvas.width || b.ch !== gameCanvas.height) return null; // fenêtre redimensionnée
    const d = readPixels(b.x1, b.y, b.x2 - b.x1 + 1);
    const n = d.length / 4;
    let last = -1;
    for (let i = 0; i < n; i++) if (dist(d, i * 4, b.color) <= cfg.tolerance) last = i;
    return last < 0 ? null : Math.round((100 * (last + 1)) / n);
  }

  // ---------------------------------------------------------------- logique
  const state = {
    active: sessionStorage.getItem(ACTIVE_KEY) === "1",
    paused: false,
    hp: null,
    busyUntil: 0,
    lastHeal: -Infinity,
    lastFollow: -Infinity,
    lastBuff: [],
    queue: [],
  };

  function resetTimers() {
    state.busyUntil = 0;
    state.lastHeal = state.lastFollow = -Infinity;
    state.lastBuff = cfg.buffs.map(() => -Infinity); // tous les buffs partent au démarrage
    state.queue = [];
  }
  resetTimers();

  function step() {
    state.hp = readHp();
    if (!state.active || state.paused) return;
    const now = performance.now() / 1000;

    // 1. Soin prioritaire
    const heal = cfg.heal.enabled ? parseKey(cfg.heal.key) : null;
    const low = heal && state.hp !== null && state.hp < cfg.heal.threshold;
    if (low) {
      if (now - state.lastHeal >= cfg.heal.cooldown) {
        press(heal);
        state.lastHeal = now;
        state.busyUntil = now + cfg.castDelay;
        log(`Soin (PV ${state.hp} %)`);
      }
      return;
    }

    // 2. Buffs
    cfg.buffs.forEach((b, i) => {
      if (b.enabled && parseKey(b.key) && !state.queue.includes(i) && now - state.lastBuff[i] >= b.interval) {
        state.queue.push(i);
      }
    });
    if (state.queue.length && now >= state.busyUntil) {
      const i = state.queue.shift();
      const k = parseKey(cfg.buffs[i].key);
      if (k && cfg.buffs[i].enabled) {
        press(k);
        state.lastBuff[i] = now;
        state.busyUntil = now + cfg.castDelay;
        log(`Buff ${k.label}`);
      }
      return;
    }

    // 3. Suivi, hors incantation
    const follow = cfg.follow.enabled ? parseKey(cfg.follow.key) : null;
    if (follow && !state.queue.length && now >= state.busyUntil && now - state.lastFollow >= cfg.follow.interval) {
      press(follow);
      state.lastFollow = now;
    }
  }

  // Pause/reprise depuis n'importe quel onglet du jeu (même celui du perso principal)
  const channel = "BroadcastChannel" in window ? new BroadcastChannel("flyffassist") : null;
  function togglePause(fromRemote) {
    if (!state.active) return;
    state.paused = !state.paused;
    log(state.paused ? "Pause" : "Reprise");
    render();
    if (!fromRemote) channel?.postMessage({ type: "toggle" });
  }
  // Appelé par FlyffAssist.exe quand on appuie sur la touche pause n'importe où dans Windows
  window.__flyffAssistToggle = () => togglePause(false);
  channel?.addEventListener("message", (e) => {
    if (e.data?.type === "toggle") togglePause(true);
  });
  window.addEventListener("keydown", (e) => {
    if (!e.isTrusted || e.repeat) return;
    if (window.__flyffAssistExe) return; // l'exe gère déjà la touche pause dans tout Windows
    if (e.key.toUpperCase() === String(cfg.toggleKey).toUpperCase()) {
      if (state.active) togglePause(false);
      else channel?.postMessage({ type: "toggle" });
    }
  }, true);

  // ---------------------------------------------------------------- interface
  const logs = [];
  function log(msg) {
    const t = new Date().toLocaleTimeString("fr-FR");
    logs.unshift(`${t}  ${msg}`);
    logs.length = Math.min(logs.length, 8);
    if (ui.log) ui.log.textContent = logs.join("\n");
  }

  const ui = {};
  const CSS = `
    :host { all: initial; }
    * { box-sizing: border-box; font-family: "Segoe UI", system-ui, sans-serif; }
    .panel { position: fixed; z-index: 2147483647; width: 320px; color: #f3ead2;
      background: linear-gradient(180deg, rgba(36,28,18,.96), rgba(22,17,11,.96));
      border: 1px solid #b8914a; border-radius: 10px; box-shadow: 0 8px 30px rgba(0,0,0,.55);
      font-size: 12px; user-select: none; }
    .head { display: flex; align-items: center; gap: 8px; padding: 8px 10px; cursor: move;
      border-bottom: 1px solid rgba(184,145,74,.4); }
    .title { font-weight: 700; color: #f0c766; letter-spacing: .3px; flex: 1; }
    .pill { padding: 2px 8px; border-radius: 99px; font-size: 11px; font-weight: 600; }
    .pill.off { background: #3b3326; color: #b9ad94; }
    .pill.on { background: #2f6b3a; color: #d6f5d9; }
    .pill.pause { background: #7a5a1c; color: #ffe7b0; }
    .icon { background: none; border: none; color: #f0c766; cursor: pointer; font-size: 14px; padding: 0 2px; }
    .body { padding: 8px 10px 10px; max-height: 75vh; overflow-y: auto; }
    .collapsed .body { display: none; }
    .sec { margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(184,145,74,.2); }
    .sec:first-child { margin-top: 0; padding-top: 0; border-top: none; }
    .sec h4 { margin: 0 0 6px; font-size: 11px; text-transform: uppercase; letter-spacing: .8px; color: #c9a65c;
      display: flex; align-items: center; justify-content: space-between; }
    .row { display: flex; align-items: center; gap: 6px; margin: 4px 0; }
    .row label { color: #cfc3a6; }
    .grow { flex: 1; }
    input[type=text], input[type=number] { width: 54px; padding: 3px 5px; border-radius: 5px;
      border: 1px solid #5a4a30; background: #120e08; color: #fff; font-size: 12px; text-align: center; }
    input[type=number]::-webkit-inner-spin-button, input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
    input[type=range] { flex: 1; accent-color: #f0c766; }
    button.btn { padding: 5px 10px; border-radius: 6px; border: 1px solid #b8914a; background: #3a2d18;
      color: #f3ead2; cursor: pointer; font-size: 12px; }
    button.btn:hover { background: #4d3b1f; }
    button.main { width: 100%; padding: 8px; font-weight: 700; font-size: 13px; }
    button.main.on { background: #2f6b3a; border-color: #5fb36d; }
    .sw { position: relative; width: 30px; height: 16px; flex: none; }
    .sw input { opacity: 0; width: 0; height: 0; }
    .sw span { position: absolute; inset: 0; background: #4a4033; border-radius: 99px; cursor: pointer; transition: .15s; }
    .sw span::before { content: ""; position: absolute; width: 12px; height: 12px; left: 2px; top: 2px;
      background: #d8cdb4; border-radius: 50%; transition: .15s; }
    .sw input:checked + span { background: #c9973a; }
    .sw input:checked + span::before { transform: translateX(14px); background: #fff; }
    .hpbar { height: 10px; border-radius: 5px; background: #2a2219; overflow: hidden; flex: 1; border: 1px solid #4a3d28; }
    .hpbar div { height: 100%; width: 0; background: linear-gradient(90deg, #c0392b, #e74c3c); transition: width .2s; }
    .buffs { display: grid; grid-template-columns: auto 1fr 58px auto 1fr 58px; gap: 4px 6px; align-items: center; }
    .buffs input[type=text], .buffs input[type=number] { width: 100%; }
    .hint { color: #9d917a; font-size: 11px; line-height: 1.35; margin: 4px 0; }
    .log { white-space: pre; font-family: Consolas, monospace; font-size: 11px; color: #cdbf9e;
      background: #120e08; border-radius: 6px; padding: 6px; min-height: 40px; max-height: 110px; overflow: auto; }
    .overlay { position: fixed; z-index: 2147483646; cursor: crosshair; background: rgba(0,0,0,.05); }
    .overlay .msg { position: absolute; left: 50%; top: 40%; transform: translateX(-50%); padding: 10px 14px;
      background: rgba(20,15,8,.92); border: 1px solid #f0c766; border-radius: 8px; color: #fff; font-size: 14px;
      pointer-events: none; text-align: center; }
  `;

  const sw = (bind) => `<label class="sw"><input type="checkbox" data-bind="${bind}"><span></span></label>`;

  function buildUi() {
    const host = document.createElement("div");
    host.id = "flyffassist-host";
    // Empêche le jeu de recevoir ce qu'on tape dans le panneau
    for (const t of ["keydown", "keyup", "keypress", "mousedown", "mouseup", "click", "wheel", "pointerdown", "pointerup"]) {
      host.addEventListener(t, (e) => e.stopPropagation());
    }
    const root = host.attachShadow({ mode: "open" });
    const buffRows = cfg.buffs.map((_, i) =>
      `${sw(`buffs.${i}.enabled`)}<input type="text" data-bind="buffs.${i}.key" placeholder="–"><input type="number" min="5" data-bind="buffs.${i}.interval" title="secondes">`
    ).join("");
    root.innerHTML = `<style>${CSS}</style>
      <div class="panel">
        <div class="head" data-drag>
          <span class="title">⚜ FlyffAssist</span>
          <span class="pill off" data-status>Inactif</span>
          <button class="icon" data-collapse title="Réduire">▾</button>
        </div>
        <div class="body">
          <div class="sec">
            <button class="btn main" data-run></button>
            <div class="hint">Active-le seulement dans la fenêtre du perso soutien. <b data-tg></b> met en pause, même depuis la fenêtre de ton perso principal.</div>
          </div>

          <div class="sec">
            <h4>PV de la cible</h4>
            <div class="row"><div class="hpbar"><div data-hpfill></div></div><b data-hptxt style="width:42px;text-align:right">–</b></div>
            <div class="row"><button class="btn" data-calib>Calibrer la barre</button><span class="grow"></span><label>Tolérance</label><input type="number" min="5" max="300" data-bind="tolerance"></div>
            <div class="hint">Cible ton perso principal (il doit être à 100 % PV), puis clique sur « Calibrer » et suis les instructions.</div>
          </div>

          <div class="sec">
            <h4>Soin ${sw("heal.enabled")}</h4>
            <div class="row"><label>Touche</label><input type="text" data-bind="heal.key"><span class="grow"></span><label>Délai (s)</label><input type="number" step="0.1" min="0.3" data-bind="heal.cooldown"></div>
            <div class="row"><label>Sous</label><input type="range" min="10" max="95" data-bind="heal.threshold"><b data-thr style="width:36px;text-align:right"></b></div>
          </div>

          <div class="sec">
            <h4>Buffs <span style="text-transform:none;letter-spacing:0;color:#9d917a">touche · relance (s)</span></h4>
            <div class="buffs">${buffRows}</div>
            <div class="row"><span class="grow"></span><label>Durée d'un sort (s)</label><input type="number" step="0.1" min="0.3" data-bind="castDelay"></div>
          </div>

          <div class="sec">
            <h4>Suivi ${sw("follow.enabled")}</h4>
            <div class="row"><label>Touche</label><input type="text" data-bind="follow.key"><span class="grow"></span><label>Toutes les (s)</label><input type="number" step="0.5" min="0.5" data-bind="follow.interval"></div>
          </div>

          <div class="sec">
            <h4>Outils</h4>
            <div class="row"><input type="text" value="1" data-testkey><button class="btn" data-test>Tester une touche</button><span class="grow"></span><label>Pause</label><input type="text" data-bind="toggleKey"></div>
          </div>

          <div class="sec"><div class="log" data-log></div></div>
        </div>
      </div>`;

    const $ = (s) => root.querySelector(s);
    ui.root = root;
    ui.panel = $(".panel");
    ui.status = $("[data-status]");
    ui.run = $("[data-run]");
    ui.hpfill = $("[data-hpfill]");
    ui.hptxt = $("[data-hptxt]");
    ui.thr = $("[data-thr]");
    ui.tg = $("[data-tg]");
    ui.log = $("[data-log]");

    // Liaison des champs avec la config
    const getPath = (p) => p.split(".").reduce((o, k) => o[k], cfg);
    const setPath = (p, v) => {
      const ks = p.split(".");
      const last = ks.pop();
      ks.reduce((o, k) => o[k], cfg)[last] = v;
    };
    root.querySelectorAll("[data-bind]").forEach((el) => {
      const p = el.dataset.bind;
      const v = getPath(p);
      if (el.type === "checkbox") el.checked = !!v;
      else el.value = v;
      el.addEventListener(el.type === "range" ? "input" : "change", () => {
        let val = el.type === "checkbox" ? el.checked : el.value;
        if (el.type === "number" || el.type === "range") {
          val = parseFloat(String(val).replace(",", "."));
          if (!isFinite(val)) { el.value = getPath(p); return; }
        }
        if (el.type === "text" && p !== "toggleKey" && val.trim() && !parseKey(val)) {
          log(`Touche « ${val} » non reconnue (ex. 1, 0, alt+3, z, F1)`);
          el.value = getPath(p);
          return;
        }
        setPath(p, val);
        saveConfig();
        render();
      });
    });

    ui.run.addEventListener("click", () => {
      state.active = !state.active;
      state.paused = false;
      sessionStorage.setItem(ACTIVE_KEY, state.active ? "1" : "0");
      if (state.active) {
        resetTimers();
        log("Assistant activé sur ce perso");
        if (!cfg.bar) log("⚠ Barre de PV non calibrée : pas de soin");
      } else log("Assistant arrêté");
      render();
    });
    $("[data-test]").addEventListener("click", () => {
      const k = parseKey($("[data-testkey]").value);
      if (!k) return log("Touche non reconnue");
      press(k);
      log(`Test : ${k.label} envoyée`);
    });
    $("[data-calib]").addEventListener("click", calibrate);
    $("[data-collapse]").addEventListener("click", () => {
      cfg.panel.collapsed = !cfg.panel.collapsed;
      saveConfig();
      render();
    });

    // Déplacement du panneau
    const head = $("[data-drag]");
    head.addEventListener("pointerdown", (e) => {
      if (e.target.closest("button")) return;
      const sx = e.clientX - cfg.panel.x, sy = e.clientY - cfg.panel.y;
      const move = (ev) => {
        cfg.panel.x = Math.max(0, Math.min(window.innerWidth - 60, ev.clientX - sx));
        cfg.panel.y = Math.max(0, Math.min(window.innerHeight - 30, ev.clientY - sy));
        place();
      };
      const up = () => {
        window.removeEventListener("pointermove", move, true);
        window.removeEventListener("pointerup", up, true);
        saveConfig();
      };
      window.addEventListener("pointermove", move, true);
      window.addEventListener("pointerup", up, true);
    });

    document.documentElement.appendChild(host);
    place();
    render();
    log("Prêt. Active-le dans la fenêtre du soutien.");
  }

  function place() {
    ui.panel.style.left = cfg.panel.x + "px";
    ui.panel.style.top = cfg.panel.y + "px";
  }

  function render() {
    if (!ui.panel) return;
    ui.panel.classList.toggle("collapsed", !!cfg.panel.collapsed);
    const st = !state.active ? ["off", "Inactif"] : state.paused ? ["pause", "En pause"] : ["on", "En marche"];
    ui.status.className = "pill " + st[0];
    ui.status.textContent = st[1];
    ui.run.textContent = state.active ? "■ Arrêter sur ce perso" : "▶ Activer sur ce perso";
    ui.run.classList.toggle("on", state.active);
    ui.thr.textContent = Math.round(cfg.heal.threshold) + " %";
    ui.tg.textContent = cfg.toggleKey;
    const hp = state.hp;
    ui.hpfill.style.width = (hp ?? 0) + "%";
    ui.hptxt.textContent = hp === null ? (cfg.bar ? "?" : "–") : hp + " %";
  }

  // Calibrage : deux clics sur la barre de PV de la cible
  function calibrate() {
    if (!gameCanvas) return log("Canvas du jeu introuvable");
    const r = gameCanvas.getBoundingClientRect();
    const ov = document.createElement("div");
    ov.className = "overlay";
    Object.assign(ov.style, { left: r.left + "px", top: r.top + "px", width: r.width + "px", height: r.height + "px" });
    ov.innerHTML = `<div class="msg">Clique sur le <b>début (gauche)</b> de la barre rouge de PV de ta cible<br><small>Échap pour annuler</small></div>`;
    ui.root.appendChild(ov);
    const msg = ov.querySelector(".msg");
    const toCanvas = (e) => [
      Math.round(((e.clientX - r.left) * gameCanvas.width) / r.width),
      Math.round(((e.clientY - r.top) * gameCanvas.height) / r.height),
    ];
    let first = null;
    const done = () => { ov.remove(); window.removeEventListener("keydown", esc, true); };
    const esc = (e) => { if (e.key === "Escape") { done(); log("Calibrage annulé"); } };
    window.addEventListener("keydown", esc, true);
    ov.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const [x, y] = toCanvas(e);
      if (!first) {
        const d = readPixels(x, y, 1);
        if (d[3] === 0) {
          done();
          return log("⚠ Impossible de lire l'image du jeu. Recharge la page (F5) avec l'extension active.");
        }
        first = { x, y, color: [d[0], d[1], d[2]] };
        msg.innerHTML = `Maintenant clique sur la <b>fin (droite)</b> de la barre<br><small>Échap pour annuler</small>`;
        return;
      }
      done();
      if (x <= first.x) return log("⚠ La fin doit être à droite du début, recommence");
      state.warnedSize = false;
      cfg.bar = { x1: first.x, x2: x, y: first.y, color: first.color, cw: gameCanvas.width, ch: gameCanvas.height };
      saveConfig();
      const hp = readHp();
      log(`Barre calibrée, couleur ${first.color.join(",")} → lu ${hp ?? "?"} %`);
      render();
    });
  }

  // ---------------------------------------------------------------- démarrage
  function findCanvas() {
    let best = null;
    for (const c of document.querySelectorAll("canvas")) {
      if (c === probe) continue;
      if (!best || c.width * c.height > best.width * best.height) best = c;
    }
    return best && best.width > 300 ? best : null;
  }

  const boot = setInterval(() => {
    const c = findCanvas();
    if (!c) return;
    gameCanvas = c;
    clearInterval(boot);
    buildUi();
    setInterval(() => {
      try { step(); } catch (e) { log("Erreur : " + e.message); }
    }, 100);
    setInterval(() => {
      const c2 = findCanvas();
      if (c2) gameCanvas = c2; // au cas où le jeu recrée son canvas
      render();
      if (cfg.bar && gameCanvas && (cfg.bar.cw !== gameCanvas.width || cfg.bar.ch !== gameCanvas.height) && !state.warnedSize) {
        state.warnedSize = true;
        log("⚠ Taille de fenêtre changée : recalibre la barre de PV");
      }
    }, 300);
  }, 500);
})();
