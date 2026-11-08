/* Platform manager graphs: PM21 (weekly activity and design category interest) and the ratings overview.
   Everything lives in classes. Each graph asks the boundary (boundaries/platform_charts.py) for JSON
   and draws it with Chart.js. Search this file for "PM21 START", "PM21 CATEGORY INTEREST START" or "PM24 RATINGS START". */
'use strict';

/* ---------------------------------------------------------------- shared settings */
class GraphSettings {
  // Fixed order, validated for colour-blind viewers. Colour never carries meaning alone:
  // every chart also has a legend or direct labels, and every section has a table.
  static COLOURS = { views: '#2a78d6', projects: '#eb6834', favourites: '#1baf7a', users: '#eda100' };
  static LABELS = { projects: 'New projects', views: 'Project views', favourites: 'New favourites', users: 'New users' };
  static METRICS = ['views', 'projects', 'favourites', 'users'];
  static CATEGORY_COLOURS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948'];
  static OTHER = '#8f8e8a';
  static UP = '#2a78d6';          // diverging pair: blue = growing, red = falling
  static DOWN = '#d03b3b';
  static INK = '#0b0b0b';
  static MUTED = '#52514e';
  static GRID = '#e8e7e2';
  static SURFACE = '#fcfcfb';
  static RAMP_LOW = [205, 226, 251];   // #cde2fb
  static RAMP_HIGH = [13, 54, 107];    // #0d366b
  static EMPTY_CELL = '#f0efec';
}

/* ---------------------------------------------------------------- shared helpers */
class GraphHelpers {
  // textContent (not innerHTML) so a category called "<b>" is shown as plain text and can never run as code.
  static cell(text, className) {
    const td = document.createElement('td');
    td.textContent = text;
    if (className) { td.className = className; }
    return td;
  }

  static fillTable(tbody, rows, lastRowClass) {
    tbody.replaceChildren();
    rows.forEach((values, index) => {
      const tr = document.createElement('tr');
      if (lastRowClass && index === rows.length - 1) { tr.className = lastRowClass; }
      values.forEach((value) => tr.appendChild(GraphHelpers.cell(value)));
      tbody.appendChild(tr);
    });
  }

  static setStatus(element, text, isError) {
    element.textContent = text || '';
    element.className = 'chart-status' + (text && isError ? ' error' : '');
  }

  static setList(list, lines) {
    list.replaceChildren();
    (lines || []).forEach((line) => {
      const li = document.createElement('li');
      li.textContent = line;
      list.appendChild(li);
    });
  }

  // A KPI card. With a `metric` it is a button (picks what the trend chart plots).
  static kpi(label, value, note, colour, noteClass, metric) {
    const box = document.createElement(metric ? 'button' : 'div');
    box.className = 'kpi';
    if (metric) { box.type = 'button'; box.dataset.metric = metric; box.setAttribute('aria-pressed', 'false'); }
    box.style.setProperty('--kpi', colour || GraphSettings.COLOURS.views);
    const l = document.createElement('span');
    l.className = 'kpi-label';
    l.textContent = label;
    const big = document.createElement('strong');
    big.textContent = value;
    box.append(l, big);
    if (note) {
      const small = document.createElement('small');
      small.textContent = note;
      if (noteClass) { small.className = noteClass; }
      box.appendChild(small);
    }
    return box;
  }

  // Add whole days to a 'YYYY-MM-DD' text, in UTC so the browser's own time zone cannot move the date.
  static addDays(isoDate, days) {
    const d = new Date(isoDate + 'T00:00:00Z');
    d.setUTCDate(d.getUTCDate() + days);
    return d.toISOString().slice(0, 10);
  }

  static shortDate(isoDate) {
    const d = new Date(isoDate + 'T00:00:00Z');
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });
  }

  static async getJson(url) {
    const response = await fetch(url, { headers: { Accept: 'application/json' } });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) { throw new Error(body.error || 'Could not load the graph data.'); }
    return body;
  }

  static withQuery(url, params) {
    const query = Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined)
      .map(([k, v]) => encodeURIComponent(k) + '=' + encodeURIComponent(v)).join('&');
    return query ? url + (url.includes('?') ? '&' : '?') + query : url;
  }

  // Replace a chart that is already on a canvas
  static draw(holder, canvas, config) {
    if (holder.chart) { holder.chart.destroy(); }
    holder.chart = new Chart(canvas, config);
    return holder.chart;
  }

  static baseOptions() {
    return {
      responsive: true, maintainAspectRatio: false, animation: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: GraphSettings.INK, usePointStyle: true, boxWidth: 8 } },
        tooltip: { backgroundColor: GraphSettings.INK, titleColor: '#fff', bodyColor: '#fff' }
      }
    };
  }

  static axis(title, extra) {
    return Object.assign({
      grid: { color: GraphSettings.GRID }, border: { display: false },
      ticks: { color: GraphSettings.MUTED },
      title: { display: !!title, text: title || '', color: GraphSettings.MUTED }
    }, extra || {});
  }

  static mix(t) {      // sequential blue: light (few) -> dark (many)
    const a = GraphSettings.RAMP_LOW, b = GraphSettings.RAMP_HIGH;
    return 'rgb(' + a.map((v, i) => Math.round(v + (b[i] - v) * t)).join(',') + ')';
  }
}

/* =============================================================== PM21 START
   Weekly activity: date controls, four KPI cards (click one to plot it), a line chart with a
   7-day average, last week, a forecast band and unusual-day markers, a weekday x hour heatmap, a table. */
class WeeklyActivityGraph {
  constructor(root) {
    this.root = root;
    this.input = root.querySelector('[data-week-end]');
    this.status = root.querySelector('[data-status]');
    this.range = root.querySelector('[data-week-range]');
    this.statsBox = root.querySelector('[data-week-stats]');
    this.tbody = root.querySelector('[data-week-table] tbody');
    this.canvas = root.querySelector('#trend-canvas');
    this.title = root.querySelector('[data-trend-title]');
    this.note = root.querySelector('[data-trend-note]');
    this.insights = root.querySelector('[data-trend-insights]');
    this.heat = root.querySelector('[data-heatmap]');
    this.heatLegend = root.querySelector('[data-heat-legend]');
    this.heatNote = root.querySelector('[data-heatmap-note]');
    this.prev = root.querySelector('[data-week-prev]');
    this.next = root.querySelector('[data-week-next]');
    this.live = root.querySelector('[data-live]');
    this.updated = root.querySelector('[data-updated]');
    this.timer = null;
    this.metric = 'views';
    this.end = '';
    this.today = '';
    this.chart = null;
    this.weekly = null;
    this.tip = null;

    this.input.addEventListener('change', () => {
      if (this.live.checked) { this.live.checked = false; this.setLive(false); }
      this.end = this.input.value; this.load();
    });
    this.prev.addEventListener('click', () => this.shift(-7));
    this.next.addEventListener('click', () => this.shift(7));
    // Live updates: while ticked, the week always ends today and everything is re-fetched every 30 seconds.
    this.live.addEventListener('change', () => this.setLive(this.live.checked));
    this.load();
  }

  setLive(on) {
    clearInterval(this.timer);
    this.timer = null;
    this.updated.textContent = '';
    if (on) {
      this.end = '';                                   // blank = today
      this.load();
      this.timer = setInterval(() => this.load(), 30000);
    }
  }

  shift(days) {
    if (!this.end) { return; }
    if (this.live.checked) { this.live.checked = false; this.setLive(false); }   // browsing the past turns live off
    this.end = GraphHelpers.addDays(this.end, days);
    if (this.today && this.end > this.today) { this.end = this.today; }
    this.load();
  }

  load() {
    GraphHelpers.setStatus(this.status, '');
    const end = this.end;
    Promise.all([
      GraphHelpers.getJson(GraphHelpers.withQuery(this.root.dataset.weeklyUrl, { end })),
      GraphHelpers.getJson(GraphHelpers.withQuery(this.root.dataset.heatmapUrl,
        { end, tz: -new Date().getTimezoneOffset() }))
    ]).then(([weekly, heat]) => {
      this.weekly = weekly;
      this.end = weekly.end;
      this.today = weekly.today;
      this.input.value = weekly.end;
      this.input.max = weekly.today;
      this.next.disabled = weekly.end >= weekly.today;
      this.range.textContent = GraphHelpers.shortDate(weekly.start) + ' to ' + GraphHelpers.shortDate(weekly.end);
      this.renderStats(weekly);
      this.renderTable(weekly);
      this.renderHeatmap(heat);
      if (this.timer) { this.updated.textContent = 'Updated ' + new Date().toLocaleTimeString(); }
      return this.loadTrend();
    }).catch((error) => GraphHelpers.setStatus(this.status, error.message, true));
  }

  loadTrend() {
    const url = GraphHelpers.withQuery(this.root.dataset.trendUrl, { metric: this.metric, end: this.end });
    return GraphHelpers.getJson(url).then((trend) => this.renderTrend(trend))
      .catch((error) => GraphHelpers.setStatus(this.status, error.message, true));
  }

  renderStats(data) {
    this.statsBox.replaceChildren();
    GraphSettings.METRICS.forEach((metric) => {
      const change = data.change[metric];
      let note = 'No previous-week data';
      let noteClass = '';
      if (change !== null && change !== undefined) {
        note = (change > 0 ? '▲ +' : change < 0 ? '▼ ' : '▬ ') + change + '% vs previous 7 days';
        noteClass = change > 0 ? 'up' : change < 0 ? 'down' : '';
      }
      const card = GraphHelpers.kpi(GraphSettings.LABELS[metric], data.totals[metric], note,
        GraphSettings.COLOURS[metric], noteClass, metric);
      card.setAttribute('aria-pressed', String(metric === this.metric));
      card.addEventListener('click', () => {
        this.metric = metric;
        this.statsBox.querySelectorAll('button.kpi').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.metric === metric)));
        this.loadTrend();
      });
      this.statsBox.appendChild(card);
    });
    if (!data.has_activity) { GraphHelpers.setStatus(this.status, 'No activity recorded in this week.'); }
  }

  renderTable(data) {
    // the table header order is projects, views, favourites, users
    GraphHelpers.fillTable(this.tbody, data.labels.map((label, i) =>
      [label, data.series.projects[i], data.series.views[i], data.series.favourites[i], data.series.users[i]])
      .concat([['Total', data.totals.projects, data.totals.views, data.totals.favourites, data.totals.users]]),
      'total-row');
  }

  renderTrend(t) {
    const colour = GraphSettings.COLOURS[t.metric];
    this.title.textContent = GraphSettings.LABELS[t.metric] + ', last 28 days';
    GraphHelpers.setList(this.insights, t.insights);
    this.note.textContent = (t.partial_today ? 'The last day is today and still in progress, so it looks lower than it will end up. ' : '')
      + (t.forecast ? 'The shaded band is the likely range for the next 7 days.' : 'The forecast only appears when the week ends today and there are at least 14 days of history.');
    if (!t.has_activity) { this.canvas.parentElement.hidden = true; return; }
    this.canvas.parentElement.hidden = false;

    const labels = t.labels.map((l) => GraphHelpers.shortDate(l)).map((l, i, all) =>
      (t.partial_today && i === all.length - 1) ? l + ' (so far)' : l);
    const forecast = t.forecast;
    const futureLabels = forecast ? forecast.labels.map((l) => GraphHelpers.shortDate(l)) : [];
    const allLabels = labels.concat(futureLabels);
    const n = labels.length;
    const pad = (arr, front) => front ? arr.concat(new Array(futureLabels.length).fill(null))
      : new Array(n).fill(null).concat(arr);

    const datasets = [
      { label: GraphSettings.LABELS[t.metric], data: pad(t.values, true), borderColor: colour, backgroundColor: colour,
        borderWidth: 2, pointRadius: 2, pointBackgroundColor: colour, tension: 0.25, order: 2 },
      { label: '7-day average', data: pad(t.moving_average, true), borderColor: GraphSettings.INK, borderWidth: 2,
        pointRadius: 0, tension: 0.35, order: 3 },
      { label: 'Previous week', data: pad(t.previous_week, true), borderColor: GraphSettings.MUTED, borderWidth: 1.5,
        borderDash: [6, 4], pointRadius: 0, tension: 0.25, order: 4 }
    ];
    if (forecast) {
      const join = n - 2;      // last complete day, so the dotted line starts where the data stops
      const line = new Array(n).fill(null).concat(forecast.values);
      const lower = new Array(n).fill(null).concat(forecast.lower);
      const upper = new Array(n).fill(null).concat(forecast.upper);
      if (join >= 0) { line[join] = t.values[join]; lower[join] = t.values[join]; upper[join] = t.values[join]; }
      datasets.push(
        { label: 'Forecast lower', data: lower, borderWidth: 0, pointRadius: 0, fill: false, order: 6 },
        { label: 'Likely range', data: upper, borderWidth: 0, pointRadius: 0, fill: '-1',
          backgroundColor: colour + '2e', order: 6 },
        { label: 'Forecast', data: line, borderColor: colour, borderWidth: 2, borderDash: [2, 4], pointRadius: 2,
          pointBackgroundColor: GraphSettings.SURFACE, pointBorderColor: colour, tension: 0.25, order: 1 });
    }
    const flagged = new Array(allLabels.length).fill(null);
    t.anomalies.forEach((a) => { if (a.index >= 0 && a.index < n) { flagged[a.index] = a.value; } });
    datasets.push({ label: 'Unusual day', data: flagged, showLine: false, pointStyle: 'triangle', pointRadius: 8,
      pointBackgroundColor: GraphSettings.DOWN, pointBorderColor: GraphSettings.SURFACE, pointBorderWidth: 2, order: 0 });

    const options = GraphHelpers.baseOptions();
    options.interaction = { mode: 'index', intersect: false };
    options.plugins.legend.labels.filter = (item) => item.text !== 'Forecast lower';
    options.scales = {
      x: GraphHelpers.axis('', { grid: { display: false }, ticks: { color: GraphSettings.MUTED, maxTicksLimit: 10 } }),
      y: GraphHelpers.axis(GraphSettings.LABELS[t.metric], { beginAtZero: true })
    };
    GraphHelpers.draw(this, this.canvas, { type: 'line', data: { labels: allLabels, datasets }, options });
  }

  // Weekday x hour grid. One hue, light to dark; a hover label gives the exact count.
  renderHeatmap(h) {
    this.heat.replaceChildren();
    this.heatLegend.replaceChildren();
    if (!h.total) {
      this.heatNote.textContent = 'No project views in these 28 days.';
      return;
    }
    const hours = (h.offset / 60);
    const zone = 'UTC' + (hours >= 0 ? '+' : '') + (Number.isInteger(hours) ? hours : hours.toFixed(1));
    const peak = h.peak;
    this.heatNote.textContent = 'Project views per weekday and hour (' + zone + ') over the 28 days ending '
      + GraphHelpers.shortDate(h.end) + '.' + (peak ? ' Busiest: ' + peak.day + ' at ' + String(peak.hour).padStart(2, '0') + ':00 (' + peak.count + ' views).' : '');
    const corner = document.createElement('div');
    this.heat.appendChild(corner);
    for (let hour = 0; hour < 24; hour++) {
      const el = document.createElement('div');
      el.className = 'hour';
      el.textContent = hour % 3 === 0 ? String(hour) : '';
      this.heat.appendChild(el);
    }
    h.days.forEach((day, d) => {
      const label = document.createElement('div');
      label.className = 'day';
      label.textContent = day;
      this.heat.appendChild(label);
      for (let hour = 0; hour < 24; hour++) {
        const count = h.grid[d][hour];
        const cell = document.createElement('div');
        cell.className = 'cell';
        cell.style.background = count ? GraphHelpers.mix(0.12 + 0.88 * count / h.max) : GraphSettings.EMPTY_CELL;
        const text = day + ' ' + String(hour).padStart(2, '0') + ':00 – ' + count + ' view' + (count === 1 ? '' : 's');
        cell.setAttribute('aria-label', text);
        cell.addEventListener('mouseenter', (e) => this.showTip(e, text));
        cell.addEventListener('mousemove', (e) => this.moveTip(e));
        cell.addEventListener('mouseleave', () => this.hideTip());
        this.heat.appendChild(cell);
      }
    });
    const less = document.createElement('span'); less.textContent = 'Fewer';
    this.heatLegend.appendChild(less);
    [0, 0.25, 0.5, 0.75, 1].forEach((t) => {
      const s = document.createElement('span');
      s.className = 'swatch';
      s.style.background = GraphHelpers.mix(0.12 + 0.88 * t);
      this.heatLegend.appendChild(s);
    });
    const more = document.createElement('span'); more.textContent = 'More views (max ' + h.max + ')';
    this.heatLegend.appendChild(more);
  }

  showTip(event, text) {
    this.hideTip();
    this.tip = document.createElement('div');
    this.tip.className = 'heat-tip';
    this.tip.textContent = text;
    document.body.appendChild(this.tip);
    this.moveTip(event);
  }
  moveTip(event) { if (this.tip) { this.tip.style.left = (event.clientX + 12) + 'px'; this.tip.style.top = (event.clientY + 12) + 'px'; } }
  hideTip() { if (this.tip) { this.tip.remove(); this.tip = null; } }
}
/* PM21 END */

/* =============================================================== PM21 START
   Category interest: headline cards, insight sentences, bubble chart (views vs shortlist rate),
   stacked area (weekly views, top 5 + Other), diverging growth bars and a table. */
class CategoryInterestGraph {
  constructor(root) {
    this.root = root;
    this.status = root.querySelector('[data-status]');
    this.statsBox = root.querySelector('[data-category-stats]');
    this.insights = root.querySelector('[data-category-insights]');
    this.tbody = root.querySelector('[data-category-table] tbody');
    this.growthBox = root.querySelector('[data-growth-box]');
    this.bubble = { canvas: root.querySelector('#bubble-canvas'), chart: null };
    this.area = { canvas: root.querySelector('#area-canvas'), chart: null };
    this.growth = { canvas: root.querySelector('#growth-canvas'), chart: null };
    GraphHelpers.getJson(root.dataset.url)
      .then((data) => this.render(data))
      .catch((error) => GraphHelpers.setStatus(this.status, error.message, true));
    GraphHelpers.getJson(root.dataset.trendUrl)
      .then((data) => this.renderTrend(data))
      .catch((error) => GraphHelpers.setStatus(this.status, error.message, true));
  }

  render(data) {
    const categories = data.categories;
    GraphHelpers.fillTable(this.tbody, categories.map((c) =>
      [c.active ? c.name : c.name + ' (inactive)', c.projects, c.views, c.favourites,
       c.shortlist_rate + '%', c.share_of_views + '%']));
    this.statsBox.replaceChildren();
    this.statsBox.appendChild(GraphHelpers.kpi('Most viewed category',
      data.top_viewed ? data.top_viewed.name : '–',
      data.top_viewed ? data.top_viewed.count + ' views' : 'No views yet', GraphSettings.COLOURS.views));
    this.statsBox.appendChild(GraphHelpers.kpi('Most shortlisted category',
      data.top_shortlisted ? data.top_shortlisted.name : '–',
      data.top_shortlisted ? data.top_shortlisted.count + ' shortlists' : 'No shortlists yet', GraphSettings.COLOURS.favourites));
    GraphHelpers.setList(this.insights, data.insights);
    if (!categories.length) { GraphHelpers.setStatus(this.status, 'No categories have been created yet.'); return; }
    if (!data.has_data) { GraphHelpers.setStatus(this.status, 'No views or shortlists recorded yet.'); return; }
    this.renderBubbles(categories.filter((c) => c.views > 0));
  }

  // x = views, y = shortlist rate, size = projects. Bottom right = looked at a lot, rarely saved.
  renderBubbles(items) {
    const maxProjects = Math.max(1, ...items.map((c) => c.projects));
    const radius = (c) => 6 + 16 * Math.sqrt(c.projects / maxProjects);
    const labelled = new Set(items.slice().sort((a, b) => b.views - a.views).slice(0, 6).map((c) => c.name));
    const lowest = items.filter((c) => c.views >= 10).sort((a, b) => a.shortlist_rate - b.shortlist_rate)[0];
    if (lowest) { labelled.add(lowest.name); }
    const names = {
      id: 'bubbleNames',
      afterDatasetsDraw(chart) {
        const ctx = chart.ctx;
        ctx.save();
        ctx.font = '12px system-ui, sans-serif';
        ctx.fillStyle = GraphSettings.INK;
        ctx.textBaseline = 'middle';
        chart.getDatasetMeta(0).data.forEach((point, i) => {
          if (!labelled.has(items[i].name)) { return; }
          const r = point.options.radius || 8;
          const right = point.x + r + 4 + ctx.measureText(items[i].name).width < chart.chartArea.right;
          ctx.textAlign = right ? 'left' : 'right';
          ctx.fillText(items[i].name, right ? point.x + r + 4 : point.x - r - 4, point.y);
        });
        ctx.restore();
      }
    };
    const options = GraphHelpers.baseOptions();
    options.plugins.legend.display = false;
    options.plugins.tooltip.callbacks = {
      title: (c) => items[c[0].dataIndex].name,
      label: (c) => { const i = items[c.dataIndex];
        return [i.views + ' views', i.favourites + ' shortlists (' + i.shortlist_rate + '%)', i.projects + ' projects']; }
    };
    options.scales = {
      x: GraphHelpers.axis('Project views', { beginAtZero: true }),
      y: GraphHelpers.axis('Shortlist rate (%)', { beginAtZero: true })
    };
    GraphHelpers.draw(this.bubble, this.bubble.canvas, {
      type: 'bubble', plugins: [names], options,
      data: { datasets: [{ label: 'Categories', data: items.map((c) => ({ x: c.views, y: c.shortlist_rate, r: radius(c) })),
        backgroundColor: GraphSettings.COLOURS.views + 'b3', borderColor: GraphSettings.SURFACE, borderWidth: 2 }] }
    });
  }

  renderTrend(data) {
    if (!data.has_data) { this.area.canvas.parentElement.hidden = true; this.growthBox.hidden = true; return; }
    GraphHelpers.setList(this.insights, (this.insights ? Array.from(this.insights.children).map((li) => li.textContent) : []).concat(data.insights));
    const labels = data.labels.map((l) => 'Week of ' + GraphHelpers.shortDate(l));
    const datasets = data.series.map((s, i) => {
      const colour = s.name === 'Other' && s.id === null ? GraphSettings.OTHER : GraphSettings.CATEGORY_COLOURS[i % 8];
      return { label: s.name, data: s.data, fill: true, borderColor: GraphSettings.SURFACE, borderWidth: 2,
        backgroundColor: colour + 'cc', pointRadius: 0, tension: 0.25 };
    });
    const options = GraphHelpers.baseOptions();
    options.interaction = { mode: 'index', intersect: false };
    options.scales = {
      x: GraphHelpers.axis('', { grid: { display: false } }),
      y: GraphHelpers.axis('Views per week', { stacked: true, beginAtZero: true })
    };
    GraphHelpers.draw(this.area, this.area.canvas, { type: 'line', data: { labels, datasets }, options });

    // growth: one bar per category, blue = growing, red = cooling, categories with no earlier views are left out
    const rows = data.growth.filter((g) => g.change !== null);
    this.growthBox.hidden = !rows.length;
    this.growthBox.style.height = Math.max(160, rows.length * 30 + 60) + 'px';
    if (!rows.length) { return; }
    const growthOptions = GraphHelpers.baseOptions();
    growthOptions.indexAxis = 'y';
    growthOptions.plugins.legend.display = false;
    growthOptions.plugins.tooltip.callbacks = {
      label: (c) => { const g = rows[c.dataIndex];
        return (g.change > 0 ? '+' : '') + g.change + '% (' + g.previous + ' to ' + g.recent + ' views)'; }
    };
    growthOptions.scales = {
      x: GraphHelpers.axis('Change in views (%)'),
      y: GraphHelpers.axis('', { grid: { display: false } })
    };
    GraphHelpers.draw(this.growth, this.growth.canvas, {
      type: 'bar', options: growthOptions,
      data: { labels: rows.map((g) => g.name), datasets: [{ data: rows.map((g) => g.change),
        backgroundColor: rows.map((g) => g.change >= 0 ? GraphSettings.UP : GraphSettings.DOWN),
        borderRadius: 4, barThickness: 16 }] }
    });
  }
}
/* PM21 END */

/* =============================================================== PM24 RATINGS START
   Platform-wide review picture: how many reviews at each star level, and the average per month. */
class RatingsOverviewGraph {
  constructor(root) {
    this.root = root;
    this.status = root.querySelector('[data-status]');
    this.statsBox = root.querySelector('[data-ratings-stats]');
    this.dist = { canvas: root.querySelector('#ratings-dist-canvas'), chart: null };
    this.month = { canvas: root.querySelector('#ratings-month-canvas'), chart: null };
    GraphHelpers.getJson(root.dataset.url).then((d) => this.render(d))
      .catch((error) => GraphHelpers.setStatus(this.status, error.message, true));
  }

  render(data) {
    this.statsBox.replaceChildren();
    this.statsBox.appendChild(GraphHelpers.kpi('Visible reviews', data.total, '', GraphSettings.COLOURS.views));
    this.statsBox.appendChild(GraphHelpers.kpi('Average rating',
      data.average === null ? '–' : data.average + ' / 5', '', GraphSettings.COLOURS.projects));
    if (!data.total) {
      GraphHelpers.setStatus(this.status, 'No reviews yet.');
      this.dist.canvas.parentElement.hidden = true;
      this.month.canvas.parentElement.hidden = true;
      return;
    }
    const stars = [5, 4, 3, 2, 1];
    const options = GraphHelpers.baseOptions();
    options.indexAxis = 'y';
    options.plugins.legend.display = false;
    options.scales = { x: GraphHelpers.axis('Reviews', { beginAtZero: true, ticks: { precision: 0, color: GraphSettings.MUTED } }),
      y: GraphHelpers.axis('', { grid: { display: false } }) };
    GraphHelpers.draw(this.dist, this.dist.canvas, { type: 'bar', options, data: {
      labels: stars.map((s) => s + (s === 1 ? ' star' : ' stars')),
      datasets: [{ data: stars.map((s) => data.distribution[s]), backgroundColor: GraphSettings.COLOURS.views,
        borderRadius: 4, barThickness: 16 }] } });

    const monthOptions = GraphHelpers.baseOptions();
    monthOptions.plugins.legend.display = false;
    monthOptions.plugins.tooltip.callbacks = {
      label: (c) => (c.parsed.y === null ? 'No reviews' : c.parsed.y + ' average from ' + data.monthly[c.dataIndex].count + ' reviews') };
    monthOptions.scales = { x: GraphHelpers.axis('', { grid: { display: false } }),
      y: GraphHelpers.axis('Average rating', { min: 1, max: 5, ticks: { stepSize: 1, color: GraphSettings.MUTED } }) };
    GraphHelpers.draw(this.month, this.month.canvas, { type: 'line', options: monthOptions, data: {
      labels: data.monthly.map((m) => m.label),
      datasets: [{ data: data.monthly.map((m) => m.average), borderColor: GraphSettings.COLOURS.views,
        backgroundColor: GraphSettings.COLOURS.views, borderWidth: 2, pointRadius: 4, spanGaps: true, tension: 0.2 }] } });
  }
}
/* PM24 RATINGS END */

class PlatformGraphsPage {
  static start() {
    const weekly = document.getElementById('weekly-chart');
    const category = document.getElementById('category-chart');
    const ratings = document.getElementById('ratings-chart');
    if (typeof Chart === 'undefined') { return; }
    if (weekly) { new WeeklyActivityGraph(weekly); }
    if (category) { new CategoryInterestGraph(category); }
    if (ratings) { new RatingsOverviewGraph(ratings); }
  }
}
// The only top-level statement: run once the page has loaded.
document.addEventListener('DOMContentLoaded', PlatformGraphsPage.start);
