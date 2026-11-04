/* Overview page: draws the three charts and their table views.
   Chart.js is loaded from assets/vendor (stored in the repo, not a CDN). */

(async () => {
  const data = await Atlas.load();
  const rows = data.rows;
  const c = {
    s1: Atlas.cssVar("--series-1"),
    s2: Atlas.cssVar("--series-2"),
    neutral: Atlas.cssVar("--series-neutral"),
    grid: Atlas.cssVar("--grid"),
    text: Atlas.cssVar("--text"),
    text2: Atlas.cssVar("--text-2"),
    surface: Atlas.cssVar("--surface"),
  };

  // Shared look: recessive grid, readable ticks, no built-in legend
  // (each chart has an HTML legend above it).
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.font.size = 12;
  Chart.defaults.color = c.text2;
  Chart.defaults.plugins.legend.display = false;
  Chart.defaults.animation = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? false : { duration: 400 };

  const bar = { borderRadius: 4, borderSkipped: "start", barPercentage: 0.75, categoryPercentage: 0.9,
                borderWidth: 0, maxBarThickness: 14 };
  const tooltip = { backgroundColor: c.text, titleColor: c.surface, bodyColor: c.surface, padding: 10,
                    displayColors: false };

  // Clicking a bar opens that drug's brief.
  const openBrief = list => (evt, elements) => {
    if (elements.length) window.location.href = Atlas.briefUrl(list[elements[0].index].id);
  };
  const pointer = (evt, elements) => { evt.native.target.style.cursor = elements.length ? "pointer" : "default"; };

  // ---- 1. US-to-EU approval lag -----------------------------------------
  const lagRows = rows.filter(r => r.lag !== null).sort((a, b) => b.lag - a.lag);
  new Chart(document.getElementById("chart-lag"), {
    type: "bar",
    data: {
      labels: lagRows.map(r => r.brand_us),
      datasets: [{ ...bar, minBarLength: 3, data: lagRows.map(r => r.lag),
                   backgroundColor: lagRows.map(r => (r.lag < 0 ? c.s2 : c.s1)) }],
    },
    options: {
      indexAxis: "y", maintainAspectRatio: false, onClick: openBrief(lagRows), onHover: pointer,
      scales: {
        x: { title: { display: true, text: "Days (negative = EU approved first)" },
             grid: { color: ctx => (ctx.tick.value === 0 ? c.text2 : c.grid), lineWidth: ctx => (ctx.tick.value === 0 ? 1.5 : 1) },
             border: { display: false } },
        y: { grid: { display: false }, ticks: { autoSkip: false } },
      },
      plugins: { tooltip: { ...tooltip, callbacks: {
        title: items => Atlas.drugName(lagRows[items[0].dataIndex]),
        label: item => {
          const r = lagRows[item.dataIndex];
          const days = Math.abs(r.lag);
          return [r.lag < 0 ? `EU approved ${days} days before the US` : `EU approved ${days} days after the US`,
                  `FDA ${Atlas.fmtDate(r.fda_date)} · EC ${Atlas.fmtDate(r.ec_date)}`, "Click for the brief"];
        },
      } } },
    },
  });
  document.getElementById("table-lag").innerHTML = Atlas.table(lagRows, [
    { label: "Drug", html: r => `<a href="${Atlas.briefUrl(r.id)}">${Atlas.esc(Atlas.drugName(r))}</a>` },
    { label: "FDA approval", value: r => Atlas.fmtDate(r.fda_date) },
    { label: "EC approval", value: r => Atlas.fmtDate(r.ec_date) },
    { label: "Lag (days)", value: r => r.lag, num: true },
  ]);

  // ---- 2. Italy access delay ---------------------------------------------
  const itRows = rows.filter(r => r.it_lag !== null || r.it_waiting !== null)
    .map(r => ({ ...r, days: r.it_lag ?? r.it_waiting, waiting: r.it_lag === null }))
    .sort((a, b) => b.days - a.days);
  new Chart(document.getElementById("chart-italy"), {
    type: "bar",
    data: {
      labels: itRows.map(r => r.brand_eu),
      datasets: [{ ...bar, data: itRows.map(r => r.days),
                   backgroundColor: itRows.map(r => (r.waiting ? c.neutral : c.s1)) }],
    },
    options: {
      indexAxis: "y", maintainAspectRatio: false, onClick: openBrief(itRows), onHover: pointer,
      scales: {
        x: { beginAtZero: true, title: { display: true, text: "Days after EC approval" },
             grid: { color: c.grid }, border: { display: false } },
        y: { grid: { display: false }, ticks: { autoSkip: false } },
      },
      plugins: { tooltip: { ...tooltip, callbacks: {
        title: items => Atlas.drugName(itRows[items[0].dataIndex]),
        label: item => {
          const r = itRows[item.dataIndex];
          return r.waiting
            ? [`Not reimbursed: ${r.days} days since EC approval`, `as of ${Atlas.fmtDate(r.it_checked)} (class ${r.it_class})`, "Click for the brief"]
            : [`Reimbursed ${r.days} days after EC approval`, `Gazzetta Ufficiale ${Atlas.fmtDate(r.it_date)}, class ${r.it_class}`, "Click for the brief"];
        },
      } } },
    },
  });
  document.getElementById("table-italy").innerHTML = Atlas.table(itRows, [
    { label: "Drug", html: r => `<a href="${Atlas.briefUrl(r.id)}">${Atlas.esc(Atlas.drugName(r))}</a>` },
    { label: "EC approval", value: r => Atlas.fmtDate(r.ec_date) },
    { label: "Italian reimbursement", value: r => (r.waiting ? `Not reimbursed as of ${Atlas.fmtDate(r.it_checked)}` : Atlas.fmtDate(r.it_date)) },
    { label: "Class", value: r => r.it_class },
    { label: "Days", value: r => r.days + (r.waiting ? " (so far)" : ""), num: true },
  ]);

  // ---- 3. G-BA ratings ------------------------------------------------------
  const order = ["major", "considerable", "minor", "non-quantifiable", "no added benefit", "lesser"];
  const counts = order.map(k => data.summary.gba_ratings[k]);
  // Small plugin: print the count at the end of each bar (only six bars).
  const valueLabels = {
    id: "valueLabels",
    afterDatasetsDraw(chart) {
      const { ctx } = chart;
      ctx.save();
      ctx.fillStyle = c.text;
      ctx.font = `600 12px ${Chart.defaults.font.family}`;
      ctx.textBaseline = "middle";
      chart.getDatasetMeta(0).data.forEach((el, i) => ctx.fillText(String(counts[i]), el.x + 6, el.y));
      ctx.restore();
    },
  };
  new Chart(document.getElementById("chart-gba"), {
    type: "bar",
    data: {
      labels: order.map(k => k.charAt(0).toUpperCase() + k.slice(1)),
      datasets: [{ ...bar, data: counts, backgroundColor: c.s1, maxBarThickness: 18 }],
    },
    options: {
      indexAxis: "y", maintainAspectRatio: false, layout: { padding: { right: 24 } },
      scales: {
        x: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: "Number of drugs" },
             grid: { color: c.grid }, border: { display: false } },
        y: { grid: { display: false } },
      },
      plugins: { tooltip: { ...tooltip, callbacks: {
        label: item => {
          const names = rows.filter(r => r.gba_rating === order[item.dataIndex]).map(r => r.brand_eu);
          return [`${item.raw} drug${item.raw === 1 ? "" : "s"}`, ...names];
        },
      } } },
    },
    plugins: [valueLabels],
  });
  document.getElementById("table-gba").innerHTML = Atlas.table(order.map((k, i) => ({ k, n: counts[i] })), [
    { label: "Best G-BA rating", value: r => r.k },
    { label: "Drugs", value: r => r.n, num: true },
    { label: "Which", html: r => rows.filter(x => x.gba_rating === r.k)
        .map(x => `<a href="${Atlas.briefUrl(x.id)}">${Atlas.esc(x.brand_eu)}</a>`).join(", ") || "none" },
  ]);
})();
