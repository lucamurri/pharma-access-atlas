/* United States page: European milestones counted from FDA approval (Kaplan-Meier curves computed in
   pipeline/analysis.py as *_from_fda), the FDA review mix, therapy areas and two drug lists. */

(async () => {
  const { summary } = await Atlas.load();
  const us = summary.us;
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

  // ---- Curves from FDA approval ------------------------------------------------------------
  const SERIES = [
    { key: "ec_from_fda", name: Atlas.t("js.us.ec"), color: c.neutral },
    { key: "fr_from_fda", name: Atlas.t("js.country.fr"), color: Atlas.cssVar("--country-fr") },
    { key: "de_from_fda", name: Atlas.t("js.country.de"), color: Atlas.cssVar("--country-de") },
    { key: "en_from_fda", name: Atlas.t("js.country.en"), color: Atlas.cssVar("--country-en") },
    { key: "it_from_fda", name: Atlas.t("js.country.it"), color: Atlas.cssVar("--country-it") },
  ].map(s => ({ ...s, ...summary.access[s.key] }));
  const HORIZON = 5 * 365;
  const grid = Array.from({ length: HORIZON + 1 }, (_, d) => d);
  // Steps are in time order except a leading [0, 0]; events before FDA approval count from day 0.
  const reachedBy = (steps, day) => Math.max(0, ...steps.filter(([t]) => t <= day).map(([, p]) => p));
  const narrow = document.getElementById("chart-us").parentElement.clientWidth < 520;
  const endLabels = {
    id: "endLabels",
    afterDatasetsDraw(chart) {
      const { ctx, chartArea } = chart;
      const ends = chart.data.datasets.map((ds, i) => ({ i, y: chart.getDatasetMeta(i).data[HORIZON].y }))
        .sort((p, q) => p.y - q.y);
      for (let k = 1; k < ends.length; k++) ends[k].y = Math.max(ends[k].y, ends[k - 1].y + 15);
      ctx.save();
      ctx.font = `600 ${narrow ? 11 : 12}px ${Chart.defaults.font.family}`; ctx.textBaseline = "middle";
      ends.forEach(({ i, y }) => {
        ctx.fillStyle = SERIES[i].color; ctx.beginPath(); ctx.arc(chartArea.right + 8, y, 4, 0, 2 * Math.PI); ctx.fill();
        ctx.fillStyle = c.text;
        ctx.fillText(`${SERIES[i].name} ${Atlas.t("js.pct", { n: Math.round(chart.data.datasets[i].data[HORIZON]) })}`, chartArea.right + 16, y);
      });
      const y50 = chart.scales.y.getPixelForValue(50);
      ctx.strokeStyle = c.text2; ctx.setLineDash([4, 4]); ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(chartArea.left, y50); ctx.lineTo(chartArea.right, y50); ctx.stroke();
      ctx.restore();
    },
  };
  new Chart(document.getElementById("chart-us"), {
    type: "line",
    data: { labels: grid, datasets: SERIES.map(s => ({
      label: s.name, data: grid.map(d => reachedBy(s.steps, d)), borderColor: s.color, backgroundColor: s.color,
      borderWidth: 2, pointRadius: 0, pointHoverRadius: 4,
    })) },
    options: {
      maintainAspectRatio: false, layout: { padding: { right: narrow ? 118 : 130 } },
      interaction: { mode: "index", intersect: false },
      scales: {
        x: { type: "linear", min: 0, max: HORIZON, grid: { color: c.grid }, border: { display: false },
             title: { display: true, text: Atlas.t("js.us.axis") },
             ticks: { stepSize: 365, maxRotation: 0,
                      callback: v => (v === 0 ? "0" : narrow ? Atlas.t("js.yr", { n: v / 365 }) : Atlas.t("js.tick_days_yr", { v: Atlas.num(v), n: v / 365 })) } },
        y: { min: 0, max: 100, grid: { color: c.grid }, border: { display: false },
             ticks: { stepSize: 25, callback: v => `${v}%` } },
      },
      plugins: { tooltip: { ...tooltip, displayColors: true, boxPadding: 4, callbacks: {
        title: items => Atlas.t("js.us.tip_day", { d: Atlas.num(items[0].parsed.x) }),
        label: item => ` ${Atlas.t("js.tip_reached", { name: SERIES[item.datasetIndex].name, pct: Math.round(item.parsed.y) })}`,
      } } },
    },
    plugins: [endLabels],
  });
  document.getElementById("table-us").innerHTML = Atlas.table(SERIES, [
    { label: Atlas.t("js.col_milestone"), value: s => s.name },
    { label: Atlas.t("js.us.col_median"), value: s => (s.median === null ? Atlas.t("js.not_reached") : Atlas.num(s.median)), num: true },
    { label: Atlas.t("js.col_within1s"), value: s => Atlas.t("js.pct", { n: Math.round(s.pct_1y) }), num: true },
    { label: Atlas.t("js.col_within2s"), value: s => Atlas.t("js.pct", { n: Math.round(s.pct_2y) }), num: true },
    { label: Atlas.t("js.col_counted"), value: s => Atlas.num(s.n), num: true },
    { label: Atlas.t("js.col_still_waiting"), value: s => Atlas.num(s.waiting), num: true },
  ]);

  // ---- Review mix ------------------------------------------------------------------------------
  const mix = Object.entries(us.mix).map(([label, n]) => ({ label: Atlas.label(label), n }));
  new Chart(document.getElementById("chart-us-mix"), {
    type: "bar",
    data: { labels: mix.map(m => m.label),
            datasets: [{ data: mix.map(m => m.n), backgroundColor: c.s1, borderRadius: 4, borderSkipped: "start", maxBarThickness: 18 }] },
    options: {
      indexAxis: "y", maintainAspectRatio: false, layout: { padding: { right: 36 } },
      scales: { x: { beginAtZero: true, grid: { color: c.grid }, border: { display: false }, ticks: { precision: 0 } },
                y: { grid: { display: false }, ticks: { autoSkip: false } } },
      plugins: { tooltip: { ...tooltip, displayColors: false, callbacks: { label: item => Atlas.t("js.n_drugs", { n: item.raw }) } } },
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
  document.getElementById("table-us-mix").innerHTML = Atlas.table(mix, [
    { label: Atlas.t("js.us.col_review"), value: m => m.label }, { label: Atlas.t("js.col_drugs"), value: m => m.n, num: true },
  ]);

  // ---- Areas and lists -----------------------------------------------------------------------------
  document.getElementById("table-us-areas").innerHTML = Atlas.table(us.areas, [
    { label: Atlas.t("js.col_area"), value: a => Atlas.label(a.area) },
    { label: Atlas.t("js.col_median_days"), value: a => Atlas.num(a.median), num: true },
    { label: Atlas.t("js.us.col_first"), value: a => Atlas.t("js.x_of_y", { x: a.us_first, y: a.n }), num: true },
  ]);
  const list = (items, text) => `<ol class="rank-list">${items.map(d => `
    <li><a href="${Atlas.briefUrl(d.id)}">${Atlas.esc(d.brand)}</a>
      <span class="muted small">${Atlas.esc(Atlas.label(d.area))}</span>
      <span class="rank-days">${text(d)}</span></li>`).join("")}</ol>`;
  document.getElementById("list-gap").innerHTML =
    list(us.longest_gap, d => Atlas.t("js.us.after", { n: Atlas.num(d.days) }));
  document.getElementById("list-eu-first").innerHTML =
    list(us.eu_first, d => Atlas.t("js.us.before", { n: Atlas.num(-d.days) }));
})();
