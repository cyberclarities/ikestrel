"use strict";
const main = document.getElementById("main");
function el(tag, text, cls) { const e = document.createElement(tag); if (text != null) e.textContent = String(text); if (cls) e.className = cls; return e; }
function card(title) { const c = el("section", null, "card"); c.appendChild(el("h2", title)); return c; }
function kv(pairs) { const d = el("dl", null, "kv"); pairs.forEach(([k, v]) => { d.appendChild(el("dt", k)); d.appendChild(el("dd", v == null ? "" : (typeof v === "object" ? JSON.stringify(v) : v))); }); return d; }
function table(cols, rows) {
  const w = el("div", null, "tbl"), t = el("table"), h = el("tr");
  cols.forEach(c => h.appendChild(el("th", c))); t.appendChild(h);
  rows.forEach(r => { const tr = el("tr"); cols.forEach(c => tr.appendChild(el("td", r[c] == null ? "" : (typeof r[c] === "object" ? JSON.stringify(r[c]) : r[c])))); t.appendChild(tr); });
  w.appendChild(t); return w;
}
let all = [], selId = new URLSearchParams(location.search).get("id");

function layout() {
  main.replaceChildren();
  if (!Reveal.on()) return Reveal.offNotice(main);
  const g = el("div", null, "grid2");
  const left = el("div"); const right = el("div"); right.id = "profile";
  const s = el("input"); s.type = "search"; s.placeholder = "name, phone or email"; s.id = "q";
  const count = el("p", "", "meta"); const list = el("div", null, "list card");
  left.appendChild(s); left.appendChild(count); left.appendChild(list);
  g.appendChild(left); g.appendChild(right); main.appendChild(g);
  const draw = () => {
    const q = s.value.trim().toLowerCase();
    const vis = all.filter(p => !q || p.name.toLowerCase().includes(q) || p.handles.some(h => h.toLowerCase().includes(q)));
    count.textContent = `${vis.length} of ${all.length} people`;
    list.replaceChildren();
    vis.slice(0, 600).forEach(p => {
      const b = el("button", null, p.id === selId ? "sel" : ""); b.type = "button";
      b.appendChild(document.createTextNode(p.name)); b.appendChild(el("small", p.n_handles ? `${p.n_handles} handle(s)` : "no handles"));
      b.addEventListener("click", () => { selId = p.id; history.replaceState(null, "", "?id=" + encodeURIComponent(p.id)); draw(); profile(p.id); });
      list.appendChild(b);
    });
  };
  s.addEventListener("input", draw);
  Reveal.get("people").then(d => { all = d.data.people; draw(); if (selId) profile(selId); else right.appendChild(el("p", "Pick someone on the left.", "offnote")); })
    .catch(e => { count.textContent = "Could not load people (" + e.message + ")."; });
}

function profile(id) {
  const R = document.getElementById("profile"); R.replaceChildren(el("p", "Reading…", "meta"));
  Reveal.get("person?id=" + encodeURIComponent(id)).then(({ data: P, gaps }) => {
    R.replaceChildren();
    const head = card(P.name || "(no name)"); if (P.is_owner) head.querySelector("h2").appendChild(el("span", "this is the Mac's owner", "badge"));
    head.appendChild(kv([["Entity id", P.id], ["Phones and emails", (P.handles || []).join(", ") || "none"]])); R.appendChild(head);

    const c = P.communications;
    const cc = card("Communication history (Siri, synced)");
    if (!c || !c.total) cc.appendChild(el("p", "No Siri interactions joined to this person." + (c ? ` Matched entities: ${c.matched_entities.handle} by handle, ${c.matched_entities["contact id"]} by contact id.` : ""), "meta"));
    else {
      cc.appendChild(kv([["Interactions", c.total], [c.is_owner ? "Sent by you" : "Sent to them", c.sent], [c.is_owner ? "Received by you" : "Received from them", c.received],
        ["Group messages they were in", c.group], ["First", c.first], ["Last", c.last],
        ["Joined by", `${c.matched_entities.handle} handle(s), ${c.matched_entities["contact id"]} contact id(s)`],
        ["By app", Object.entries(c.by_app).sort((a, b) => b[1] - a[1]).map(([a, n]) => `${a}: ${n}`).join(", ")]]));
      cc.appendChild(el("h3", `Most recent ${c.items.length}`));
      cc.appendChild(table(["when", "direction", "app", "intent", "duration_s", "device"], c.items));
    }
    R.appendChild(cc);

    if (P.relationship_scores && Object.keys(P.relationship_scores).length) {
      const rc = card("How the Mac thinks they're related to you");
      Object.entries(P.relationship_scores).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => {
        const row = el("div", null, "score"); row.appendChild(el("span", k)); const bar = el("div", null, "bar"); bar.style.width = Math.round(v * 100) + "%"; row.appendChild(bar); row.appendChild(el("span", v)); rc.appendChild(row);
      });
      R.appendChild(rc);
    }
    if (P.importance) R.appendChild(Object.assign(card("Importance flags"), {}).appendChild(kv(Object.entries(P.importance))).parentNode);
    if (P.relevance) { const r = card("Relevance ranking"); r.appendChild(kv([["Score", P.relevance.score]])); const pre = el("pre", JSON.stringify(P.relevance.explanation, null, 2), "json"); r.appendChild(pre); R.appendChild(r); }
    if (P.graph) {
      const gc = card("Knowledge graph");
      gc.appendChild(table(["predicate", "value"], P.graph.facts));
      P.graph.relations.forEach(r => {
        gc.appendChild(el("h3", r.predicate));
        gc.appendChild(kv(Object.entries(r.fields).concat(r.place ? Object.entries(r.place).map(([k, v]) => ["place: " + k, v]) : [])));
      });
      R.appendChild(gc);
    }
    if (P.features && P.features.length) { const f = card("Features behind the scores"); f.appendChild(table(["view", "feature", "value", "confidence"], P.features)); R.appendChild(f); }
    if (P.siri_summary) { const s = card("Siri's summary of this person"); s.appendChild(el("pre", JSON.stringify(P.siri_summary, null, 2), "json")); R.appendChild(s); }
    if (P.spoken_aliases && P.spoken_aliases.length) { const a = card("Spoken names Siri listens for"); a.appendChild(table(["alias", "signal"], P.spoken_aliases)); R.appendChild(a); }
    if (P.observed_ages && P.observed_ages.length) { const a = card("Ages read from faces"); a.appendChild(table(["date", "age"], P.observed_ages)); R.appendChild(a); }
    if (gaps && gaps.length) R.appendChild(el("p", "Not read: " + gaps.map(g => g.store + " (" + g.reason + ")").join("; "), "meta"));
  }).catch(e => { R.replaceChildren(el("p", "Could not load this person (" + e.message + ").", "meta")); });
}
document.addEventListener("reveal-change", layout);
layout();
