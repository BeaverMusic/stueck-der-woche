/* Blattvorlage: erzeugt das HTML eines Blatts aus den gespeicherten Angaben.
   Wird von der Vorschau (preview.html) und vom PDF-Export (print.html) genutzt. */

(function () {
  "use strict";

  const GENRES = {
    klassik: {
      label: "Klassik",
      accent: "#2E6B4F",
      fields: [
        ["Komponist", true],
        ["Werk", true],
        ["Entstehung", false],
        ["Epoche", false],
        ["Aufnahme", true],
      ],
    },
    pop: {
      label: "Pop / Rock",
      accent: "#A3302A",
      fields: [
        ["Interpret", true],
        ["Album", true],
        ["Erscheinungsjahr", false],
        ["Genre", false],
      ],
    },
    jazz: {
      label: "Jazz",
      accent: "#8A5A00",
      fields: [
        ["Interpret", true],
        ["Komposition", true],
        ["Album", true],
        ["Aufnahmejahr", false],
        ["Stil", false],
      ],
    },
    sonstiges: {
      label: "Sonstiges",
      accent: "#1F3A5F",
      fields: [
        ["Künstler:in", true],
        ["Entstehung", false],
        ["Genre", false],
      ],
    },
  };

  const ACCENTS = ["#2E6B4F", "#1F3A5F", "#A3302A", "#8A5A00"];

  // Schriften (müssen zu HEAD_FONTS/BODY_FONTS in app/storage.py passen).
  // g = Abfrage bei Google Fonts; ohne g ist es eine Systemschrift (kein Download).
  const FONTS = {
    head: {
      "DM Serif Display": { css: '"DM Serif Display", Georgia, serif', g: "DM+Serif+Display" },
      "Playfair Display": { css: '"Playfair Display", Georgia, serif', g: "Playfair+Display:wght@600", w: 600 },
      Merriweather: { css: "Merriweather, Georgia, serif", g: "Merriweather:wght@700", w: 700 },
      Lora: { css: "Lora, Georgia, serif", g: "Lora:wght@600", w: 600 },
      "Source Serif 4": { css: '"Source Serif 4", Georgia, serif', g: "Source+Serif+4:wght@600", w: 600 },
      Fraunces: { css: "Fraunces, Georgia, serif", g: "Fraunces:wght@600", w: 600 },
      Montserrat: { css: "Montserrat, Arial, sans-serif", g: "Montserrat:wght@600", w: 600 },
      Georgia: { css: 'Georgia, "Times New Roman", serif', label: "Georgia (Systemschrift)" },
    },
    body: {
      "DM Sans": { css: '"DM Sans", "Helvetica Neue", Arial, sans-serif', g: "DM+Sans:wght@400;600" },
      "Source Sans 3": { css: '"Source Sans 3", Arial, sans-serif', g: "Source+Sans+3:wght@400;600" },
      "Open Sans": { css: '"Open Sans", Arial, sans-serif', g: "Open+Sans:wght@400;600" },
      Lato: { css: "Lato, Arial, sans-serif", g: "Lato:wght@400;700" },
      Nunito: { css: "Nunito, Arial, sans-serif", g: "Nunito:wght@400;600" },
      "Atkinson Hyperlegible": { css: '"Atkinson Hyperlegible", Arial, sans-serif', g: "Atkinson+Hyperlegible:wght@400;700", label: "Atkinson Hyperlegible (besonders gut lesbar)" },
      Andika: { css: "Andika, Arial, sans-serif", g: "Andika:wght@400;700", label: "Andika (Leseschrift für Kinder)" },
      Merriweather: { css: "Merriweather, Georgia, serif", g: "Merriweather:wght@400;700", label: "Merriweather (mit Serifen)" },
      Lora: { css: "Lora, Georgia, serif", g: "Lora:wght@400;600", label: "Lora (mit Serifen)" },
      Helvetica: { css: '"Helvetica Neue", Helvetica, Arial, sans-serif', label: "Helvetica / Arial (Systemschrift)" },
    },
  };
  // Standardwerte in Punkt (pt)
  const DESIGN_DEFAULTS = { font_head: "DM Serif Display", font_body: "DM Sans", font_info: "",
    size_title: 27, size_fields: 9.5, size_info: 9.5 };
  const SIZE_LIMITS = { size_title: [16, 40], size_fields: [7, 13], size_info: [7, 13] };

  /* Gestaltung aus den Einstellungen (und ggf. dem Blatt) – nur bekannte Werte. */
  function design(settings, sheet) {
    settings = settings || {};
    const d = {};
    d.font_head = FONTS.head[settings.font_head] ? settings.font_head : DESIGN_DEFAULTS.font_head;
    d.font_body = FONTS.body[settings.font_body] ? settings.font_body : DESIGN_DEFAULTS.font_body;
    d.font_info = FONTS.body[settings.font_info] ? settings.font_info : d.font_body;
    for (const k of Object.keys(SIZE_LIMITS)) {
      const [lo, hi] = SIZE_LIMITS[k];
      const v = settings[k] === "" || settings[k] == null ? DESIGN_DEFAULTS[k] : num(String(settings[k]).replace(",", "."), DESIGN_DEFAULTS[k], lo, hi);
      d[k] = v;
    }
    // Eigene Infotext-Größe für einzelne Blätter (z. B. bei langem Text)
    if (sheet && sheet.info_size !== "" && sheet.info_size != null) {
      d.size_info = num(sheet.info_size, d.size_info, ...SIZE_LIMITS.size_info);
    }
    return d;
  }

  function fontUrl(d) {
    // Gleiche Familie nur einmal anfragen, Schriftstärken zusammenführen
    const merged = new Map();
    for (const g of [FONTS.head[d.font_head].g, FONTS.body[d.font_body].g, FONTS.body[d.font_info].g]) {
      if (!g) continue;
      const [name, w] = g.split(":wght@");
      const set = merged.get(name) || new Set();
      (w || "400").split(";").forEach((x) => set.add(Number(x)));
      merged.set(name, set);
    }
    const fams = [...merged].map(([name, set]) => {
      const ws = [...set].sort((a, b) => a - b);
      return ws.length === 1 && ws[0] === 400 ? name : `${name}:wght@${ws.join(";")}`;
    });
    return fams.length
      ? "https://fonts.googleapis.com/css2?" + fams.map((f) => "family=" + f).join("&") + "&display=swap"
      : "";
  }

  /* Bindet die benötigten Schriften in das Dokument ein (nur Google-Fonts-Adressen). */
  function loadFonts(d, doc) {
    doc = doc || document;
    const url = fontUrl(d);
    let link = doc.getElementById("sheet-fonts");
    if (!url) { if (link) link.remove(); return Promise.resolve(); }
    if (link && link.getAttribute("href") === url) return link._ready || Promise.resolve();
    if (!link) {
      link = doc.createElement("link");
      link.id = "sheet-fonts";
      link.rel = "stylesheet";
      doc.head.appendChild(link);
    }
    link._ready = new Promise((r) => { link.onload = link.onerror = () => r(); setTimeout(r, 8000); });
    link.href = url;
    return link._ready;
  }

  function designStyle(d) {
    return `--head-font:${FONTS.head[d.font_head].css};--head-weight:${FONTS.head[d.font_head].w || 400};--body-font:${FONTS.body[d.font_body].css};` +
      `--info-font:${FONTS.body[d.font_info].css};--title-size:${d.size_title}pt;` +
      `--field-size:${d.size_fields}pt;--info-size:${d.size_info}pt`;
  }

  // Ausgangslage des Bildausschnitts (Mitte, eher oben – wo bei Porträts das Gesicht ist)
  const IMAGE_DEFAULTS = { x: 50, y: 25, zoom: 1 };

  function newSheet(kind) {
    const g = GENRES[kind] || GENRES.klassik;
    return {
      id: null,
      kind: kind in GENRES ? kind : "klassik",
      accent: g.accent,
      short_title: "",
      title: "",
      subtitle: "",
      fields: g.fields.map(([label, wide]) => ({ label, value: "", wide, show: true })),
      infotext: "",
      info_size: "", // eigene Infotext-Größe in pt, leer = wie alle Blätter
      ai_checks: [],
      image: { file: "", v: 0, credit: "", ...IMAGE_DEFAULTS },
      links: { youtube: "", spotify: "", apple: "" },
      codes: { youtube: "", spotify: "", apple: "" },
    };
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function safeColor(c) {
    return /^#[0-9a-fA-F]{6}$/.test(c || "") ? c : "#2E6B4F";
  }

  function num(v, def, min, max) {
    const n = Number(v);
    if (!isFinite(n)) return def;
    return Math.min(max, Math.max(min, n));
  }

  // SVG kommt von unserem eigenen Server (QR-Erzeugung bzw. Spotify) und ist dort
  // schon bereinigt. Zur Sicherheit wird es hier noch einmal aus einer Positivliste
  // neu aufgebaut: nur einfache Formen, keine Skripte, Links, Bilder oder Verweise.
  const SVG_TAGS = new Set(["svg", "g", "rect", "path", "circle", "ellipse", "line", "polyline", "polygon"]);
  const SVG_ATTRS = new Set(["viewBox", "width", "height", "x", "y", "rx", "ry", "cx", "cy", "r", "d", "fill",
    "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "fill-rule", "clip-rule", "transform",
    "points", "x1", "y1", "x2", "y2", "opacity", "fill-opacity", "shape-rendering", "version"]);
  const SAFE_VALUE = /^[\w\s.,:;#%()+-]*$/;
  const svgCache = new Map();
  function safeSvg(svg) {
    svg = String(svg || "");
    if (!svg) return "";
    if (svgCache.has(svg)) return svgCache.get(svg);
    let out = "";
    try {
      const doc = new DOMParser().parseFromString(svg, "image/svg+xml");
      const build = (el) => {
        const tag = el.localName;
        if (!SVG_TAGS.has(tag)) return "";
        let attrs = tag === "svg" ? ' xmlns="http://www.w3.org/2000/svg"' : "";
        for (const a of el.attributes) {
          if (SVG_ATTRS.has(a.localName) && SAFE_VALUE.test(a.value) && !/url/i.test(a.value))
            attrs += ` ${a.localName}="${a.value}"`;
        }
        let inner = "";
        for (const c of el.children) inner += build(c);
        return `<${tag}${attrs}>${inner}</${tag}>`;
      };
      const root = doc.documentElement;
      if (root && root.localName === "svg" && !doc.querySelector("parsererror")) out = build(root);
    } catch (_) { out = ""; }
    if (svgCache.size > 50) svgCache.clear();
    svgCache.set(svg, out);
    return out;
  }

  // Weiße Bogenmaske über dem Porträt: rundet die Ecken in jedem PDF-Betrachter
  // zuverlässig ab (statt sich auf die Beschneidung durch den Betrachter zu verlassen).
  const PORTRAIT_MASK =
    '<svg class="s-mask" viewBox="0 0 164 210" preserveAspectRatio="none" aria-hidden="true">' +
    '<path fill="#fff" fill-rule="evenodd" d="M-2 -2H166V212H-2Z M0 82A82 82 0 0 1 164 82V202A8 8 0 0 1 156 210H8A8 8 0 0 1 0 202Z"/></svg>';

  const ICON_PERSON =
    '<svg width="46" height="46" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/></svg>';
  const ICON_QR =
    '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><path d="M14 14h3v3h-3zM18 18h3v3h-3z"/></svg>';

  const SERVICES = [
    { key: "youtube", verb: "Anschauen", name: "YouTube", type: "qr" },
    { key: "spotify", verb: "Anhören", name: "Spotify", type: "spotify" },
    { key: "apple", verb: "Anhören", name: "Apple Music", type: "qr" },
  ];

  function render(sheet, opts) {
    opts = opts || {};
    const preview = !!opts.preview;
    const s = sheet || newSheet();
    const accent = safeColor(s.accent);
    const d = design(opts.design, s);

    // Titelgröße an die Länge anpassen
    const tlen = (s.title || "").length;
    const tclass = tlen > 34 ? " s-xlong" : tlen > 20 ? " s-long" : "";

    const fields = (s.fields || [])
      .filter((f) => f.show !== false && String(f.value || "").trim())
      .map(
        (f) =>
          `<div class="s-field${f.wide ? " s-wide" : ""}"><div class="s-flabel">${esc(
            f.label
          )}</div><div>${esc(f.value)}</div></div>`
      )
      .join("");

    // Porträt
    const img = s.image || {};
    let portrait;
    if (img.file && s.id) {
      const x = num(img.x, 50, 0, 100);
      const y = num(img.y, IMAGE_DEFAULTS.y, 0, 100);
      const z = num(img.zoom, 1, 1, 3);
      const src = `${opts.assetBase || ""}/data/${encodeURIComponent(s.id)}/${encodeURIComponent(
        img.file
      )}?v=${encodeURIComponent(img.v || 0)}`;
      // Vergrößern ohne CSS-Transformation (wird in PDFs zuverlässiger dargestellt):
      // Bild größer als der Rahmen und so verschoben, dass der gewählte Punkt sichtbar bleibt.
      const off = (v) => (-(z - 1) * v).toFixed(2);
      portrait = `<img src="${esc(src)}" alt="" style="width:${(z * 100).toFixed(2)}%;height:${(z * 100).toFixed(2)}%;left:${off(x)}%;top:${off(y)}%;object-position:${x}% ${y}%">`;
    } else {
      portrait = preview
        ? `<div class="s-placeholder">${ICON_PERSON}<div>Porträt<br>noch kein Bild</div></div>`
        : "";
    }

    // Codes
    const codes = s.codes || {};
    const boxes = [];
    const cols = [];
    for (const sv of SERVICES) {
      const svg = safeSvg(codes[sv.key]);
      if (!svg && !preview) continue;
      let inner;
      if (sv.type === "qr") {
        inner = svg
          ? `<div class="s-qr">${svg}</div>`
          : `<div class="s-qr s-empty">${ICON_QR}</div>`;
        cols.push("1fr");
      } else {
        inner = `<div class="s-spot-wrap">${
          svg ? `<div class="s-spot">${svg}</div>` : `<div class="s-spot s-empty">Spotify-Code</div>`
        }</div>`;
        cols.push("1.5fr");
      }
      boxes.push(
        `<div class="s-code">${inner}<div class="s-clabel"><b>${sv.verb}</b><br><span>${sv.name}</span></div></div>`
      );
    }
    const codesHtml = boxes.length
      ? `<div class="s-codes" style="grid-template-columns:${cols.join(" ")}">${boxes.join("")}</div>`
      : `<div class="s-codes-none"></div>`;

    const info = String(s.infotext || "")
      .split(/\n\s*\n/)
      .map((p) => p.trim())
      .filter(Boolean)
      .map((p) => `<p>${esc(p).replace(/\n/g, "<br>")}</p>`)
      .join("");

    const credit = String(img.credit || "").trim();
    const creditHtml = credit
      ? `<div class="s-credit">Bild: ${esc(credit)}</div>`
      : preview && img.file
      ? `<div class="s-credit" style="color:#A3302A">Bildquelle fehlt noch</div>`
      : "";

    const short = String(s.short_title || "").trim();

    return `<div class="sheet" style="--accent:${accent};${esc(designStyle(d))}">
<div class="sheet-inner">
<div class="s-head"><div><span class="s-label">Stück der Woche</span>${
      short ? ` <span class="s-short">· ${esc(short)}</span>` : ""
    }</div><div class="s-right">${esc(opts.headerRight || "")}</div></div>
<div class="s-staff" aria-hidden="true"><div></div><div></div><div></div><div></div><div></div></div>
<div class="s-top">
<div class="s-main">
<div><h1 class="s-title${tclass}">${esc(s.title || (preview ? "Titel" : ""))}</h1>${
      s.subtitle ? `<div class="s-subtitle">${esc(s.subtitle)}</div>` : ""
    }</div>
<div class="s-fields">${fields}</div>
</div>
${portrait || preview ? `<div class="s-portrait">${portrait}${PORTRAIT_MASK}</div>` : ""}
</div>
<div class="s-info">${info}</div>
${codesHtml}
${creditHtml}
</div>
</div>`;
  }

  /* Prüft, ob der Inhalt über das Blatt hinausläuft. */
  function overflows(root) {
    const inner = root.querySelector(".sheet-inner");
    return inner ? inner.scrollHeight > inner.clientHeight + 1 : false;
  }

  /* Lange Wörter im Titel (z. B. „Mondscheinsonate“ bei großer Schrift) nicht mitten
     im Wort umbrechen, sondern den Titel so weit verkleinern, bis jedes Wort passt. */
  function fitTitles(root) {
    root.querySelectorAll(".s-title").forEach((el) => {
      el.style.fontSize = "";
      el.style.overflowWrap = "normal";
      const start = parseFloat(getComputedStyle(el).fontSize);
      let size = start;
      while (el.scrollWidth > el.clientWidth + 1 && size > start * 0.6) {
        size *= 0.95;
        el.style.fontSize = size.toFixed(2) + "px";
      }
      if (el.scrollWidth > el.clientWidth + 1) el.style.overflowWrap = "break-word"; // letzter Ausweg
    });
  }

  /* Wartet, bis Schriften und Bilder geladen sind. */
  function whenReady(root) {
    const imgs = Array.from(root.querySelectorAll("img"));
    const loads = imgs.map((im) =>
      im.complete ? Promise.resolve() : new Promise((r) => { im.onload = im.onerror = r; })
    );
    const fonts = document.fonts ? document.fonts.ready : Promise.resolve();
    return Promise.all([fonts, ...loads]);
  }

  window.Sheet = { GENRES, ACCENTS, IMAGE_DEFAULTS, FONTS, DESIGN_DEFAULTS, SIZE_LIMITS, design, loadFonts,
    newSheet, render, overflows, whenReady, fitTitles, esc };
})();
