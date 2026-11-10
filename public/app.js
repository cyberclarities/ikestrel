"use strict";
// Everything rendered with textContent. No store value is ever parsed as HTML.
function el(tag, text, cls) { const e = document.createElement(tag); if (text != null) e.textContent = String(text); if (cls) e.className = cls; return e; }
function row(cells, head) { const tr = el("tr"); cells.forEach(c => tr.appendChild(el(head ? "th" : "td", c))); return tr; }
function val(m) {
  if (!m.measured) return "not measured";
  if (m.groups) return Object.entries(m.groups).sort((a, b) => (b[1] || 0) - (a[1] || 0)).map(([k, v]) => k + ": " + (v == null ? "not measured" : v)).join("  ·  ");
  return m.value;
}
function render(d) {
  document.getElementById("meta").textContent = "iKestrel " + d.version + " · " + (d.mode === "copy" ? "reading a copy at " : "reading this Mac live at ") + d.root + " · " + d.generated;
  const F = document.getElementById("findings"); F.replaceChildren();
  if (!d.findings.length) F.appendChild(el("p", "No findings fired. Read the open questions before treating that as clear."));
  d.findings.forEach(f => {
    const s = el("article", null, "finding");
    const h = el("h3"); h.appendChild(el("span", f.severity, "sev")); h.appendChild(document.createTextNode(" " + f.id + " " + f.title));
    s.appendChild(h); s.appendChild(el("p", f.impact)); s.appendChild(el("p", "Action: " + f.action, "action"));
    F.appendChild(s);
  });
  const O = document.getElementById("open"); O.replaceChildren(); d.open.forEach(q => O.appendChild(el("li", q)));
  const C = document.getElementById("coverage"); C.replaceChildren();
  C.appendChild(row(["Group", "Store", "Sensitivity", "Status", "Measured", "Reason"], true));
  d.coverage.forEach(c => C.appendChild(row([c.group, c.path, c.sensitivity, c.status, c.measured + " of " + c.measurements, c.reasons.join("; ")])));
  const M = document.getElementById("measurements"); M.replaceChildren();
  M.appendChild(row(["Id", "What", "Value"], true));
  d.measurements.forEach(m => M.appendChild(row([m.id, m.title, val(m)])));
}
function load() {
  const w = document.getElementById("watch").value;
  const qs = w ? "?watch=" + encodeURIComponent(w) : "";
  document.getElementById("brief").href = "/report/brief" + qs;
  document.getElementById("tech").href = "/report/technical" + qs;
  fetch("/api/summary" + qs, { credentials: "same-origin" }).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(render).catch(e => { document.getElementById("meta").textContent = "Could not read the stores (" + e.message + "). Check the terminal."; });
}
document.getElementById("watch").addEventListener("change", load);
load();
