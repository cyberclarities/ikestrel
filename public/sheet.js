"use strict";
// Store sheet. Everything is rendered with textContent; nothing is parsed as HTML.
const $ = id => document.getElementById(id);
function el(tag, text, cls) { const e = document.createElement(tag); if (text != null) e.textContent = String(text); if (cls) e.className = cls; return e; }
const NUM = new Set(["ids_entity", "ids_contact", "ids_handle", "ids_face", "ids_device", "joins"]);
const TEXT = new Set(["holds", "alone", "worst"]);
const SENS = { High: 0, Medium: 1, Low: 2 };
let cols = [], rows = [], sortKey = null, sortDir = 1;

function cmp(a, b, k) {
  if (k === "sensitivity") return (SENS[a[k]] ?? 9) - (SENS[b[k]] ?? 9);
  const x = a[k], y = b[k];
  if (NUM.has(k)) return (typeof x === "number" ? x : -1) - (typeof y === "number" ? y : -1);
  if (k === "headline") { const nx = parseFloat(String(x).split(": ").pop()) || 0, ny = parseFloat(String(y).split(": ").pop()) || 0; return nx - ny; }
  return String(x ?? "").localeCompare(String(y ?? ""));
}

function visible() {
  const q = $("q").value.trim().toLowerCase(), g = $("group").value, s = $("sens").value;
  let r = rows.filter(x => (!g || x.group === g) && (!s || x.sensitivity === s) &&
    (!q || cols.some(([k]) => String(x[k] ?? "").toLowerCase().includes(q))));
  if (sortKey) r = r.slice().sort((a, b) => cmp(a, b, sortKey) * sortDir);
  return r;
}

function head() {
  const tr = el("tr");
  cols.forEach(([k, label]) => {
    const th = el("th", label, k === "store" ? "store" : (TEXT.has(k) ? "text" : (k === "example" ? "ex" : "")));
    th.scope = "col"; th.tabIndex = 0;
    if (k === sortKey) th.setAttribute("aria-sort", sortDir > 0 ? "ascending" : "descending");
    const go = () => { if (sortKey === k) sortDir = -sortDir; else { sortKey = k; sortDir = NUM.has(k) || k === "headline" ? -1 : 1; } render(); };
    th.addEventListener("click", go); th.addEventListener("keydown", e => { if (e.key === "Enter") go(); });
    tr.appendChild(th);
  });
  $("sheet").tHead.replaceChildren(tr);
}

function render() {
  head();
  const tb = $("sheet").tBodies[0]; tb.replaceChildren();
  const vr = visible();
  vr.forEach(r => {
    const tr = el("tr");
    cols.forEach(([k]) => {
      const v = r[k];
      const td = el("td", null, k === "store" ? "store" : NUM.has(k) ? "num" : TEXT.has(k) ? "text" : k === "example" ? "ex" : "");
      if (k === "sensitivity") td.appendChild(el("span", v, "sev " + v));
      else if (k === "example") String(v || "").split("\n").forEach(line => td.appendChild(el("div", line)));
      else td.textContent = v === "" || v == null ? "" : String(v);
      if (k === "store") td.title = r.path;
      tr.appendChild(td);
    });
    tb.appendChild(tr);
  });
  $("count").textContent = `Showing ${vr.length} of ${rows.length} stores`;
}

["q", "group", "sens"].forEach(id => $(id).addEventListener("input", render));
$("text").addEventListener("change", () => $("sheet").classList.toggle("hide-text", !$("text").checked));
$("ex").addEventListener("change", () => $("sheet").classList.toggle("hide-ex", !$("ex").checked));

fetch("/api/sheet", { credentials: "same-origin" }).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }).then(d => {
  cols = d.columns; rows = d.rows;
  [...new Set(rows.map(r => r.group))].sort().forEach(g => { const o = el("option", g); o.value = g; $("group").appendChild(o); });
  $("meta").textContent = (d.mode === "copy" ? "Reading a copy" : "Reading this Mac live") + " · " + d.generated +
    (d.gaps.length ? ` · ${d.gaps.length} store(s) could not be read; their cells say not measured.` : "") +
    " · Click a column header to sort.";
  render();
}).catch(e => { $("meta").textContent = "Could not load the sheet (" + e.message + "). Check the terminal."; });
