/* Druckansicht: ein A5-Blatt oder zwei A5-Blätter auf A4 quer (für PDF-Export und Druckdialog). */
(async function () {
  "use strict";
  const params = new URLSearchParams(location.search);
  const mode = params.get("mode") === "a4" ? "a4" : "a5";
  const ids = (params.get("ids") || "").split(",").filter(Boolean).slice(0, 2);
  const out = document.getElementById("out");
  out.classList.add(mode);
  const page = document.createElement("style");
  page.textContent = `@page { size: ${mode === "a4" ? "297mm 210mm" : "148mm 210mm"}; margin: 0; }`;
  document.head.appendChild(page);
  try {
    const settings = await (await fetch("/api/settings")).json();
    const sheets = [];
    for (const id of ids) {
      const r = await fetch("/api/sheets/" + encodeURIComponent(id));
      if (!r.ok) throw new Error("Blatt nicht gefunden: " + id);
      sheets.push(await r.json());
    }
    const fonts = sheets.map((s) => Sheet.loadFonts(Sheet.design(settings, s)));
    out.innerHTML = sheets
      .map((s) => Sheet.render(s, { headerRight: settings.header_right, design: settings }))
      .join(mode === "a4" ? '<div class="cut"></div>' : "");
    await Promise.all(fonts);
    await Sheet.whenReady(out);
    Sheet.fitTitles(out);
  } catch (err) {
    window.__printError = String((err && err.message) || err);
    out.textContent = "Fehler: " + window.__printError;
  }
  window.__printReady = true;
})();
