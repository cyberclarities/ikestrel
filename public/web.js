// The spider map. iOwl's force.js draws it; iKestrel supplies the data and the explanations.
// Every value goes in through textContent. Names come from a personal store.
import { forceGraph } from './force.js';

const $ = id => document.getElementById(id);
const el = (tag, text, cls) => { const e = document.createElement(tag); if (text != null) e.textContent = String(text); if (cls) e.className = cls; return e; };

const ROLE_COLOUR = {
  you: 'var(--text-primary)', partner: 'var(--series-5)', family: 'var(--series-8)', friend: 'var(--series-2)',
  coworker: 'var(--series-7)', talk: 'var(--series-1)', marked: 'var(--series-3)', known: 'var(--axis)', org: 'var(--series-4)',
};
const KIND_COLOUR = {
  messages: 'var(--series-1)', scored: 'var(--series-2)', family: 'var(--series-8)',
  household: 'var(--series-6)', flagged: 'var(--series-5)', employer: 'var(--series-4)',
};
// Lines between the same two circles lie on top of each other, so the wide ones go underneath
// as a halo and the message line, the one most worth reading, paints last and thinnest.
const KIND_STYLE = {
  scored: { dash: '7 4', width: 6, minOpacity: 0.45 }, family: { width: 9, minOpacity: 0.35 },
  household: { width: 9, minOpacity: 0.35 }, flagged: { dash: '2 3', width: 4, minOpacity: 0.7 },
  employer: { minOpacity: 0.5 }, messages: { width: 1.8, minOpacity: 0.55 },
};
const PAINT = ['employer', 'family', 'household', 'scored', 'flagged', 'messages'];
const KIND_DASH = { scored: 'dashed', flagged: 'dotted' };

let data = null, graph = null, shownKinds = new Set(Object.keys(KIND_COLOUR)), byId = new Map();

function load() {
  const qs = `scope=${encodeURIComponent($('scope').value)}&limit=${encodeURIComponent($('limit').value)}`;
  $('headline').textContent = 'Reading the stores…';
  const req = (window.Reveal && Reveal.on())
    ? Reveal.get('web?' + qs).then(r => Object.assign(r.data, { gaps: r.gaps }))
    : fetch('/api/web?' + qs, { credentials: 'same-origin' }).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
  req.then(d => { data = d; render(); })
     .catch(e => { $('headline').textContent = 'Could not read the stores (' + e.message + '). Check the terminal.'; });
}

function render() {
  const c = data.counts;
  $('headline').textContent = data.headline;
  $('mode').textContent = data.real
    ? 'Real names are on. They are shown only in this browser and never go into reports or the CSV.'
    : 'Names are hidden: people are numbered by how much the Mac holds on them. Turn on "Show real values" at the top to see who they are.';
  $('count').textContent = `Showing ${c.shown} of ${c.pool} people` + (c.employers ? ` and ${c.employers} employer(s)` : '')
    + (data.gaps && data.gaps.length ? ` · ${data.gaps.length} store(s) could not be read` : '');
  kinds(); roles();
  byId = new Map(data.nodes.map(n => [String(n.id), n]));
  draw();
  panel(null);
}

function kinds() {
  const K = $('kinds'); K.replaceChildren(el('span', 'Lines:'));
  const present = new Set(data.links.map(l => l.kind));
  data.kinds.filter(k => present.has(k.id)).forEach(k => {
    const n = data.links.filter(l => l.kind === k.id).length;
    const b = el('button', null, 'pill'); b.type = 'button'; b.setAttribute('aria-pressed', String(shownKinds.has(k.id)));
    const sw = el('span', null, 'swl'); sw.style.borderTopColor = KIND_COLOUR[k.id]; if (KIND_DASH[k.id]) sw.style.borderTopStyle = KIND_DASH[k.id];
    b.appendChild(sw); b.appendChild(document.createTextNode(`${k.label} · ${n}`));
    b.addEventListener('click', () => { shownKinds.has(k.id) ? shownKinds.delete(k.id) : shownKinds.add(k.id);
      b.setAttribute('aria-pressed', String(shownKinds.has(k.id))); graph && graph.update({ nodes: nodes(), links: links() }); });
    K.appendChild(b);
  });
}

function roles() {
  const R = $('roles'); R.replaceChildren(el('span', 'Circles:'));
  const n = {}; data.nodes.forEach(x => { n[x.role] = (n[x.role] || 0) + 1; });
  data.roles.filter(r => n[r.id]).forEach(r => {
    const s = el('span'); const d = el('span', null, 'dot'); d.style.background = ROLE_COLOUR[r.id];
    s.appendChild(d); s.appendChild(document.createTextNode(` ${r.label} · ${n[r.id]}`)); R.appendChild(s);
  });
}

const nodes = () => data.nodes.map(n => Object.assign({}, n));
const links = () => data.links.filter(l => shownKinds.has(l.kind))
  .sort((a, b) => PAINT.indexOf(a.kind) - PAINT.indexOf(b.kind)).map(l => Object.assign({}, l));

function draw() {
  if (graph) { graph.destroy(); graph = null; }
  $('graph').replaceChildren();
  graph = forceGraph($('graph'), {
    nodes: nodes(), links: links(), width: 1000, height: 720, expand: $('split'),
    colorFor: n => ROLE_COLOUR[n.role] || ROLE_COLOUR.known,
    linkColorFor: l => KIND_COLOUR[l.kind] || null,
    linkStyleFor: l => KIND_STYLE[l.kind] || null,
    labelFor: n => (n.role === 'known' || n.role === 'talk') ? undefined : true,
    labelMax: 40,
    onSelect: n => panel(n ? byId.get(String(n.id)) : null),
    onLinkHover: (l, ev, also) => tip(l, ev, also),
  });
}

function tip(l, ev, also) {
  const T = $('tip');
  if (!l) { T.classList.remove('on'); return; }
  const a = byId.get(String(l.source.id || l.source)) || {}, b = byId.get(String(l.target.id || l.target)) || {};
  T.replaceChildren(el('b', `${a.label || ''} and ${b.label || ''}`));
  [l].concat(also || []).forEach(x => T.appendChild(el('div', x.tip || x.kind)));
  T.style.left = Math.min(ev.clientX + 14, innerWidth - 330) + 'px'; T.style.top = (ev.clientY + 14) + 'px';
  T.classList.add('on');
}

function panel(n) {
  const P = $('panel'); P.replaceChildren();
  if (!n) {
    P.appendChild(el('h2', 'How to read this'));
    const ul = el('ul', null, 'story');
    ['You are the circle in the middle. Every line out from you is a link your Mac holds between you and someone else.',
     'A blue line means the person is in your message and call history. Darker means more of it.',
     'A wide orange dashed band means the Mac has scored a relationship with them, such as family, partner, friend or coworker. You did not enter these.',
     'A wide red band is iCloud Family Sharing; a wide green band is a shared home address; a pink dotted line is someone you marked a favorite, an emergency contact, or gave a label. These sit under the blue line when both apply.',
     'Yellow circles are employers. A yellow line says the graph holds where that person works.',
     'Click anyone to see, in plain words, everything the Mac holds on them.'].forEach(t => ul.appendChild(el('li', t)));
    P.appendChild(ul);
    return;
  }
  P.appendChild(el('h2', n.label));
  const role = (data.roles.find(r => r.id === n.role) || {}).label || '';
  P.appendChild(el('p', role, 'role'));
  const ul = el('ul', null, 'story'); (n.story || []).forEach(t => ul.appendChild(el('li', t))); P.appendChild(ul);
  if (data.real && n.profile) {
    const a = el('a', 'Open the full profile →', 'open'); a.href = '/person?id=' + encodeURIComponent(n.profile); P.appendChild(a);
  } else if (!data.real && n.kind === 'person') {
    P.appendChild(el('p', 'Turn on "Show real values" to see who this is and open their full profile.', 'note'));
  }
}

$('scope').addEventListener('change', load);
$('limit').addEventListener('change', load);
document.addEventListener('reveal-change', load);
load();
