"use strict";
// Connection map. Hand-written force layout, no libraries. Everything is text-rendered;
// nothing from the server is parsed as HTML. The server sends counts, never identifiers.
const NS = "http://www.w3.org/2000/svg";
const W = 1000, H = 680;
const GROUPS = ["Knowledge graph", "Communications", "Identity and context", "Relationships", "Photos",
                "Life events", "Topics", "Pipeline", "Apple-shipped"];
const GVAR = ["--g1", "--g3", "--g5", "--g4", "--g2", "--g6", "--g9", "--g8", "--g7"];
const KEYS = { entity: { v: "--k1", dash: "" }, contact: { v: "--k2", dash: "10 5" }, handle: { v: "--k3", dash: "2 4" },
               face: { v: "--k4", dash: "" }, device: { v: "--k5", dash: "12 3 2 3" } };
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const $ = id => document.getElementById(id);
function el(tag, text, cls) { const e = document.createElement(tag); if (text != null) e.textContent = String(text); if (cls) e.className = cls; return e; }
function sv(tag, attrs) { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; }

let data, nodes = [], edges = [], byId = {}, shownKeys = new Set(Object.keys(KEYS)), selected = null, alpha = 0, raf = 0;

function groupColor(g) { const i = GROUPS.indexOf(g); return css(GVAR[i < 0 ? 7 : i]); }
function size(n) { const m = Math.max(0, ...Object.values(n.spaces || {}).map(v => v || 0)); return 7 + Math.sqrt(m) * 0.75; }
function edgeWidth(e) { return e.overlap ? 1.5 + Math.log10(e.overlap + 1) * 2.2 : 1.2; }

function visibleEdges() {
  return edges.filter(e => e.measured && shownKeys.has(e.space) && !($("hideZero").checked && !e.overlap));
}
function visibleNodes() {
  const ve = visibleEdges(), linked = new Set();
  ve.forEach(e => { linked.add(e.a); linked.add(e.b); });
  return nodes.filter(n => !$("hideIsolated").checked || linked.has(n.id));
}

function seed() {
  const vn = visibleNodes();
  vn.forEach((n, i) => {
    if (n.id === "graph") { n.x = W / 2; n.y = H / 2; return; }
    const gi = Math.max(0, GROUPS.indexOf(n.group)), a = (gi / GROUPS.length) * Math.PI * 2 + (i % 5) * 0.12;
    const r = 220 + (i % 3) * 40;
    n.x = W / 2 + Math.cos(a) * r; n.y = H / 2 + Math.sin(a) * r * 0.7; n.vx = 0; n.vy = 0;
  });
}

function tick() {
  const vn = visibleNodes(), ve = visibleEdges(), k = alpha;
  for (let i = 0; i < vn.length; i++) for (let j = i + 1; j < vn.length; j++) {
    const a = vn[i], b = vn[j]; let dx = b.x - a.x, dy = b.y - a.y, d2 = dx * dx + dy * dy || 1;
    const min = size(a) + size(b) + 40, f = (16000 / d2) * k;
    const d = Math.sqrt(d2); dx /= d; dy /= d;
    let push = f; if (d < min) push += (min - d) * 0.5;
    a.vx -= dx * push; a.vy -= dy * push; b.vx += dx * push; b.vy += dy * push;
  }
  ve.forEach(e => {
    const a = byId[e.a], b = byId[e.b]; if (!a || !b) return;
    const dx = b.x - a.x, dy = b.y - a.y, d = Math.sqrt(dx * dx + dy * dy) || 1;
    const target = e.space === "entity" ? 270 : 190, s = (d - target) * 0.02 * k * (e.overlap ? 1 : 0.3);
    a.vx += dx / d * s; a.vy += dy / d * s; b.vx -= dx / d * s; b.vy -= dy / d * s;
  });
  vn.forEach(n => {
    if (n.fixed) { n.vx = n.vy = 0; return; }
    n.vx += (W / 2 - n.x) * 0.0015 * k; n.vy += (H / 2 - n.y) * 0.003 * k;
    if (n.id === "graph") { n.vx += (W / 2 - n.x) * 0.05; n.vy += (H / 2 - n.y) * 0.05; }
    n.vx *= 0.82; n.vy *= 0.82; n.x += n.vx; n.y += n.vy;
    const r = size(n) + 4; n.x = Math.max(r, Math.min(W - r, n.x)); n.y = Math.max(r + 14, Math.min(H - r, n.y));
  });
}

function draw() {
  const vn = visibleNodes(), ve = visibleEdges(), vis = new Set(vn.map(n => n.id));
  const E = $("edges"), N = $("nodes"), L = $("labels");
  E.replaceChildren(); N.replaceChildren(); L.replaceChildren();
  const nbr = new Set();
  if (selected && selected.kind === "node") { nbr.add(selected.id); ve.forEach(e => { if (e.a === selected.id) nbr.add(e.b); if (e.b === selected.id) nbr.add(e.a); }); }
  ve.forEach(e => {
    if (!vis.has(e.a) || !vis.has(e.b)) return;
    const a = byId[e.a], b = byId[e.b], key = KEYS[e.space];
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2, off = e.space === "entity" ? 0 : 28;
    const dx = b.x - a.x, dy = b.y - a.y, d = Math.sqrt(dx * dx + dy * dy) || 1;
    const cx = mx - dy / d * off, cy = my + dx / d * off;
    const p = sv("path", { d: `M${a.x},${a.y} Q${cx},${cy} ${b.x},${b.y}`, stroke: css(key.v), "stroke-width": edgeWidth(e),
                           "stroke-dasharray": e.overlap ? key.dash : "2 5", tabindex: 0,
                           class: "edge" + (e.overlap ? "" : " zero") + (selected && selected.kind === "edge" && selected.e === e ? " sel" : "") +
                                  (selected && selected.kind === "node" && !(nbr.has(e.a) && nbr.has(e.b) && (e.a === selected.id || e.b === selected.id)) ? " dim" : "") });
    p.appendChild(sv("title", {})).textContent = `${e.a} and ${e.b}: ${e.overlap} shared ${e.space} ids`;
    p.addEventListener("click", ev => { ev.stopPropagation(); select({ kind: "edge", e }); });
    p.addEventListener("keydown", ev => { if (ev.key === "Enter") select({ kind: "edge", e }); });
    E.appendChild(p);
  });
  vn.forEach(n => {
    const g = sv("g", { class: "node" + (n.id === "graph" ? " hub" : "") + (selected && selected.kind === "node" && selected.id === n.id ? " sel" : "") +
                         (selected && selected.kind === "node" && !nbr.has(n.id) ? " dim" : ""), transform: `translate(${n.x},${n.y})`, tabindex: 0 });
    const c = sv("circle", { r: size(n), stroke: groupColor(n.group) });
    g.appendChild(c); g.appendChild(sv("title", {})).textContent = `${n.id} (${n.group})`;
    g.addEventListener("pointerdown", ev => startDrag(ev, n));
    g.addEventListener("keydown", ev => { if (ev.key === "Enter") select({ kind: "node", id: n.id }); });
    N.appendChild(g);
    const t = sv("text", { x: n.x, y: n.y - size(n) - 5, "text-anchor": "middle",
                           class: "lbl" + (selected && selected.kind === "node" && !nbr.has(n.id) ? " dim" : "") });
    t.textContent = n.id; L.appendChild(t);
  });
}

function loop() { if (alpha > 0.005) { tick(); alpha *= 0.985; draw(); raf = requestAnimationFrame(loop); } else { raf = 0; draw(); } }
function kick(a) { alpha = Math.max(alpha, a); if (!raf) raf = requestAnimationFrame(loop); }

let drag = null;
function svgPoint(ev) { const r = $("map").getBoundingClientRect(); return { x: (ev.clientX - r.left) * W / r.width, y: (ev.clientY - r.top) * H / r.height }; }
function startDrag(ev, n) { ev.preventDefault(); ev.stopPropagation(); drag = { n, moved: false }; n.fixed = true; $("map").setPointerCapture(ev.pointerId); }
$("map").addEventListener("pointermove", ev => { if (!drag) return; const p = svgPoint(ev); drag.n.x = p.x; drag.n.y = p.y; drag.moved = true; kick(0.15); draw(); });
$("map").addEventListener("pointerup", () => { if (!drag) return; if (!drag.moved) select({ kind: "node", id: drag.n.id }); drag.n.fixed = drag.moved; drag = null; });
$("map").addEventListener("click", () => { if (selected) { selected = null; panelDefault(); draw(); } });

function dl(pairs) { const d = el("dl"); pairs.forEach(([k, v]) => { d.appendChild(el("dt", k)); d.appendChild(el("dd", v)); }); return d; }
function panelDefault() { const P = $("panel"); P.replaceChildren(el("h2", "Details"), el("p", "Click a store or a line. Drag stores to rearrange.")); }
function pct(a, b) { return b ? Math.round(100 * a / b) + "%" : "n/a"; }

function select(s) {
  selected = s; const P = $("panel"); P.replaceChildren();
  if (s.kind === "node") {
    const n = byId[s.id]; P.appendChild(el("h2", n.id));
    P.appendChild(dl([["Store", n.path], ["Group", n.group], ["Sensitivity", n.sensitivity], ["Holds", n.holds]]));
    const sp = Object.entries(n.spaces || {});
    P.appendChild(el("h3", "Identifiers it holds"));
    if (!sp.length) P.appendChild(el("p", "None of the five join keys. This store stands alone."));
    else { const ul = el("ul"); sp.forEach(([k, v]) => ul.appendChild(el("li", `${k}: ${v == null ? "not measured" : v}`))); P.appendChild(ul); }
    const mine = visibleEdges().filter(e => e.a === n.id || e.b === n.id).sort((x, y) => (y.overlap || 0) - (x.overlap || 0));
    P.appendChild(el("h3", "Joins"));
    if (!mine.length) P.appendChild(el("p", "No joins shown with the current filters."));
    else { const ul = el("ul"); mine.forEach(e => { const o = e.a === n.id ? e.b : e.a; ul.appendChild(el("li", `${o} by ${e.space}: ${e.overlap} shared`)); }); P.appendChild(ul); }
  } else {
    const e = s.e; P.appendChild(el("h2", `${e.a} and ${e.b}`));
    const sp = data.spaces.find(x => x.id === e.space) || { label: e.space, about: "" };
    P.appendChild(dl([["Join key", sp.label], ["What it is", sp.about], ["Shared identifiers", String(e.overlap)],
      [`Share of ${e.a}`, `${pct(e.overlap, e.a_size)} of ${e.a_size}`], [`Share of ${e.b}`, `${pct(e.overlap, e.b_size)} of ${e.b_size}`]]));
    if (e.space === "contact" && e.overlap < Math.min(e.a_size, e.b_size) * 0.2)
      P.appendChild(el("p", "Low overlap on contact ids usually means the two stores come from different devices: Contacts gives each device its own UUIDs. Check the handle join for the real bridge."));
  }
  draw();
}

function legend() {
  const Lg = $("legend"); Lg.replaceChildren();
  data.spaces.forEach(s => { const sp = el("span"); const sw = el("span", null, "sw k-" + s.id); sw.style.borderTopColor = css(KEYS[s.id].v); sp.appendChild(sw); sp.appendChild(document.createTextNode(s.label)); Lg.appendChild(sp); });
  const z = el("span"); const sw = el("span", null, "sw k-zero"); sw.style.borderTopColor = css("--muted"); z.appendChild(sw); z.appendChild(document.createTextNode("Zero overlap (faint dots)")); Lg.appendChild(z);
  [...new Set(nodes.map(n => n.group))].forEach(g => { const sp = el("span"); const d = el("span", null, "dot"); d.style.borderColor = groupColor(g); sp.appendChild(d); sp.appendChild(document.createTextNode(g)); Lg.appendChild(sp); });
}

function table() {
  const T = $("edgeTable"); T.replaceChildren();
  const hr = el("tr"); ["Join key", "Store", "Store", "Shared ids", "Share of each"].forEach(h => hr.appendChild(el("th", h))); T.appendChild(hr);
  edges.slice().sort((a, b) => a.space.localeCompare(b.space) || (b.overlap || 0) - (a.overlap || 0)).forEach(e => {
    const tr = el("tr"); [e.space, e.a, e.b, e.measured ? e.overlap : "not measured",
      e.measured ? `${pct(e.overlap, e.a_size)} / ${pct(e.overlap, e.b_size)}` : ""].forEach(v => tr.appendChild(el("td", v))); T.appendChild(tr);
  });
}

function controls() {
  const S = $("spaces"); S.replaceChildren();
  data.spaces.forEach(s => {
    const lab = el("label"); const cb = el("input"); cb.type = "checkbox"; cb.checked = true;
    cb.addEventListener("change", () => { cb.checked ? shownKeys.add(s.id) : shownKeys.delete(s.id); seed(); kick(1); });
    lab.appendChild(cb); lab.appendChild(document.createTextNode(" " + s.label)); S.appendChild(lab);
  });
  ["hideIsolated", "hideZero"].forEach(id => $(id).addEventListener("change", () => { seed(); kick(1); }));
  $("relayout").addEventListener("click", () => { nodes.forEach(n => n.fixed = false); seed(); kick(1); });
}

fetch("/api/linkage", { credentials: "same-origin" }).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }).then(d => {
  data = d; nodes = d.nodes.map(n => Object.assign({ x: 0, y: 0, vx: 0, vy: 0 }, n)); edges = d.edges;
  byId = Object.fromEntries(nodes.map(n => [n.id, n]));
  const b = d.bridge && d.bridge.phone_history_to_graph_people;
  $("bridge").textContent = b == null
    ? "The phone-to-Mac bridge could not be measured on this copy."
    : `Phone history on this Mac reaches ${b} people in its knowledge graph through phone numbers and email addresses, even where contact ids don't match.`;
  if (d.gaps && d.gaps.length) $("bridge").textContent += ` ${d.gaps.length} store(s) could not be read; their joins are marked not measured.`;
  controls(); legend(); table(); panelDefault(); seed(); kick(1);
}).catch(e => { $("bridge").textContent = "Could not load the map (" + e.message + "). Check the terminal."; });
