/* Stück der Woche – Editor */
(function () {
  "use strict";

  const APP_VERSION = "6.6"; // muss zu app/__init__.py passen
  const { GENRES, ACCENTS, newSheet, esc } = window.Sheet;
  const $ = (sel, root = document) => root.querySelector(sel);

  const state = {
    list: [],
    current: null,
    settings: { header_right: "Musik" },
    search: "",
    genre: "all",
    saveTimer: null,
    saving: null,
    dirty: false,
    previewReady: false,
  };

  // ------------------------------------------------------------------ Ladeanzeige

  // Kleine tanzende Noten – zeigen, dass gerade gearbeitet wird.
  const NOTES = `<span class="notes" aria-hidden="true"><i>♪</i><i>♫</i><i>♪</i></span>`;
  function busyHtml(text) {
    return `<span class="busy" role="status">${NOTES}<span>${esc(text)}</span></span>`;
  }

  // Oben in der Leiste, solange irgendetwas länger als eine Viertelsekunde dauert.
  const running = new Map();
  let runningId = 0, busyTimer = null;
  const LABELS = [
    [/^\/api\/lookup\/search/, "Suche in Wikipedia …"], [/^\/api\/lookup\/suggest/, "Lade Angaben und Bilder …"],
    [/^\/api\/lookup\/images/, "Suche Bilder …"], [/image(-url)?$/, "Lade Bild …"], [/^\/api\/media\//, "Suche Aufnahmen …"],
    [/^\/api\/code/, "Erzeuge Code …"], [/^\/api\/export/, "Erstelle PDF …"], [/^\/api\/ai\//, "Die KI schreibt …"],
    [/^\/api\/diagnose/, "Prüfe Verbindungen …"], [/^\/api\/sheets/, "Speichere …"], [/^\/api\/chromium/, "Lade Chromium …"],
  ];
  function busyStart(path) {
    const id = ++runningId;
    const label = (LABELS.find(([re]) => re.test(path)) || [null, "Arbeite …"])[1];
    running.set(id, label);
    clearTimeout(busyTimer);
    busyTimer = setTimeout(renderBusy, 250);
    return id;
  }
  function busyEnd(id) {
    running.delete(id);
    if (!running.size) { clearTimeout(busyTimer); renderBusy(); }
    else renderBusy();
  }
  function renderBusy() {
    const el = $("#busy");
    if (!el) return;
    if (!running.size) { el.hidden = true; el.innerHTML = ""; return; }
    const labels = [...new Set(running.values())];
    el.innerHTML = NOTES + `<span>${esc(labels[labels.length - 1])}</span>`;
    el.hidden = false;
  }

  // ------------------------------------------------------------------ API

  async function request(method, path, body) {
    const opts = { method, headers: {} };
    if (method === "POST") {
      opts.headers["Content-Type"] = "application/json";
      opts.headers["X-App"] = "1";
      opts.body = JSON.stringify(body || {});
    }
    let res;
    const busyId = busyStart(path);
    try {
      res = await fetch(path, opts);
    } catch (_) {
      busyEnd(busyId);
      appGone();
      const err = new Error("Die App läuft im Hintergrund nicht mehr – bitte „Stück der Woche“ neu starten. Ungespeicherte Änderungen werden danach automatisch nachgespeichert, solange dieses Fenster offen bleibt.");
      err.code = "offline";
      throw err;
    }
    appBack();
    let data = null;
    try { data = await res.json(); } catch (_) { /* leer */ }
    busyEnd(busyId);
    if (!res.ok) {
      const err = new Error((data && data.error) || `Fehler ${res.status}`);
      err.code = data && data.code;
      throw err;
    }
    return data;
  }
  let offline = false;
  function appGone() {
    if (offline) return;
    offline = true;
    document.body.classList.add("app-offline");
    setStatus("Keine Verbindung zur App – bitte „Stück der Woche“ neu starten.", true);
  }
  function appBack() {
    if (!offline) return;
    offline = false;
    document.body.classList.remove("app-offline");
    setStatus("Verbindung wiederhergestellt");
    if (state.dirty) saveNow();
  }
  const get = (p) => request("GET", p);
  const post = (p, b) => request("POST", p, b);

  // ------------------------------------------------------------------ Meldungen

  function setStatus(text, isError) {
    const el = $("#status");
    el.textContent = text;
    el.classList.toggle("error", !!isError);
  }

  let toastTimer;
  function toast(text, opts = {}) {
    const el = $("#toast");
    el.innerHTML = `<span>${esc(text)}</span>`;
    el.classList.toggle("error", !!opts.error);
    if (opts.action) {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = opts.action.label;
      b.onclick = () => { opts.action.run(); el.hidden = true; };
      el.appendChild(b);
    }
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (el.hidden = true), opts.error ? 7000 : 5000);
  }

  // ------------------------------------------------------------------ Dialoge

  function dialog(html, bind) {
    const dlg = $("#dlg");
    dlg.className = "dialog";
    dlg.oncancel = null; // eigene Esc-Behandlung eines früheren Dialogs entfernen
    dlg.innerHTML = html;
    return new Promise((resolve) => {
      const close = (val) => { dlg.close(); resolve(val); };
      dlg.onclose = () => resolve(undefined);
      dlg.querySelectorAll("[data-close]").forEach((b) => (b.onclick = () => close(undefined)));
      if (bind) bind(dlg, close);
      dlg.showModal();
    });
  }

  function confirmDialog(title, text, okLabel, danger) {
    return dialog(
      `<h2>${esc(title)}</h2><p>${esc(text)}</p>
       <div class="buttons"><button type="button" class="btn" data-close>Abbrechen</button>
       <button type="button" class="btn ${danger ? "btn-primary" : "btn-primary"}" id="dlg-ok"
         ${danger ? 'style="background:var(--danger);border-color:var(--danger)"' : ""}>${esc(okLabel)}</button></div>`,
      (dlg, close) => ($("#dlg-ok", dlg).onclick = () => close(true))
    );
  }

  // ------------------------------------------------------------------ Bibliothek

  function renderGenreFilter() {
    const box = $("#genre-filter");
    const items = [["all", "Alle"], ...Object.entries(GENRES).map(([k, g]) => [k, g.label])];
    box.innerHTML = items
      .map(([k, l]) => `<button type="button" class="chip" data-g="${k}" aria-pressed="${state.genre === k}">${esc(l)}</button>`)
      .join("");
    box.querySelectorAll("button").forEach((b) => (b.onclick = () => {
      state.genre = b.dataset.g;
      renderGenreFilter();
      renderList();
    }));
  }

  let lastListKey = "";
  function renderList() {
    const q = state.search.toLowerCase();
    const items = state.list.filter((s) => {
      if (state.genre !== "all" && s.kind !== state.genre) return false;
      if (!q) return true;
      return [s.short_title, s.title, s.person].join(" ").toLowerCase().includes(q);
    });
    const ul = $("#sheet-list");
    // Nur neu aufbauen, wenn sich an der Liste etwas geändert hat
    const key = JSON.stringify([items.map((x) => [x.id, x.short_title, x.title, x.person, x.kind]),
      state.current && state.current.id, state.list.length]);
    if (key === lastListKey && ul.childElementCount) return;
    lastListKey = key;
    if (!items.length) {
      ul.innerHTML = `<li class="none">${state.list.length ? "Keine Treffer." : "Noch keine Blätter gespeichert."}</li>`;
      return;
    }
    ul.innerHTML = items
      .map((s) => {
        const color = (GENRES[s.kind] || GENRES.klassik).accent;
        const cur = state.current && state.current.id === s.id;
        return `<li><button type="button" data-id="${esc(s.id)}" aria-current="${cur}">
          <span class="dot" style="background:${color}"></span>
          <span><div class="t">${esc(s.short_title || s.title || "Ohne Titel")}</div>
          <div class="p">${esc(s.person || "")}</div></span></button></li>`;
      })
      .join("");
    ul.querySelectorAll("button").forEach((b) => (b.onclick = () => openSheet(b.dataset.id)));
  }

  async function refreshList() {
    state.list = await get("/api/sheets");
    renderList();
  }

  // ------------------------------------------------------------------ Blatt öffnen / anlegen

  async function openSheet(id) {
    await flushSave();
    try {
      state.current = await get("/api/sheets/" + encodeURIComponent(id));
    } catch (e) {
      toast(e.message, { error: true });
      return;
    }
    normalize(state.current);
    try { localStorage.setItem("lastSheet", id); } catch (_) { /* egal */ }
    showEditor();
  }

  function normalize(s) {
    const base = newSheet(s.kind);
    for (const k of Object.keys(base)) if (s[k] === undefined) s[k] = base[k];
    s.image = Object.assign(base.image, s.image || {});
    s.links = Object.assign(base.links, s.links || {});
    s.codes = Object.assign(base.codes, s.codes || {});
    s.fields = (s.fields || []).map((f) => Object.assign({ label: "", value: "", wide: false, show: true }, f));
  }

  async function newSheetFlow() {
    const kind = await dialog(
      `<h2>Neues Blatt</h2><p>Welche Art von Stück? Das legt die passenden Felder und die Farbe fest. Beides kannst du danach ändern.</p>
       <div class="genre-grid">${Object.entries(GENRES)
         .map(([k, g]) => `<button type="button" class="btn" data-k="${k}"><span class="dot" style="background:${g.accent}"></span>${esc(g.label)}</button>`)
         .join("")}</div>
       <div class="buttons"><button type="button" class="btn" data-close>Abbrechen</button></div>`,
      (dlg, close) => dlg.querySelectorAll("[data-k]").forEach((b) => (b.onclick = () => close(b.dataset.k)))
    );
    if (!kind) return;
    await flushSave();
    const sheet = newSheet(kind);
    try {
      state.current = await post("/api/sheets", sheet);
    } catch (e) {
      toast(e.message, { error: true });
      return;
    }
    normalize(state.current);
    try { localStorage.setItem("lastSheet", state.current.id); } catch (_) { /* egal */ }
    await refreshList();
    showEditor();
    const t = $("#f-lookup");
    if (t) t.focus();
  }

  // ------------------------------------------------------------------ Speichern

  function changed() {
    state.dirty = true;
    setStatus("Ungespeicherte Änderungen …");
    clearTimeout(state.saveTimer);
    state.saveTimer = setTimeout(saveNow, 800);
    updatePreview();
  }

  async function saveNow() {
    clearTimeout(state.saveTimer);
    if (!state.current || !state.dirty) return state.saving;
    state.dirty = false;
    const snapshot = JSON.parse(JSON.stringify(state.current));
    const previous = state.saving;
    state.saving = (async () => {
      if (previous) { try { await previous; } catch (_) { /* egal */ } }
      try {
        const saved = await post("/api/sheets", snapshot);
        if (state.current && state.current.id === saved.id) {
          state.current.updated = saved.updated;
          state.current.created = saved.created;
        }
        setStatus("Gespeichert");
        const item = state.list.find((s) => s.id === saved.id);
        if (item) {
          item.short_title = saved.short_title;
          item.title = saved.title;
          item.kind = saved.kind;
          item.person = (saved.fields.find((f) => f.value) || {}).value || "";
          renderList();
        } else {
          refreshList();
        }
      } catch (e) {
        state.dirty = true;
        setStatus("Speichern fehlgeschlagen: " + e.message, true);
      }
    })();
    return state.saving;
  }

  async function flushSave() {
    if (state.dirty) await saveNow();
    else if (state.saving) await state.saving;
  }

  // ------------------------------------------------------------------ Vorschau

  let previewQueued = false;
  function updatePreview() {
    if (previewQueued) return;
    previewQueued = true;
    requestAnimationFrame(() => {
      previewQueued = false;
      if (!state.previewReady || !state.current) return;
      // Suchergebnisse und Prüfliste braucht die Vorschau nicht – kleinere Nachricht
      const { lookup, ai_checks, ...sheet } = state.current;
      $("#preview").contentWindow.postMessage(
        { type: "render", sheet: JSON.parse(JSON.stringify(sheet)), headerRight: state.settings.header_right,
          settings: designSettings(state.designOverride || state.settings) },
        location.origin
      );
    });
  }

  const DESIGN_KEYS = ["font_head", "font_body", "font_info", "size_title", "size_fields", "size_info"];
  function designSettings(src) {
    const out = {};
    for (const k of DESIGN_KEYS) out[k] = (src && src[k]) || "";
    return out;
  }

  function sizePreview() {
    const box = $("#preview-box");
    const ratio = 148 / 210;
    const w = Math.max(200, Math.min(box.clientWidth, (box.clientHeight - 4) * ratio, 720));
    const frame = $("#preview");
    frame.style.width = Math.floor(w) + "px";
    frame.style.height = Math.floor(w / ratio) + "px";
  }

  window.addEventListener("message", (e) => {
    if (e.source !== $("#preview").contentWindow || e.origin !== location.origin || !e.data) return;
    if (e.data.type === "preview-ready") {
      state.previewReady = true;
      updatePreview();
    } else if (e.data.type === "overflow") {
      $("#overflow-warning").hidden = !e.data.value;
    }
  });

  // ------------------------------------------------------------------ Editor

  function showEditor() {
    const has = !!state.current;
    document.body.classList.toggle("no-sheet", !has);
    $("#editor").hidden = !has;
    $("#empty").hidden = has;
    ["#btn-pdf-a5", "#btn-pdf-a4", "#btn-print", "#btn-duplicate", "#btn-delete"].forEach((s) => ($(s).disabled = !has));
    if (!has) { setStatus(""); renderList(); return; }
    buildEditor();
    renderList();
    sizePreview();
    updatePreview();
    setStatus(state.current.updated ? "Gespeichert" : "");
  }

  function buildEditor() {
    const s = state.current;
    const ed = $("#editor");
    ed.innerHTML = `
    <section class="section section-lookup">
      <h3>Automatisch ausfüllen <small>Wikipedia, Wikidata, Commons</small></h3>
      <form id="lookup-form" class="link-line" role="search">
        <label class="visually-hidden" for="f-lookup">Stück, Person oder Band suchen</label>
        <input type="search" id="f-lookup" value="${esc((s.lookup && s.lookup.q) || s.title)}" placeholder="z. B. Mondscheinsonate Beethoven" autocomplete="off">
        <button type="submit" class="btn btn-primary btn-small">Suchen</button>
      </form>
      <div id="lookup-results" class="lookup-results"></div>
    </section>

    <section class="section">
      <h3>Grunddaten</h3>
      <div class="grid2">
        <div class="row"><label for="f-kind">Art</label>
          <select id="f-kind">${Object.entries(GENRES)
            .map(([k, g]) => `<option value="${k}" ${s.kind === k ? "selected" : ""}>${esc(g.label)}</option>`)
            .join("")}</select></div>
        <div class="row"><span class="lbl" id="lbl-accent">Farbe</span>
          <div class="swatches" role="group" aria-labelledby="lbl-accent">
            ${ACCENTS.map((c) => `<button type="button" class="swatch" data-c="${c}" style="background:${c}" aria-label="Farbe ${c}" aria-pressed="${s.accent.toLowerCase() === c.toLowerCase()}"></button>`).join("")}
            <input type="color" id="f-accent" value="${esc(s.accent)}" aria-label="Eigene Farbe">
          </div></div>
      </div>
      <div class="row"><label for="f-short">Kurztitel (Kopfzeile)</label>
        <input type="text" id="f-short" value="${esc(s.short_title)}" placeholder="z. B. Mondscheinsonate"></div>
      <div class="row"><label for="f-title">Titel</label>
        <input type="text" id="f-title" value="${esc(s.title)}" placeholder="z. B. Mondscheinsonate"></div>
      <div class="row"><label for="f-subtitle">Untertitel</label>
        <input type="text" id="f-subtitle" value="${esc(s.subtitle)}" placeholder="z. B. 1. Satz: Adagio sostenuto"></div>
    </section>

    <section class="section">
      <h3>Angaben <small>leere Felder erscheinen nicht auf dem Blatt</small></h3>
      <div id="fields"></div>
      <div class="add-row">
        ${["Werkverzeichnis", "Gesamtwerk", "Satz", "Album", "Besetzung", "Tonart"]
          .map((l) => `<button type="button" class="btn btn-small" data-add="${l}">+ ${l}</button>`).join("")}
        <button type="button" class="btn btn-small" data-add="">+ Eigenes Feld</button>
      </div>
    </section>

    <section class="section">
      <h3>Infotext <span id="counter" class="counter"></span></h3>
      <label class="visually-hidden" for="f-info">Infotext</label>
      <textarea id="f-info" rows="11" placeholder="80–150 Wörter zu Entstehung, Einordnung, musikalischen Merkmalen und Wirkung. Leerzeile = neuer Absatz.">${esc(s.infotext)}</textarea>
      <div class="info-opts">
        <label for="f-info-size">Schriftgröße auf diesem Blatt</label>
        <select id="f-info-size">${infoSizeOptions(s.info_size)}</select>
        <button type="button" class="btn btn-small btn-ghost" id="f-design">Schriften für alle Blätter …</button>
      </div>
      <div id="ai-checks"></div>
      <div class="ai-bar">
        <label class="visually-hidden" for="f-wish">Wunsch an die KI (optional)</label>
        <input type="text" id="f-wish" placeholder="Wunsch (optional), z. B. einfacher für Klasse 5">
        <button type="button" class="btn btn-primary btn-small" id="f-ai">Text vorschlagen</button>
        <button type="button" class="icon-btn" id="f-ai-settings" title="KI-Einstellungen" aria-label="KI-Einstellungen">⚙</button>
      </div>
      <div id="ai-proposal"></div>
    </section>

    <section class="section">
      <h3>Bild</h3>
      <div class="image-row">
        <div class="thumb" id="thumb"></div>
        <div class="image-ctrls">
          <div style="display:flex;gap:6px;flex-wrap:wrap">
            <label class="btn btn-small" for="f-file" style="cursor:pointer">Bild wählen …</label>
            <input type="file" id="f-file" accept="image/jpeg,image/png,image/webp,image/gif" class="visually-hidden">
            <button type="button" class="btn btn-small" id="f-img-search">Auf Commons suchen …</button>
            <button type="button" class="btn btn-small btn-ghost btn-danger" id="f-img-remove">Entfernen</button>
          </div>
          <div class="slider"><label for="f-x">Waagerecht</label><input type="range" id="f-x" min="0" max="100" value="${esc(s.image.x)}"></div>
          <div class="slider"><label for="f-y">Senkrecht</label><input type="range" id="f-y" min="0" max="100" value="${esc(s.image.y)}"></div>
          <div class="hint" id="img-hint"></div>
          <div class="slider"><label for="f-zoom">Vergrößern</label><input type="range" id="f-zoom" min="1" max="3" step="0.05" value="${esc(s.image.zoom)}"></div>
          <div><button type="button" class="btn btn-small btn-ghost" id="f-img-reset" title="Ausschnitt und Vergrößerung auf die Standardwerte setzen">↺ Zurücksetzen</button></div>
        </div>
      </div>
      <div class="row" style="margin-top:10px"><label for="f-credit">Bildquelle</label>
        <input type="text" id="f-credit" value="${esc(s.image.credit)}" placeholder="Urheber:in · Lizenz · via Wikimedia Commons"></div>
    </section>

    <section class="section">
      <h3>Links und Codes <button type="button" class="btn btn-primary btn-small" id="f-versions">Versionen suchen …</button></h3>
      ${[
        ["youtube", "YouTube", "https://www.youtube.com/watch?v=…"],
        ["spotify", "Spotify", "https://open.spotify.com/track/…"],
        ["apple", "Apple Music", "https://music.apple.com/…"],
      ].map(([k, n, ph]) => `
        <div class="link-row">
          <label class="lbl" for="f-link-${k}">${n}</label>
          <div class="link-line">
            <input type="url" id="f-link-${k}" data-service="${k}" value="${esc(s.links[k])}" placeholder="${ph}">
            <button type="button" class="btn btn-small" data-open="${k}">Öffnen</button>
          </div>
          <div class="link-status ${s.codes[k] ? "ok" : ""}" id="st-${k}">${s.codes[k] ? "Code erstellt" : ""}</div>
        </div>`).join("")}
      <div class="hint">„Versionen suchen …“ findet Aufnahmen bei YouTube, Spotify und Apple Music. Oder Link einfügen – der Code wird automatisch erzeugt.</div>
    </section>`;

    bindEditor();
    renderLookup();
    renderChecks();
    renderFields();
    renderThumb();
    updateCounter();
  }

  // Auswahl für die Infotext-Größe eines einzelnen Blatts
  function infoSizeOptions(current) {
    const [lo, hi] = Sheet.SIZE_LIMITS.size_info;
    const global = Sheet.design(state.settings).size_info;
    let html = `<option value="">wie alle Blätter (${fmtPt(global)})</option>`;
    for (let v = lo; v <= hi; v += 0.5) {
      html += `<option value="${v}" ${current !== "" && current != null && Number(current) === v ? "selected" : ""}>${fmtPt(v)}</option>`;
    }
    return html;
  }
  function fmtPt(v) {
    return String(v).replace(".", ",") + " pt";
  }

  function bindEditor() {
    const s = state.current;
    const ed = $("#editor");

    $("#lookup-form", ed).onsubmit = (e) => { e.preventDefault(); lookupSearch(); };

    $("#f-kind", ed).onchange = (e) => {
      const old = GENRES[s.kind];
      s.kind = e.target.value;
      if (old && s.accent.toLowerCase() === old.accent.toLowerCase()) {
        s.accent = GENRES[s.kind].accent;
        syncSwatches();
      }
      changed();
    };
    ed.querySelectorAll(".swatch").forEach((b) => (b.onclick = () => { s.accent = b.dataset.c; syncSwatches(); changed(); }));
    $("#f-accent", ed).oninput = (e) => { s.accent = e.target.value; syncSwatches(); changed(); };

    const text = (id, setter) => ($(id, ed).oninput = (e) => { setter(e.target.value); changed(); });
    text("#f-short", (v) => (s.short_title = v));
    text("#f-title", (v) => (s.title = v));
    text("#f-subtitle", (v) => (s.subtitle = v));
    text("#f-info", (v) => { s.infotext = v; updateCounter(); });
    $("#f-ai", ed).onclick = () => aiPropose();
    $("#f-wish", ed).onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); aiPropose(); } };
    $("#f-ai-settings", ed).onclick = aiSettingsFlow;
    text("#f-credit", (v) => (s.image.credit = v));
    text("#f-x", (v) => { s.image.x = Number(v); renderThumb(); });
    text("#f-y", (v) => { s.image.y = Number(v); renderThumb(); });
    text("#f-zoom", (v) => { s.image.zoom = Number(v); renderThumb(); });
    $("#f-img-reset", ed).onclick = () => {
      Object.assign(s.image, Sheet.IMAGE_DEFAULTS);
      syncImageSliders();
      renderThumb();
      changed();
    };
    $("#f-info-size", ed).onchange = (e) => { s.info_size = e.target.value === "" ? "" : Number(e.target.value); changed(); };
    $("#f-design", ed).onclick = () => settingsFlow("blatt");

    ed.querySelectorAll("[data-add]").forEach((b) => (b.onclick = () => {
      s.fields.push({ label: b.dataset.add, value: "", wide: !!b.dataset.add && b.dataset.add !== "Tonart", show: true });
      renderFields();
      changed();
      const rows = $("#fields").querySelectorAll(".field-row");
      const last = rows[rows.length - 1];
      if (last) $(b.dataset.add ? "[data-k=value]" : "[data-k=label]", last).focus();
    }));

    $("#f-file", ed).onchange = (e) => uploadImage(e.target.files[0]);
    $("#f-img-search", ed).onclick = commonsSearchFlow;
    $("#f-img-remove", ed).onclick = () => {
      s.image.file = "";
      s.image.v = Date.now();
      renderThumb();
      changed();
    };

    ed.querySelectorAll("input[data-service]").forEach((inp) => {
      let t;
      inp.oninput = () => {
        s.links[inp.dataset.service] = inp.value.trim();
        clearTimeout(t);
        t = setTimeout(() => makeCode(inp.dataset.service), 700);
      };
    });
    $("#f-versions", ed).onclick = versionsFlow;
    ed.querySelectorAll("[data-open]").forEach((b) => (b.onclick = async () => {
      const url = s.links[b.dataset.open];
      if (!url) return toast("Noch kein Link eingetragen.");
      try { await post("/api/open-url", { url }); } catch (e) { toast(e.message, { error: true }); }
    }));
  }

  // ------------------------------------------------------------------ Wikidata

  // Die letzte Suche wird mit dem Blatt gespeichert und bleibt sichtbar.
  function renderLookup() {
    const s = state.current;
    const box = $("#lookup-results");
    if (!box) return;
    const lk = s.lookup;
    if (!lk || !lk.hits) { box.innerHTML = ""; return; }
    if (!lk.hits.length) {
      box.innerHTML = `<div class="hint">Keine Treffer für „${esc(lk.q)}“. Versuch es mit anderen Wörtern, z. B. nur dem Titel oder nur dem Namen.</div>`;
      return;
    }
    box.innerHTML = `<div class="lookup-head"><span class="hint">Treffer für „${esc(lk.q)}“ – welcher ist gemeint?</span>
        <button type="button" class="btn btn-small btn-ghost" id="lookup-clear">Ausblenden</button></div>` + lk.hits
      .map((h) => `<button type="button" class="hit${lk.chosen === h.id ? " hit-chosen" : ""}" data-id="${esc(h.id)}">
        <span class="hit-label">${esc(h.label)}${lk.chosen === h.id ? ' <span class="hit-tag">gewählt</span>' : ""}</span>
        <span class="hit-desc">${esc(h.description || "keine Beschreibung")}</span>
        <span class="hit-src">${esc(h.source || "")}${h.translated ? " · automatisch übersetzt" : ""}</span></button>`)
      .join("");
    box.querySelectorAll(".hit").forEach((b) => (b.onclick = () => loadSuggestions(b.dataset.id, b)));
    $("#lookup-clear", box).onclick = () => { s.lookup = null; renderLookup(); changed(); };
  }

  // Lädt ein Bild im Browser und gibt es als data:-URL zurück.
  async function browserImage(urls) {
    const toDataUrl = (blob) => new Promise((res, rej) => {
      const r = new FileReader();
      r.onload = () => res(r.result);
      r.onerror = () => rej(new Error("Lesefehler"));
      r.readAsDataURL(blob);
    });
    let last = "keine Adresse";
    for (const url of urls.filter(Boolean)) {
      try {
        const ctrl = new AbortController();
        const timer = setTimeout(() => ctrl.abort(), 10000);
        const resp = await fetch(url, { mode: "cors", credentials: "omit", signal: ctrl.signal })
          .finally(() => clearTimeout(timer));
        if (!resp.ok) { last = "HTTP " + resp.status; continue; }
        const blob = await resp.blob();
        if (!/^image\/(jpeg|png|webp|gif)$/.test(blob.type)) { last = "Format " + (blob.type || "unbekannt"); continue; }
        if (blob.size > 15 * 1024 * 1024) { last = "zu groß"; continue; }
        return await toDataUrl(blob);
      } catch (_) {
        // Notfalls über ein Bild-Element und eine Zeichenfläche
        try {
          return await new Promise((res, rej) => {
            const img = new Image();
            img.crossOrigin = "anonymous";
            img.onload = () => {
              try {
                const c = document.createElement("canvas");
                c.width = img.naturalWidth;
                c.height = img.naturalHeight;
                c.getContext("2d").drawImage(img, 0, 0);
                res(c.toDataURL("image/jpeg", 0.92));
              } catch (err) { rej(err); }
            };
            img.onerror = () => rej(new Error("nicht ladbar"));
            setTimeout(() => rej(new Error("Zeitüberschreitung")), 10000);
            img.src = url;
          });
        } catch (err) {
          last = err.message || "nicht ladbar";
        }
      }
    }
    throw new Error(last);
  }

  let lookupBusy = false;
  async function lookupSearch() {
    const s = state.current;
    const q = $("#f-lookup").value.trim();
    const box = $("#lookup-results");
    if (!q || lookupBusy) return;
    lookupBusy = true;
    const btn = $("#lookup-form button");
    if (btn) btn.disabled = true;
    box.innerHTML = busyHtml("Suche in Wikipedia (deutsch und englisch) und Wikidata …");
    try {
      const hits = await post("/api/lookup/search", { q, kind: s.kind });
      if (s !== state.current) return;
      s.lookup = { q, hits, chosen: null };
      renderLookup();
      changed();
    } catch (e) {
      box.innerHTML = `<div class="hint" style="color:var(--danger)">${esc(e.message)}</div>`;
    } finally {
      lookupBusy = false;
      const b2 = $("#lookup-form button");
      if (b2) b2.disabled = false;
    }
  }

  let suggestBusy = false;
  async function loadSuggestions(id, btn) {
    const s = state.current;
    if (suggestBusy) return;
    suggestBusy = true;
    const all = [...document.querySelectorAll("#lookup-results .hit")];
    all.forEach((b) => (b.disabled = true));
    const label = btn.querySelector(".hit-desc");
    const old = label.innerHTML;
    label.innerHTML = busyHtml("Lade Angaben und Bilder …");
    try {
      const sug = await post("/api/lookup/suggest", { id, kind: s.kind });
      const hit = s.lookup && s.lookup.hits.find((h) => h.id === id);
      if (hit && hit.description) sug.description = hit.description;
      if (s.lookup) s.lookup.chosen = id;
      await openSuggestions(sug);
      renderLookup();
    } catch (e) {
      toast(e.message, { error: true });
    } finally {
      suggestBusy = false;
      all.forEach((b) => (b.disabled = false));
      if (label.isConnected) label.innerHTML = old;
    }
  }

  const SYNONYMS = [
    ["komponist", "komponistin", "komponist:in", "komposition"],
    ["interpret", "interpretin", "interpret:in", "band", "ensemble", "künstler:in", "künstler", "künstlerin"],
    ["entstehung", "erscheinungsjahr", "aufnahmejahr", "jahr"],
    ["genre", "stil"],
    ["werkverzeichnis", "opus", "opuszahl"],
  ];
  function sameField(a, b) {
    a = (a || "").trim().toLowerCase();
    b = (b || "").trim().toLowerCase();
    if (a === b) return true;
    return SYNONYMS.some((g) => g.includes(a) && g.includes(b));
  }

  async function openSuggestions(sug) {
    const s = state.current;
    const rows = [];
    if (sug.title) rows.push({ key: "title", label: "Titel", value: sug.title, current: s.title });
    if (sug.short_title) rows.push({ key: "short_title", label: "Kurztitel", value: sug.short_title, current: s.short_title });
    for (const f of sug.fields) {
      const match = s.fields.find((x) => sameField(x.label, f.label));
      rows.push({ key: "field", label: f.label, value: f.value, wide: f.wide, current: match ? match.value : "" });
    }
    rows.forEach((r) => (r.checked = !r.current || r.current.trim() === r.value.trim()));

    const hasImage = !!s.image.file;
    const imgs = sug.images || [];
    const imgDefault = hasImage || !imgs.length ? "keep" : "0";

    const result = await dialog(
      `<h2>Vorschläge: ${esc(sug.label)}</h2>
       <p>${esc(sug.description || "")}${sug.description ? " · " : ""}<a href="#" id="sug-wd">${esc(sug.url_label || "Quelle ansehen")}</a><br>
       Häkchen = wird übernommen. Du kannst die Texte vorher noch ändern.</p>
       ${rows.length ? `<div class="sug-rows">${rows.map((r, i) => `
         <div class="sug-row">
           <input type="checkbox" id="sug-c${i}" ${r.checked ? "checked" : ""} aria-label="${esc(r.label)} übernehmen">
           <label for="sug-c${i}" class="sug-label">${esc(r.label)}</label>
           <div><input type="text" id="sug-v${i}" value="${esc(r.value)}" aria-label="${esc(r.label)}">
           ${r.current && r.current.trim() !== r.value.trim() ? `<div class="sug-current">bisher: ${esc(r.current)}</div>` : ""}</div>
         </div>`).join("")}</div>` : `<p>Zu diesem Eintrag gibt es keine passenden Angaben.</p>`}
       <h3 class="sug-h">Bild</h3>
       ${imgs.length ? `<div class="sug-images" role="radiogroup" aria-label="Bild wählen">
         <label class="sug-img sug-keep" title="${hasImage ? "Aktuelles Bild behalten" : "Kein Bild"}"><input type="radio" name="sug-img" value="keep" ${imgDefault === "keep" ? "checked" : ""}>
           ${hasImage
             ? `<img src="/data/${encodeURIComponent(s.id)}/${encodeURIComponent(s.image.file)}?v=${encodeURIComponent(s.image.v || 0)}" alt="Aktuelles Bild"><span class="sug-badge">aktuell</span>`
             : `<span>Kein Bild</span>`}</label>
         ${imgs.map((im, i) => `<label class="sug-img" title="${esc(im.title)}">
           <input type="radio" name="sug-img" value="${i}" ${imgDefault === String(i) ? "checked" : ""}>
           <img src="${esc(im.preview || im.thumb)}" alt="${esc(im.title)}" loading="lazy"></label>`).join("")}
       </div>
       <div class="sug-credit" id="sug-credit"></div>`
       : `<p>Auf Wikimedia Commons wurde kein passendes Bild gefunden. Unter „Bild“ kannst du mit „Auf Commons suchen …“ selbst nach einem Bild suchen.</p>`}
       <div class="buttons"><button type="button" class="btn" data-close>Abbrechen</button>
       <button type="button" class="btn btn-primary" id="dlg-ok">Übernehmen</button></div>`,
      (dlg, close) => {
        dlg.classList.add("dialog-wide");
        $("#sug-wd", dlg).onclick = (e) => { e.preventDefault(); post("/api/open-url", { url: sug.url }); };
        const credit = () => {
          const c = $("#sug-credit", dlg);
          if (!c) return;
          const sel = dlg.querySelector("input[name=sug-img]:checked");
          const im = sel && sel.value !== "keep" ? imgs[Number(sel.value)] : null;
          c.textContent = im ? "Bildquelle: " + im.credit : "";
        };
        dlg.querySelectorAll("input[name=sug-img]").forEach((r) => (r.onchange = credit));
        credit();
        $("#dlg-ok", dlg).onclick = () => {
          rows.forEach((r, i) => {
            r.checked = $("#sug-c" + i, dlg).checked;
            r.value = $("#sug-v" + i, dlg).value.trim();
          });
          const sel = dlg.querySelector("input[name=sug-img]:checked");
          close({ rows, image: sel && sel.value !== "keep" ? imgs[Number(sel.value)] : null });
        };
      }
    );
    if (!result) return;
    applySuggestions(result.rows, result.image);
  }

  async function applySuggestions(rows, image) {
    const s = state.current;
    for (const r of rows) {
      if (!r.checked || !r.value) continue;
      if (r.key === "title") s.title = r.value;
      else if (r.key === "short_title") s.short_title = r.value;
      else {
        const match = s.fields.find((x) => sameField(x.label, r.label));
        if (match) {
          match.label = r.label;
          match.value = r.value;
          match.show = true;
        } else {
          const field = { label: r.label, value: r.value, wide: !!r.wide, show: true };
          const before = s.fields.findIndex((x) => sameField(x.label, "Aufnahme"));
          if (before >= 0) s.fields.splice(before, 0, field);
          else s.fields.push(field);
        }
      }
    }
    // Angaben sofort eintragen – das Bild kommt danach.
    buildEditor();
    changed();
    if (!image) {
      toast("Vorschläge übernommen – bitte noch einmal prüfen.");
      return;
    }
    toast("Angaben übernommen – Bild wird geladen …");
    const ok = await applyCommonsImage(image);
    if (ok) toast("Vorschläge und Bild übernommen – bitte noch einmal prüfen.");
  }

  // Ein Bild von Wikimedia Commons ins Blatt holen – auf zwei Wegen.
  async function applyCommonsImage(image) {
    const s = state.current;
    setStatus("Bild wird geladen …");
    const thumb = $("#thumb");
    if (thumb) thumb.insertAdjacentHTML("beforeend", `<div class="thumb-busy">${NOTES}</div>`);
    await flushSave();
    let file = "";
    const errors = [];
    // Weg 1: Der Browser lädt das Bild (wie in der Auswahl) und übergibt es.
    try {
      const dataUrl = await browserImage([image.thumb, image.preview, image.original]);
      ({ file } = await post(`/api/sheets/${encodeURIComponent(s.id)}/image`, { data_url: dataUrl }));
    } catch (e) {
      errors.push("Browser: " + e.message);
    }
    // Weg 2: Die App lädt das Bild selbst.
    if (!file) {
      try {
        ({ file } = await post(`/api/sheets/${encodeURIComponent(s.id)}/image-url`,
          { url: image.thumb, original: image.original || "" }));
      } catch (e) {
        errors.push("App: " + e.message);
      }
    }
    document.querySelectorAll(".thumb-busy").forEach((x) => x.remove());
    if (s !== state.current) return false;
    if (!file) {
      setStatus("Bild konnte nicht geladen werden", true);
      toast(`Das Bild konnte nicht geladen werden (${errors.join("; ")})`, { error: true });
      logError("Bild " + (image.thumb || "") + ": " + errors.join("; "));
      return false;
    }
    Object.assign(s.image, { file, v: Date.now(), credit: image.credit, ...Sheet.IMAGE_DEFAULTS });
    renderThumb();
    $("#f-credit").value = image.credit;
    syncImageSliders();
    changed();
    return true;
  }

  // Freie Bildsuche auf Commons (z. B. wenn kein passendes Bild gefunden wurde)
  async function commonsSearchFlow() {
    const s = state.current;
    const order = s.kind === "klassik" ? ["Komponist", "Interpret"] : ["Interpret", "Komponist"];
    const person = (s.fields.find((f) => f.value && sameField(f.label, order[0]))
      || s.fields.find((f) => f.value && sameField(f.label, order[1]))
      || s.fields.find((f) => f.value) || {}).value || s.title || "";
    const initial = person.replace(/\s*\([^)]*\)\s*$/, "");
    let images = [];
    const choice = await dialog(
      `<h2>Bild auf Wikimedia Commons suchen</h2>
       <p>Freie Fotos und Gemälde. Die Bildquelle mit Lizenz wird automatisch eingetragen.</p>
       <form id="cs-form" class="link-line" role="search">
         <label class="visually-hidden" for="cs-q">Suchbegriff</label>
         <input type="search" id="cs-q" value="${esc(initial)}" placeholder="z. B. Name der Band oder Person">
         <button type="submit" class="btn btn-primary btn-small">Suchen</button>
       </form>
       <div id="cs-res" class="sug-images cs-grid" role="radiogroup" aria-label="Bild wählen" style="margin-top:12px"></div>
       <div class="sug-credit" id="cs-credit"></div>
       <div class="buttons"><button type="button" class="btn" data-close>Abbrechen</button>
       <button type="button" class="btn btn-primary" id="dlg-ok" disabled>Bild übernehmen</button></div>`,
      (dlg, close) => {
        dlg.classList.add("dialog-wide");
        const res = $("#cs-res", dlg);
        const ok = $("#dlg-ok", dlg);
        const run = async () => {
          const q = $("#cs-q", dlg).value.trim();
          if (!q) return;
          res.innerHTML = busyHtml("Suche auf Wikimedia Commons …");
          ok.disabled = true;
          $("#cs-credit", dlg).textContent = "";
          try {
            images = await post("/api/lookup/images", { q });
          } catch (e) {
            res.innerHTML = `<div class="hint" style="color:var(--danger)">${esc(e.message)}</div>`;
            return;
          }
          if (!images.length) {
            res.innerHTML = `<div class="hint">Keine Bilder gefunden. Versuch einen anderen Begriff.</div>`;
            return;
          }
          res.innerHTML = images.map((im, i) => `<label class="sug-img" title="${esc(im.title)}">
              <input type="radio" name="cs-img" value="${i}"><img src="${esc(im.preview || im.thumb)}" alt="${esc(im.title)}" loading="lazy"></label>`).join("");
          res.querySelectorAll("input").forEach((r) => (r.onchange = () => {
            ok.disabled = false;
            $("#cs-credit", dlg).textContent = "Bildquelle: " + images[Number(r.value)].credit;
          }));
        };
        $("#cs-form", dlg).onsubmit = (e) => { e.preventDefault(); run(); };
        ok.onclick = () => {
          const sel = dlg.querySelector("input[name=cs-img]:checked");
          if (sel) close(images[Number(sel.value)]);
        };
        if (initial) run();
      }
    );
    if (!choice) return;
    if (await applyCommonsImage(choice)) toast("Bild übernommen.");
  }

  // ------------------------------------------------------------------ Versionen (YouTube, Spotify, Apple)

  const MEDIA = [
    { key: "youtube", name: "YouTube", browse: (q) => "https://www.youtube.com/results?search_query=" + encodeURIComponent(q) },
    { key: "spotify", name: "Spotify", browse: (q) => "https://open.spotify.com/search/" + encodeURIComponent(q) },
    { key: "apple", name: "Apple Music", browse: (q) => "https://music.apple.com/de/search?term=" + encodeURIComponent(q) },
  ];

  function mainPerson(s) {
    const order = s.kind === "klassik" ? ["Komponist", "Interpret"] : ["Interpret", "Komponist"];
    const f = s.fields.find((x) => x.value && sameField(x.label, order[0]))
      || s.fields.find((x) => x.value && sameField(x.label, order[1]));
    return f ? f.value.replace(/\s*\([^)]*\)\s*$/, "") : "";
  }

  function defaultMediaQuery(s) {
    const name = mainPerson(s);
    const work = (s.fields.find((x) => x.value && sameField(x.label, "Werk")) || {}).value;
    const title = s.title || work || "";
    const part = s.kind === "klassik" ? (s.subtitle || "").split(":")[0] : "";
    return [title, part, name].filter(Boolean).join(" ").replace(/\s+/g, " ").trim();
  }

  const normWords = (t) => (t || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
    .split(/[^a-z0-9]+/).filter((w) => w.length > 2);

  // Wie gut passt Treffer b zur gewählten Aufnahme a? (gleiche Interpret:innen, gleiche Dauer)
  function matchScore(a, b) {
    let score = 0;
    if (a.duration_ms && b.duration_ms) {
      const diff = Math.abs(a.duration_ms - b.duration_ms);
      if (diff <= 3000) score += 2;
      else if (diff <= 8000) score += 1;
      else if (diff > 30000) score -= 2;
    }
    const aw = normWords(a.artist);
    const bw = new Set(normWords(b.artist + " " + b.title));
    if (aw.length && aw.filter((w) => bw.has(w)).length >= Math.min(2, aw.length)) score += 2;
    return score;
  }

  async function versionsFlow() {
    const s = state.current;
    await flushSave();
    const classical = s.kind === "klassik";
    const results = { youtube: [], spotify: [], apple: [] };
    const choice = { youtube: "keep", spotify: "keep", apple: "keep" };
    const manual = { youtube: false, spotify: false, apple: false };

    const picked = await dialog(
      `<h2>Versionen suchen</h2>
       <p>${classical
         ? "Bei klassischen Werken gibt es meist viele Aufnahmen – bitte wähle je Dienst die passende. Wählst du eine Aufnahme, markiert die App in den anderen Spalten dieselbe Aufnahme, wenn sie sie findet."
         : "Die besten Treffer sind vorausgewählt. Gibt es mehrere Versionen (Live, Remaster, Cover …), wähle die passende."}</p>
       <form id="mv-form" class="link-line" role="search">
         <label class="visually-hidden" for="mv-q">Suchbegriff</label>
         <input type="search" id="mv-q" value="${esc(defaultMediaQuery(s))}" placeholder="Titel und Interpret:in bzw. Komponist:in">
         <button type="submit" class="btn btn-primary btn-small">Suchen</button>
       </form>
       <div class="mv-cols">${MEDIA.map((m) => `
         <section class="mv-col" aria-label="${m.name}">
           <div class="mv-head"><b>${m.name}</b><button type="button" class="btn btn-small btn-ghost" data-browse="${m.key}">im Browser suchen</button></div>
           <div class="mv-list" id="mv-${m.key}" role="radiogroup" aria-label="${m.name}-Aufnahme wählen"></div>
         </section>`).join("")}</div>
       ${classical ? `<label class="mv-rec"><input type="checkbox" id="mv-rec" checked> Interpret:innen der gewählten Aufnahme ins Feld „Aufnahme“ eintragen</label>` : ""}
       <div class="buttons"><button type="button" class="btn" data-close>Abbrechen</button>
       <button type="button" class="btn btn-primary" id="dlg-ok">Links übernehmen</button></div>`,
      (dlg, close) => {
        dlg.classList.add("dialog-wide", "dialog-xwide");

        const renderCol = (key, message) => {
          const box = $("#mv-" + key, dlg);
          const current = s.links[key];
          const keep = `<label class="mv-item mv-keep"><input type="radio" name="mv-${key}" value="keep" ${choice[key] === "keep" ? "checked" : ""}>
            <span>${current ? "Bisherigen Link behalten" : "Keinen Link"}</span></label>`;
          if (message) { box.innerHTML = keep + message; bindCol(key); return; }
          const list = results[key];
          const anchor = MEDIA.map((m) => m.key).find((k) => k !== key && manual[k] && choice[k] !== "keep");
          const ref = anchor ? results[anchor][Number(choice[anchor])] : null;
          box.innerHTML = keep + (list.length ? list.map((r, i) => {
            const match = ref && matchScore(ref, r) >= 3;
            return `<label class="mv-item${match ? " mv-match" : ""}">
              <input type="radio" name="mv-${key}" value="${i}" ${choice[key] === String(i) ? "checked" : ""}>
              ${r.thumb ? `<img src="${esc(r.thumb)}" alt="" loading="lazy">` : `<span class="mv-noimg"></span>`}
              <span class="mv-text"><span class="mv-title">${esc(r.title)}</span>
                <span class="mv-artist">${esc(r.artist)}</span>
                <span class="mv-extra">${esc([r.extra, r.duration].filter(Boolean).join(" · "))}</span>
                ${match ? `<span class="mv-badge">passt zur Auswahl</span>` : ""}</span>
              <button type="button" class="icon-btn mv-play" data-url="${esc(r.url)}" aria-label="In ${key === "youtube" ? "YouTube" : key === "spotify" ? "Spotify" : "Apple Music"} öffnen" title="Öffnen und anhören">▶</button>
            </label>`;
          }).join("") : `<div class="hint mv-msg">Keine Treffer.</div>`);
          bindCol(key);
        };

        const autoMatch = (from) => {
          const ref = results[from][Number(choice[from])];
          if (!ref) return;
          for (const m of MEDIA) {
            if (m.key === from || manual[m.key]) continue;
            let best = -1, bestScore = 2;
            results[m.key].forEach((r, i) => {
              const sc = matchScore(ref, r);
              if (sc > bestScore) { bestScore = sc; best = i; }
            });
            if (best >= 0) choice[m.key] = String(best);
            renderCol(m.key);
          }
        };

        const bindCol = (key) => {
          const box = $("#mv-" + key, dlg);
          box.querySelectorAll(`input[name=mv-${key}]`).forEach((r) => (r.onchange = () => {
            choice[key] = r.value;
            manual[key] = true;
            if (r.value !== "keep") autoMatch(key);
          }));
          box.querySelectorAll(".mv-play").forEach((b) => (b.onclick = (e) => {
            e.preventDefault();
            e.stopPropagation();
            post("/api/open-url", { url: b.dataset.url });
          }));
        };

        const run = () => {
          const q = $("#mv-q", dlg).value.trim();
          if (!q) return;
          for (const m of MEDIA) {
            manual[m.key] = false;
            choice[m.key] = "keep";
            $("#mv-" + m.key, dlg).innerHTML = `<div class="hint mv-msg">${busyHtml("Suche …")}</div>`;
            post("/api/media/search", { service: m.key, q })
              .then((list) => {
                results[m.key] = list;
                if (!classical && list.length && !s.links[m.key]) choice[m.key] = "0";
                renderCol(m.key);
              })
              .catch((e) => {
                results[m.key] = [];
                const msg = e.code === "nokey"
                  ? `<div class="hint mv-msg">${esc(e.message)}. Mit „im Browser suchen“ den Link holen und im Editor einfügen – oder den Schlüssel in den Einstellungen (Zahnrad) eintragen.</div>`
                  : `<div class="hint mv-msg" style="color:var(--danger)">${esc(e.message)}</div>`;
                renderCol(m.key, msg);
              });
          }
        };

        $("#mv-form", dlg).onsubmit = (e) => { e.preventDefault(); run(); };
        dlg.querySelectorAll("[data-browse]").forEach((b) => (b.onclick = () => {
          const m = MEDIA.find((x) => x.key === b.dataset.browse);
          post("/api/open-url", { url: m.browse($("#mv-q", dlg).value.trim()) });
        }));
        $("#dlg-ok", dlg).onclick = () => close({
          picks: Object.fromEntries(MEDIA.map((m) => [m.key, choice[m.key] === "keep" ? null : results[m.key][Number(choice[m.key])]])),
          recording: !!(classical && $("#mv-rec", dlg) && $("#mv-rec", dlg).checked),
        });
        run();
      }
    );
    if (!picked) return;

    const changedKeys = [];
    for (const m of MEDIA) {
      const r = picked.picks[m.key];
      if (!r) continue;
      s.links[m.key] = r.url;
      const inp = $("#f-link-" + m.key);
      if (inp) inp.value = r.url;
      changedKeys.push(m.key);
    }
    if (picked.recording) {
      const rec = picked.picks.spotify || picked.picks.apple;
      if (rec && rec.artist) {
        const composer = normWords(mainPerson(s));
        const performers = rec.artist.split(/\s*,\s*|\s*&\s*/)
          .filter((a) => !normWords(a).some((w) => composer.includes(w)));
        if (performers.length) {
          let f = s.fields.find((x) => sameField(x.label, "Aufnahme"));
          if (!f) { f = { label: "Aufnahme", value: "", wide: true, show: true }; s.fields.push(f); }
          f.value = performers.join(", ");
          f.show = true;
          renderFields();
        }
      }
    }
    changed();
    await Promise.all(changedKeys.map((k) => makeCode(k)));
    if (changedKeys.length) toast(`Links übernommen: ${changedKeys.map((k) => MEDIA.find((m) => m.key === k).name).join(", ")}`);
  }

  // ------------------------------------------------------------------ KI-Infotext

  // „Bitte prüfen“-Liste: nur im Editor, nie auf dem Blatt
  function renderChecks() {
    const s = state.current;
    const box = $("#ai-checks");
    if (!box) return;
    const checks = s.ai_checks || [];
    if (!checks.length) { box.innerHTML = ""; return; }
    box.innerHTML = `<div class="ai-checks"><div class="ai-checks-head"><b>Bitte prüfen</b>
        <button type="button" class="btn btn-small btn-ghost" id="ai-checks-done">Erledigt</button></div>
      <ul>${checks.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>
      <div class="hint">Diese Hinweise erscheinen nicht auf dem Blatt.</div></div>`;
    $("#ai-checks-done", box).onclick = () => { s.ai_checks = []; renderChecks(); changed(); };
  }

  async function aiPropose() {
    const s = state.current;
    const btn = $("#f-ai");
    const wish = $("#f-wish").value.trim();
    const box = $("#ai-proposal");
    await flushSave();
    btn.disabled = true;
    const label = btn.textContent;
    btn.textContent = "Schreibt …";
    box.innerHTML = `<div class="ai-proposal ai-wait">${busyHtml("Die KI schreibt einen Vorschlag … das kann ein paar Sekunden dauern.")}</div>`;
    try {
      const r = await post("/api/ai/infotext", { id: s.id, wish, previous: wish ? s.infotext : "" });
      if (s !== state.current) return;
      const ok = r.words >= 80 && r.words <= 150;
      box.innerHTML = `<div class="ai-proposal">
        <div class="ai-head"><b>Vorschlag</b><span class="hint">${esc(r.provider || "")} · <span class="counter ${ok ? "ok" : "warn"}">${r.words} Wörter</span></span></div>
        ${r.sources ? "" : `<div class="hint ai-nosrc">Ohne Wikipedia-Quelle geschrieben – mit „Automatisch ausfüllen“ oben wird der Text genauer.</div>`}
        <div class="ai-text">${esc(r.text).split(/\n\s*\n/).map((p) => `<p>${p.replace(/\n/g, "<br>")}</p>`).join("")}</div>
        ${r.pruefen && r.pruefen.length ? `<div class="ai-checks inline"><b>Bitte prüfen</b><ul>${r.pruefen.map((c) => `<li>${esc(c)}</li>`).join("")}</ul></div>` : ""}
        <div class="ai-actions">
          <button type="button" class="btn btn-small" id="ai-discard">Verwerfen</button>
          <button type="button" class="btn btn-primary btn-small" id="ai-take">${s.infotext.trim() ? "Bisherigen Text ersetzen" : "Übernehmen"}</button>
        </div></div>`;
      $("#ai-discard", box).onclick = () => (box.innerHTML = "");
      $("#ai-take", box).onclick = () => {
        s.infotext = r.text;
        s.ai_checks = r.pruefen || [];
        $("#f-info").value = r.text;
        $("#f-wish").value = "";
        box.innerHTML = "";
        updateCounter();
        renderChecks();
        changed();
        toast("Infotext übernommen – bitte noch einmal lesen und anpassen.");
      };
    } catch (e) {
      box.innerHTML = `<div class="ai-proposal ai-error">${esc(e.message)}
        <div class="ai-actions"><button type="button" class="btn btn-small" id="ai-open-settings">KI-Einstellungen</button></div></div>`;
      $("#ai-open-settings", box).onclick = aiSettingsFlow;
    } finally {
      btn.disabled = false;
      btn.textContent = label;
    }
  }

  function logError(message) {
    fetch("/api/log", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-App": "1" },
      body: JSON.stringify({ message }),
    }).catch(() => {});
  }
  window.addEventListener("error", (e) => logError(`${e.message} (${e.filename}:${e.lineno})`));
  window.addEventListener("unhandledrejection", (e) => logError("Unbehandelt: " + (e.reason && (e.reason.stack || e.reason.message) || e.reason)));

  function syncSwatches() {
    const s = state.current;
    document.querySelectorAll(".swatch").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.c.toLowerCase() === s.accent.toLowerCase())));
    const c = $("#f-accent");
    if (c && c.value.toLowerCase() !== s.accent.toLowerCase()) c.value = s.accent;
  }

  const HANDLE_ICON = `<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M2 4h12M2 8h12M2 12h12" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`;

  function renderFields(focusHandle) {
    const s = state.current;
    const box = $("#fields");
    box.innerHTML = s.fields
      .map((f, i) => `
      <div class="field-row ${f.show ? "" : "hidden-field"}" data-i="${i}">
        <button type="button" class="drag-handle" title="Ziehen zum Sortieren (oder Pfeiltasten)"
          aria-label="„${esc(f.label || "Feld")}“ verschieben – Pfeiltasten hoch/runter">${HANDLE_ICON}</button>
        <input type="text" data-k="label" value="${esc(f.label)}" placeholder="Bezeichnung" aria-label="Bezeichnung ${i + 1}">
        <input type="text" data-k="value" value="${esc(f.value)}" placeholder="Inhalt" aria-label="${esc(f.label || "Inhalt")}">
        <div class="field-tools">
          <label title="Über die ganze Breite"><input type="checkbox" data-k="wide" ${f.wide ? "checked" : ""}>breit</label>
          <label title="Auf dem Blatt zeigen"><input type="checkbox" data-k="show" ${f.show ? "checked" : ""}>zeigen</label>
          <button type="button" class="icon-btn" data-act="del" aria-label="Feld entfernen" title="Feld entfernen">×</button>
        </div>
      </div>`)
      .join("");

    box.querySelectorAll(".field-row").forEach((row) => {
      const i = Number(row.dataset.i);
      const f = s.fields[i];
      row.querySelectorAll("input[type=text]").forEach((inp) => (inp.oninput = () => { f[inp.dataset.k] = inp.value; changed(); }));
      row.querySelectorAll("input[type=checkbox]").forEach((inp) => (inp.onchange = () => {
        f[inp.dataset.k] = inp.checked;
        row.classList.toggle("hidden-field", !f.show);
        changed();
      }));
      $("[data-act=del]", row).onclick = () => { s.fields.splice(i, 1); renderFields(); changed(); };

      const handle = $(".drag-handle", row);
      // Tastatur: Pfeiltasten verschieben das Feld
      handle.onkeydown = (e) => {
        const to = e.key === "ArrowUp" ? i - 1 : e.key === "ArrowDown" ? i + 1 : -1;
        if (to < 0 || to >= s.fields.length) return;
        e.preventDefault();
        const [moved] = s.fields.splice(i, 1);
        s.fields.splice(to, 0, moved);
        renderFields(to);
        changed();
      };
      // Maus, Touchpad, Finger: ziehen
      handle.onpointerdown = (e) => startDrag(e, row, box);
    });
    if (focusHandle !== undefined) {
      const h = box.querySelectorAll(".drag-handle")[focusHandle];
      if (h) h.focus();
    }
  }

  // Sortieren per Ziehen: Die Zeile folgt dem Zeiger, die anderen rutschen weich zur Seite.
  function startDrag(e, row, box) {
    if (e.button !== undefined && e.button !== 0) return;
    e.preventDefault();
    // Bewegungen auf der ganzen Seite verfolgen: Beim Umhängen der Zeile im Dokument
    // würde der Browser eine Bindung an den Griff sonst lösen.
    const pointerId = e.pointerId;
    const editor = $("#editor");
    const boxTop = () => box.getBoundingClientRect().top;
    const grab = e.clientY - boxTop() - row.offsetTop;
    row.classList.add("dragging");
    box.classList.add("sorting");
    let lastY = e.clientY;
    let scrollTimer = null;

    const others = () => [...box.querySelectorAll(".field-row")].filter((r) => r !== row);
    const place = () => {
      const y = lastY - boxTop();
      // Ziel: vor der ersten Zeile, deren Mitte unter dem Zeiger liegt
      let before = null;
      for (const o of others()) {
        if (y < o.offsetTop + o.offsetHeight / 2) { before = o; break; }
      }
      const changedPos = before ? before !== row.nextElementSibling : row !== box.lastElementChild;
      if (changedPos) {
        const list = others();
        const tops = new Map(list.map((o) => [o, o.offsetTop]));
        box.insertBefore(row, before);
        for (const o of list) {
          const d = tops.get(o) - o.offsetTop;
          if (!d) continue;
          o.style.transition = "none";
          o.style.transform = `translateY(${d}px)`;
          o.getBoundingClientRect(); // erzwingt Neuberechnung
          o.style.transition = "transform .15s ease";
          o.style.transform = "";
        }
      }
      row.style.transform = `translateY(${y - grab - row.offsetTop}px)`;
    };
    const autoScroll = () => {
      const r = editor.getBoundingClientRect();
      const step = lastY < r.top + 50 ? -10 : lastY > r.bottom - 50 ? 10 : 0;
      if (step) { editor.scrollTop += step; place(); }
    };
    const move = (ev) => {
      if (ev.pointerId !== pointerId) return;
      ev.preventDefault();
      lastY = ev.clientY;
      place();
    };
    const up = (ev) => {
      if (ev && ev.pointerId !== undefined && ev.pointerId !== pointerId) return;
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
      clearInterval(scrollTimer);
      const order = [...box.querySelectorAll(".field-row")].map((r) => Number(r.dataset.i));
      const s = state.current;
      const before = s.fields.slice();
      s.fields = order.map((i) => before[i]);
      const moved = order.some((v, k) => v !== k);
      box.classList.remove("sorting");
      renderFields();
      if (moved) changed();
    };
    window.addEventListener("pointermove", move, { passive: false });
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
    scrollTimer = setInterval(autoScroll, 30);
  }

  function updateCounter() {
    const n = (state.current.infotext || "").trim().split(/\s+/).filter(Boolean).length;
    const el = $("#counter");
    el.textContent = `${n} Wörter`;
    el.className = "counter " + (n >= 80 && n <= 150 ? "ok" : n ? "warn" : "");
  }

  function syncImageSliders() {
    const im = state.current.image;
    if (!$("#f-x")) return;
    $("#f-x").value = im.x;
    $("#f-y").value = im.y;
    $("#f-zoom").value = im.zoom;
  }

  function renderThumb() {
    const s = state.current;
    const el = $("#thumb");
    if (!el) return;
    const hint = $("#img-hint");
    if (s.image.file) {
      const clamp = (v, d, lo, hi) => (isFinite(Number(v)) ? Math.min(hi, Math.max(lo, Number(v))) : d);
      const x = clamp(s.image.x, 50, 0, 100), y = clamp(s.image.y, 25, 0, 100);
      const z = clamp(s.image.zoom, 1, 1, 3);
      const off = (v) => (-(z - 1) * v).toFixed(2);
      el.innerHTML = `<img alt="" src="/data/${encodeURIComponent(s.id)}/${encodeURIComponent(s.image.file)}?v=${encodeURIComponent(s.image.v || 0)}"
        style="position:absolute;width:${z * 100}%;height:${z * 100}%;left:${off(x)}%;top:${off(y)}%;object-fit:cover;object-position:${x}% ${y}%">`;
      // Lässt sich in eine Richtung nichts verschieben (Bild passt genau), Hinweis zeigen.
      const img = el.querySelector("img");
      const check = () => {
        if (!hint || !img.naturalWidth) return;
        const fw = 164, fh = 210;
        const sc = Math.max(fw / img.naturalWidth, fh / img.naturalHeight);
        const freeX = img.naturalWidth * sc - fw > 2 || z > 1.01;
        const freeY = img.naturalHeight * sc - fh > 2 || z > 1.01;
        const dirs = [!freeX && "waagerecht", !freeY && "senkrecht"].filter(Boolean);
        hint.textContent = dirs.length ? `Das Bild füllt den Rahmen ${dirs.join(" und ")} genau aus – zum Verschieben erst etwas vergrößern.` : "";
      };
      if (img.complete) check(); else img.onload = check;
    } else {
      el.innerHTML = "";
      if (hint) hint.textContent = "";
    }
  }

  async function uploadImage(file) {
    if (!file) return;
    if (file.size > 15 * 1024 * 1024) return toast("Das Bild ist zu groß (max. 15 MB).", { error: true });
    const s = state.current;
    const dataUrl = await new Promise((res, rej) => {
      const r = new FileReader();
      r.onload = () => res(r.result);
      r.onerror = rej;
      r.readAsDataURL(file);
    });
    try {
      await flushSave();
      const { file: name } = await post(`/api/sheets/${encodeURIComponent(s.id)}/image`, { data_url: dataUrl });
      s.image.file = name;
      s.image.v = Date.now();
      Object.assign(s.image, Sheet.IMAGE_DEFAULTS);
      syncImageSliders();
      renderThumb();
      changed();
    } catch (e) {
      toast(e.message, { error: true });
    }
    $("#f-file").value = "";
  }

  async function makeCode(service) {
    const s = state.current;
    const url = s.links[service];
    const st = $("#st-" + service);
    if (!url) {
      s.codes[service] = "";
      if (st) { st.textContent = ""; st.className = "link-status"; }
      changed();
      return;
    }
    if (st) { st.innerHTML = busyHtml("Code wird erzeugt …"); st.className = "link-status"; }
    try {
      const { svg } = await post("/api/code", { service, url });
      if (s !== state.current || s.links[service] !== url) return;
      s.codes[service] = svg;
      if (st) { st.textContent = "Code erstellt"; st.className = "link-status ok"; }
    } catch (e) {
      if (s !== state.current) return;
      s.codes[service] = "";
      if (st) { st.textContent = e.message; st.className = "link-status err"; }
    }
    changed();
  }

  // ------------------------------------------------------------------ Export

  let exporting = false;
  async function exportPdf(mode, ids) {
    if (exporting) return;
    exporting = true;
    const btns = ["#btn-pdf-a5", "#btn-pdf-a4"].map((x) => $(x));
    btns.forEach((b) => (b.disabled = true));
    try { await exportPdfInner(mode, ids); } finally {
      exporting = false;
      btns.forEach((b) => (b.disabled = !state.current));
    }
  }
  async function exportPdfInner(mode, ids) {
    await flushSave();
    setStatus("PDF wird erstellt …");
    try {
      const res = await post("/api/export", { mode, ids });
      setStatus("Gespeichert");
      toast(`PDF gespeichert: ${res.name}`, { action: { label: "Ordner öffnen", run: () => post("/api/open", { what: "export" }) } });
    } catch (e) {
      setStatus("PDF-Export fehlgeschlagen", true);
      toast(e.message, { error: true, action: { label: "Druckdialog öffnen", run: () => printDialog(mode, ids) } });
    }
  }

  // Druckdialog des Browsers (funktioniert mit jedem Browser, auch ohne Chromium)
  async function printDialog(mode, ids) {
    await flushSave();
    const old = document.getElementById("print-frame");
    if (old) old.remove();
    const frame = document.createElement("iframe");
    frame.id = "print-frame";
    frame.title = "Druckansicht";
    frame.style.cssText = "position:fixed;left:-10000px;top:0;width:1200px;height:900px;border:0;";
    frame.src = `print.html?mode=${mode}&ids=${encodeURIComponent(ids.join(","))}`;
    document.body.appendChild(frame);
    setStatus("Druckansicht wird vorbereitet …");
    const started = Date.now();
    const wait = setInterval(() => {
      const w = frame.contentWindow;
      if (w && w.__printReady) {
        clearInterval(wait);
        setStatus("Gespeichert");
        if (w.__printError) return toast(w.__printError, { error: true });
        w.focus();
        w.print();
      } else if (Date.now() - started > 20000) {
        clearInterval(wait);
        setStatus("");
        toast("Die Druckansicht konnte nicht geladen werden.", { error: true });
      }
    }, 150);
  }

  async function printFlow() {
    const cur = state.current;
    const others = state.list.filter((x) => x.id !== cur.id);
    const choice = await dialog(
      `<h2>Drucken</h2>
       <p>Öffnet den Druckdialog. Dort kannst du direkt drucken oder „Als PDF speichern“ wählen. Falls Farben fehlen: „Hintergrundgrafiken“ einschalten.</p>
       <div class="row"><label for="dlg-mode">Format</label>
       <select id="dlg-mode"><option value="a4">A4 quer – zwei A5-Blätter zum Schneiden</option>
       <option value="a5">A5 – ein Blatt</option></select></div>
       <div class="row" id="dlg-second-row"><label for="dlg-second">Rechte Hälfte</label>
       <select id="dlg-second"><option value="${esc(cur.id)}">Dasselbe Blatt noch einmal</option>
       ${others.map((o) => `<option value="${esc(o.id)}">${esc(o.short_title || o.title || "Ohne Titel")}</option>`).join("")}</select></div>
       <div class="buttons"><button type="button" class="btn" data-close>Abbrechen</button>
       <button type="button" class="btn btn-primary" id="dlg-ok">Druckdialog öffnen</button></div>`,
      (dlg, close) => {
        const mode = $("#dlg-mode", dlg);
        mode.onchange = () => ($("#dlg-second-row", dlg).hidden = mode.value !== "a4");
        $("#dlg-ok", dlg).onclick = () => close({ mode: mode.value, second: $("#dlg-second", dlg).value });
      }
    );
    if (!choice) return;
    printDialog(choice.mode, choice.mode === "a4" ? [cur.id, choice.second] : [cur.id]);
  }

  async function exportA4Flow() {
    const cur = state.current;
    const others = state.list.filter((x) => x.id !== cur.id);
    const choice = await dialog(
      `<h2>PDF zum Drucken (A4 quer)</h2>
       <p>Links steht „${esc(cur.short_title || cur.title || "dieses Blatt")}“. Was soll rechts daneben stehen?</p>
       <div class="row"><label for="dlg-second">Rechte Hälfte</label>
       <select id="dlg-second"><option value="${esc(cur.id)}">Dasselbe Blatt noch einmal</option>
       ${others.map((o) => `<option value="${esc(o.id)}">${esc(o.short_title || o.title || "Ohne Titel")}</option>`).join("")}</select></div>
       <div class="buttons"><button type="button" class="btn" data-close>Abbrechen</button>
       <button type="button" class="btn btn-primary" id="dlg-ok">PDF erstellen</button></div>`,
      (dlg, close) => ($("#dlg-ok", dlg).onclick = () => close($("#dlg-second", dlg).value))
    );
    if (choice) exportPdf("a4", [cur.id, choice]);
  }

  // ------------------------------------------------------------------ Einstellungen (mit Reitern)

  const SETTINGS_TABS = [
    ["allgemein", "Allgemein"],
    ["blatt", "Blatt & Schrift"],
    ["quellen", "Wikipedia"],
    ["musik", "Musikdienste"],
    ["ki", "KI-Anbindung"],
    ["hilfe", "Hilfe & Fehler"],
  ];
  let lastSettingsTab = "allgemein";

  function aiSettingsFlow() {
    return settingsFlow("ki");
  }

  // Beispielblatt für die Vorschau im Reiter „Blatt & Schrift“, wenn keins geöffnet ist
  function sampleSheet() {
    const s = newSheet("klassik");
    s.title = "Mondscheinsonate";
    s.subtitle = "1. Satz: Adagio sostenuto";
    s.short_title = "Mondscheinsonate";
    s.fields[0].value = "Ludwig van Beethoven (1770–1827)";
    s.fields[1].value = "Klaviersonate Nr. 14 cis-Moll, op. 27 Nr. 2";
    s.fields[2].value = "1801";
    s.fields[3].value = "Wiener Klassik";
    s.infotext = "Beethoven schrieb die Sonate 1801 und nannte sie „Sonata quasi una fantasia“. " +
      "Den Beinamen „Mondscheinsonate“ erhielt sie erst Jahre später durch den Dichter Ludwig Rellstab. " +
      "Der berühmte erste Satz lebt von gleichmäßig fließenden Triolen, über denen sich eine schlichte, " +
      "fast stockende Melodie erhebt.\n\nSo entsteht eine ruhige, nachdenkliche Stimmung, die Musiker:innen " +
      "und Zuhörer:innen bis heute fasziniert.";
    return s;
  }

  async function settingsFlow(tab) {
    let s, info;
    try {
      [s, info] = await Promise.all([get("/api/settings"), post("/api/ai/info", {})]);
    } catch (e) { return toast(e.message, { error: true }); }
    const startTab = typeof tab === "string" && SETTINGS_TABS.some(([k]) => k === tab) ? tab : lastSettingsTab;
    const provider = s.ai_provider || info.default_provider || "gemini";
    const presets = info.presets;
    const preset = s.openai_preset || "gemini";
    const sel = (cur, val) => (cur === val ? "selected" : "");
    const resultRow = (id) => `<span class="hint test-out" id="${id}"></span>`;
    const D = Sheet.DESIGN_DEFAULTS;
    // Schritt-für-Schritt-Anleitung; aufgeklappt, solange der Schlüssel noch fehlt
    const guide = (title, open, steps, note) => `
        <details class="guide" ${open ? "open" : ""}><summary>${title}</summary>
          <ol>${steps.map((st) => `<li>${st}</li>`).join("")}</ol>
          ${note ? `<p class="hint">${note}</p>` : ""}</details>`;
    const linkBtn = (url, label) => `<button type="button" class="btn btn-small" data-url="${esc(url)}">${label} ↗</button>`;

    const pathRow = (id, what, label, value, effective, hint) => `
        <div class="row"><label for="${id}">${label}</label>
          <div class="link-line"><input type="text" id="${id}" value="${esc(value)}" placeholder="${esc(effective)}" spellcheck="false">
            <button type="button" class="btn btn-small" data-pick="${what}" data-target="${id}">Auswählen …</button>
            <button type="button" class="btn btn-small btn-ghost" data-open-folder="${what}" title="Ordner im Dateimanager öffnen">Öffnen</button></div>
          ${hint ? `<span class="hint">${hint}</span>` : ""}</div>`;

    const fontOptions = (group, current, extra) =>
      (extra || "") + Object.entries(Sheet.FONTS[group]).map(([k, f]) =>
        `<option value="${esc(k)}" ${sel(current, k)}>${esc(f.label || k)}${k === D["font_" + (group === "head" ? "head" : "body")] ? " (Standard)" : ""}</option>`).join("");
    const sizeInput = (id, key, label) => {
      const [lo, hi] = Sheet.SIZE_LIMITS[key];
      return `<div class="row"><label for="${id}">${label}</label>
        <div class="size-line"><input type="number" id="${id}" min="${lo}" max="${hi}" step="0.5" value="${esc(s[key])}" placeholder="${String(D[key]).replace(".", ",")}">
        <span>pt</span></div></div>`;
    };

    const panels = {
      allgemein: `
        <div class="row"><label for="set-head">Kopfzeile rechts</label>
          <input type="text" id="set-head" value="${esc(s.header_right)}"></div>
        ${pathRow("set-data", "data", "Ordner für die Blätter", s.data_dir, s.data_dir_effective, "Leer lassen für den Standardordner.")}
        ${pathRow("set-export", "export", "Ordner für PDFs", s.export_dir, s.export_dir_effective, "")}
        <div class="row" style="margin-top:14px"><label for="set-browser">Eigener Browser-Pfad (optional)</label>
          <input type="text" id="set-browser" value="${esc(s.browser_path)}" placeholder="leer = automatisch" spellcheck="false">
          <span class="hint" id="pdf-engine">PDF-Export nutzt: ${s.pdf_engine_effective ? esc(s.pdf_engine_effective) : "noch kein Chromium vorhanden – bis dahin „Drucken …“ nutzen."}</span>
          ${s.pdf_engine_effective ? "" : `<div class="set-actions"><button type="button" class="btn btn-small" id="get-chromium">Chromium laden (ca. 100 MB)</button></div>`}</div>`,

      blatt: `
        <div class="design-grid">
          <div>
            <p class="hint">Gilt für alle Blätter. Die Größe des Infotexts kannst du zusätzlich für einzelne Blätter ändern (unter dem Infotext).</p>
            <div class="row"><label for="ds-head">Schrift für den Titel</label>
              <select id="ds-head">${fontOptions("head", s.font_head || D.font_head)}</select></div>
            <div class="row"><label for="ds-body">Schrift für Kopfzeile, Angaben und Codes</label>
              <select id="ds-body">${fontOptions("body", s.font_body || D.font_body)}</select></div>
            <div class="row"><label for="ds-info">Schrift für den Infotext</label>
              <select id="ds-info">${fontOptions("body", s.font_info, `<option value="">wie Angaben</option>`)}</select></div>
            <div class="grid3">
              ${sizeInput("ds-stitle", "size_title", "Titel")}
              ${sizeInput("ds-sfields", "size_fields", "Angaben")}
              ${sizeInput("ds-sinfo", "size_info", "Infotext")}
            </div>
            <div class="set-actions"><button type="button" class="btn btn-small btn-ghost" id="ds-reset">↺ Standard wiederherstellen</button></div>
            <p class="hint">Leeres Feld = Standardgröße. Lange Titel werden automatisch etwas kleiner gesetzt.
              Die Schriften kommen von Google Fonts; Systemschriften (Georgia, Helvetica/Arial) brauchen keinen Download.</p>
          </div>
          <div class="design-preview">
            <iframe id="ds-preview" src="preview.html" title="Vorschau der Schriften"></iframe>
            <div class="hint" id="ds-overflow"></div>
          </div>
        </div>`,

      quellen: `
        <p class="hint">„Automatisch ausfüllen“ sucht in der deutschen und englischen Wikipedia, in Wikidata und auf Wikimedia Commons.</p>
        <div class="row"><label for="set-contact">Kontakt-E-Mail für Wikipedia (optional, empfohlen)</label>
          <input type="text" id="set-contact" value="${esc(s.wiki_contact)}" placeholder="z. B. name@schule.de" autocomplete="off" spellcheck="false">
          <span class="hint">Wikimedia bittet Programme, eine Kontaktadresse mitzuschicken. Sie wird nur an Wikipedia/Wikidata übermittelt.</span></div>
        <div class="set-actions"><button type="button" class="btn btn-small" id="diag">Verbindungen prüfen</button>
          <button type="button" class="btn btn-small btn-ghost" id="clear-cache">Zwischenspeicher leeren</button></div>
        <div id="diag-out" class="diag-out"></div>`,

      musik: `
        <p class="hint">Für „Versionen suchen …“: Damit die App Aufnahmen bei YouTube und Spotify findet, braucht sie je einen
          kostenlosen Zugangsschlüssel. Das Einrichten dauert pro Dienst etwa 5 Minuten und ist nur einmal nötig.
          Apple Music braucht keinen Schlüssel.</p>
        <fieldset class="set-group"><legend>YouTube</legend>
          ${guide("So bekommst du den YouTube-Schlüssel", !s.youtube_key, [
            `Mit deinem Google-Konto ein Projekt anlegen – als Name z. B. „Stück der Woche“ eintragen und „Erstellen“ klicken.
             ${linkBtn("https://console.cloud.google.com/projectcreate", "Projekt anlegen")}`,
            `Die „YouTube Data API v3“ für dieses Projekt einschalten: oben das neue Projekt ausgewählt lassen und „Aktivieren“ klicken.
             ${linkBtn("https://console.cloud.google.com/apis/library/youtube.googleapis.com", "YouTube-API aktivieren")}`,
            `Unter „Anmeldedaten“ auf <b>„+ Anmeldedaten erstellen“ → „API-Schlüssel“</b> klicken.
             ${linkBtn("https://console.cloud.google.com/apis/credentials", "Anmeldedaten öffnen")}`,
            `Den angezeigten Schlüssel (beginnt mit „AIza…“) kopieren, unten einfügen und „Testen“ klicken.`,
          ], "Kostenlos, keine Zahlungsdaten nötig. Das Tageskontingent reicht für etwa 100 Suchen. Empfohlen: beim Schlüssel unter „API-Einschränkungen“ nur „YouTube Data API v3“ erlauben.")}
          <div class="row"><label for="set-yt">API-Schlüssel</label>
            <div class="link-line"><input type="password" id="set-yt" value="${esc(s.youtube_key)}" autocomplete="off" spellcheck="false" placeholder="AIza…">
            <button type="button" class="btn btn-small" data-test="youtube">Testen</button></div>
            ${resultRow("test-youtube")}</div></fieldset>
        <fieldset class="set-group"><legend>Spotify</legend>
          ${guide("So bekommst du die Spotify-Zugangsdaten", !s.spotify_id || !s.spotify_secret, [
            `Im Spotify-Entwicklerbereich mit deinem Spotify-Konto anmelden und den Nutzungsbedingungen zustimmen.
             ${linkBtn("https://developer.spotify.com/dashboard", "Spotify-Dashboard öffnen")}`,
            `<b>„Create app“</b> klicken und ausfüllen: App name „Stück der Woche“, App description „Musikunterricht“,
             Redirect URI <code>http://127.0.0.1:47110/callback</code> (wird nicht benutzt, muss aber ausgefüllt sein) und „Add“ klicken.
             Bei „Which API/SDKs“ <b>„Web API“</b> ankreuzen, den Bedingungen zustimmen, „Save“.`,
            `In der neuen App oben rechts <b>„Settings“</b> öffnen. Die <b>Client ID</b> kopieren und unten einfügen.`,
            `Darunter <b>„View client secret“</b> klicken, das <b>Client Secret</b> kopieren, unten einfügen und „Testen“ klicken.`,
          ], "Spotify erlaubt eigene Apps seit Februar 2026 nur noch mit einem Premium-Konto. Die Zugangsdaten gehören zu deinem Konto – nicht weitergeben.")}
          <div class="row"><label for="set-spid">Client-ID</label>
            <input type="text" id="set-spid" value="${esc(s.spotify_id)}" autocomplete="off" spellcheck="false"></div>
          <div class="row"><label for="set-spsec">Client-Secret</label>
            <div class="link-line"><input type="password" id="set-spsec" value="${esc(s.spotify_secret)}" autocomplete="off" spellcheck="false">
            <button type="button" class="btn btn-small" data-test="spotify">Testen</button></div>
            ${resultRow("test-spotify")}</div></fieldset>`,

      ki: `
        <p class="hint">Woher die Vorschläge für den Infotext kommen. Empfohlen und voreingestellt ist Google Gemini – kostenlos, nur ein Schlüssel nötig.</p>
        <div class="row"><label for="ai-prov">Anbieter</label>
          <select id="ai-prov">
            <option value="gemini" ${sel(provider, "gemini")}>Google Gemini – kostenlos (empfohlen)</option>
            ${info.platform === "darwin" || provider === "apple" ? `<option value="apple" ${sel(provider, "apple")}>Apple Intelligence – ohne Schlüssel (nur Mac)</option>` : ""}
            <option value="claude_code" ${sel(provider, "claude_code")}>Claude-Abo (über Claude Code)</option>
            <option value="anthropic" ${sel(provider, "anthropic")}>Claude-API mit Schlüssel (nach Verbrauch)</option>
            <option value="openai" ${sel(provider, "openai")}>Anderer Dienst – auch kostenlos oder lokal</option>
          </select></div>
        <div data-for="gemini">
          ${guide("So bekommst du den Gemini-Schlüssel (ca. 2 Minuten)", !s.gemini_key, [
            `Google AI Studio öffnen und mit deinem Google-Konto anmelden (ggf. den Bedingungen zustimmen).
             ${linkBtn(info.gemini_key_url || "https://aistudio.google.com/apikey", "Google AI Studio öffnen")}`,
            `<b>„API-Schlüssel erstellen“</b> („Create API key“) klicken. Fragt Google nach einem Projekt, ein neues anlegen lassen.`,
            `Den Schlüssel (beginnt mit „AIza…“) kopieren, unten einfügen und „Testen“ klicken.`,
          ], "Kostenlos im Rahmen von Googles Tageskontingent. Im kostenlosen Kontingent darf Google die Anfragen zur Verbesserung seiner Dienste nutzen – übermittelt werden nur Angaben zum Stück und die Wikipedia-Auszüge, keine Daten von Schüler:innen.")}
          <div class="row"><label for="ai-gkey">Gemini-Schlüssel</label>
            <input type="password" id="ai-gkey" value="${esc(s.gemini_key)}" autocomplete="off" spellcheck="false" placeholder="AIza…"></div>
          <details class="ai-template"><summary>Modell (nur für Fortgeschrittene)</summary>
            <div class="row"><label for="ai-gmodel">Modell</label>
              <input type="text" id="ai-gmodel" value="${esc(s.gemini_model)}" placeholder="${esc(info.default_gemini_model)}" spellcheck="false">
              <span class="hint">Leer lassen: Die App nimmt automatisch das aktuelle „Flash“-Modell und weicht selbst aus, wenn Google ein Modell abschaltet.</span></div>
          </details>
        </div>
        <div data-for="apple">
          ${guide("So richtest du Apple Intelligence ein (einmalig, ca. 3 Minuten)", true, [
            `„Kurzbefehle“ öffnen, links auf <b>„Galerie“</b> klicken und im Bereich <b>„Apple Intelligence“</b> bei <b>„Haiku“</b> auf <b>+</b> klicken.
             <button type="button" class="btn btn-small" id="open-shortcuts">Kurzbefehle öffnen ↗</button>`,
            `In deinen Kurzbefehlen „Haiku“ mit Rechtsklick → <b>„Duplizieren“</b>. Die Kopie umbenennen in genau
             <code>${esc(s.apple_shortcut || info.default_apple_shortcut)}</code> und doppelklicken.`,
            `Die erste Aktion <b>„Nach Text mit … fragen“</b> löschen (anklicken, Rückschritt-Taste).`,
            `In der Aktion <b>„Cloud-Modell verwenden“</b> den ganzen Text im Feld löschen. Dann per Rechtsklick ins Feld →
             <b>„Variable einfügen“ → „Kurzbefehleingabe“</b> wählen – sonst nichts eintippen. „Cloud“ so lassen.`,
            `Die letzte Aktion <b>„Antwort anzeigen“</b> löschen. Stattdessen rechts in der Suche „<b>ausgeben</b>“ eingeben, die Aktion
             <b>„Stoppen und ausgeben“</b> an diese Stelle ziehen und als Inhalt die <b>„Antwort“</b> wählen.`,
            `Fertig – die Aktionen sind jetzt nur noch „Cloud-Modell verwenden“ und „Stoppen und ausgeben“. Hier auf „Testen“ klicken.`,
          ], "Kostenlos, ohne Konto und ohne Schlüssel. „Cloud“ bedeutet Apples „Private Cloud Compute“: Die Anfrage wird auf Apples Servern verarbeitet, aber nicht gespeichert. Wikipedia-Auszüge werden für Apple Intelligence gekürzt, weil das Modell nur kürzere Anfragen verarbeitet.")}
          <div class="row"><label for="ai-apple">Name des Kurzbefehls</label>
            <input type="text" id="ai-apple" value="${esc(s.apple_shortcut)}" placeholder="${esc(info.default_apple_shortcut)}" spellcheck="false">
            <span class="hint" id="ai-apple-status"></span></div>
        </div>
        <div data-for="claude_code">
          <p class="hint">${info.claude_path ? "Claude Code gefunden: " + esc(info.claude_path) : "Claude Code wurde nicht gefunden. Installation: siehe LIESMICH.md, Abschnitt „KI-Infotexte“."}</p>
          <div class="grid2">
            <div class="row"><label for="ai-cmodel">Modell</label>
              <select id="ai-cmodel">${[["", "Standard"], ["sonnet", "Sonnet"], ["opus", "Opus"], ["haiku", "Haiku (schnell, sparsam)"]]
                .map(([v, l]) => `<option value="${v}" ${sel(s.claude_model, v)}>${l}</option>`).join("")}</select></div>
            <div class="row"><label for="ai-cpath">Pfad zu „claude“ (optional)</label>
              <input type="text" id="ai-cpath" value="${esc(s.claude_path)}" placeholder="automatisch" spellcheck="false"></div>
          </div>
        </div>
        <div data-for="anthropic">
          <div class="row"><label for="ai-akey">Claude-API-Schlüssel</label>
            <input type="password" id="ai-akey" value="${esc(s.anthropic_key)}" autocomplete="off" spellcheck="false"></div>
          <div class="row"><label for="ai-amodel">Modell</label>
            <input type="text" id="ai-amodel" value="${esc(s.anthropic_model)}" placeholder="${esc(info.default_anthropic_model)}"></div>
        </div>
        <div data-for="openai">
          <div class="row"><label for="ai-preset">Dienst</label>
            <select id="ai-preset">${Object.entries(presets).map(([k, p]) => `<option value="${k}" ${sel(preset, k)}>${esc(p.name)}</option>`).join("")}</select>
            <span class="hint" id="ai-preset-hint"></span></div>
          <div class="row"><label for="ai-obase">Adresse</label>
            <input type="text" id="ai-obase" value="${esc(s.openai_base)}" spellcheck="false"></div>
          <div class="row"><label for="ai-okey">Schlüssel</label>
            <input type="password" id="ai-okey" value="${esc(s.openai_key)}" autocomplete="off" spellcheck="false" placeholder="bei lokalen Modellen leer lassen"></div>
          <div class="row"><label for="ai-omodel">Modell</label>
            <div class="link-line"><input type="text" id="ai-omodel" list="ai-models" value="${esc(s.openai_model)}" spellcheck="false">
            <datalist id="ai-models"></datalist>
            <button type="button" class="btn btn-small" id="ai-load-models">Modelle laden</button></div>
            <span class="hint" id="ai-models-hint"></span></div>
        </div>
        <div class="set-actions"><button type="button" class="btn btn-small" id="ai-test">Testen</button></div>
        ${resultRow("ai-test-out")}
        <details class="ai-template"><summary>Aufgabe für die KI (Vorlage) bearbeiten</summary>
          <p class="hint">Platzhalter: {TITEL}, {ART}, {ANGABEN}, {QUELLEN}, {WUNSCH}. Die Antwort muss das JSON-Format am Ende behalten.</p>
          <textarea id="ai-prompt" rows="14">${esc(s.ai_prompt || info.default_prompt)}</textarea>
          <button type="button" class="btn btn-small btn-ghost" id="ai-prompt-reset">Standard wiederherstellen</button>
        </details>`,

      hilfe: `
        <p>Stück der Woche, Version ${esc(APP_VERSION)}.</p>
        <p class="hint">Installiert in: <code>${esc(s.app_dir_effective || "")}</code><br>
          Update: neue Version herunterladen und darin <code>bash install.sh</code> ausführen – Blätter und Einstellungen bleiben erhalten.</p>
        <p class="hint">Bei Problemen hilft das Fehlerprotokoll: Dort steht jeder Fehler mit Uhrzeit. Die Datei <code>protokoll.txt</code> kannst du weitergeben – API-Schlüssel werden darin unkenntlich gemacht.</p>
        <div class="set-actions">
          <button type="button" class="btn btn-small" data-open-folder="log">Fehlerprotokoll öffnen</button>
          <button type="button" class="btn btn-small" id="diag2">Verbindungen prüfen</button></div>
        <div id="diag-out2" class="diag-out"></div>
        <fieldset class="set-group"><legend>Updates</legend>
          <p class="hint" id="upd-info">Neue Versionen kommen von GitHub${s.update_repo_effective ? ` (${esc(s.update_repo_effective)})` : ""}.</p>
          <label class="check"><input type="checkbox" id="set-upd-auto" ${s.update_auto !== "0" ? "checked" : ""}> Beim Start automatisch nach Updates schauen</label>
          <div class="set-actions"><button type="button" class="btn btn-small" id="upd-check">Jetzt nach Updates suchen</button></div>
          ${resultRow("upd-out")}</fieldset>
        <p class="hint" style="margin-top:14px">Anleitungen (Installation, Schlüssel, KI) stehen in der Datei LIESMICH.md im App-Ordner.</p>`,
    };

    await dialog(
      `<h2>Einstellungen</h2>
       <div class="tabs" role="tablist" aria-label="Bereiche der Einstellungen">
         ${SETTINGS_TABS.map(([k, l]) => `<button type="button" role="tab" id="tab-${k}" aria-controls="panel-${k}"
           aria-selected="${k === startTab}" tabindex="${k === startTab ? 0 : -1}">${l}</button>`).join("")}
       </div>
       ${SETTINGS_TABS.map(([k]) => `<section class="tab-panel" role="tabpanel" id="panel-${k}" aria-labelledby="tab-${k}" ${k === startTab ? "" : "hidden"}>${panels[k]}</section>`).join("")}
       <div class="buttons" id="set-buttons">
         <span class="hint set-status" id="set-status" role="status" aria-live="polite">„Testen“ und „Öffnen“ speichern vorher.</span>
         <button type="button" class="btn" id="dlg-close">Schließen</button>
         <button type="button" class="btn btn-primary" id="dlg-ok">Speichern</button></div>
       <div class="buttons unsaved" id="set-unsaved" hidden>
         <span class="set-status" style="color:var(--danger)">Es gibt nicht gespeicherte Änderungen.</span>
         <button type="button" class="btn" id="dlg-back">Zurück</button>
         <button type="button" class="btn btn-ghost btn-danger" id="dlg-discard">Verwerfen</button>
         <button type="button" class="btn btn-primary" id="dlg-save-close">Speichern und schließen</button></div>`,
      (dlg, close) => {
        dlg.classList.add("dialog-wide", "dialog-settings");

        // Reiter (auch mit Pfeiltasten)
        const tabs = [...dlg.querySelectorAll("[role=tab]")];
        const show = (k, focus) => {
          lastSettingsTab = k;
          tabs.forEach((b) => {
            const on = b.id === "tab-" + k;
            b.setAttribute("aria-selected", String(on));
            b.tabIndex = on ? 0 : -1;
            if (on && focus) b.focus();
          });
          dlg.querySelectorAll(".tab-panel").forEach((p) => (p.hidden = p.id !== "panel-" + k));
          if (k === "blatt") drawDesign();
        };
        tabs.forEach((b, i) => {
          b.onclick = () => show(b.id.slice(4));
          b.onkeydown = (e) => {
            const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
            if (!d) return;
            e.preventDefault();
            show(tabs[(i + d + tabs.length) % tabs.length].id.slice(4), true);
          };
        });

        const values = () => {
          const promptText = $("#ai-prompt", dlg).value.trim();
          return {
            header_right: $("#set-head", dlg).value,
            data_dir: $("#set-data", dlg).value,
            export_dir: $("#set-export", dlg).value,
            browser_path: $("#set-browser", dlg).value,
            wiki_contact: $("#set-contact", dlg).value,
            youtube_key: $("#set-yt", dlg).value,
            spotify_id: $("#set-spid", dlg).value,
            spotify_secret: $("#set-spsec", dlg).value,
            ai_provider: $("#ai-prov", dlg).value,
            claude_model: $("#ai-cmodel", dlg).value,
            claude_path: $("#ai-cpath", dlg).value,
            anthropic_key: $("#ai-akey", dlg).value,
            gemini_key: $("#ai-gkey", dlg).value,
            apple_shortcut: $("#ai-apple", dlg).value,
            update_auto: $("#set-upd-auto", dlg).checked ? "1" : "0",
            gemini_model: $("#ai-gmodel", dlg).value,
            anthropic_model: $("#ai-amodel", dlg).value,
            openai_preset: $("#ai-preset", dlg).value,
            openai_base: $("#ai-obase", dlg).value,
            openai_key: $("#ai-okey", dlg).value,
            openai_model: $("#ai-omodel", dlg).value,
            ai_prompt: promptText === info.default_prompt.trim() ? "" : promptText,
            ...designValues(),
          };
        };
        // Vergleichsform: Leerzeichen am Rand zählen nicht als Änderung
        const fingerprint = () => JSON.stringify(Object.entries(values()).map(([k, v]) => [k, String(v).trim()]));
        let baseline = fingerprint();
        const isDirty = () => fingerprint() !== baseline;

        const statusEl = $("#set-status", dlg);
        const setInfo = (text, color) => {
          statusEl.textContent = text;
          statusEl.style.color = color || "";
        };
        dlg.addEventListener("input", () => { if (isDirty()) setInfo("Nicht gespeicherte Änderungen", ""); });
        dlg.addEventListener("change", () => { if (isDirty()) setInfo("Nicht gespeicherte Änderungen", ""); });

        // Speichern, ohne den Dialog zu schließen
        const save = async () => {
          await flushSave();
          const before = state.settings || {};
          state.settings = await post("/api/settings", values());
          // Werte so anzeigen, wie sie gespeichert wurden (z. B. begrenzte Schriftgrößen)
          $("#ds-stitle", dlg).value = state.settings.size_title;
          $("#ds-sfields", dlg).value = state.settings.size_fields;
          $("#ds-sinfo", dlg).value = state.settings.size_info;
          baseline = fingerprint();
          if (statusEl.textContent.startsWith("Nicht gespeichert")) setInfo("");
          await applySettings(before);
        };
        const saveClicked = async () => {
          const btn = $("#dlg-ok", dlg);
          btn.disabled = true;
          setInfo("Speichere …");
          try {
            await save();
            setInfo("✓ Gespeichert", "var(--ok)");
          } catch (e) {
            setInfo(e.message, "var(--danger)");
          }
          btn.disabled = false;
        };
        $("#dlg-ok", dlg).onclick = saveClicked;

        // Schließen: bei ungespeicherten Änderungen nachfragen
        const unsaved = $("#set-unsaved", dlg), normal = $("#set-buttons", dlg);
        const askOrClose = () => {
          if (!isDirty()) return close();
          normal.hidden = true;
          unsaved.hidden = false;
          $("#dlg-save-close", dlg).focus();
        };
        const back = () => { unsaved.hidden = true; normal.hidden = false; };
        $("#dlg-close", dlg).onclick = askOrClose;
        $("#dlg-back", dlg).onclick = back;
        $("#dlg-discard", dlg).onclick = () => close();
        $("#dlg-save-close", dlg).onclick = async () => {
          try { await save(); close(); } catch (e) { back(); setInfo(e.message, "var(--danger)"); }
        };
        dlg.oncancel = (e) => { e.preventDefault(); if (!unsaved.hidden) back(); else askOrClose(); }; // Esc

        // Test: erst speichern, dann prüfen; Ergebnis mit Ladeanzeige
        const runTest = async (out, fn) => {
          out.style.color = "";
          out.innerHTML = busyHtml("Teste …");
          try {
            await save();
            const msg = await fn();
            out.style.color = "var(--ok)";
            out.textContent = msg;
          } catch (e) {
            out.style.color = "var(--danger)";
            out.textContent = e.message;
          }
        };

        // Ordner: auswählen (Finder/Dateimanager) und öffnen
        dlg.querySelectorAll("[data-pick]").forEach((b) => (b.onclick = async () => {
          const input = $("#" + b.dataset.target, dlg);
          b.disabled = true;
          setInfo("Auswahlfenster ist geöffnet – es kann hinter diesem Fenster liegen.");
          try {
            const r = await post("/api/pick-folder", { what: b.dataset.pick, start: input.value });
            if (r.path) {
              input.value = r.path;
              setInfo("Ordner gewählt – zum Übernehmen „Speichern“ klicken.");
            } else {
              setInfo(isDirty() ? "Nicht gespeicherte Änderungen" : "");
            }
          } catch (e) {
            setInfo(e.message, "var(--danger)");
          }
          b.disabled = false;
        }));
        dlg.querySelectorAll("[data-open-folder]").forEach((b) => (b.onclick = async () => {
          try {
            if (isDirty() && b.dataset.openFolder !== "log") await save();
            await post("/api/open", { what: b.dataset.openFolder });
          } catch (e) {
            setInfo(e.message, "var(--danger)");
          }
        }));
        dlg.querySelectorAll("[data-url]").forEach((b) => (b.onclick = () =>
          post("/api/open-url", { url: b.dataset.url }).catch((e) => setInfo(e.message, "var(--danger)"))));
        dlg.querySelectorAll("[data-test]").forEach((b) => (b.onclick = () =>
          runTest($("#test-" + b.dataset.test, dlg), async () => (await post("/api/media/test", { service: b.dataset.test })).message)));
        $("#ai-test", dlg).onclick = () => runTest($("#ai-test-out", dlg), async () => (await post("/api/ai/test", {})).message);

        const diag = async (out) => {
          out.innerHTML = busyHtml("Prüfe Verbindungen … (bis zu einer Minute)");
          try {
            await save();
            const res = await post("/api/diagnose", {});
            out.innerHTML = `<ul>${res.map((r) => `<li class="${r.ok ? "ok" : "err"}"><b>${esc(r.name)}:</b> ${r.ok ? "erreichbar" : "FEHLER"} – ${esc(r.info)}${r.ms ? ` (${r.ms} ms)` : ""}</li>`).join("")}</ul>
              <div class="hint">Das Ergebnis steht auch im Fehlerprotokoll.</div>`;
          } catch (e) {
            out.innerHTML = `<div class="hint" style="color:var(--danger)">${esc(e.message)}</div>`;
          }
        };
        const getChromium = $("#get-chromium", dlg);
        if (getChromium) getChromium.onclick = async () => {
          const out = $("#pdf-engine", dlg);
          getChromium.disabled = true;
          out.style.color = "";
          out.innerHTML = busyHtml("Lade Chromium … (kann einige Minuten dauern)");
          try {
            const r = await post("/api/chromium", {});
            out.style.color = "var(--ok)";
            out.textContent = "PDF-Export nutzt: " + r.engine;
            getChromium.remove();
          } catch (e) {
            out.style.color = "var(--danger)";
            out.textContent = e.message;
            getChromium.disabled = false;
          }
        };
        $("#upd-check", dlg).onclick = async () => {
          const out = $("#upd-out", dlg);
          out.style.color = "";
          out.innerHTML = busyHtml("Frage bei GitHub nach …");
          try {
            const u = await checkUpdate(true);
            if (u.available) {
              out.style.color = "var(--ok)";
              out.innerHTML = `Version ${esc(u.latest)} ist verfügbar. <button type="button" class="btn btn-small btn-primary" id="upd-now">Ansehen …</button>`;
              $("#upd-now", dlg).onclick = () => { close(); updateFlow(); };
            } else {
              out.style.color = u.repo ? "var(--ok)" : "";
              out.textContent = u.repo ? `Du hast die neueste Version (${u.current}).` : u.message;
            }
          } catch (e) {
            out.style.color = "var(--danger)";
            out.textContent = e.message;
          }
        };
        $("#diag", dlg).onclick = () => diag($("#diag-out", dlg));
        $("#diag2", dlg).onclick = () => diag($("#diag-out2", dlg));
        $("#clear-cache", dlg).onclick = async () => {
          const out = $("#diag-out", dlg);
          try {
            const r = await post("/api/cache/clear", {});
            out.innerHTML = `<div class="hint" style="color:var(--ok)">${esc(r.message)}</div>`;
          } catch (e) {
            out.innerHTML = `<div class="hint" style="color:var(--danger)">${esc(e.message)}</div>`;
          }
        };

        // Blatt & Schrift: Werte, Vorschau, Zurücksetzen
        function designValues() {
          const head = $("#ds-head", dlg).value, body = $("#ds-body", dlg).value;
          return {
            font_head: head === D.font_head ? "" : head,
            font_body: body === D.font_body ? "" : body,
            font_info: $("#ds-info", dlg).value,
            size_title: $("#ds-stitle", dlg).value,
            size_fields: $("#ds-sfields", dlg).value,
            size_info: $("#ds-sinfo", dlg).value,
          };
        }
        const frame = $("#ds-preview", dlg);
        let frameReady = false;
        const drawDesign = () => {
          if (!frameReady || $("#panel-blatt", dlg).hidden) return;
          const base = state.current ? JSON.parse(JSON.stringify(state.current)) : sampleSheet();
          delete base.lookup;
          delete base.ai_checks;
          frame.contentWindow.postMessage({ type: "render", sheet: base, headerRight: $("#set-head", dlg).value,
            settings: designValues() }, location.origin);
        };
        const onFrameMessage = (e) => {
          if (e.source !== frame.contentWindow || e.origin !== location.origin || !e.data) return;
          if (e.data.type === "preview-ready") { frameReady = true; drawDesign(); }
          if (e.data.type === "overflow") {
            $("#ds-overflow", dlg).textContent = e.data.value ? "Achtung: So passt der Inhalt nicht mehr auf das Blatt." : "";
            $("#ds-overflow", dlg).style.color = "var(--danger)";
          }
        };
        window.addEventListener("message", onFrameMessage);
        dlg.addEventListener("close", () => window.removeEventListener("message", onFrameMessage), { once: true });
        $("#panel-blatt", dlg).addEventListener("input", drawDesign);
        $("#panel-blatt", dlg).addEventListener("change", drawDesign);
        $("#ds-reset", dlg).onclick = () => {
          $("#ds-head", dlg).value = D.font_head;
          $("#ds-body", dlg).value = D.font_body;
          $("#ds-info", dlg).value = "";
          ["#ds-stitle", "#ds-sfields", "#ds-sinfo"].forEach((id) => ($(id, dlg).value = ""));
          drawDesign();
          setInfo(isDirty() ? "Nicht gespeicherte Änderungen" : "");
        };

        // KI: Anbieter umschalten, Voreinstellungen, Modelle laden
        const prov = $("#ai-prov", dlg);
        const showProv = () => dlg.querySelectorAll("[data-for]").forEach((d) => (d.hidden = d.dataset.for !== prov.value));
        // Apple: anzeigen, ob der Kurzbefehl schon existiert
        let appleTimer = 0;
        const appleCheck = async () => {
          const out = $("#ai-apple-status", dlg);
          if (prov.value !== "apple" || !out) return;
          try {
            const r = await post("/api/ai/apple-check", { name: $("#ai-apple", dlg).value });
            out.style.color = r.exists ? "var(--ok)" : r.exists === false ? "var(--danger)" : "";
            out.textContent = r.exists ? `✓ Kurzbefehl „${r.name}“ gefunden.`
              : r.exists === false ? `Kurzbefehl „${r.name}“ noch nicht gefunden – siehe Anleitung oben.`
              : "Kurzbefehle lassen sich auf diesem Rechner nicht prüfen (nur Mac).";
          } catch (_) { /* egal */ }
        };
        $("#ai-apple", dlg).addEventListener("input", () => { clearTimeout(appleTimer); appleTimer = setTimeout(appleCheck, 500); });
        $("#open-shortcuts", dlg).onclick = () => post("/api/open-shortcuts", {}).catch((e) => setInfo(e.message, "var(--danger)"));
        window.addEventListener("focus", appleCheck); // nach dem Anlegen zurück in die App: neu prüfen
        dlg.addEventListener("close", () => window.removeEventListener("focus", appleCheck), { once: true });
        prov.onchange = () => { showProv(); appleCheck(); };
        showProv();
        appleCheck();
        const presetSel = $("#ai-preset", dlg);
        const presetHint = () => {
          const p = presets[presetSel.value];
          $("#ai-preset-hint", dlg).innerHTML = p.key_url
            ? `Schlüssel bekommst du hier: <a href="#" id="ai-keylink">${esc(p.key_url.replace(/^https:\/\//, ""))}</a>`
            : (presetSel.value === "custom" ? "Adresse, Schlüssel und Modell des Dienstes eintragen." : "Läuft auf deinem Rechner, kein Schlüssel nötig.");
          const link = $("#ai-keylink", dlg);
          if (link) link.onclick = (e) => { e.preventDefault(); post("/api/open-url", { url: p.key_url }); };
        };
        presetSel.onchange = () => {
          const p = presets[presetSel.value];
          if (p.base) $("#ai-obase", dlg).value = p.base;
          $("#ai-omodel", dlg).value = p.model;
          presetHint();
        };
        if (!s.openai_base && presets[preset]) {
          $("#ai-obase", dlg).value = presets[preset].base;
          if (!s.openai_model) $("#ai-omodel", dlg).value = presets[preset].model;
        }
        presetHint();
        $("#ai-load-models", dlg).onclick = async () => {
          const hint = $("#ai-models-hint", dlg);
          hint.style.color = "";
          hint.innerHTML = busyHtml("Lade Modelle …");
          try {
            const models = await post("/api/ai/models", { base: $("#ai-obase", dlg).value, key: $("#ai-okey", dlg).value });
            $("#ai-models", dlg).innerHTML = models.map((m) => `<option value="${esc(m)}"></option>`).join("");
            const free = models.filter((m) => m.endsWith(":free")).length;
            hint.textContent = `${models.length} Modelle verfügbar${free ? `, davon ${free} kostenlos („:free“)` : ""} – ins Feld klicken zum Auswählen.`;
          } catch (e) {
            hint.style.color = "var(--danger)";
            hint.textContent = e.message;
          }
        };
        $("#ai-prompt-reset", dlg).onclick = () => {
          $("#ai-prompt", dlg).value = info.default_prompt;
          setInfo(isDirty() ? "Nicht gespeicherte Änderungen" : "");
        };

        // Vorgaben (z. B. Adresse des KI-Dienstes) zählen nicht als Änderung
        baseline = fingerprint();
      }
    );
  }

  // Nach dem Speichern der Einstellungen: Liste, Editor und Vorschau anpassen
  async function applySettings(before) {
    const after = state.settings;
    if ((before.data_dir || "") !== (after.data_dir || "")) {
      await refreshList();
      if (state.current && !state.list.some((x) => x.id === state.current.id)) {
        state.current = null;
        showEditor();
      }
    }
    const sizeSel = $("#f-info-size");
    if (sizeSel && state.current) sizeSel.innerHTML = infoSizeOptions(state.current.info_size);
    updatePreview();
  }

  // ------------------------------------------------------------------ Updates

  let updateInfo = null;

  async function checkUpdate(force) {
    updateInfo = await post("/api/update/check", { force: !!force });
    renderUpdateBar();
    return updateInfo;
  }

  function renderUpdateBar() {
    const bar = $("#update-bar");
    const u = updateInfo;
    bar.hidden = !(u && u.available);
    if (bar.hidden) return;
    bar.innerHTML = `<span>Version ${esc(u.latest)} ist da</span>
      <button type="button" class="btn btn-small btn-primary">Aktualisieren …</button>`;
    bar.querySelector("button").onclick = updateFlow;
  }

  async function updateFlow() {
    const u = updateInfo;
    if (!u || !u.available) return;
    const auto = u.kind === "mac" || u.kind === "linux";
    const how = auto
      ? "Die App lädt die neue Version von GitHub, prüft sie und startet danach neu. Blätter, Einstellungen und Schlüssel bleiben erhalten."
      : u.kind === "paket"
        ? "Diese Installation stammt aus dem pacman-Paket: neue Version herunterladen und in <code>paket/arch</code> „makepkg -si“ ausführen."
        : "Die App läuft aus dem heruntergeladenen Ordner: bitte die neue Version herunterladen und installieren.";
    await dialog(
      `<h2>Neue Version ${esc(u.latest)}</h2>
       <p class="hint">Installiert ist Version ${esc(u.current)}.</p>
       ${u.notes ? `<div class="update-notes">${esc(u.notes)}</div>` : ""}
       <p>${how}</p>
       <div class="buttons"><span class="hint set-status" id="upd-status"></span>
         ${u.page ? `<button type="button" class="btn btn-ghost" id="upd-page">Auf GitHub ansehen ↗</button>` : ""}
         <button type="button" class="btn" data-close>Später</button>
         ${auto ? `<button type="button" class="btn btn-primary" id="upd-go">Jetzt aktualisieren</button>` : ""}</div>`,
      (dlg) => {
        const page = $("#upd-page", dlg);
        if (page) page.onclick = () => post("/api/open-url", { url: u.page });
        const go = $("#upd-go", dlg);
        if (!go) return;
        go.onclick = async () => {
          const out = $("#upd-status", dlg);
          go.disabled = true;
          dlg.querySelectorAll("[data-close]").forEach((b) => (b.disabled = true));
          out.style.color = "";
          out.innerHTML = busyHtml("Lade und prüfe das Update …");
          try {
            await flushSave();
            const r = await post("/api/update/install", {});
            out.innerHTML = busyHtml(`Version ${esc(r.version)} startet …`);
            waitForVersion(r.version, out);
          } catch (e) {
            out.style.color = "var(--danger)";
            out.textContent = e.message;
            go.disabled = false;
            dlg.querySelectorAll("[data-close]").forEach((b) => (b.disabled = false));
          }
        };
      }
    );
  }

  // Nach dem Update: warten, bis die neue Version antwortet, dann die Seite neu laden
  function waitForVersion(version, out) {
    const started = Date.now();
    const tick = async () => {
      try {
        const d = await (await fetch("/api/ping", { cache: "no-store" })).json();
        if (d.version === version) { location.reload(); return; }
      } catch (_) { /* startet noch */ }
      if (Date.now() - started > 90000) {
        out.style.color = "var(--danger)";
        out.textContent = "Die neue Version startet nicht von selbst – bitte die App schließen und neu öffnen.";
        return;
      }
      setTimeout(tick, 1000);
    };
    setTimeout(tick, 1500);
  }

  // ------------------------------------------------------------------ Start

  async function init() {
    renderGenreFilter();
    $("#search").oninput = (e) => { state.search = e.target.value; renderList(); };
    $("#btn-new").onclick = newSheetFlow;
    $("#btn-pdf-a5").onclick = () => exportPdf("a5", [state.current.id]);
    $("#btn-pdf-a4").onclick = exportA4Flow;
    $("#btn-print").onclick = printFlow;
    $("#btn-settings").onclick = () => settingsFlow();
    $("#btn-duplicate").onclick = async () => {
      await flushSave();
      try {
        const copy = await post(`/api/sheets/${encodeURIComponent(state.current.id)}/duplicate`, {});
        await refreshList();
        await openSheet(copy.id);
        toast("Kopie angelegt");
      } catch (e) { toast(e.message, { error: true }); }
    };
    $("#btn-delete").onclick = async () => {
      const cur = state.current;
      const ok = await confirmDialog("Blatt löschen?",
        `„${cur.short_title || cur.title || "Ohne Titel"}“ wird in den Papierkorb-Ordner der App verschoben.`, "Löschen", true);
      if (!ok) return;
      clearTimeout(state.saveTimer);
      state.dirty = false;
      // Ein laufendes Speichern erst abwarten – sonst könnte es das Blatt wieder anlegen
      if (state.saving) { try { await state.saving; } catch (_) { /* egal */ } }
      try {
        await post(`/api/sheets/${encodeURIComponent(cur.id)}/delete`, {});
        state.current = null;
        await refreshList();
        showEditor();
      } catch (e) { toast(e.message, { error: true }); }
    };
    document.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") { e.preventDefault(); saveNow(); }
    });
    window.addEventListener("resize", sizePreview);
    // Ändert sich der Platz für die Vorschau (z. B. durch den Hinweis „passt nicht“),
    // wird sie neu vermessen.
    if (window.ResizeObserver) new ResizeObserver(() => sizePreview()).observe($("#preview-box"));
    window.addEventListener("beforeunload", () => { if (state.dirty) saveNow(); });

    // Lebenszeichen an die App: wird das Fenster geschlossen, beendet sie sich.
    const ping = () => fetch("/api/ping")
      .then((r) => r.json())
      .then((d) => {
        appBack();
        if (d.version !== APP_VERSION) {
          // Läuft im Hintergrund schon eine neuere Version, die Seite einfach neu laden
          if (!state.dirty) location.reload();
          else setStatus("Die App wurde aktualisiert – bitte kurz warten, dann wird neu geladen.", true);
        }
      })
      .catch(() => appGone());
    ping();
    setInterval(ping, 15000);
    window.addEventListener("pageshow", ping);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) ping(); });
    window.addEventListener("pagehide", () => {
      try {
        fetch("/api/bye", { method: "POST", keepalive: true, headers: { "X-App": "1", "Content-Type": "application/json" }, body: "{}" });
      } catch (_) { /* egal */ }
    });

    try {
      state.settings = await get("/api/settings");
      await refreshList();
    } catch (e) {
      setStatus("Verbindung zur App fehlgeschlagen: " + e.message, true);
      return;
    }
    let last = null;
    try { last = localStorage.getItem("lastSheet"); } catch (_) { /* egal */ }
    if (last && state.list.some((x) => x.id === last)) await openSheet(last);
    else showEditor();
    sizePreview();
    // Einmal beim Start still nach Updates schauen (Fehler, z. B. offline, ignorieren)
    if (state.settings.update_auto !== "0") setTimeout(() => checkUpdate(false).catch(() => {}), 2500);
  }

  init();
})();
