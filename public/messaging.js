"use strict";
// Messaging apps. Every value goes in through textContent.
const $ = id => document.getElementById(id);
const el = (tag, text, cls) => { const e = document.createElement(tag); if (text != null) e.textContent = String(text); if (cls) e.className = cls; return e; };
const fmt = n => (n == null ? "—" : Number(n).toLocaleString());
let data = null;

function load() {
  $("headline").textContent = "Reading the stores…";
  const req = (window.Reveal && Reveal.on())
    ? Reveal.get("messaging").then(r => Object.assign(r.data, { gaps: r.gaps }))
    : fetch("/api/messaging", { credentials: "same-origin" }).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
  req.then(d => { data = d; render(); }).catch(e => { $("headline").textContent = "Could not read the stores (" + e.message + ")."; });
}

function stat(v, label) { const s = el("div", null, "stat"); s.appendChild(el("b", fmt(v))); s.appendChild(el("span", label)); return s; }

function table(head, rows) {
  const t = el("table", null, "mini"), tr = el("tr"); head.forEach(h => tr.appendChild(el("th", h))); t.appendChild(tr);
  rows.forEach(r => { const row = el("tr"); r.forEach((v, i) => { const td = el("td", null, i && typeof v === "number" ? "n" : "");
    if (v && typeof v === "object" && v.href) { const a = el("a", v.text); a.href = v.href; td.appendChild(a); } else td.textContent = v == null ? "" : String(v);
    row.appendChild(td); }); t.appendChild(row); });
  return t;
}

function card(a) {
  const c = el("article", null, "appcard" + (a.seen ? "" : " quiet"));
  const h = el("h3", a.product);
  const chip = el("span", a.status, "chip " + (a.status === "logged" ? "logged" : a.status.startsWith("present") ? "present" : "none"));
  h.appendChild(chip); c.appendChild(h);
  if (a.seen) {
    const s = el("div", null, "stats");
    [[a.interactions, "interactions"], [a.sent, "outgoing"], [a.received, "incoming"], [a.group_chats, "group chats"],
     [a.people, "people or handles"], [a.named_on_this_mac, "named on this Mac"], [a.pairings, "Siri pairings"],
     [a.other_devices, "other devices"]].forEach(([v, l]) => s.appendChild(stat(v, l)));
    c.appendChild(s);
  }
  const ul = el("ul"); (a.story || []).forEach(t => ul.appendChild(el("li", t))); c.appendChild(ul);
  if (a.note) c.appendChild(el("p", a.note, "note"));
  if (data.real && a.top_people && a.top_people.length) {
    c.appendChild(el("h4", "People, most first"));
    c.appendChild(table(["Who", "Out", "In", "Other", "Last"], a.top_people.map(p =>
      [p.profile ? { text: p.name, href: "/person?id=" + encodeURIComponent(p.profile) } : p.name, p.sent, p.received, p.other, p.last])));
  }
  if (data.real && a.group_names && a.group_names.length) {
    c.appendChild(el("h4", "Group chats Siri keeps by name"));
    c.appendChild(table(["Group", "Interactions", "Last"], a.group_names.map(g => [g.name, g.count, g.last])));
  }
  if (!data.real && a.interactions) c.appendChild(el("p", "Turn on “Show real values” to see the people and group chat names.", "note"));
  return c;
}

function render() {
  $("headline").textContent = data.headline;
  $("mode").textContent = data.real ? "Real names are on, in this browser only. They never go into reports or the CSV."
                                    : "Counts only. Turn on “Show real values” to see who and which groups.";
  const box = $("apps"); box.replaceChildren();
  const showQuiet = $("quiet").checked;
  data.kinds.forEach(kind => {
    const apps = data.apps.filter(a => a.kind === kind && (showQuiet || a.seen));
    if (!apps.length) return;
    box.appendChild(el("h2", kind, "kind"));
    const g = el("div", null, "cards"); apps.forEach(a => g.appendChild(card(a))); box.appendChild(g);
  });
  if (data.gaps && data.gaps.length) box.appendChild(el("p", "Not read: " + data.gaps.map(x => x.store + " (" + x.reason + ")").join("; "), "meta"));
}

$("quiet").addEventListener("change", () => data && render());
document.addEventListener("reveal-change", load);
load();
