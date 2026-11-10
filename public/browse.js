"use strict";
const main = document.getElementById("main");
function el(tag, text, cls) { const e = document.createElement(tag); if (text != null) e.textContent = String(text); if (cls) e.className = cls; return e; }
let store = null, table = null, offset = 0; const LIMIT = 50;
const params = new URLSearchParams(location.search);

function layout() {
  main.replaceChildren();
  if (!Reveal.on()) return Reveal.offNotice(main);
  const tb = el("div", null, "toolbar");
  const ss = el("select"); ss.id = "store"; const ts = el("select"); ts.id = "table";
  const prev = el("button", "Previous", "btn"), nextb = el("button", "Next", "btn"); prev.type = nextb.type = "button";
  const info = el("span", "", "meta");
  [["Store ", ss], ["Table ", ts]].forEach(([l, s]) => { const lab = el("label", l); lab.appendChild(s); tb.appendChild(lab); });
  tb.appendChild(prev); tb.appendChild(nextb); tb.appendChild(info); main.appendChild(tb);
  const grid = el("div", null, "tbl card"); grid.id = "grid"; main.appendChild(grid);
  Reveal.get("stores").then(({ data }) => {
    data.forEach(s => { const o = el("option", `${s.id} (${s.sensitivity})`); o.value = s.id; ss.appendChild(o); });
    ss.value = params.get("store") || "graph"; pickStore();
  });
  ss.addEventListener("change", pickStore); ts.addEventListener("change", () => { table = ts.value; offset = 0; page(); });
  prev.addEventListener("click", () => { offset = Math.max(0, offset - LIMIT); page(); });
  nextb.addEventListener("click", () => { offset += LIMIT; page(); });
  function pickStore() {
    store = ss.value; ts.replaceChildren();
    Reveal.get("tables?store=" + store).then(({ data }) => {
      data.forEach(t => { const o = el("option", `${t.table} (${t.rows})`); o.value = t.table; ts.appendChild(o); });
      const big = data.slice().sort((a, b) => (b.rows || 0) - (a.rows || 0))[0];
      table = (params.get("table") && data.some(t => t.table === params.get("table"))) ? params.get("table") : (big ? big.table : null);
      ts.value = table; offset = 0; page();
    }).catch(e => { info.textContent = "This store could not be opened (" + e.message + ")."; grid.replaceChildren(); });
  }
  function page() {
    if (!table) { grid.replaceChildren(el("p", "No readable tables.", "meta")); return; }
    info.textContent = "Reading…";
    Reveal.get(`browse?store=${store}&table=${encodeURIComponent(table)}&offset=${offset}&limit=${LIMIT}`).then(({ data }) => {
      const t = el("table"), h = el("tr"); data.columns.forEach(c => h.appendChild(el("th", c))); t.appendChild(h);
      data.rows.forEach(r => { const tr = el("tr"); data.columns.forEach(c => tr.appendChild(el("td", r[c] == null ? "" : r[c]))); t.appendChild(tr); });
      grid.replaceChildren(t);
      info.textContent = `${data.path} · ${data.table} · rows ${data.total ? offset + 1 : 0}–${Math.min(offset + LIMIT, data.total)} of ${data.total}`;
      prev.disabled = offset === 0; nextb.disabled = offset + LIMIT >= data.total;
    }).catch(e => { info.textContent = "Could not read (" + e.message + ")."; });
  }
}
document.addEventListener("reveal-change", layout);
layout();
