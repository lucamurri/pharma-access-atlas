/* Overview page: four charts and their table views, built for ~200 drugs.
   Headline charts use only the "core" cohort (drugs selected by rule).
   Chart.js is loaded from assets/vendor (stored in the repo, not a CDN). */

(async () => {
  const data = await Atlas.load();
  const rows = data.rows.filter(r => r.cohort === "core");
  const s = data.summary;
  const c = {
    s1: Atlas.cssVar("--series-1"), s2: Atlas.cssVar("--series-2"), grid: Atlas.cssVar("--grid"),
    text: Atlas.cssVar("--text"), text2: Atlas.cssVar("--text-2"), surface: Atlas.cssVar("--surface"),
  };

  // Shared look: recessive grid, readable ticks, HTML legends instead of built-in ones.
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.font.size = 12;
  Chart.defaults.color = c.text2;
  Chart.defaults.plugins.legend.display = false;
  Chart.defaults.animation = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? false : { duration: 400 };

  const bar = { borderRadius: 4, borderSkipped: "start", borderWidth: 0, barPercentage: 0.8, categoryPercentage: 0.9 };
  const tooltip = { backgroundColor: c.text, titleColor: c.surface, bodyColor: c.surface, padding: 10, displayColors: false };
  const median = xs => {
    const v = xs.filter(x => x !== null && x !== undefined).sort((a, b) => a - b);
    if (!v.length) return null;
    const m = Math.floor(v.length / 2);
    return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
  };
  const round = x => Math.floor(x + 0.5);

  // Prints the value at the end of each bar (used on charts with few bars).
  const valueLabels = labels => ({
    id: "valueLabels",
    afterDatasetsDraw(chart) {
      const { ctx } = chart;
      ctx.save();
      ctx.fillStyle = c.text;
      ctx.font = `600 12px ${Chart.defaults.font.family}`;
      ctx.textBaseline = "middle";
      chart.getDatasetMeta(0).data.forEach((el, i) => ctx.fillText(labels[i], el.x + 6, el.y));
      ctx.restore();
    },
  });
  const hbar = (id, labels, values, valueText, tip, height) => new Chart(document.getElementById(id), {
    type: "bar",
    data: { labels, datasets: [{ ...bar, data: values, backgroundColor: c.s1, maxBarThickness: 18 }] },
    options: {
      indexAxis: "y", maintainAspectRatio: false, layout: { padding: { right: 56 } },
      scales: { x: { beginAtZero: true, grid: { color: c.grid }, border: { display: false }, ticks: { precision: 0 } },
                y: { grid: { display: false }, ticks: { autoSkip: false } } },
      plugins: { tooltip: { ...tooltip, callbacks: { label: tip } } },
    },
    plugins: [valueLabels(valueText)],
  });

  // ---- 1. Time to each country's milestone (Kaplan-Meier, computed in the pipeline) ----
  // Each curve is the share of drugs that had reached the milestone by a given day.
  // Drugs still waiting stay in the denominator until the day they were checked.
  const HORIZON = 4 * 365;
  const countries = [
    { key: "fr", name: "France", milestone: "HAS opinion", color: Atlas.cssVar("--country-fr") },
    { key: "de", name: "Germany", milestone: "G-BA decision", color: Atlas.cssVar("--country-de") },
    { key: "en", name: "England", milestone: "NICE guidance", color: Atlas.cssVar("--country-en") },
    { key: "it", name: "Italy", milestone: "reimbursement", color: Atlas.cssVar("--country-it") },
  ].map(ct => ({ ...ct, ...s.access[ct.key] }));
  // Read the step curve on every day so the tooltip can compare countries on the same day.
  const reachedBy = (steps, day) => { let v = 0; for (const [t, p] of steps) { if (t > day) break; v = p; } return v; };
  const grid = Array.from({ length: HORIZON + 1 }, (_, d) => d);
  const curveLabels = {
    id: "curveLabels",
    afterDatasetsDraw(chart) {
      const { ctx, chartArea } = chart;
      const ends = chart.data.datasets.map((ds, i) => {
        const pts = chart.getDatasetMeta(i).data; return { i, y: pts[pts.length - 1].y };
      }).sort((p, q) => p.y - q.y);
      for (let k = 1; k < ends.length; k++) ends[k].y = Math.max(ends[k].y, ends[k - 1].y + 15); // avoid overlaps
      ctx.save();
      ctx.font = `600 12px ${Chart.defaults.font.family}`; ctx.textBaseline = "middle";
      ends.forEach(({ i, y }) => {
        const ct = countries[i];
        ctx.fillStyle = ct.color; ctx.beginPath(); ctx.arc(chartArea.right + 8, y, 4, 0, 2 * Math.PI); ctx.fill();
        ctx.fillStyle = c.text; ctx.fillText(`${ct.name} ${Math.round(chart.data.datasets[i].data[HORIZON])}%`, chartArea.right + 16, y);
      });
      // Dashed reference line at 50%: where each curve crosses it is that country's median.
      const y50 = chart.scales.y.getPixelForValue(50);
      ctx.strokeStyle = c.text2; ctx.setLineDash([4, 4]); ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(chartArea.left, y50); ctx.lineTo(chartArea.right, y50); ctx.stroke();
      ctx.restore();
    },
  };
  new Chart(document.getElementById("chart-countries"), {
    type: "line",
    data: { labels: grid, datasets: countries.map(ct => ({
      label: `${ct.name}: ${ct.milestone}`, data: grid.map(d => reachedBy(ct.steps, d)),
      borderColor: ct.color, backgroundColor: ct.color, borderWidth: 2, pointRadius: 0, pointHoverRadius: 4,
      pointHoverBorderColor: c.surface, pointHoverBorderWidth: 2,
    })) },
    options: {
      maintainAspectRatio: false, layout: { padding: { right: 110 } },
      interaction: { mode: "index", intersect: false },
      scales: {
        x: { type: "linear", min: 0, max: HORIZON, grid: { color: c.grid }, border: { display: false },
             title: { display: true, text: "Days after European Commission approval" },
             ticks: { stepSize: 365, callback: v => (v === 0 ? "0" : `${v} (${v / 365} yr)`) } },
        y: { min: 0, max: 100, grid: { color: c.grid }, border: { display: false },
             title: { display: true, text: "Drugs that reached the milestone" }, ticks: { stepSize: 25, callback: v => `${v}%` } },
      },
      plugins: { tooltip: { ...tooltip, displayColors: true, boxPadding: 4, callbacks: {
        title: items => `Day ${items[0].parsed.x} after EU approval`,
        label: item => ` ${countries[item.datasetIndex].name}: ${Math.round(item.parsed.y)}% reached`,
      } } },
    },
    plugins: [curveLabels],
  });
  document.getElementById("table-countries").innerHTML = Atlas.table(countries, [
    { label: "Milestone", value: ct => `${ct.name}: ${ct.milestone}` },
    { label: "Median days (incl. waiting)", value: ct => ct.median ?? "not reached", num: true },
    { label: "Reached within 1 year", value: ct => `${Math.round(ct.pct_1y)}%`, num: true },
    { label: "Reached within 2 years", value: ct => `${Math.round(ct.pct_2y)}%`, num: true },
    { label: "Drugs counted", value: ct => ct.n, num: true },
    { label: "Still waiting when checked", value: ct => ct.waiting, num: true },
  ]);

  // ---- 2. US-to-EU lag distribution -------------------------------------------
  const width = 90;
  const lags = rows.filter(r => r.lag !== null);
  const lo = Math.floor(Math.min(...lags.map(r => r.lag)) / width) * width;
  const hi = Math.ceil((Math.max(...lags.map(r => r.lag)) + 1) / width) * width;
  const bins = [];
  for (let start = lo; start < hi; start += width) {
    bins.push({ start, end: start + width - 1, drugs: lags.filter(r => r.lag >= start && r.lag < start + width) });
  }
  new Chart(document.getElementById("chart-lag"), {
    type: "bar",
    data: {
      labels: bins.map(b => `${b.start} to ${b.end}`),
      datasets: [{ ...bar, data: bins.map(b => b.drugs.length), barPercentage: 0.95, categoryPercentage: 1,
                   backgroundColor: bins.map(b => (b.end < 0 ? c.s2 : c.s1)) }],
    },
    options: {
      maintainAspectRatio: false,
      scales: {
        x: { title: { display: true, text: "Days from FDA to EC approval (negative = EU first)" }, grid: { display: false },
             ticks: { maxRotation: 0, autoSkip: true, callback: (v, i) => bins[i].start } },
        y: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: "Drugs" },
             grid: { color: c.grid }, border: { display: false } },
      },
      plugins: { tooltip: { ...tooltip, callbacks: {
        title: items => `${bins[items[0].dataIndex].start} to ${bins[items[0].dataIndex].end} days`,
        label: item => {
          const names = bins[item.dataIndex].drugs.map(r => r.brand_us);
          return [`${names.length} drug${names.length === 1 ? "" : "s"}`,
                  ...names.slice(0, 8), ...(names.length > 8 ? [`and ${names.length - 8} more`] : [])];
        },
      } } },
    },
  });
  document.getElementById("table-lag").innerHTML = Atlas.table(bins.filter(b => b.drugs.length), [
    { label: "Days (FDA to EC)", value: b => `${b.start} to ${b.end}` },
    { label: "Drugs", value: b => b.drugs.length, num: true },
    { label: "Which", html: b => b.drugs.map(r => `<a href="${Atlas.briefUrl(r.id)}">${Atlas.esc(r.brand_us)}</a>`).join(", ") },
  ]);

  // ---- 3. Italy delay by therapy area -----------------------------------------
  const areas = Object.entries(s.it_lag_by_area).filter(([, v]) => v.n >= 3)
    .map(([area, v]) => ({ area, ...v })).sort((a, b) => b.median - a.median);
  hbar("chart-italy", areas.map(a => a.area), areas.map(a => a.median),
       areas.map(a => `${round(a.median)} (n=${a.n})`),
       item => [`Median ${round(item.raw)} days`, `${areas[item.dataIndex].n} reimbursed drugs`]);
  document.getElementById("table-italy").innerHTML = Atlas.table(areas, [
    { label: "Therapy area", value: a => a.area },
    { label: "Median days to reimbursement", value: a => round(a.median), num: true },
    { label: "Reimbursed drugs", value: a => a.n, num: true },
  ]);

  // ---- 4. Verdicts: Germany, France, England -----------------------------------
  const cap = t => t.charAt(0).toUpperCase() + t.slice(1);
  const gOrder = ["major", "considerable", "minor", "non-quantifiable", "no added benefit", "lesser"];
  const fOrder = ["I", "II", "III", "IV", "V", "SMR insufficient"];
  const eOrder = ["recommended", "optimised", "managed access", "not recommended", "terminated"];
  const g = gOrder.map(k => s.gba_ratings[k]);
  const f = fOrder.map(k => s.fr_asmr[k]);
  const e = eOrder.map(k => s.en_decisions[k] || 0);
  const names = (key, k) => rows.filter(r => r[key] === k).map(r => r.brand_us);
  const tipFor = (key, order) => item => {
    const list = names(key, order[item.dataIndex]);
    return [`${item.raw} drugs`, ...list.slice(0, 8), ...(list.length > 8 ? [`and ${list.length - 8} more`] : [])];
  };
  hbar("chart-gba", gOrder.map(cap), g, g.map(String), tipFor("gba_rating", gOrder));
  const frLabel = k => (k.startsWith("SMR") ? k : `ASMR ${k}`);
  hbar("chart-fr", fOrder.map(frLabel), f, f.map(String), tipFor("fr_verdict", fOrder));
  hbar("chart-en", eOrder.map(cap), e, e.map(String), tipFor("en_decision", eOrder));
  const htaRows = [
    ...gOrder.map((k, i) => ({ country: "Germany", verdict: k, n: g[i] })),
    ...fOrder.map((k, i) => ({ country: "France", verdict: frLabel(k), n: f[i] })),
    ...eOrder.map((k, i) => ({ country: "England", verdict: k, n: e[i] })),
  ];
  document.getElementById("table-hta").innerHTML = Atlas.table(htaRows, [
    { label: "Country", value: r => r.country }, { label: "Verdict", value: r => r.verdict },
    { label: "Drugs", value: r => r.n, num: true },
  ]);
})();
