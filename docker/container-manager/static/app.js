'use strict';
/* Justice League Console — SPA sans dépendance. Toute donnée affichée passe par esc(). */
const $ = (s, r = document) => r.querySelector(s);
const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const P = {
  shield:'<path d="M12 3l8 3v6c0 5-3.4 8-8 9-4.6-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
  grid:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  box:'<path d="M21 8l-9-5-9 5v8l9 5 9-5z"/><path d="M3 8l9 5 9-5M12 13v8"/>',
  wrench:'<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
  list:'<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  layers:'<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>',
  db:'<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
  net:'<circle cx="12" cy="5" r="2.5"/><circle cx="5" cy="19" r="2.5"/><circle cx="19" cy="19" r="2.5"/><path d="M12 7.5v4M12 11.5l-6 5.5M12 11.5l6 5.5"/>',
  refresh:'<path d="M20 11a8 8 0 10-2.3 5.7M20 4v7h-7"/>', moon:'<path d="M20 14A8 8 0 1110 4a6.5 6.5 0 0010 10z"/>', sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5"/>',
  menu:'<path d="M4 6h16M4 12h16M4 18h16"/>', play:'<path d="M7 4l13 8-13 8z"/>', stop:'<rect x="5" y="5" width="14" height="14" rx="2"/>', restart:'<path d="M20 11a8 8 0 10-2.3 5.7M20 4v7h-7"/>',
  pause:'<path d="M8 5v14M16 5v14"/>', logs:'<path d="M4 5h16M4 10h16M4 15h10M4 20h7"/>', close:'<path d="M6 6l12 12M18 6L6 18"/>', radar:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.5"/><path d="M12 12l6-6"/>',
  eye:'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>', newspaper:'<path d="M4 4h13v16H6a2 2 0 01-2-2zM17 8h3v10a2 2 0 01-2 2M8 8h5M8 12h5M8 16h5"/>',
  folder:'<path d="M3 6a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>', file:'<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5"/>', dl:'<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/>', ext:'<path d="M14 4h6v6M20 4l-9 9M18 14v5H5V6h5"/>', bolt:'<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>', up:'<path d="M15 18l-6-6 6-6"/>'
};
const icon = (n, c = '') => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="${c}">${P[n] || ''}</svg>`;
function hydrateIcons(r = document) { r.querySelectorAll('[data-icon]').forEach(e => { if (!e.querySelector('svg')) e.insertAdjacentHTML('afterbegin', icon(e.dataset.icon)); }); }

const fmtB = n => { n = +n || 0; const u = ['o','Ko','Mo','Go','To']; let i = 0; while (n >= 1024 && i < 4) { n /= 1024; i++; } return (i ? n.toFixed(n < 10 ? 1 : 0) : n) + ' ' + u[i]; };
const ago = iso => { if (!iso || iso.startsWith('0001')) return '—'; const s = (Date.now() - new Date(iso)) / 1000; if (s < 60) return Math.floor(s) + ' s'; if (s < 3600) return Math.floor(s / 60) + ' min'; if (s < 86400) return Math.floor(s / 3600) + ' h'; return Math.floor(s / 86400) + ' j'; };
const hhmm = t => t ? new Date(t * 1000).toLocaleTimeString('fr-FR') : '—';

async function api(url, opts = {}) {
  const r = await fetch(url, { ...opts, headers: { 'Content-Type': 'application/json', 'X-JLC': '1', ...(opts.headers || {}) } });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.detail || r.statusText || 'Erreur');
  return d;
}
function toast(msg, kind = '') { const t = document.createElement('div'); t.className = 'toast ' + kind; t.textContent = msg; $('#toasts').append(t); setTimeout(() => t.remove(), kind === 'err' ? 7000 : 3500); }

/* ---------------------------------------------------------------- état */
const S = { route: 'dashboard', containers: [], overview: null, tools: [], jobs: [], hist: { cpu: [], mem: [] }, filter: 'all', q: '', sortKey: 'name', timer: null };
const NAV = [['dashboard','Tableau de bord','grid'],['containers','Conteneurs','box'],['tools','Outils','wrench'],['jobs','Tâches','list'],['_','Ressources'],['images','Images','layers'],['volumes','Volumes','db'],['networks','Réseaux','net']];
const TITLES = Object.fromEntries(NAV.filter(n => n[0] !== '_').map(n => [n[0], n[1]]));

function renderNav() {
  const bad = (S.overview?.counts.unhealthy.length || 0) + (S.overview?.counts.restarting.length || 0);
  const running = S.jobs.filter(j => j.status === 'running').length;
  $('#nav').innerHTML = NAV.map(([id, label, ic]) => id === '_' ? `<div class="sep">${label}</div>` :
    `<a data-nav="${id}" class="${S.route === id ? 'on' : ''}" href="#${id}">${icon(ic)}<span>${label}</span>${id === 'containers' && bad ? `<span class="badge">${bad}</span>` : ''}${id === 'jobs' && running ? `<span class="pill run" style="margin-left:auto">${running}</span>` : ''}</a>`).join('');
}

/* ---------------------------------------------------------------- helpers UI */
function statePill(c) {
  if (c.health === 'unhealthy') return '<span class="pill bad"><i></i>unhealthy</span>';
  if (c.status === 'running') return `<span class="pill ok"><i></i>${c.health === 'starting' ? 'démarrage' : 'actif'}</span>`;
  if (c.status === 'paused') return '<span class="pill warn"><i></i>pause</span>';
  if (c.status === 'restarting') return '<span class="pill warn"><i></i>redémarre</span>';
  return `<span class="pill bad"><i></i>${esc(c.status === 'exited' ? 'arrêté' : c.status)}</span>`;
}
const dotCls = c => c.health === 'unhealthy' || c.status === 'exited' || c.status === 'dead' ? 'bad' : c.status === 'running' ? 'ok' : 'warn';
function bar(pct, extra = '') { const p = Math.max(0, Math.min(100, pct)); return `<div class="bar ${p > 90 ? 'bad' : p > 75 ? 'warn' : ''}"><i style="width:${p}%"></i></div>`; }
function spark(arr) {
  if (arr.length < 2) return '<svg class="spark" viewBox="0 0 100 40"></svg>';
  const max = Math.max(...arr, 1), w = 100 / (arr.length - 1);
  const pts = arr.map((v, i) => `${(i * w).toFixed(1)},${(38 - v / max * 34).toFixed(1)}`);
  return `<svg class="spark" viewBox="0 0 100 40" preserveAspectRatio="none"><path class="a" d="M0,40 L${pts.join(' L')} L100,40Z"/><path class="l" d="M${pts.join(' L')}" vector-effect="non-scaling-stroke"/></svg>`;
}
const memPct = s => s && s.mem_limit ? s.mem / s.mem_limit * 100 : 0;

/* ---------------------------------------------------------------- vues */
function viewDashboard() {
  const o = S.overview; if (!o) return '<div class="empty">Chargement…</div>';
  const c = o.counts, h = o.host, u = o.usage;
  const alerts = [...c.unhealthy.map(n => ['bad', n, 'unhealthy']), ...c.restarting.map(n => ['warn', n, 'redémarre en boucle']),
    ...S.containers.filter(x => x.status === 'exited' && x.exit_code).map(x => ['bad', x.name, 'arrêté avec le code ' + x.exit_code])];
  return `
  <div class="grid g4">
    <div class="card stat"><h3>Conteneurs actifs</h3><div class="v">${c.running}<small> / ${c.total}</small></div><div class="s">${c.stopped} arrêté(s) · ${c.paused} en pause</div></div>
    <div class="card stat"><h3>CPU (total)</h3><div class="v">${u.cpu}<small> %</small></div>${spark(S.hist.cpu)}</div>
    <div class="card stat"><h3>Mémoire</h3><div class="v">${fmtB(u.mem)}<small> / ${fmtB(h.mem)}</small></div>${spark(S.hist.mem)}</div>
    <div class="card stat"><h3>Réseau cumulé</h3><div class="v" style="font-size:20px">↓ ${fmtB(u.rx)}</div><div class="s">↑ ${fmtB(u.tx)} · ${c.images} image(s)</div></div>
  </div>
  <div class="grid g2" style="grid-template-columns:2fr 1fr;margin-top:14px">
    <div class="card"><h3>Stack Justice League <span class="right muted">${c.running} actifs</span></h3>
      <div class="tiles">${S.containers.map(x => `<button class="tile" data-open="${esc(x.name)}"><div class="t1"><span class="dot ${dotCls(x)}"></span><span>${esc(x.codename || x.name)}</span></div><small>${esc(x.role || x.image)}</small>
        <small class="mono">${x.stats ? `CPU ${x.stats.cpu}% · ${fmtB(x.stats.mem)}` : esc(x.status)}</small></button>`).join('')}</div></div>
    <div class="grid" style="align-content:start">
      <div class="card"><h3>Alertes</h3>${alerts.length ? alerts.map(a => `<div class="alert"><span class="pill ${a[0]}"><i></i></span><b>${esc(a[1])}</b><span class="muted">${esc(a[2])}</span></div>`).join('') : '<div class="muted">Aucune alerte — tout est nominal ✓</div>'}</div>
      <div class="card"><h3>Hôte Docker</h3><dl class="kv" style="grid-template-columns:90px 1fr"><dt>Nom</dt><dd>${esc(h.name)}</dd><dt>Système</dt><dd>${esc(h.os)}</dd><dt>Noyau</dt><dd>${esc(h.kernel)}</dd><dt>CPU</dt><dd>${esc(h.cpus)} · ${esc(h.arch)}</dd><dt>Docker</dt><dd>${esc(h.docker)}</dd></dl></div>
      <div class="card"><h3>Outils rapides</h3><div class="actions" style="grid-template-columns:1fr">${S.tools.map(t => `<button class="act" data-go="tools"><b>${icon(t.icon)}${esc(t.codename)} · ${esc(t.title)}</b><small>${t.state === 'running' ? 'Prêt' : 'Conteneur ' + esc(t.state)}</small></button>`).join('') || '<div class="muted">—</div>'}</div></div>
    </div>
  </div>`;
}

function filteredContainers() {
  const q = S.q.toLowerCase();
  let a = S.containers.filter(c => (S.filter === 'all' || (S.filter === 'running' ? c.status === 'running' : c.status !== 'running')) &&
    [c.name, c.codename, c.role, c.image, c.status, ...c.ports].join(' ').toLowerCase().includes(q));
  const k = S.sortKey;
  a.sort((x, y) => k === 'cpu' ? (y.stats?.cpu || 0) - (x.stats?.cpu || 0) : k === 'mem' ? (y.stats?.mem || 0) - (x.stats?.mem || 0) : k === 'state' ? x.status.localeCompare(y.status) : x.name.localeCompare(y.name));
  return a;
}
function viewContainers() {
  return `<div class="toolbar"><input id="q" placeholder="Filtrer : nom, codename, image, port…" value="${esc(S.q)}" aria-label="Filtrer">
    <div class="seg" id="seg">${[['all','Tous'],['running','Actifs'],['stopped','Arrêtés']].map(([k, l]) => `<button data-f="${k}" class="${S.filter === k ? 'on' : ''}">${l}</button>`).join('')}</div>
    <select id="sort" aria-label="Trier">${[['name','Nom'],['cpu','CPU'],['mem','Mémoire'],['state','État']].map(([k, l]) => `<option value="${k}" ${S.sortKey === k ? 'selected' : ''}>Trier : ${l}</option>`).join('')}</select></div>
  <div class="tw"><table><thead><tr><th>Conteneur</th><th>État</th><th>CPU</th><th>Mémoire</th><th>Ports</th><th>Âge</th><th></th></tr></thead><tbody id="ctb">${containerRows()}</tbody></table></div>`;
}
function containerRows() {
  const a = filteredContainers();
  if (!a.length) return '<tr><td colspan="7" class="empty">Aucun conteneur ne correspond.</td></tr>';
  return a.map(c => { const s = c.stats, run = c.status === 'running';
    return `<tr class="click" data-open="${esc(c.name)}"><td class="nm"><b>${esc(c.codename ? c.codename + ' · ' : '')}${esc(c.name)}</b><small>${esc(c.role || c.image)}</small></td><td>${statePill(c)}</td>
    <td>${s ? `<div class="cell-bar">${bar(s.cpu)}<span>${s.cpu}%</span></div>` : '<span class="muted">—</span>'}</td>
    <td>${s ? `<div class="cell-bar">${bar(memPct(s))}<span>${fmtB(s.mem)}</span></div>` : '<span class="muted">—</span>'}</td>
    <td>${c.ports.length ? `<div class="chips">${c.ports.map(p => `<span class="chip">${esc(p)}</span>`).join('')}</div>` : '<span class="muted">—</span>'}</td><td class="muted">${run ? ago(c.started) : '—'}</td>
    <td><div class="acts">${run ? `<button class="btn sm" data-act="restart" data-name="${esc(c.name)}" title="Redémarrer">${icon('restart')}</button><button class="btn sm danger" data-act="stop" data-name="${esc(c.name)}" title="Arrêter">${icon('stop')}</button>`
      : `<button class="btn sm primary" data-act="start" data-name="${esc(c.name)}" title="Démarrer">${icon('play')}</button>`}</div></td></tr>`; }).join('');
}

function viewTools() {
  if (!S.tools.length) return '<div class="empty">Chargement…</div>';
  return `<div class="grid" style="gap:16px">${S.tools.map(t => { const ok = t.state === 'running';
    return `<section class="card tool" data-tool="${t.id}"><div class="hd"><div class="ic">${icon(t.icon)}</div><div class="sp"><h2>${esc(t.codename)} · ${esc(t.title)}</h2><p>${esc(t.desc)}</p></div>
      <span class="pill ${ok ? 'ok' : 'bad'}"><i></i>${ok ? 'prêt' : esc(t.state)}</span>${t.link ? `<a class="btn sm" target="_blank" rel="noopener" href="${esc(t.link.url)}">${icon('ext')}Interface</a>` : ''}</div>
      ${t.warning ? `<div class="warnbox">⚠ ${esc(t.warning)}</div>` : ''}
      ${t.id === 'scanner' ? `<div class="muted">Périmètre autorisé (AUTHORIZED_CIDRS) : ${t.cidrs.length ? t.cidrs.map(c => `<span class="chip">${esc(c)}</span>`).join(' ') : '<b>aucun</b> — renseignez AUTHORIZED_CIDRS dans config.env pour activer découverte et scans'}</div>` : ''}
      <div class="actions">${t.actions.map(a => `<button class="act ${a.danger ? 'danger' : ''}" ${ok ? '' : 'disabled'} data-run="${t.id}" data-action="${a.id}"><b>${icon(a.danger ? 'bolt' : 'play')}${esc(a.label)}</b><small>${esc(a.desc)}</small></button>`).join('')}</div>
      <div class="files"><div class="row" style="margin-bottom:8px"><b>Fichiers</b>${t.files.length > 1 ? `<select data-root="${t.id}">${t.files.map(f => `<option value="${f.id}">${esc(f.label)}</option>`).join('')}</select>` : `<span class="muted">${esc(t.files[0].label)}</span>`}
        <span class="sp"></span><button class="btn sm ghost" data-files-refresh="${t.id}">${icon('refresh')}</button></div><div class="crumb" id="crumb-${t.id}"></div><div class="flist" id="files-${t.id}"><span class="muted">${ok ? 'Chargement…' : 'Conteneur arrêté'}</span></div></div></section>`; }).join('')}</div>`;
}
const FS = {}; // état navigateur de fichiers par outil
async function loadFiles(tid) {
  const t = S.tools.find(x => x.id === tid); if (!t || t.state !== 'running') return;
  const st = FS[tid] = FS[tid] || { root: t.files[0].id, path: '' };
  const sel = $(`[data-root="${tid}"]`); if (sel) st.root = sel.value;
  const box = $('#files-' + tid), cr = $('#crumb-' + tid); if (!box) return;
  try {
    const d = await api(`/api/tools/${tid}/files?root=${encodeURIComponent(st.root)}&path=${encodeURIComponent(st.path)}`);
    cr.innerHTML = st.path ? `<button class="btn sm" data-fup="${tid}">${icon('up')}Retour</button><span class="mono muted">/${esc(st.path)}</span>` : '';
    box.innerHTML = d.items.length ? d.items.map(f => `<div class="fi" data-fopen="${tid}" data-name="${esc(f.name)}" data-dir="${f.dir ? 1 : 0}">${icon(f.dir ? 'folder' : 'file')}<span title="${esc(f.name)}">${esc(f.name)}</span>${f.dir ? '' : `<a href="/api/tools/${tid}/file?root=${encodeURIComponent(st.root)}&path=${encodeURIComponent((st.path ? st.path + '/' : '') + f.name)}&download=1" data-stop title="Télécharger">${icon('dl')}</a>`}</div>`).join('') : '<span class="muted">Dossier vide (rien n\'a encore été généré).</span>';
  } catch (e) { box.innerHTML = `<span class="muted">${esc(e.message)}</span>`; }
}
async function openFile(tid, name) {
  const st = FS[tid], path = (st.path ? st.path + '/' : '') + name;
  try {
    const d = await api(`/api/tools/${tid}/file?root=${encodeURIComponent(st.root)}&path=${encodeURIComponent(path)}`);
    let body;
    if (/\.csv$/i.test(name)) {
      const rows = d.content.trim().replace(/^﻿/, '').split(/\r?\n/).map(l => l.split(';'));
      body = `<div class="csv"><table><thead><tr>${rows[0].map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.slice(1).map(r => `<tr>${r.map(c => `<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
    } else body = `<div class="term">${esc(d.content)}</div>`;
    modal(`<div class="dlg wide"><div class="dlg-h"><h2>${esc(name)}</h2><a class="btn sm" href="/api/tools/${tid}/file?root=${encodeURIComponent(st.root)}&path=${encodeURIComponent(path)}&download=1">${icon('dl')}Télécharger</a><button class="icon-btn" data-close>${icon('close')}</button></div><div class="dlg-b">${body}${d.truncated ? '<p class="muted">Aperçu tronqué — téléchargez le fichier complet.</p>' : ''}</div></div>`);
  } catch (e) { toast(e.message, 'err'); }
}

function viewJobs() {
  return S.jobs.length ? `<div class="tw"><table><thead><tr><th>Tâche</th><th>Paramètres</th><th>État</th><th>Début</th><th>Durée</th><th>Par</th></tr></thead><tbody>${S.jobs.map(j => `<tr class="click" data-job="${j.id}"><td class="nm"><b>${esc(j.label)}</b><small>${esc(j.container)}</small></td><td class="mono">${esc(Object.values(j.params).join(' · ') || '—')}</td><td>${jobPill(j)}</td><td>${hhmm(j.started)}</td><td>${Math.round((j.ended || Date.now() / 1000) - j.started)} s</td><td>${esc(j.user)}</td></tr>`).join('')}</tbody></table></div>`
    : '<div class="card empty">Aucune tâche lancée depuis le démarrage de la console. Lancez une action depuis « Outils ».</div>';
}
const jobPill = j => j.status === 'running' ? '<span class="pill run"><i></i>en cours</span>' : j.status === 'ok' ? '<span class="pill ok"><i></i>terminé</span>' : j.status === 'timeout' ? '<span class="pill warn"><i></i>délai dépassé</span>' : `<span class="pill bad"><i></i>échec (${esc(j.exit)})</span>`;

const viewImages = d => `<div class="tw"><table><thead><tr><th>Image</th><th>ID</th><th>Taille</th><th>Utilisée par</th></tr></thead><tbody>${d.items.map(i => `<tr><td class="nm"><b>${esc(i.tags[0] || '<sans tag>')}</b><small>${esc(i.tags.slice(1).join(', '))}</small></td><td class="mono">${esc(i.id)}</td><td>${fmtB(i.size)}</td><td>${i.used_by.length ? i.used_by.map(n => `<span class="chip">${esc(n)}</span>`).join(' ') : '<span class="muted">inutilisée</span>'}</td></tr>`).join('')}</tbody></table></div>`;
const viewVolumes = d => `<div class="tw"><table><thead><tr><th>Volume</th><th>Pilote</th><th>Créé</th><th>Utilisé par</th></tr></thead><tbody>${d.items.map(v => `<tr><td><b>${esc(v.name)}</b></td><td>${esc(v.driver)}</td><td class="muted">${esc(String(v.created).slice(0, 10))}</td><td>${v.used_by.map(n => `<span class="chip">${esc(n)}</span>`).join(' ') || '<span class="muted">orphelin</span>'}</td></tr>`).join('')}</tbody></table></div>`;
const viewNetworks = d => `<div class="tw"><table><thead><tr><th>Réseau</th><th>Pilote</th><th>Sous-réseau</th><th>Conteneurs</th></tr></thead><tbody>${d.items.map(n => `<tr><td><b>${esc(n.name)}</b></td><td>${esc(n.driver)}</td><td class="mono">${esc(n.subnet || '—')}</td><td>${n.containers.map(c => `<span class="chip">${esc(c)}</span>`).join(' ') || '<span class="muted">—</span>'}</td></tr>`).join('')}</tbody></table></div>`;

/* ---------------------------------------------------------------- routage / chargement */
async function load(force) {
  try {
    if (S.route === 'dashboard') {
      const [o, c, t] = await Promise.all([api('/api/overview'), api('/api/containers'), S.tools.length && !force ? null : api('/api/tools')]);
      S.overview = o; S.containers = c.items; if (t) S.tools = t.items;
      S.hist.cpu.push(o.usage.cpu); S.hist.mem.push(o.usage.mem); Object.values(S.hist).forEach(a => a.length > 60 && a.shift());
      $('#view').innerHTML = viewDashboard();
    } else if (S.route === 'containers') {
      const c = await api('/api/containers'); S.containers = c.items;
      if ($('#ctb')) $('#ctb').innerHTML = containerRows(); else $('#view').innerHTML = viewContainers();
    } else if (S.route === 'tools') {
      S.tools = (await api('/api/tools')).items;
      if (!$('[data-tool]') || force) { $('#view').innerHTML = viewTools(); S.tools.forEach(t => loadFiles(t.id)); }
    } else if (S.route === 'jobs') { S.jobs = (await api('/api/jobs')).items; $('#view').innerHTML = viewJobs(); }
    else if (['images', 'volumes', 'networks'].includes(S.route)) {
      const d = await api('/api/' + S.route);
      $('#view').innerHTML = { images: viewImages, volumes: viewVolumes, networks: viewNetworks }[S.route](d);
    }
    if (S.route !== 'jobs') api('/api/jobs').then(j => { S.jobs = j.items; renderNav(); }).catch(() => {});
    $('#hostline').textContent = S.overview ? `${S.overview.host.name} · Docker ${S.overview.host.docker}` : '';
    $('#live').classList.remove('off');
  } catch (e) { $('#live').classList.add('off'); if (!$('#view').children.length || /introuvable|indisponible/i.test(e.message)) $('#view').innerHTML = `<div class="card empty">${esc(e.message)}</div>`; }
  renderNav();
}
function go(route) {
  S.route = TITLES[route] ? route : 'dashboard'; $('#title').textContent = TITLES[S.route]; $('#side').classList.remove('open');
  $('#view').innerHTML = S.route === 'dashboard' || S.route === 'containers' ? '' : '<div class="empty">Chargement…</div>';
  renderNav(); load(true);
  clearInterval(S.timer);
  const every = { dashboard: 5000, containers: 5000, jobs: 4000 }[S.route];
  if (every) S.timer = setInterval(() => { if (!document.hidden && !$('#drawer').childElementCount) load(); }, every);
}

/* ---------------------------------------------------------------- modales / tiroir */
function modal(html) { const m = $('#modal'); m.innerHTML = html; m.hidden = false; hydrateIcons(m); }
function closeModal() { const m = $('#modal'); m.hidden = true; m.innerHTML = ''; clearInterval(S.jobTimer); }
function closeDrawer() { clearInterval(S.logTimer); const d = $('#drawer'); d.hidden = true; d.innerHTML = ''; }

async function openContainer(name, tab = 'overview') {
  const d = $('#drawer'); d.hidden = false; clearInterval(S.logTimer);
  try {
    const c = await api('/api/containers/' + encodeURIComponent(name)); const run = c.status === 'running';
    d.innerHTML = `<div class="sheet" role="dialog" aria-label="${esc(c.name)}"><div class="sheet-h"><div class="sp" style="min-width:0"><h2>${esc(c.name)}</h2><span class="muted">${esc(c.codename)} ${c.role ? '· ' + esc(c.role) : ''}</span></div>${statePill(c)}
      <div class="acts">${run ? `<button class="btn sm" data-act="restart" data-name="${esc(c.name)}">${icon('restart')}</button><button class="btn sm" data-act="${c.status === 'paused' ? 'unpause' : 'pause'}" data-name="${esc(c.name)}">${icon('pause')}</button><button class="btn sm danger" data-act="stop" data-name="${esc(c.name)}">${icon('stop')}</button>` : `<button class="btn sm primary" data-act="start" data-name="${esc(c.name)}">${icon('play')}Démarrer</button>`}</div>
      <button class="icon-btn" data-dclose>${icon('close')}</button></div>
      <div class="tabs">${[['overview','Aperçu'],['logs','Journaux'],['config','Configuration']].map(([k, l]) => `<button data-tab="${k}" data-name="${esc(c.name)}" class="${tab === k ? 'on' : ''}">${l}</button>`).join('')}</div><div class="sheet-b" id="sheet-b"></div></div>`;
    const b = $('#sheet-b');
    if (tab === 'overview') {
      const s = c.stats;
      b.innerHTML = `${s ? `<div class="grid g3" style="margin-bottom:14px"><div class="card stat"><h3>CPU</h3><div class="v">${s.cpu}<small> %</small></div>${bar(s.cpu)}</div><div class="card stat"><h3>Mémoire</h3><div class="v">${fmtB(s.mem)}</div>${bar(memPct(s))}</div><div class="card stat"><h3>Réseau</h3><div class="v" style="font-size:17px">↓ ${fmtB(s.rx)}</div><div class="s">↑ ${fmtB(s.tx)} · ${s.pids} proc.</div></div></div>` : ''}
      <dl class="kv"><dt>ID</dt><dd class="mono">${esc(c.id)}</dd><dt>Image</dt><dd>${esc(c.image)}</dd><dt>Démarré</dt><dd>${esc(c.started)} (${ago(c.started)})</dd><dt>Redémarrages</dt><dd>${c.restarts} · politique : ${esc(c.restart_policy)}</dd><dt>Utilisateur</dt><dd>${esc(c.user)}</dd>
      <dt>Ports</dt><dd>${c.ports.map(p => `<span class="chip">${esc(p)}</span>`).join(' ') || '—'}</dd>
      <dt>Réseaux</dt><dd>${Object.entries(c.networks).map(([n, v]) => `<span class="chip">${esc(n)} ${esc(v.ip)}</span>`).join(' ') || '—'}</dd>
      <dt>Volumes</dt><dd>${c.mounts.map(m => `<div class="mono">${esc(m.src)} → ${esc(m.dst)} ${m.rw ? '' : '(ro)'}</div>`).join('') || '—'}</dd>
      <dt>Durcissement</dt><dd>${c.read_only ? '<span class="chip">read-only</span> ' : ''}${(c.cap_drop || []).map(x => `<span class="chip">drop ${esc(x)}</span>`).join(' ')}${(c.cap_add || []).map(x => `<span class="chip">add ${esc(x)}</span>`).join(' ')}${c.privileged ? '<span class="pill bad">privilégié</span>' : ''}</dd></dl>
      ${c.healthcheck.length ? `<h3 style="margin:18px 0 8px" class="muted">Derniers contrôles de santé</h3>${c.healthcheck.map(h => `<div class="alert"><span class="pill ${h.code === 0 ? 'ok' : 'bad'}"><i></i>${h.code}</span><span class="mono">${esc(String(h.end).slice(11, 19))}</span><span class="muted">${esc(h.out.trim().slice(0, 120))}</span></div>`).join('')}` : ''}`;
    } else if (tab === 'config') {
      b.innerHTML = `<p class="muted">Les valeurs sensibles (mots de passe, jetons, clés, DSN) sont masquées.</p><dl class="kv"><dt>Entrypoint</dt><dd class="mono">${esc((c.entrypoint || []).join(' ') || '—')}</dd><dt>Commande</dt><dd class="mono">${esc((c.cmd || []).join(' ') || '—')}</dd></dl>
      <h3 class="muted" style="margin:16px 0 8px">Variables d'environnement</h3><div class="term">${c.env.map(e => `<span class="ts">${esc(e.key)}</span>=${esc(e.value)}`).join('\n')}</div>`;
    } else if (tab === 'logs') logsTab(b, c.name);
  } catch (e) { d.innerHTML = `<div class="sheet"><div class="sheet-h"><h2>Erreur</h2><button class="icon-btn" data-dclose>${icon('close')}</button></div><div class="sheet-b">${esc(e.message)}</div></div>`; }
}
function logsTab(b, name) {
  b.innerHTML = `<div class="toolbar"><input id="lf" placeholder="Filtrer les lignes…"><label class="row muted"><input type="checkbox" id="follow" checked style="width:auto"> Suivre</label><button class="btn sm" id="ldl">${icon('dl')}Télécharger</button></div><div class="term" id="logbox" style="max-height:calc(100vh - 250px)">Chargement…</div>`;
  let lines = [], last = '';
  const draw = () => { const f = $('#lf')?.value.toLowerCase() || ''; const box = $('#logbox'); if (!box) return clearInterval(S.logTimer);
    box.innerHTML = lines.filter(l => l.toLowerCase().includes(f)).map(l => { const i = l.indexOf(' '); const ts = l.slice(0, i), msg = l.slice(i + 1); const cls = /error|fatal|traceback|exception/i.test(msg) ? 'e' : /warn/i.test(msg) ? 'w' : '';
      return `<span class="ts">${esc(ts.slice(11, 19))}</span> <span class="${cls}">${esc(msg)}</span>`; }).join('\n') || '(aucun journal)';
    if ($('#follow')?.checked) box.scrollTop = box.scrollHeight; };
  const pull = async () => { try { const d = await api(`/api/containers/${encodeURIComponent(name)}/logs?tail=${last ? 50 : 400}`);
    const fresh = d.lines.filter(l => !last || l.split(' ')[0] > last); if (fresh.length || !last) { lines = lines.concat(fresh).slice(-3000); last = d.lines.length ? d.lines[d.lines.length - 1].split(' ')[0] : last; draw(); } } catch (e) { clearInterval(S.logTimer); } };
  pull(); S.logTimer = setInterval(pull, 2000);
  $('#lf').oninput = draw;
  $('#ldl').onclick = () => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/plain' })); a.download = name + '.log'; a.click(); };
}

/* ---------------------------------------------------------------- actions outils */
async function runTool(tid, aid) {
  const t = S.tools.find(x => x.id === tid), a = t.actions.find(x => x.id === aid);
  const params = {};
  if (a.params.length) {
    const fields = await Promise.all(a.params.map(async p => {
      if (p.type === 'select') { let items = []; try { items = (await api(`/api/tools/${tid}/options/${p.source}`)).items; } catch (e) {}
        return `<div class="field"><label for="p-${p.name}">${esc(p.label)}</label>${items.length ? `<select id="p-${p.name}">${items.map(i => `<option>${esc(i)}</option>`).join('')}</select>` : `<div class="warnbox">Aucune option disponible${p.source === 'cidrs' ? ' : définissez AUTHORIZED_CIDRS dans config.env' : ''}.</div>`}</div>`; }
      return `<div class="field"><label for="p-${p.name}">${esc(p.label)}</label><input id="p-${p.name}" placeholder="${esc(p.placeholder || '')}" autocomplete="off" spellcheck="false"></div>`; }));
    const ok = await new Promise(res => { modal(`<div class="dlg"><div class="dlg-h"><h2>${esc(a.label)}</h2><button class="icon-btn" data-close>${icon('close')}</button></div><form id="pf"><div class="dlg-b"><p class="muted" style="margin-top:0">${esc(a.desc)}</p>${a.confirm ? `<div class="warnbox" style="margin-bottom:12px">${esc(a.confirm)}</div>` : ''}${fields.join('')}</div><div class="dlg-f"><button type="button" class="btn" data-close>Annuler</button><button class="btn ${a.danger ? 'danger' : 'primary'}" type="submit">Lancer</button></div></form></div>`);
      $('#pf').onsubmit = e => { e.preventDefault(); a.params.forEach(p => params[p.name] = $('#p-' + p.name)?.value.trim() || ''); res(true); };
      $('#modal').onclick = e => { if (e.target.closest('[data-close]') || e.target === $('#modal')) { closeModal(); res(false); } }; });
    if (!ok) return; closeModal();
  } else if (a.confirm && !confirm(a.confirm)) return;
  try { const j = await api(`/api/tools/${tid}/${aid}`, { method: 'POST', body: JSON.stringify({ params }) }); toast('Tâche lancée : ' + a.label, 'ok'); watchJob(j.id); }
  catch (e) { toast(e.message, 'err'); }
}
function watchJob(id) {
  clearInterval(S.jobTimer);
  modal(`<div class="dlg wide"><div class="dlg-h"><h2 id="jt">Tâche</h2><span id="jp"></span><button class="icon-btn" data-close>${icon('close')}</button></div><div class="dlg-b"><div class="term" id="jo" style="max-height:60vh"></div></div></div>`);
  let since = 0, buf = '';
  const tick = async () => { try { const j = await api(`/api/jobs/${id}?since=${since}`); since = j.next;
    $('#jt').textContent = j.label + (Object.keys(j.params).length ? ' — ' + Object.values(j.params).join(' ') : ''); $('#jp').innerHTML = jobPill(j);
    if (j.lines.length) buf += j.lines.map(esc).join('\n') + '\n'; const jo = $('#jo'); if (!jo) return clearInterval(S.jobTimer);
    jo.innerHTML = buf || '<span class="ts">En attente de sortie…</span>'; jo.scrollTop = jo.scrollHeight;
    if (j.status !== 'running') { clearInterval(S.jobTimer); S.tools.forEach(t => loadFiles(t.id)); } } catch (e) { clearInterval(S.jobTimer); } };
  tick(); S.jobTimer = setInterval(tick, 1000);
}

/* ---------------------------------------------------------------- événements */
document.addEventListener('click', async e => {
  const t = e.target;
  const el = s => t.closest(s);
  if (el('[data-stop]')) return e.stopPropagation();
  let x;
  if ((x = el('[data-act]'))) { e.stopPropagation(); const { act, name } = x.dataset;
    if (act === 'stop' && !confirm(`Arrêter ${name} ?`)) return;
    x.disabled = true;
    try { await api(`/api/containers/${encodeURIComponent(name)}/action`, { method: 'POST', body: JSON.stringify({ action: act }) }); toast(`${name} : ${act} effectué`, 'ok'); if (!$('#drawer').hidden) openContainer(name); load(); }
    catch (err) { toast(err.message, 'err'); x.disabled = false; } return; }
  if ((x = el('[data-open]'))) return openContainer(x.dataset.open);
  if ((x = el('[data-tab]'))) return openContainer(x.dataset.name, x.dataset.tab);
  if (el('[data-dclose]') || t === $('#drawer')) return closeDrawer();
  if (el('[data-close]') || t === $('#modal')) return closeModal();
  if ((x = el('[data-go]'))) return (location.hash = x.dataset.go);
  if ((x = el('[data-run]'))) return runTool(x.dataset.run, x.dataset.action);
  if ((x = el('[data-job]'))) return watchJob(x.dataset.job);
  if ((x = el('[data-f]'))) { S.filter = x.dataset.f; $('#view').innerHTML = viewContainers(); return; }
  if ((x = el('[data-fopen]'))) { const tid = x.dataset.fopen; if (x.dataset.dir === '1') { const st = FS[tid]; st.path = (st.path ? st.path + '/' : '') + x.dataset.name; return loadFiles(tid); } return openFile(tid, x.dataset.name); }
  if ((x = el('[data-fup]'))) { const st = FS[x.dataset.fup]; st.path = st.path.split('/').slice(0, -1).join('/'); return loadFiles(x.dataset.fup); }
  if ((x = el('[data-files-refresh]'))) return loadFiles(x.dataset.filesRefresh);
});
document.addEventListener('input', e => { if (e.target.id === 'q') { S.q = e.target.value; $('#ctb').innerHTML = containerRows(); } });
document.addEventListener('change', e => {
  if (e.target.id === 'sort') { S.sortKey = e.target.value; $('#ctb').innerHTML = containerRows(); }
  if (e.target.dataset.root) { FS[e.target.dataset.root] = { root: e.target.value, path: '' }; loadFiles(e.target.dataset.root); }
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') { if (!$('#modal').hidden) closeModal(); else if (!$('#drawer').hidden) closeDrawer(); } });
$('#refresh').onclick = () => load(true);
$('#burger').onclick = () => $('#side').classList.toggle('open');
$('#theme').onclick = () => { const d = document.documentElement; const n = d.dataset.theme === 'dark' ? 'light' : 'dark'; d.dataset.theme = n; try { localStorage.setItem('jlc-theme', n); } catch (e) {} setThemeIcon(); };
function setThemeIcon() { const b = $('#theme'); b.innerHTML = icon(document.documentElement.dataset.theme === 'dark' ? 'moon' : 'sun'); }
try { const t = localStorage.getItem('jlc-theme'); if (t) document.documentElement.dataset.theme = t; } catch (e) {}
window.addEventListener('hashchange', () => go(location.hash.slice(1)));
hydrateIcons(); setThemeIcon(); go(location.hash.slice(1) || 'dashboard');
