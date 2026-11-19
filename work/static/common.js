// Shared helpers
window.WR = {
  api(method, url, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    return fetch(url, opts).then(async r => {
      if (r.status === 204) return null;
      if (!r.ok) throw new Error(`${r.status}`);
      const ct = r.headers.get("content-type") || "";
      return ct.includes("application/json") ? r.json() : r.blob();
    });
  },
  loadLayoutPref() {
    return localStorage.getItem("layout") || "bottom";  // bottom|right
  },
  saveLayoutPref(v) { localStorage.setItem("layout", v); },
  loadKeypadPref() { return localStorage.getItem("keypad") === "on"; },
  saveKeypadPref(on) { localStorage.setItem("keypad", on ? "on" : "off"); },
  loadThemePref() { return localStorage.getItem("theme") || "light"; },   // light|dark
  saveThemePref(v) { localStorage.setItem("theme", v); },
  loadFontPref() { return localStorage.getItem("fontsize") || "normal"; }, // normal|large|xlarge
  saveFontPref(v) { localStorage.setItem("fontsize", v); },
  loadBtnAreaPx() { const v = parseInt(localStorage.getItem("btnAreaPx"), 10); return Number.isFinite(v) ? v : null; },
  saveBtnAreaPx(px) { localStorage.setItem("btnAreaPx", String(px)); },
  loadAttAreaPx() { const v = parseInt(localStorage.getItem("attAreaPx"), 10); return Number.isFinite(v) ? v : null; },
  saveAttAreaPx(px) { localStorage.setItem("attAreaPx", String(px)); },
  formatJpDate(iso) {
    const [y, m, d] = iso.split("-");
    return `${+y}年${+m}月${+d}日`;
  },
  nowHHMM() {
    const d = new Date();
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  },
  todayISO() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
  },
};
