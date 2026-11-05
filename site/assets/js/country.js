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
    { key: "fr", name: Atlas.t("js.country.fr"), color: Atlas.cssVar("--country-fr") },
    { key: "de", name: Atlas.t("js.country.de"), color: Atlas.cssVar("--country-de") },
    { key: "en", name: Atlas.t("js.country.en"), color: Atlas.cssVar("--country-en") },
    { key: "it", name: Atlas.t("js.country.it"), color: Atlas.cssVar("--country-it") },
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
        ctx.fillText(`${ct.name} ${Atlas.t("js.pct", { n: Math.round(chart.data.datasets[i].data[HORIZON]) })}`, chartArea.right + 16, y);
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
                      callback: v => (v === 0 ? "0" : narrow ? Atlas.t("js.yr", { n: v / 365 }) : Atlas.t("js.tick_days_yr", { v: Atlas.num(v), n: v / 365 })) } },
        y: { min: 0, max: 100, grid: { color: c.grid }, border: { display: false },
             ticks: { stepSize: 25, callback: v => `${v}%` } },
      },
      plugins: { tooltip: { ...tooltip, displayColors: false, callbacks: {
        title: items => Atlas.t("js.tip_day_after_ec", { d: Atlas.num(items[0].parsed.x) }),
        label: item => Atlas.t("js.tip_reached", { name: ordered[item.datasetIndex].name, pct: Math.round(item.parsed.y) }),
      } } },
    },
    plugins: [endLabels],
  });
  document.getElementById("table-country").innerHTML = Atlas.table(COUNTRIES, [
    { label: Atlas.t("js.col_country"), value: ct => ct.name },
    { label: Atlas.t("js.col_median_incl"), value: ct => (ct.median === null ? Atlas.t("js.not_reached") : Atlas.num(ct.median)), num: true },
    { label: Atlas.t("js.col_within1s"), value: ct => Atlas.t("js.pct", { n: Math.round(ct.pct_1y) }), num: true },
    { label: Atlas.t("js.col_within2s"), value: ct => Atlas.t("js.pct", { n: Math.round(ct.pct_2y) }), num: true },
    { label: Atlas.t("js.col_counted"), value: ct => Atlas.num(ct.n), num: true },
    { label: Atlas.t("js.col_still_waiting"), value: ct => Atlas.num(ct.waiting), num: true },
  ]);

  // ---- Verdict mix -----------------------------------------------------------------------
  // Verdict names come from the data as codes (G-BA, NICE) or labels (ASMR, Italian classes).
  const mixLabel = k => {
    for (const p of ["gba", "nice"]) { const v = Atlas.t(`${p}.${k}`); if (v !== `${p}.${k}`) return v; }
    if (k.startsWith("ASMR ")) return Atlas.t(`asmr.${k.slice(5)}`);
    if (k === "SMR insufficient") return Atlas.t("asmr.SMR insufficient");
    return Atlas.label(k);
  };
  const mix = Object.entries(profile.mix).map(([k, n]) => ({ label: mixLabel(k), n }));
  new Chart(document.getElementById("chart-mix"), {
    type: "bar",
    data: { labels: mix.map(m => m.label),
            datasets: [{ data: mix.map(m => m.n), backgroundColor: COUNTRIES.find(ct => ct.key === key).color,
                         borderRadius: 4, borderSkipped: "start", maxBarThickness: 18 }] },
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
  document.getElementById("table-mix").innerHTML = Atlas.table(mix, [
    { label: Atlas.t("js.col_verdict"), value: m => m.label }, { label: Atlas.t("js.col_drugs"), value: m => m.n, num: true },
  ]);

  // ---- Therapy areas and drug lists ---------------------------------------------------------
  document.getElementById("table-areas").innerHTML = Atlas.table(profile.areas, [
    { label: Atlas.t("js.col_area"), value: a => Atlas.label(a.area) },
    { label: Atlas.t("js.col_median_days"), value: a => (a.median === null ? Atlas.t("js.not_reached") : Atlas.num(a.median)), num: true },
    { label: Atlas.t("js.col_within2_short"), value: a => Atlas.t("js.pct", { n: Math.round(a.pct_2y) }), num: true },
    { label: Atlas.t("js.col_drugs"), value: a => a.n, num: true },
    { label: Atlas.t("js.col_waiting"), value: a => a.waiting, num: true },
  ]);
  const days = (d, suffix) => {
    if (d.days < 0) return Atlas.t("js.days_before_ec", { n: Atlas.num(-d.days) });
    const base = suffix ? Atlas.t("js.days_after_ec", { n: Atlas.num(d.days) }) : Atlas.t("js.n_days", { n: Atlas.num(d.days) });
    return d.note ? `${base} · ${Atlas.esc(Atlas.label(d.note))}` : base;
  };
  const list = (items, suffix) => (items.length ? `<ol class="rank-list">${items.map(d => `
    <li><a href="${Atlas.briefUrl(d.id)}">${Atlas.esc(d.brand)}</a>
      <span class="muted small">${Atlas.esc(Atlas.label(d.area))}${d.eu_status && d.eu_status !== "Authorised" ? ` · ${Atlas.t("js.cmp.eu_status", { status: Atlas.esc(Atlas.label(d.eu_status)) })}` : ""}</span>
      <span class="rank-days">${days(d, suffix)}</span></li>`).join("")}</ol>`
    : `<p class="muted">${Atlas.t("js.none")}</p>`);
  document.getElementById("list-fastest").innerHTML = list(profile.fastest, "");
  document.getElementById("list-slowest").innerHTML = list(profile.slowest, "");
  document.getElementById("list-waiting").innerHTML = list(profile.longest_waiting, true);
})();
