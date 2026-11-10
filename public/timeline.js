"use strict";
const main = document.getElementById("main");
function el(tag, text, cls) { const e = document.createElement(tag); if (text != null) e.textContent = String(text); if (cls) e.className = cls; return e; }
const SOURCES = [["siri", "Siri history"], ["wifi", "Wi-Fi"], ["calendar", "Calendar"], ["mechanisms", "Two-way contact"], ["faces", "Photos"]];
const COLS = ["when", "source", "what", "direction", "detail", "app", "duration_s", "device"];
let next = null, tbody = null, status = null;

function layout() {
  main.replaceChildren();
  if (!Reveal.on()) return Reveal.offNotice(main);
  const tb = el("div", null, "toolbar");
  SOURCES.forEach(([k, l]) => { const lab = el("label"); const cb = el("input"); cb.type = "checkbox"; cb.checked = true; cb.value = k; cb.className = "src"; cb.addEventListener("change", reload); lab.appendChild(cb); lab.appendChild(document.createTextNode(" " + l)); tb.appendChild(lab); });
  status = el("span", "", "meta"); tb.appendChild(status); main.appendChild(tb);
  const wrap = el("div", null, "tbl card"), t = el("table"), h = el("tr"); COLS.forEach(c => h.appendChild(el("th", c))); t.appendChild(h);
  tbody = el("tbody"); t.appendChild(tbody); wrap.appendChild(t); main.appendChild(wrap);
  const more = el("button", "Load older", "btn"); more.type = "button"; more.id = "more"; more.addEventListener("click", () => load(false)); main.appendChild(more);
  reload();
}
function sources() { return [...document.querySelectorAll("input.src:checked")].map(x => x.value).join(","); }
function reload() { next = null; tbody.replaceChildren(); load(true); }
function load(first) {
  const s = sources(); if (!s) { status.textContent = "Pick at least one source."; return; }
  status.textContent = "Reading…";
  Reveal.get("timeline?limit=200&sources=" + s + (next && !first ? "&before=" + next : "")).then(({ data }) => {
    data.events.forEach(ev => { const tr = el("tr"); COLS.forEach(c => tr.appendChild(el("td", ev[c] == null ? "" : ev[c]))); tbody.appendChild(tr); });
    next = data.next_before; document.getElementById("more").hidden = !next;
    status.textContent = `${tbody.children.length} events shown` + (next ? "" : " (all loaded)");
  }).catch(e => { status.textContent = "Could not load (" + e.message + ")."; });
}
document.addEventListener("reveal-change", layout);
layout();
