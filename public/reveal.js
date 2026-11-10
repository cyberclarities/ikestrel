"use strict";
// Shared real-values toggle. Off by default. Kept in this tab's session storage, which is
// tied to this server's port, so it resets every time the server starts.
(function () {
  const KEY = "kestrel.reveal";
  let on = false;
  try { on = sessionStorage.getItem(KEY) === "1"; } catch (e) { on = false; }
  function el(tag, text, cls) { const e = document.createElement(tag); if (text != null) e.textContent = String(text); if (cls) e.className = cls; return e; }
  const bar = el("div", null, "revealbar");
  const lab = el("label"); const cb = el("input"); cb.type = "checkbox"; cb.id = "revealToggle"; cb.checked = on;
  lab.appendChild(cb); lab.appendChild(document.createTextNode(" Show real values"));
  const warn = el("span", "Real values are on. Anyone who can see this screen can see them. They never go into reports or the CSV.", "revealwarn");
  const nav = el("nav", null, "revealnav");
  [["/", "Findings"], ["/map", "Map"], ["/sheet", "Sheet"], ["/person", "People"], ["/timeline", "Timeline"], ["/browse", "Browse stores"]]
    .forEach(([h, t]) => { const a = el("a", t); a.href = h; if (location.pathname === h) a.className = "here"; nav.appendChild(a); });
  bar.appendChild(nav); bar.appendChild(lab); bar.appendChild(warn);
  function paint() { document.body.classList.toggle("reveal-on", on); warn.hidden = !on; }
  cb.addEventListener("change", () => {
    on = cb.checked;
    try { sessionStorage.setItem(KEY, on ? "1" : "0"); } catch (e) { /* storage unavailable: stays per page */ }
    paint(); document.dispatchEvent(new CustomEvent("reveal-change", { detail: on }));
  });
  document.body.prepend(bar); paint();
  window.Reveal = {
    on: () => on,
    get: (path) => fetch("/api/reveal/" + path, { credentials: "same-origin", headers: { "X-Kestrel-Reveal": "1" } })
      .then(r => { if (!r.ok) return r.text().then(t => { throw new Error(r.status + " " + t); }); return r.json(); }),
    offNotice: (into) => { into.replaceChildren(el("p", "Real values are off. Turn on “Show real values” at the top of the page to use this view.", "offnote")); },
  };
})();
