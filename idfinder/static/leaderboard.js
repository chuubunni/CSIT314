/* Designer leaderboard: live re-ranking with weight sliders + a radar chart to compare designers.
   Search this file for "RANKING" (the same maths as controller/ranking.py) or "RADAR".
   The numbers come from the page itself (<script id="leaderboard-data">), so the sliders never
   need to ask the server. */
'use strict';

class Leaderboard {
  constructor() {
    const node = document.getElementById('leaderboard-data');
    if (!node) { return; }
    this.data = JSON.parse(node.textContent);
    this.weights = Object.assign({}, this.data.weights);
    this.defaults = Object.assign({}, this.data.weights);
    this.selected = [];                                   // ids ticked for the radar chart
    this.tbody = document.querySelector('[data-leaderboard] tbody');
    this.hint = document.querySelector('[data-compare-hint]');
    this.radar = null;
    this.colours = ['#377ba8', '#e69f00', '#009e73'];
    this.bindSliders();
    this.render();
  }

  /* ----- RANKING: same rules as ranking.score() / ranking.rank() on the server ----- */
  score(row) {
    const total = this.data.components.reduce((s, c) => s + this.weights[c], 0);
    if (!total) { return 0; }
    const sum = this.data.components.reduce((s, c) => s + row.components[c] * this.weights[c], 0);
    return Math.round(sum / total * 1000) / 10;
  }

  ranked() {
    const rows = this.data.rows.map((r) => Object.assign({}, r, { live: this.score(r) }));
    rows.sort((a, b) => b.live - a.live || b.reviews - a.reviews ||
                        a.name.toLowerCase().localeCompare(b.name.toLowerCase()) || a.id - b.id);
    let previous = null, previousRank = 0;
    rows.forEach((r, i) => {                              // equal scores share a rank
      r.liveRank = r.live === previous ? previousRank : i + 1;
      previous = r.live; previousRank = r.liveRank;
    });
    return rows;
  }

  bindSliders() {
    document.querySelectorAll('[data-weight]').forEach((input) => {
      input.addEventListener('input', () => {
        this.weights[input.dataset.weight] = Number(input.value);
        document.querySelector(`[data-weight-out="${input.dataset.weight}"]`).textContent = input.value;
        this.render();
      });
    });
    const reset = document.querySelector('[data-reset-weights]');
    if (reset) {
      reset.addEventListener('click', () => {
        this.weights = Object.assign({}, this.defaults);
        document.querySelectorAll('[data-weight]').forEach((input) => {
          input.value = this.defaults[input.dataset.weight];
          document.querySelector(`[data-weight-out="${input.dataset.weight}"]`).textContent = input.value;
        });
        this.render();
      });
    }
  }

  /* ----- the table ----- */
  cell(text) { const td = document.createElement('td'); td.textContent = text; return td; }

  render() {
    const rows = this.ranked();
    this.tbody.replaceChildren();
    if (!rows.length) {
      const tr = document.createElement('tr'); const td = this.cell('No designers match these filters.');
      td.colSpan = 7; tr.appendChild(td); this.tbody.appendChild(tr);
    }
    rows.forEach((r) => {
      const tr = document.createElement('tr');
      tr.appendChild(this.cell(r.liveRank));

      const nameCell = document.createElement('td');
      const link = document.createElement('a');
      link.href = '/designers/' + r.id; link.textContent = r.name;
      nameCell.appendChild(link);
      if (r.company) { const small = document.createElement('small'); small.className = 'muted'; small.textContent = ' ' + r.company; nameCell.appendChild(small); }
      tr.appendChild(nameCell);

      tr.appendChild(this.scoreCell(r));
      tr.appendChild(this.cell(r.reviews ? `${r.avg_rating.toFixed(1)} ★ (${r.reviews})` : '–'));
      tr.appendChild(this.cell(r.conversion === null ? '–' : r.conversion + '%'));
      tr.appendChild(this.cell(r.completed_jobs));

      const pick = document.createElement('td');
      const box = document.createElement('input');
      box.type = 'checkbox'; box.checked = this.selected.includes(r.id);
      box.setAttribute('aria-label', 'Compare ' + r.name);
      box.addEventListener('change', () => this.toggle(r.id, box));
      pick.appendChild(box); tr.appendChild(pick);
      this.tbody.appendChild(tr);
    });
    this.drawRadar();
  }

  /* a score number with a bar split into the five parts, so the reader sees WHY */
  scoreCell(r) {
    const td = document.createElement('td');
    const total = this.data.components.reduce((s, c) => s + this.weights[c], 0) || 1;
    const bar = document.createElement('div'); bar.className = 'rv-stack';
    bar.title = this.data.components.map((c) =>
      `${this.data.labels[c]}: ${(r.components[c] * this.weights[c] / total * 100).toFixed(1)} pts`).join('\n');
    this.data.components.forEach((c, i) => {
      const part = document.createElement('span');
      part.className = 'part part-' + i;
      part.style.width = (r.components[c] * this.weights[c] / total * 100) + '%';
      bar.appendChild(part);
    });
    const label = document.createElement('strong'); label.textContent = r.live.toFixed(1);
    td.append(label, bar);
    return td;
  }

  toggle(id, box) {
    if (box.checked) {
      if (this.selected.length >= 3) { box.checked = false; return; }   // at most 3 on the radar
      this.selected.push(id);
    } else {
      this.selected = this.selected.filter((x) => x !== id);
    }
    this.drawRadar();
  }

  /* ----- RADAR: the five components of the ticked designers ----- */
  drawRadar() {
    const canvas = document.getElementById('rv-radar');
    if (!canvas || typeof Chart === 'undefined') { return; }
    if (this.hint) { this.hint.hidden = this.selected.length > 0; }
    const chosen = this.selected.map((id) => this.data.rows.find((r) => r.id === id)).filter(Boolean);
    const datasets = chosen.map((r, i) => ({
      label: r.name,
      data: this.data.components.map((c) => Math.round(r.components[c] * 100)),
      borderColor: this.colours[i], backgroundColor: this.colours[i] + '33', pointBackgroundColor: this.colours[i],
    }));
    if (this.radar) { this.radar.destroy(); this.radar = null; }
    this.radar = new Chart(canvas, {
      type: 'radar',
      data: { labels: this.data.components.map((c) => this.data.labels[c]), datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        layout: { padding: { left: 44, right: 44, top: 18, bottom: 18 } },
        scales: { r: { min: 0, max: 100, ticks: { stepSize: 25, backdropColor: 'transparent' }, pointLabels: { font: { size: 11 } } } },
        plugins: { legend: { display: datasets.length > 0 } },
      },
    });
  }
}

document.addEventListener('DOMContentLoaded', () => new Leaderboard());
