/* Insights page: finding 7 chart (computed in pipeline/analysis.py, italy_drivers).
   Two bars per trait: share reimbursed in Italy within two years, with and without the trait. */

(async () => {
  const { summary } = await Atlas.load();
  const drivers = summary.drivers;
  const c = {
    s1: Atlas.cssVar("--series-1"), s2: Atlas.cssVar("--series-2"), grid: Atlas.cssVar("--grid"),
    text: Atlas.cssVar("--text"), text2: Atlas.cssVar("--text-2"), surface: Atlas.cssVar("--surface"),
  };
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.font.size = 12;
  Chart.defaults.color = c.text2;
  Chart.defaults.plugins.legend.display = false;
  Chart.defaults.animation = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? false : { duration: 400 };

  const labels = drivers.map(d => d.yes_label);
  const pct = x => Math.round(x);
  const bar = { borderRadius: 4, borderSkipped: "start", borderWidth: 0, maxBarThickness: 14,
                categoryPercentage: 0.75, barPercentage: 0.9 };

  // Value at the end of each bar, in text ink (identity is carried by the bar colour and legend).
  const valueLabels = {
    id: "valueLabels",
    afterDatasetsDraw(chart) {
      const { ctx } = chart;
      ctx.save();
      ctx.fillStyle = c.text;
      ctx.font = `600 11px ${Chart.defaults.font.family}`;
      ctx.textBaseline = "middle";
      chart.data.datasets.forEach((ds, i) => chart.getDatasetMeta(i).data.forEach((el, j) =>
        ctx.fillText(`${pct(ds.data[j])}%`, el.x + 5, el.y)));
      ctx.restore();
    },
  };

  new Chart(document.getElementById("chart-drivers"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        { ...bar, label: "With the trait", data: drivers.map(d => d.yes.pct_2y), backgroundColor: c.s1 },
        { ...bar, label: "Without it", data: drivers.map(d => d.no.pct_2y), backgroundColor: c.s2 },
      ],
    },
    options: {
      indexAxis: "y", maintainAspectRatio: false, layout: { padding: { right: 40 } },
      scales: {
        x: { min: 0, max: 100, grid: { color: c.grid }, border: { display: false },
             ticks: { stepSize: 25, callback: v => `${v}%` } },
        y: { grid: { display: false }, ticks: { autoSkip: false } },
      },
      plugins: { tooltip: {
        backgroundColor: c.text, titleColor: c.surface, bodyColor: c.surface, padding: 10, displayColors: true,
        callbacks: {
          title: items => drivers[items[0].dataIndex].yes_label,
          label: item => {
            const d = drivers[item.dataIndex], g = item.datasetIndex === 0 ? d.yes : d.no;
            const name = item.datasetIndex === 0 ? d.yes_label : d.no_label;
            return ` ${name}: ${pct(g.pct_2y)}% within 2 years, median ${g.median ?? "not reached"} days (${g.n} drugs)`;
          },
          footer: items => `Log-rank p = ${drivers[items[0].dataIndex].p}`,
        },
      } },
    },
    plugins: [valueLabels],
  });

  document.getElementById("table-drivers").innerHTML = Atlas.table(drivers, [
    { label: "Trait", value: d => d.yes_label },
    { label: "With: within 2 yrs", value: d => `${pct(d.yes.pct_2y)}%`, num: true },
    { label: "With: median days", value: d => d.yes.median ?? "not reached", num: true },
    { label: "With: drugs", value: d => d.yes.n, num: true },
    { label: "Without: within 2 yrs", value: d => `${pct(d.no.pct_2y)}%`, num: true },
    { label: "Without: median days", value: d => d.no.median ?? "not reached", num: true },
    { label: "Without: drugs", value: d => d.no.n, num: true },
    { label: "Log-rank p", value: d => d.p, num: true },
  ]);
})();
