/* Platform manager graphs: PM21 (weekly activity) and PM23 (interest by category).
   Everything lives in classes. Both graphs ask the boundary (boundaries/platform_charts.py)
   for JSON, then draw it with Chart.js.
   Search this file for "PM21 START" or "PM23 START" to find each user story. */
'use strict';

/* ---------------------------------------------------------------- shared settings */
class GraphSettings {
  // One colour per measure. These four are easy to tell apart for colour-blind viewers.
  static COLOURS = {
    projects: '#377ba8',
    views: '#e69f00',
    favourites: '#009e73',
    users: '#cc79a7'
  };
  static LABELS = {
    projects: 'New projects',
    views: 'Project views',
    favourites: 'New favourites',
    users: 'New users'
  };
  static METRICS = ['projects', 'views', 'favourites', 'users'];
}

/* ---------------------------------------------------------------- shared helpers */
class GraphHelpers {
  // Build a table cell. textContent (not innerHTML) so a category called "<b>" is shown
  // as plain text and can never run as code.
  static cell(text, className) {
    const td = document.createElement('td');
    td.textContent = text;
    if (className) { td.className = className; }
    return td;
  }

  // Replace the rows of a table body. `rows` is a list of lists of values.
  // `lastRowClass` lets us style a final "Total" row differently.
  static fillTable(tbody, rows, lastRowClass) {
    tbody.replaceChildren();
    rows.forEach((values, index) => {
      const tr = document.createElement('tr');
      if (lastRowClass && index === rows.length - 1) { tr.className = lastRowClass; }
      values.forEach((value) => tr.appendChild(GraphHelpers.cell(value)));
      tbody.appendChild(tr);
    });
  }

  // Show a message under the heading. isError = red; otherwise a calm grey note.
  static setStatus(element, text, isError) {
    element.textContent = text || '';
    element.className = 'chart-status' + (text && isError ? ' error' : '');
  }

  // A stat card: small label, big number, and an optional small note underneath.
  static statBox(label, value, note, metric, noteClass) {
    const box = document.createElement('div');
    box.className = 'manager-stat';
    if (metric) { box.dataset.metric = metric; }      // CSS uses this for the coloured edge
    box.appendChild(document.createTextNode(label));
    const big = document.createElement('strong');
    big.textContent = value;
    box.appendChild(big);
    if (note) {
      const small = document.createElement('small');
      small.textContent = note;
      if (noteClass) { small.className = noteClass; }
      box.appendChild(small);
    }
    return box;
  }

  // Add (or take away) whole days from a 'YYYY-MM-DD' text. Done in UTC so the
  // browser's own time zone cannot move the date by one day.
  static addDays(isoDate, days) {
    const d = new Date(isoDate + 'T00:00:00Z');
    d.setUTCDate(d.getUTCDate() + days);
    return d.toISOString().slice(0, 10);
  }

  // Ask the server for JSON. If the server answered with an error (like 400) we throw
  // an Error carrying the server's message, so the caller can show it to the manager.
  static async getJson(url) {
    const response = await fetch(url, { headers: { Accept: 'application/json' } });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) { throw new Error(body.error || 'Could not load the graph data.'); }
    return body;
  }
}

/* =============================================================== PM21 START
   Weekly platform activity: a date picker, previous/next week buttons, four stat
   cards (with the change vs the week before), four small graphs and a table. */
class WeeklyActivityGraph {
  constructor(root) {
    this.root = root;
    this.input = root.querySelector('[data-week-end]');
    this.status = root.querySelector('[data-status]');
    this.range = root.querySelector('[data-week-range]');
    this.statsBox = root.querySelector('[data-week-stats]');
    this.tbody = root.querySelector('[data-week-table] tbody');
    this.chartsBox = root.querySelector('[data-week-charts]');
    this.charts = [];       // the Chart objects currently on the page
    this.current = null;    // the data for the week currently shown

    this.bindButtons();
    this.load('');          // first load: the 7 days ending today
  }

  // Date picker, "Previous week" and "Next week"
  bindButtons() {
    this.input.addEventListener('change', () => this.load(this.input.value));
    this.root.querySelector('[data-week-prev]').addEventListener('click', () => {
      if (this.current) { this.load(GraphHelpers.addDays(this.current.end, -7)); }
    });
    this.root.querySelector('[data-week-next]').addEventListener('click', () => {
      if (!this.current) { return; }
      const next = GraphHelpers.addDays(this.current.end, 7);
      // never ask for a week that ends in the future: stop at today instead
      this.load(next > this.current.today ? this.current.today : next);
    });
  }

  // Four cards: this week's total and the % change compared with the previous week.
  renderStats(data) {
    this.statsBox.replaceChildren();
    GraphSettings.METRICS.forEach((metric) => {
      const change = data.change[metric];
      let note;
      let noteClass;
      if (change === null) {
        note = 'No previous-week data';          // previous week was 0: no % possible
      } else if (change > 0) {
        note = '\u25B2 ' + change + '% vs previous week'; noteClass = 'up';
      } else if (change < 0) {
        note = '\u25BC ' + Math.abs(change) + '% vs previous week'; noteClass = 'down';
      } else {
        note = 'No change vs previous week';
      }
      this.statsBox.appendChild(GraphHelpers.statBox(
        GraphSettings.LABELS[metric], data.totals[metric], note, metric, noteClass));
    });
  }

  // One small graph per measure, each with its own scale. On one shared scale the
  // views (hundreds a day) would squash projects and users flat against zero.
  renderCharts(data) {
    // Chart.js keeps every chart alive until told otherwise, so remove the old ones
    // before drawing the new week. Otherwise they pile up and flicker when hovered.
    this.charts.forEach((chart) => chart.destroy());
    this.charts = [];
    this.chartsBox.replaceChildren();

    GraphSettings.METRICS.forEach((metric) => {
      const card = document.createElement('div');
      card.className = 'chart-card';
      const title = document.createElement('h3');
      title.textContent = GraphSettings.LABELS[metric];
      const holder = document.createElement('div');
      holder.className = 'chart-box-small';
      const canvas = document.createElement('canvas');
      canvas.setAttribute('role', 'img');
      canvas.setAttribute('aria-label', GraphSettings.LABELS[metric] + ' per day for the selected week');
      holder.appendChild(canvas);
      card.appendChild(title);
      card.appendChild(holder);
      this.chartsBox.appendChild(card);

      this.charts.push(new Chart(canvas, {
        type: 'bar',
        data: {
          // '2026-10-22' -> '10-22' (month-day only, so the labels fit)
          labels: data.labels.map((label) => label.slice(5)),
          datasets: [{ label: GraphSettings.LABELS[metric], data: data.series[metric],
                       backgroundColor: GraphSettings.COLOURS[metric], borderRadius: 3 }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          // precision 0: counts are whole numbers, so no "0.5 views" on the axis
          scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
        }
      }));
    });
  }

  // Load one week from the server and redraw everything. `end` empty = today.
  async load(end) {
    GraphHelpers.setStatus(this.status, '');
    const url = this.root.dataset.url + (end ? '?end=' + encodeURIComponent(end) : '');
    let data;
    try {
      data = await GraphHelpers.getJson(url);
    } catch (error) {
      GraphHelpers.setStatus(this.status, error.message, true);
      return;
    }
    this.current = data;
    this.input.value = data.end;
    this.input.max = data.today;               // the date picker will not offer future days
    this.range.textContent = data.start + ' to ' + data.end;
    this.renderStats(data);
    this.renderCharts(data);

    const rows = data.labels.map((label, i) =>
      [label].concat(GraphSettings.METRICS.map((metric) => data.series[metric][i])));
    rows.push(['Total'].concat(GraphSettings.METRICS.map((metric) => data.totals[metric])));
    GraphHelpers.fillTable(this.tbody, rows, 'total-row');

    if (!data.has_activity) { GraphHelpers.setStatus(this.status, 'No activity recorded in this week.'); }
  }
}
/* PM21 END */

/* =============================================================== PM23 START
   Project interest by design category: headline cards, a horizontal bar graph of
   views and shortlists per category, and a table with the exact numbers. */
class CategoryInterestGraph {
  constructor(root) {
    this.root = root;
    this.status = root.querySelector('[data-status]');
    this.statsBox = root.querySelector('[data-category-stats]');
    this.box = root.querySelector('[data-category-box]');
    this.tbody = root.querySelector('[data-category-table] tbody');
    this.load();
  }

  load() {
    GraphHelpers.getJson(this.root.dataset.url)
      .then((data) => this.render(data))
      .catch((error) => GraphHelpers.setStatus(this.status, error.message, true));
  }

  render(data) {
    const categories = data.categories;

    GraphHelpers.fillTable(this.tbody, categories.map((c) =>
      [c.active ? c.name : c.name + ' (inactive)', c.projects, c.views,
       c.favourites, c.share_of_views + '%']));

    if (!categories.length) {
      this.box.hidden = true;
      GraphHelpers.setStatus(this.status, 'No categories have been created yet.');
      return;
    }
    if (!data.has_data) { GraphHelpers.setStatus(this.status, 'No views or shortlists recorded yet.'); }

    this.renderHeadlines(data);
    this.renderChart(categories);
  }

  // Headline answers: which category is looked at most, and saved most
  renderHeadlines(data) {
    this.statsBox.replaceChildren();
    this.statsBox.appendChild(GraphHelpers.statBox('Most viewed category',
      data.top_viewed ? data.top_viewed.name : '\u2013',
      data.top_viewed ? data.top_viewed.count + ' views' : 'No views yet', 'views'));
    this.statsBox.appendChild(GraphHelpers.statBox('Most shortlisted category',
      data.top_shortlisted ? data.top_shortlisted.name : '\u2013',
      data.top_shortlisted ? data.top_shortlisted.count + ' shortlists' : 'No shortlists yet', 'favourites'));
  }

  renderChart(categories) {
    // Give each category about 36px of height so long lists stay readable
    this.box.style.height = Math.max(320, categories.length * 36 + 90) + 'px';

    new Chart(this.root.querySelector('canvas'), {
      type: 'bar',
      data: {
        labels: categories.map((c) => c.name),
        datasets: [
          { label: 'Project views', data: categories.map((c) => c.views),
            backgroundColor: GraphSettings.COLOURS.views, borderRadius: 3 },
          { label: 'Shortlists', data: categories.map((c) => c.favourites),
            backgroundColor: GraphSettings.COLOURS.favourites, borderRadius: 3 }
        ]
      },
      options: {
        indexAxis: 'y',            // horizontal bars: long category names stay readable
        responsive: true,
        maintainAspectRatio: false,
        scales: { x: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: 'Count' } } }
      }
    });
  }
}
/* PM23 END */

/* ---------------------------------------------------------------- page start-up */
class PlatformGraphsPage {
  // Start whichever sections exist on the page
  static start() {
    const weekly = document.getElementById('weekly-chart');
    const categories = document.getElementById('category-chart');
    if (weekly) { new WeeklyActivityGraph(weekly); }
    if (categories) { new CategoryInterestGraph(categories); }
  }
}

// The one line that is not inside a class: the browser needs something to call when the
// page has loaded. It does nothing except hand over to the class above.
document.addEventListener('DOMContentLoaded', () => PlatformGraphsPage.start());