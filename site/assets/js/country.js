/* Country page: this country's time-to-access curve against the other three (grey), its verdict mix,
   therapy areas and drug lists. All numbers come from summary.access and summary.countries
   (pipeline/analysis.py). Which country is set by <body data-country="..."> at build time. */

(async () => {
  const { summary } = await Atlas.load();
  const key = document.body.dataset.country;
  const profile = summary.countries[key];
  const c = {
    grid: Atlas.cssVar("--grid"), text: Atlas.cssVar("--text"), text2: Atlas.cssVar("--text-2"),
    surface: Atlas.cssVar("--surface"), neutral: Atlas.cssVar("--series-neutral"), s1: Atlas.cssVar("--series-1"),
  };
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.font.size = 12;
  Chart.defaults.color = c.text2;
  Chart.defaults.plugins.legend.display = false;
  Chart.defaults.animation = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? false : { duration: 400 };
  const tooltip = { backgroundColor: c.text, titleColor: c.surface, bodyColor: c.surface, padding: 10 };

  // ---- Curve: this country in its own colour, the others in grey -----------------------
  const COUNTRIES = [
    { key: "fr", name: "France", color: Atlas.cssVar("--country-fr") },
    { key: "de", name: "Germany", color: Atlas.cssVar("--country-de") },
    { key: "en", name: "England", color: Atlas.cssVar("--country-en") },
    { key: "it", name: "Italy", color: Atlas.cssVar("--country-it") },
  ].map(ct => ({ ...ct, ...summary.access[ct.key] }));
  const HORIZON = 4 * 365;
  const grid = Array.from({ length: HORIZON + 1 }, (_, d) => d);
  const reachedBy = (steps, day) => { let v = 0; for (const [t, p] of steps) { if (t > day) break; v = p; } return v; };
  const narrow = document.getElementById("chart-country").parentElement.clientWidth < 520;
  // Draw the highlighted country last so it sits on top.
  const ordered = [...COUNTRIES.filter(ct => ct.key !== key), COUNTRIES.find(ct => ct.key === key)];

  const endLabels = {
    id: "endLabels",
    afterDatasetsDraw(chart) {
      const { ctx, chartArea } = chart;
      const ends = chart.data.datasets.map((ds, i) => ({ i, y: chart.getDatasetMeta(i).data[HORIZON].y }))
        .sort((p, q) => p.y - q.y);
      for (let k = 1; k < ends.length; k++) ends[k].y = Math.max(ends[k].y, ends[k - 1].y + 15);
      ctx.save();
      ctx.textBaseline = "middle";
      ends.forEach(({ i, y }) => {
        const ct = ordered[i], mine = ct.key === key;
        ctx.font = `${mine ? 700 : 500} ${narrow ? 11 : 12}px ${Chart.defaults.font.family}`;
        ctx.fillStyle = mine ? ct.color : c.neutral;
        ctx.beginPath(); ctx.arc(chartArea.right + 8, y, 4, 0, 2 * Math.PI); ctx.fill();
        ctx.fillStyle = mine ? c.text : c.text2;
        ctx.fillText(`${ct.name} ${Math.round(chart.data.datasets[i].data[HORIZON])}%`, chartArea.right + 16, y);
      });
      const y50 = chart.scales.y.getPixelForValue(50);
      ctx.strokeStyle = c.text2; ctx.setLineDash([4, 4]); ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(chartArea.left, y50); ctx.lineTo(chartArea.right, y50); ctx.stroke();
      ctx.restore();
    },
  };
  new Chart(document.getElementById("chart-country"), {
    type: "line",
    data: { labels: grid, datasets: ordered.map(ct => {
      const mine = ct.key === key;
      return { label: ct.name, data: grid.map(d => reachedBy(ct.steps, d)), pointRadius: 0, pointHoverRadius: mine ? 4 : 0,
               borderColor: mine ? ct.color : c.neutral, borderWidth: mine ? 3 : 1.5, backgroundColor: ct.color };
    }) },
    options: {
      maintainAspectRatio: false, layout: { padding: { right: narrow ? 100 : 110 } },
      interaction: { mode: "index", intersect: false },
      scales: {
        x: { type: "linear", min: 0, max: HORIZON, grid: { color: c.grid }, border: { display: false },
             title: { display: true, text: "Days after European Commission approval" },
             ticks: { stepSize: 365, maxRotation: 0,
                      callback: v => (v === 0 ? "0" : narrow ? `${v / 365} yr` : `${v} (${v / 365} yr)`) } },
        y: { min: 0, max: 100, grid: { color: c.grid }, border: { display: false },
             ticks: { stepSize: 25, callback: v => `${v}%` } },
      },
      plugins: { tooltip: { ...tooltip, displayColors: false, callbacks: {
        title: items => `Day ${items[0].parsed.x} after EU approval`,
        label: item => `${ordered[item.datasetIndex].name}: ${Math.round(item.parsed.y)}% reached`,
      } } },
    },
    plugins: [endLabels],
  });
  document.getElementById("table-country").innerHTML = Atlas.table(COUNTRIES, [
    { label: "Country", value: ct => ct.name },
    { label: "Median days (incl. waiting)", value: ct => ct.median ?? "not reached", num: true },
    { label: "Within 1 year", value: ct => `${Math.round(ct.pct_1y)}%`, num: true },
    { label: "Within 2 years", value: ct => `${Math.round(ct.pct_2y)}%`, num: true },
    { label: "Drugs counted", value: ct => ct.n, num: true },
    { label: "Still waiting", value: ct => ct.waiting, num: true },
  ]);

  // ---- Verdict mix -----------------------------------------------------------------------
  const mix = Object.entries(profile.mix).map(([label, n]) => ({ label: label.charAt(0).toUpperCase() + label.slice(1), n }));
  new Chart(document.getElementById("chart-mix"), {
    type: "bar",
    data: { labels: mix.map(m => m.label),
            datasets: [{ data: mix.map(m => m.n), backgroundColor: COUNTRIES.find(ct => ct.key === key).color,
                         borderRadius: 4, borderSkipped: "start", maxBarThickness: 18 }] },
    options: {
      indexAxis: "y", maintainAspectRatio: false, layout: { padding: { right: 36 } },
      scales: { x: { beginAtZero: true, grid: { color: c.grid }, border: { display: false }, ticks: { precision: 0 } },
                y: { grid: { display: false }, ticks: { autoSkip: false } } },
      plugins: { tooltip: { ...tooltip, displayColors: false, callbacks: { label: item => `${item.raw} drugs` } } },
    },
    plugins: [{
      id: "values",
      afterDatasetsDraw(chart) {
        const { ctx } = chart;
        ctx.save(); ctx.fillStyle = c.text; ctx.font = `600 12px ${Chart.defaults.font.family}`; ctx.textBaseline = "middle";
        chart.getDatasetMeta(0).data.forEach((el, i) => ctx.fillText(String(mix[i].n), el.x + 6, el.y));
        ctx.restore();
      },
    }],
  });
  document.getElementById("table-mix").innerHTML = Atlas.table(mix, [
    { label: "Verdict", value: m => m.label }, { label: "Drugs", value: m => m.n, num: true },
  ]);

  // ---- Therapy areas and drug lists ---------------------------------------------------------
  document.getElementById("table-areas").innerHTML = Atlas.table(profile.areas, [
    { label: "Therapy area", value: a => a.area },
    { label: "Median days", value: a => a.median ?? "not reached", num: true },
    { label: "Within 2 yrs", value: a => `${Math.round(a.pct_2y)}%`, num: true },
    { label: "Drugs", value: a => a.n, num: true },
    { label: "Waiting", value: a => a.waiting, num: true },
  ]);
  const days = (d, suffix) => {
    if (d.days < 0) return `${(-d.days).toLocaleString("en-US")} days before EU approval`;
    const base = `${d.days.toLocaleString("en-US")} days${suffix}`;
    return d.note ? `${base} · ${Atlas.esc(d.note)}` : base;
  };
  const list = (items, suffix) => (items.length ? `<ol class="rank-list">${items.map(d => `
    <li><a href="${Atlas.briefUrl(d.id)}">${Atlas.esc(d.brand)}</a>
      <span class="muted small">${Atlas.esc(d.area)}${d.eu_status && d.eu_status !== "Authorised" ? ` · EU: ${Atlas.esc(d.eu_status.toLowerCase())}` : ""}</span>
      <span class="rank-days">${days(d, suffix)}</span></li>`).join("")}</ol>`
    : '<p class="muted">None</p>');
  document.getElementById("list-fastest").innerHTML = list(profile.fastest, "");
  document.getElementById("list-slowest").innerHTML = list(profile.slowest, "");
  document.getElementById("list-waiting").innerHTML = list(profile.longest_waiting, " since EU approval");
})();
