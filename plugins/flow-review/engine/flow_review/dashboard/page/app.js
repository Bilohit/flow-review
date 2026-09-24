'use strict';

let state = null;
let openDrawerId = null;   // preserved across patches (Step 2)
let prevBadgeTotal = 0;    // for the new-P0 flash (Step 4)
let drawerReturnFocus = null;   // element to refocus when the drawer closes (E5 review fix)

function patch(newState) {
  const laneEl = document.querySelector('[data-role="lanes"]');
  const savedScroll = laneEl ? laneEl.scrollTop : 0;
  state = newState;
  render();
  if (laneEl) laneEl.scrollTop = savedScroll;
  if (openDrawerId) hydrateDrawer(openDrawerId);   // re-hydrate content, don't re-open/re-animate
}

function render() {
  renderHeader(state);
  renderBadge(state.badge);
  renderLanes(state.lanes);
  if (state.run.finished) renderReport(state.report);
}

// Live mode serves run-folder files under /run/; the static report inlines them, so paths pass through.
function _assetUrl(p) {
  if (!p || document.getElementById('state-data')) return p || '';
  return 'run/' + p.split('/').map(encodeURIComponent).join('/');
}

// Live mode fetches icons/sprite.svg over the network; the static report inlines the sprite
// into the document itself, so a <use> there must resolve a bare '#id' fragment instead.
function _iconHref(id) {
  return document.getElementById('state-data') ? '#' + id : 'icons/sprite.svg#' + id;
}

function _fmtElapsed(totalSeconds) {
  const s = totalSeconds || 0;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}:${String(rem).padStart(2, '0')}`;
}

function renderHeader(s) {
  const progressEl = document.querySelector('[data-role="progress"]');
  progressEl.textContent = `${s.run.flows_done}/${s.run.flows_total}`;
  progressEl.title = `${s.run.flows_done} of ${s.run.flows_total} flows done`;

  const elapsedEl = document.querySelector('[data-role="elapsed"]');
  elapsedEl.textContent = _fmtElapsed(s.run.elapsed_s);
  elapsedEl.title = 'elapsed';

  const budgetEl = document.querySelector('[data-role="budget"]');
  const cap = s.budget.cap_tokens;
  const used = s.budget.used_tokens;
  document.querySelector('[data-role="budget-text"]').textContent = cap ? `${used}/${cap}` : String(used);
  budgetEl.title = cap ? `${used} of ${cap} tokens used` : `${used} tokens used`;
  document.querySelector('[data-role="budget-meter"]').style.setProperty(
    '--pct', cap ? String(Math.min(1, used / cap) * 100) : '0');

  const dotsRoot = document.querySelector('[data-role="surface-dots"]');
  const dots = s.header.surface_dots || [];
  dotsRoot.hidden = dots.length === 0;
  _emptyEl(dotsRoot);
  for (const d of dots) {
    const dot = document.createElement('span');
    dot.className = `dot dot-${d.status}`;
    const label = `${d.surface_id}: ${d.status}`;
    dot.title = label;
    dot.setAttribute('role', 'img');
    dot.setAttribute('aria-label', label);
    dotsRoot.appendChild(dot);
  }
}

function _findingRow(f) {
  const row = document.createElement('button');
  row.className = `sev-${f.sev || 'none'} finding-row`;
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', _iconHref('severity-dot'));
  svg.appendChild(use);
  const label = document.createElement('span');
  label.textContent = f.text;
  row.append(svg, label);
  row.addEventListener('click', () => openDrawer(f.id));
  return row;
}

function _findingSection(title, findings, open) {
  const details = document.createElement('details');
  details.open = !!open;
  const summary = document.createElement('summary');
  summary.textContent = `${title} (${findings.length})`;
  details.appendChild(summary);
  for (const f of findings) details.appendChild(_findingRow(f));
  return details;
}

function renderReport(report) {
  const root = document.querySelector('[data-role="report"]');
  if (!report) { root.hidden = true; return; }
  root.hidden = false;
  _emptyEl(root);

  root.appendChild(_findingSection('needs attention', report.needs_attention, true));

  for (const goal of report.goal_cards) {
    const card = document.createElement('div');
    card.className = 'goal-card';
    card.textContent = goal.text || goal.flow_id || '';
    root.appendChild(card);
  }

  const collapsed = report.collapsed || {};
  root.appendChild(_findingSection('opinions', collapsed.opinions || [], false));
  root.appendChild(_findingSection('repeats', collapsed.repeats || [], false));
  root.appendChild(_findingSection('refuted', collapsed.refuted || [], false));

  const notExercised = document.createElement('details');
  const neSummary = document.createElement('summary');
  neSummary.textContent = `not-exercised (${(collapsed.not_exercised || []).length})`;
  notExercised.appendChild(neSummary);
  for (const ne of collapsed.not_exercised || []) {
    const row = document.createElement('div');
    row.className = 'not-exercised-row';
    row.textContent = `${ne.surface_id || ''} ${ne.flow_id || ''} ${ne.reason || ''}`.trim();
    notExercised.appendChild(row);
  }
  root.appendChild(notExercised);
}

function _buildLaneShell() {
  const head = document.createElement('div');
  head.className = 'lane-head';
  const name = document.createElement('span');
  name.className = 'lane-name';
  head.appendChild(name);

  const shot = document.createElement('div');
  shot.className = 'shot';

  const output = document.createElement('div');
  output.className = 'output mono';

  const currentStep = document.createElement('div');
  currentStep.className = 'current-step';

  const frag = document.createDocumentFragment();
  frag.append(head, shot, output, currentStep);
  return frag;
}

function renderLanes(lanes) {
  const root = document.querySelector('[data-role="lanes"]');
  const seen = new Set();
  for (const lane of lanes) {
    seen.add(lane.surface_id);
    let el = root.querySelector(`[data-surface-id="${CSS.escape(lane.surface_id)}"]`);
    if (!el) {
      el = document.createElement('section');
      el.className = 'lane';
      el.dataset.surfaceId = lane.surface_id;
      el.appendChild(_buildLaneShell());
      root.appendChild(el);
    }
    el.querySelector('.lane-name').textContent = lane.surface_id;
    el.className = `lane lane-${lane.state}`;
    const shotEl = el.querySelector('.shot');
    while (shotEl.firstChild) shotEl.removeChild(shotEl.firstChild);
    if (lane.shot) {
      const img = document.createElement('img');
      img.src = _assetUrl(lane.shot);
      img.alt = lane.surface_id + ' latest screen';
      shotEl.appendChild(img);
    } else if (lane.output != null) {
      el.querySelector('.output').textContent = lane.output;   // API/CLI lanes: text, not a shot
    }
    el.querySelector('.current-step').textContent = lane.current_step || '';
  }
  for (const stale of root.querySelectorAll('[data-surface-id]')) {
    if (!seen.has(stale.dataset.surfaceId)) stale.remove();
  }
}

function renderBadge(badge) {
  const el = document.querySelector('[data-role="badge"]');
  const prevTotal = prevBadgeTotal;
  prevBadgeTotal = badge.total;
  el.className = `sev-${badge.worst_sev || 'none'} badge`;
  el.textContent = String(badge.total);                 // textContent, never innerHTML -- M8 fix
  el.title = `P0 ${badge.counts.P0} · P1 ${badge.counts.P1} · P2 ${badge.counts.P2}`;
  if (badge.counts.P0 > 0 && badge.total > prevTotal) {
    el.classList.add('badge-flash');                    // one eased highlight on a new P0
    el.addEventListener('animationend', () => el.classList.remove('badge-flash'), { once: true });
  }
}

document.querySelector('[data-role="badge"]').addEventListener('click', () => {
  toggleFindingsList(state.findings);   // click opens the list (defined alongside the drawer, Step 5)
});

const TRIAGE_ACTIONS = [
  { state: 'fixed', label: 'mark fixed', key: 'x', icon: 'check' },
  { state: 'false-positive', label: 'false positive', key: 'f', icon: 'flag' },
  { state: 'wont-fix', label: "won't fix", key: 'w', icon: 'x' },
  { state: 'accepted', label: 'accept', key: 'a', icon: 'severity-dot' },
  { state: 'open', label: 'reopen', key: null, icon: 'reopen' },
];

function _iconButton(iconId, ariaLabel, titleText) {
  const btn = document.createElement('button');
  btn.setAttribute('aria-label', ariaLabel);
  btn.title = titleText;
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', _iconHref(iconId));
  svg.appendChild(use);
  btn.appendChild(svg);
  return btn;
}

function _emptyEl(el) {
  while (el.firstChild) el.removeChild(el.firstChild);
  return el;
}

function openDrawer(findingId) {
  const wasOpen = openDrawerId !== null;
  if (!wasOpen) drawerReturnFocus = document.activeElement;   // remember the trigger, not a nav hop
  openDrawerId = findingId;
  hydrateDrawer(findingId);
  const drawerEl = document.querySelector('[data-role="drawer"]');
  drawerEl.hidden = false;
  moveFocusIntoDrawer(drawerEl);   // also re-anchors focus on j/k navigation between findings
}

function moveFocusIntoDrawer(drawerEl) {
  const target = drawerEl.querySelector('button, [href], [tabindex]') || drawerEl;
  if (!drawerEl.hasAttribute('tabindex') && target === drawerEl) drawerEl.setAttribute('tabindex', '-1');
  target.focus();
}

function closeDrawer() {
  openDrawerId = null;
  document.querySelector('[data-role="drawer"]').hidden = true;
  if (drawerReturnFocus && document.contains(drawerReturnFocus)) drawerReturnFocus.focus();
  drawerReturnFocus = null;
}

function hydrateDrawer(findingId) {
  const finding = state.findings.find(f => f.id === findingId);
  const root = _emptyEl(document.querySelector('[data-role="drawer"]'));
  if (!finding) { closeDrawer(); return; }

  const head = document.createElement('div');
  head.className = 'drawer-head';
  head.textContent = finding.text;   // textContent -- M8 fix

  const evidence = document.createElement('div');
  evidence.className = 'drawer-evidence';

  const triageRow = document.createElement('div');
  triageRow.className = 'drawer-triage';
  for (const action of TRIAGE_ACTIONS) {
    const title = action.key ? `${action.label} (${action.key})` : action.label;
    const btn = _iconButton(action.icon, action.label, title);
    btn.dataset.triage = action.state;
    btn.addEventListener('click', () => triage(finding.id, btn.dataset.triage));
    triageRow.appendChild(btn);
  }

  root.append(head, evidence, triageRow);
  renderEvidence(finding, evidence);
}

// Evidence per type: before/after for regressions, an annotated shot for visual findings,
// text first for API/CLI (spec §11).
function renderEvidence(finding, container) {
  _emptyEl(container);
  if (finding.rule === 'regression' && finding.evidence.length >= 2) {
    const wrap = document.createElement('div');
    wrap.className = 'before-after';
    const labels = ['before', 'after'];
    finding.evidence.slice(0, 2).forEach((src, i) => {
      const img = document.createElement('img');
      img.src = _assetUrl(src);
      img.alt = `${finding.text || finding.rule} -- ${labels[i]}`;
      wrap.appendChild(img);
    });
    container.appendChild(wrap);
  } else if (finding.surface_id && isVisual(finding)) {
    const img = document.createElement('img');
    img.className = 'annotated-shot';
    img.src = _assetUrl(finding.evidence[0]);
    img.alt = finding.text || `${finding.surface_id} evidence`;
    container.appendChild(img);
  } else {
    const pre = document.createElement('pre');
    pre.className = 'mono';
    pre.textContent = (finding.evidence[0] || '');   // API/CLI text first, textContent only
    container.appendChild(pre);
  }
}

function isVisual(finding) {
  return ['contrast', 'layout', 'visual-diff'].includes(finding.rule);
}

function triage(findingId, newState) {
  fetch('/triage', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ finding_id: findingId, state: newState }),
  }).then(r => r.json()).then(res => { if (res.error) showTriageError(res.error); });
}

function showTriageError(message) {
  const el = document.querySelector('[data-role="drawer"] .drawer-head');
  if (el) el.title = message;   // no toast subheading -- an accessible-name-style hint only
}

function toggleFindingsList(findings) {
  const root = document.querySelector('[data-role="findings-list"]');
  if (!root.hidden) { closeFindingsList(); return; }
  _emptyEl(root);
  for (const f of findings) {
    const row = document.createElement('button');
    row.className = `sev-${f.sev || 'none'} finding-row`;
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    use.setAttribute('href', _iconHref('severity-dot'));
    svg.appendChild(use);
    const label = document.createElement('span');
    label.textContent = f.text;
    row.append(svg, label);
    row.addEventListener('click', () => { closeFindingsList(); openDrawer(f.id); });
    root.appendChild(row);
  }
  root.hidden = false;
}

function closeFindingsList() {
  const root = document.querySelector('[data-role="findings-list"]');
  root.hidden = true;
  _emptyEl(root);
}

function isFindingsListOpen() {
  const root = document.querySelector('[data-role="findings-list"]');
  return root && !root.hidden;
}

// Triage keys + drawer navigation -- ONLY act when a drawer is open, never on lane/finding rows.
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    if (openDrawerId) { closeDrawer(); return; }
    if (isFindingsListOpen()) { closeFindingsList(); return; }
    return;
  }
  if (!openDrawerId) return;
  const key = { f: 'false-positive', w: 'wont-fix', a: 'accepted', x: 'fixed' }[e.key];
  if (key) { triage(openDrawerId, key); return; }
  if (e.key === 'j' || e.key === 'k') focusAdjacentFinding(e.key === 'j' ? 1 : -1);
});

function focusAdjacentFinding(delta) {
  const ids = state.findings.map(f => f.id);
  const i = ids.indexOf(openDrawerId);
  if (i === -1) return;
  const next = ids[(i + delta + ids.length) % ids.length];
  openDrawer(next);
}

function applyStoredTheme() {
  try {
    const saved = localStorage.getItem('flow-review-theme');
    if (saved) document.documentElement.dataset.theme = saved;
  } catch (_) { /* private window / blocked storage: fall through to OS preference */ }
}

document.querySelector('[data-role="theme-toggle"]').addEventListener('click', () => {
  const current = document.documentElement.dataset.theme
    || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem('flow-review-theme', next); } catch (_) { /* best effort only */ }
});

applyStoredTheme();

function boot() {
  const embedded = document.getElementById('state-data');
  if (embedded) {
    // Static fallback (E2's static.py): no server exists, never open EventSource.
    patch(JSON.parse(embedded.textContent));
    return;
  }
  fetch('/state').then(r => r.json()).then(patch);
  const es = new EventSource('/events');   // auto-reconnects on drop, no manual retry logic
  es.addEventListener('state', e => patch(JSON.parse(e.data)));
}

document.addEventListener('DOMContentLoaded', boot);
