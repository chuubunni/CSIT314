/* Platform manager graphs: PM21 (weekly activity) and PM23 (interest by category).
   Both read JSON from the boundary routes in boundaries/platform_charts.py. */
(function () {
  'use strict';

  // One colour per measure, distinguishable for colour-blind viewers
  var COLOURS = {
    projects: '#377ba8',
    views: '#e69f00',
    favourites: '#009e73',
    users: '#cc79a7'
  };
  var LABELS = {
    projects: 'New projects',
    views: 'Project views',
    favourites: 'New favourites',
    users: 'New users'
  };
  var METRICS = ['projects', 'views', 'favourites', 'users'];

  function cell(text) {
    var td = document.createElement('td');
    td.textContent = text;           // textContent, never innerHTML
    return td;
  }

  function fillTable(tbody, rows) {
    tbody.replaceChildren();
    rows.forEach(function (values) {
      var tr = document.createElement('tr');
      values.forEach(function (value) { tr.appendChild(cell(value)); });
      tbody.appendChild(tr);
    });
  }

  function addDays(isoDate, days) {
    var d = new Date(isoDate + 'T00:00:00Z');
    d.setUTCDate(d.getUTCDate() + days);
    return d.toISOString().slice(0, 10);
  }

  async function getJson(url) {
    var response = await fetch(url, { headers: { Accept: 'application/json' } });
    var body = await response.json().catch(function () { return {}; });
    if (!response.ok) { throw new Error(body.error || 'Could not load the graph data.'); }
    return body;
  }

  /* ---------------------------------------------------------------- PM21 */
  function initWeekly(root) {
    var input = root.querySelector('[data-week-end]');
    var status = root.querySelector('[data-status]');
    var range = root.querySelector('[data-week-range]');
    var statsBox = root.querySelector('[data-week-stats]');
    var tbody = root.querySelector('[data-week-table] tbody');
    var chartsBox = root.querySelector('[data-week-charts]');
    var charts = [];
    var current = null;

    function renderStats(data) {
      statsBox.replaceChildren();
      METRICS.forEach(function (metric) {
        var box = document.createElement('div');
        box.className = 'manager-stat';
        box.appendChild(document.createTextNode(LABELS[metric]));
        var total = document.createElement('strong');
        total.textContent = data.totals[metric];
        box.appendChild(total);

        var change = data.change[metric];
        var note = document.createElement('small');
        if (change === null) {
          note.textContent = 'No previous-week data';
        } else {
          note.textContent = (change > 0 ? '+' : '') + change + '% vs previous week';
          note.className = change > 0 ? 'up' : (change < 0 ? 'down' : '');
        }
        box.appendChild(note);
        statsBox.appendChild(box);
      });
    }

    // One small chart per measure, each with its own scale. On a single shared axis the
    // views (hundreds a day) would squash projects and users flat against zero.
    function renderCharts(data) {
      charts.forEach(function (chart) { chart.destroy(); });
      charts = [];
      chartsBox.replaceChildren();
      METRICS.forEach(function (metric) {
        var cellBox = document.createElement('div');
        var title = document.createElement('h3');
        title.textContent = LABELS[metric];
        var holder = document.createElement('div');
        holder.className = 'chart-box-small';
        var canvas = document.createElement('canvas');
        canvas.setAttribute('role', 'img');
        canvas.setAttribute('aria-label', LABELS[metric] + ' per day for the selected week');
        holder.appendChild(canvas);
        cellBox.appendChild(title);
        cellBox.appendChild(holder);
        chartsBox.appendChild(cellBox);

        charts.push(new Chart(canvas, {
          type: 'bar',
          data: {
            labels: data.labels.map(function (label) { return label.slice(5); }),   // MM-DD
            datasets: [{ label: LABELS[metric], data: data.series[metric], backgroundColor: COLOURS[metric] }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
          }
        }));
      });
    }

    async function load(end) {
      status.textContent = '';
      var url = root.dataset.url + (end ? '?end=' + encodeURIComponent(end) : '');
      try {
        var data = await getJson(url);
      } catch (error) {
        status.textContent = error.message;
        return;
      }
      current = data;
      input.value = data.end;
      input.max = data.today;
      range.textContent = data.start + ' to ' + data.end;
      renderStats(data);
      renderCharts(data);
      fillTable(tbody, data.labels.map(function (label, i) {
        return [label].concat(METRICS.map(function (metric) { return data.series[metric][i]; }));
      }));
      if (!data.has_activity) { status.textContent = 'No activity recorded in this week.'; }
    }

    input.addEventListener('change', function () { load(input.value); });
    root.querySelector('[data-week-prev]').addEventListener('click', function () {
      if (current) { load(addDays(current.end, -7)); }
    });
    root.querySelector('[data-week-next]').addEventListener('click', function () {
      if (!current) { return; }
      var next = addDays(current.end, 7);
      // never ask for a week that ends in the future: clamp to today
      load(next > current.today ? current.today : next);
    });
    load('');
  }

  /* ---------------------------------------------------------------- PM23 */
  function initCategories(root) {
    var status = root.querySelector('[data-status]');
    var tbody = root.querySelector('[data-category-table] tbody');

    getJson(root.dataset.url).then(function (data) {
      var categories = data.categories;
      fillTable(tbody, categories.map(function (c) {
        return [c.active ? c.name : c.name + ' (inactive)', c.projects, c.views, c.favourites];
      }));
      if (!categories.length) { status.textContent = 'No categories have been created yet.'; return; }
      if (!data.has_data) { status.textContent = 'No views or shortlists recorded yet.'; }

      new Chart(root.querySelector('canvas'), {
        type: 'bar',
        data: {
          labels: categories.map(function (c) { return c.name; }),
          datasets: [
            { label: 'Project views', data: categories.map(function (c) { return c.views; }),
              backgroundColor: COLOURS.views },
            { label: 'Shortlists', data: categories.map(function (c) { return c.favourites; }),
              backgroundColor: COLOURS.favourites }
          ]
        },
        options: {
          indexAxis: 'y',            // horizontal bars: long category names stay readable
          responsive: true,
          maintainAspectRatio: false,
          scales: { x: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: 'Count' } } }
        }
      });
    }).catch(function (error) { status.textContent = error.message; });
  }

  document.addEventListener('DOMContentLoaded', function () {
    var weekly = document.getElementById('weekly-chart');
    var categories = document.getElementById('category-chart');
    if (weekly) { initWeekly(weekly); }
    if (categories) { initCategories(categories); }
  });
})();
