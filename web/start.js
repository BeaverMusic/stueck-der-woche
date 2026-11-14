/* Wird als Erstes geladen: Erscheinungsbild (hell/dunkel) und Zugangsschlüssel.

   Zugang: Die App beantwortet nur Anfragen ihres eigenen Fensters. Dafür gibt sie dem
   Fenster beim Öffnen einen Schlüssel mit (hinter dem # in der Adresse). Er wird hier
   gemerkt – nur für dieses Fenster – und sofort wieder aus der Adresse entfernt. */
(function () {
  "use strict";

  // ---------------------------------------------------------------- Erscheinungsbild
  const dark = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  let wish = "";
  try { wish = localStorage.getItem("sdw-theme") || ""; } catch (_) { /* egal */ }

  // value: "light", "dark" oder "" (= wie das System); ohne Angabe wird nur neu angewendet
  function theme(value, remember) {
    if (value !== undefined) {
      wish = value === "light" || value === "dark" ? value : "";
      if (remember) {
        try { localStorage.setItem("sdw-theme", wish); } catch (_) { /* egal */ }
      }
    }
    document.documentElement.dataset.theme = wish || (dark && dark.matches ? "dark" : "light");
  }
  if (dark) {
    if (dark.addEventListener) dark.addEventListener("change", () => theme());
    else if (dark.addListener) dark.addListener(() => theme());
  }
  theme();

  // ---------------------------------------------------------------- Zugang
  const KEY_RE = /^[A-Za-z0-9_-]{30,100}$/;
  let key = "";
  let ticket = "";
  try { key = sessionStorage.getItem("sdw-key") || ""; } catch (_) { /* egal */ }
  if (!KEY_RE.test(key)) key = "";

  function setKey(value) {
    key = KEY_RE.test(value || "") ? value : "";
    try {
      if (key) sessionStorage.setItem("sdw-key", key);
      else sessionStorage.removeItem("sdw-key");
    } catch (_) { /* egal */ }
  }

  const hash = new URLSearchParams(location.hash.slice(1));
  if (hash.has("k") || hash.has("t")) {
    if (KEY_RE.test(hash.get("k") || "")) setKey(hash.get("k"));
    if (/^[A-Za-z0-9_-]{20,80}$/.test(hash.get("t") || "")) ticket = hash.get("t");
    try { history.replaceState(null, "", location.pathname + location.search); } catch (_) { location.hash = ""; }
  }

  window.Start = {
    theme,
    key: () => key,
    setKey,
    ticket: () => ticket,
    // Kopfzeilen für Anfragen an die App
    headers(extra) {
      const h = Object.assign({}, extra);
      if (key) h["X-App-Key"] = key;
      return h;
    },
  };
})();
