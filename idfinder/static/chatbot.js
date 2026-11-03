// C18: render all model/user/catalogue text as text, never as HTML.
(() => {
  'use strict';
  const root = document.getElementById('chatbot');
  if (!root) return;
  const log = document.getElementById('chat-log');
  const input = document.getElementById('chat-input');
  const send = document.getElementById('chat-send');
  const reset = document.getElementById('new-chat');
  const status = document.getElementById('chat-status');
  const configured = root.dataset.configured === 'true';
  const launcher = document.getElementById('chat-launcher');
  const panel = document.getElementById('chat-panel');
  // C18: open/minimise the floating box and remember its state between pages.
  function expand(open, focus = false) {
    panel.hidden = !open;
    launcher.hidden = open;
    launcher.setAttribute('aria-expanded', String(open));
    try { sessionStorage.setItem(root.dataset.storageKey, open ? 'open' : 'closed'); } catch (_) { /* Storage may be disabled. */ }
    if (focus) (open ? input : launcher).focus();
    log.scrollTop = log.scrollHeight;
  }
  let savedOpen = false;
  try { savedOpen = sessionStorage.getItem(root.dataset.storageKey) === 'open'; } catch (_) { /* No storage required for chatting. */ }
  expand(savedOpen || root.dataset.forceOpen === 'true');
  launcher.addEventListener('click', () => expand(true, true));
  document.getElementById('chat-minimise').addEventListener('click', () => expand(false, true));
  panel.addEventListener('keydown', event => { if (event.key === 'Escape') expand(false, true); });
  let busy = false;
  function node(tag, text, parent, cls) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (cls) el.className = cls;
    parent.appendChild(el);
    return el;
  }
  function link(parent, label, path) {
    // C18: same-origin links only, including a second browser-side check.
    if (typeof path !== 'string' || !path.startsWith('/') || path.startsWith('//')) return;
    const url = new URL(path, window.location.origin);
    if (url.origin !== window.location.origin) return;
    node('a', label, parent, 'chat-link').href = url.href;
  }
  function message(role, text) {
    const box = node('article', undefined, log, 'chat-message ' + role);
    node('strong', role === 'user' ? 'You' : 'Uncle David', box);
    node('p', text, box);
    return box;
  }
  // C18: display factual project/designer results and navigation buttons.
  function display(data) {
    const box = message('assistant', data.reply || 'Please try another question.');
    if (data.filters && Object.keys(data.filters).length) {
      const f = data.filters;
      // C18: distinguish matching either tag from requiring every style tag.
      const styles = Array.isArray(f.categories) ? f.categories : (f.category ? [f.category] : []);
      const styleLabel = styles.join(f.category_mode === 'all' ? ' AND ' : ' OR ');
      // C18: show alternative housing branches and literal content terms clearly.
      const housing = Array.isArray(f.housing_options) ? f.housing_options.map(o => [o.property_type, o.subtype_name].filter(Boolean).join(' ')).join(' OR ') : [f.property_type, f.subtype_name].filter(Boolean).join(' ');
      const terms = Array.isArray(f.keywords) ? f.keywords : (f.keyword ? [f.keyword] : []);
      const content = terms.join(f.keyword_mode === 'all' ? ' AND ' : ' OR ');
      const parts = [housing, styleLabel, content && `Title/description: ${content}`];
      if (f.min_price !== undefined) parts.push(`From S$${Number(f.min_price).toLocaleString()}`);
      if (f.max_price !== undefined) parts.push(`Up to S$${Number(f.max_price).toLocaleString()}`);
      node('p', 'Applied filters: ' + parts.filter(Boolean).join(' · '), box, 'chat-filter-summary');
    }
    (data.projects || []).forEach((project, index) => {
      const card = node('div', undefined, box, 'chat-result');
      node('h2', `${index + 1}. ${project.title}`, card);
      node('p', [project.property_type, project.subtype_name, project.company_name || project.designer_name].filter(Boolean).join(' · '), card);
      if (project.category_names) node('p', 'Styles: ' + project.category_names, card);
      if (project.description) node('p', project.description.length > 180 ? project.description.slice(0, 180) + '…' : project.description, card);
      node('p', `Recorded price: S$${Number(project.price).toLocaleString()}`, card);
      link(card, 'View project', project.url);
    });
    // C18: display server-calculated ranks, evidence and existing designer-profile links.
    (data.leaderboard || []).forEach(designer => {
      const row = node('div', undefined, box, 'chat-result');
      node('h2', `#${designer.rank} ${designer.name}`, row);
      node('p', designer.company_name || 'No company listed', row);
      node('p', `Leaderboard score: ${Number(designer.score).toFixed(1)} / 100`, row);
      node('p', designer.reviews ? `Review average: ${Number(designer.avg_rating).toFixed(2)} / 5 · ${designer.reviews} visible review(s)` : 'No visible reviews yet', row);
      node('p', `${designer.completed_jobs} completed job(s)`, row);
      link(row, 'View designer', designer.url);
    });
    if (data.ranking_weights) {
      const labels = {rating: 'Star rating', sentiment: 'Review sentiment', interest: 'Customer interest', reliability: 'Reliability', experience: 'Experience'};
      node('p', 'Ranking weights: ' + Object.entries(data.ranking_weights).map(([key, value]) => `${labels[key] || key} ${value}`).join(' · '), box, 'chat-filter-summary');
    }
    (data.designers || []).forEach(designer => {
      const row = node('div', undefined, box, 'chat-result');
      node('h2', designer.name, row);
      node('p', `${designer.company_name || 'No company listed'} · ${designer.project_count} project(s)`, row);
    });
    (data.actions || []).forEach(action => link(box, action.label, action.url));
    if (data.login_url) link(box, 'Log in', data.login_url);
    log.scrollTop = log.scrollHeight;
  }
  function setBusy(value) {
    busy = value;
    send.disabled = value || !configured;
    reset.disabled = value;
    root.querySelectorAll('[data-prompt]').forEach(button => { button.disabled = value || !configured; });
    status.textContent = value ? 'Finding an answer…' : '';
  }
  async function request(url, text) {
    const body = new URLSearchParams({form_token: root.dataset.token});
    if (text !== undefined) body.set('message', text);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30000);
    try {
      const response = await fetch(url, {method: 'POST', body, credentials: 'same-origin', keepalive: true,
        headers: {'Accept': 'application/json'}, signal: controller.signal});
      if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Unexpected response');
      return {ok: response.ok, data: await response.json()};
    } finally { clearTimeout(timeout); }
  }
  // C18: send customer queries and show helpful feedback if a request fails.
  async function submit(text) {
    text = text.trim();
    if (busy || !configured || !text || text.length > 600) return;
    message('user', text);
    input.value = '';
    setBusy(true);
    try { display((await request(root.dataset.messageUrl, text)).data); }
    catch (_) {
      message('assistant', 'The request could not finish. Please wait before retrying, or use the normal browsing pages.');
      input.value = text;
    } finally { setBusy(false); input.focus(); log.scrollTop = log.scrollHeight; }
  }
  document.getElementById('chat-form').addEventListener('submit', event => { event.preventDefault(); submit(input.value); });
  input.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); submit(input.value); }
  });
  root.querySelectorAll('[data-prompt]').forEach(button => button.addEventListener('click', () => submit(button.dataset.prompt)));
  reset.addEventListener('click', async () => {
    if (busy) return;
    setBusy(true);
    try { const result = await request(root.dataset.resetUrl); if (result.ok) log.replaceChildren(); display(result.data); }
    catch (_) { message('assistant', 'Could not start a new conversation. Please try again.'); }
    finally { setBusy(false); }
  });
  // C18: reload server-owned history after navigation. No transcript in browser storage.
  let historyPolls = 0;
  async function restoreHistory() {
    setBusy(true);
    status.textContent = 'Loading conversation…';
    try {
      const response = await fetch(root.dataset.historyUrl, {credentials: 'same-origin', cache: 'no-store'});
      if (!response.ok) throw new Error('History unavailable');
      const data = await response.json();
      log.replaceChildren();
      for (const entry of data.messages || []) {
        if (entry.role === 'user') message('user', entry.text);
        else if (entry.role === 'assistant') display(entry.data);
      }
      if (!log.children.length) message('assistant', 'Hello! Uncle David here. Tell me your housing type, preferred style or budget in SGD.');
      // A keepalive request from the previous page may still be running.
      if (data.pending && historyPolls++ < 30) {
        status.textContent = 'Finishing your previous message…';
        setTimeout(restoreHistory, 1000);
        return;
      }
      setBusy(false);
      log.scrollTop = log.scrollHeight;
    } catch (_) {
      if (!log.children.length) message('assistant', 'I could not restore the conversation. Reload the page to retry.');
      setBusy(false);
    }
  }
  restoreHistory();
})();
