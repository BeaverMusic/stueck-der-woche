/* Vorschau eines Blatts im Editor (läuft im eingebetteten Rahmen von index.html). */
(function () {
  "use strict";
  const stage = document.getElementById("stage");

  // Das ganze Blatt muss sichtbar sein – Breite UND Höhe berücksichtigen.
  function fit() {
    const w = stage.offsetWidth || 559;
    const h = stage.offsetHeight || 794;
    const scale = Math.min(window.innerWidth / w, window.innerHeight / h);
    stage.style.transform = `scale(${scale})`;
    stage.style.marginLeft = Math.max(0, (window.innerWidth - w * scale) / 2) + "px";
  }

  let lastHtml = "";
  function draw(msg) {
    const d = Sheet.design(msg.settings, msg.sheet);
    const fonts = Sheet.loadFonts(d);
    const html = Sheet.render(msg.sheet, { preview: true, headerRight: msg.headerRight, design: msg.settings });
    if (html !== lastHtml) { // nur neu zeichnen, wenn sich etwas geändert hat
      stage.innerHTML = html;
      lastHtml = html;
    }
    Sheet.fitTitles(stage);
    fit();
    const report = () =>
      parent.postMessage({ type: "overflow", value: Sheet.overflows(stage), tag: msg.tag }, location.origin);
    report();
    Promise.all([fonts, Sheet.whenReady(stage)]).then(() => { Sheet.fitTitles(stage); report(); });
  }

  window.addEventListener("message", (e) => {
    // Nur Nachrichten der eigenen App annehmen
    if (e.source !== parent || e.origin !== location.origin || !e.data || e.data.type !== "render") return;
    draw(e.data);
  });
  window.addEventListener("resize", fit);
  parent.postMessage({ type: "preview-ready" }, location.origin);
})();
