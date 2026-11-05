/* Compare page: up to four drugs on one milestone chart and in one table.
   The selection lives in the URL (?ids=leqembi,kisunla) so a comparison can be shared.
   Every value comes from data/atlas.json; sources are on each drug's brief. */

(async () => {
  const { rows } = await Atlas.load();
  const byId = Object.fromEntries(rows.map(r => [r.id, r]));
  const MAX = 4;
  const PRESETS = [
    { label: "Alzheimer's antibodies", ids: ["leqembi", "kisunla"] },
    { label: "Semaglutide: diabetes vs obesity", ids: ["rybelsus", "wegovy"] },
    { label: "Myeloma CAR-T", ids: ["abecma", "carvykti"] },
    { label: "Myeloma bispecifics", ids: ["tecvayli", "elrexfio", "talvey"] },
    { label: "Spinal muscular atrophy", ids: ["zolgensma", "evrysdi"] },
    { label: "Psoriasis", ids: ["bimzelx", "sotyktu", "skyrizi"] },
  ].filter(p => p.ids.every(id => byId[id]));

  const el = id => document.getElementById(id);
  const name = r => Atlas.drugName(r);
  const label = r => `${name(r)} (${r.inn})`;

  // ---- Selection state ---------------------------------------------------------------------
  const fromUrl = (new URLSearchParams(location.search).get("ids") || "").split(",").filter(id => byId[id]);
  let ids = fromUrl.length ? [...new Set(fromUrl)].slice(0, MAX) : (PRESETS[0] ? [...PRESETS[0].ids] : []);

  el("pick-list").innerHTML = rows.slice().sort((a, b) => name(a).localeCompare(name(b)))
    .map(r => `<option value="${Atlas.esc(label(r))}"></option>`).join("");
  el("presets").innerHTML = PRESETS.map((p, i) =>
    `<button type="button" class="preset" data-i="${i}">${Atlas.esc(p.label)}</button>`).join("");
  el("presets").addEventListener("click", e => {
    const b = e.target.closest(".preset");
    if (b) { ids = [...PRESETS[Number(b.dataset.i)].ids]; render(); }
  });

  const findDrug = text => {
    const q = text.trim().toLowerCase();
    if (!q) return null;
    return rows.find(r => label(r).toLowerCase() === q)
      || rows.find(r => [r.brand_us, r.brand_eu, r.inn].some(v => (v || "").toLowerCase() === q))
      || rows.find(r => label(r).toLowerCase().includes(q));
  };
  const add = () => {
    const r = findDrug(el("pick-input").value);
    const msg = el("pick-msg");
    if (!r) { msg.textContent = "No drug matches that name."; return; }
    if (ids.includes(r.id)) { msg.textContent = `${name(r)} is already in the comparison.`; return; }
    if (ids.length >= MAX) { msg.textContent = `You can compare up to ${MAX} drugs. Remove one first.`; return; }
    ids.push(r.id); el("pick-input").value = ""; msg.textContent = `Added ${name(r)}.`; render();
  };
  el("pick-form").addEventListener("submit", add);
  el("pick-input").addEventListener("change", () => { if (findDrug(el("pick-input").value)) add(); });
  el("chips").addEventListener("click", e => {
    const b = e.target.closest("button[data-id]");
    if (b) { ids = ids.filter(id => id !== b.dataset.id); el("pick-msg").textContent = ""; render(); }
  });

  // ---- Chart -----------------------------------------------------------------------------------
  const c = {
    grid: Atlas.cssVar("--grid"), text: Atlas.cssVar("--text"), text2: Atlas.cssVar("--text-2"),
    surface: Atlas.cssVar("--surface"), neutral: Atlas.cssVar("--series-neutral"),
  };
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.font.size = 12;
  Chart.defaults.color = c.text2;
  Chart.defaults.plugins.legend.display = false;
  Chart.defaults.animation = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? false : { duration: 300 };
  const MILESTONES = [
    { key: "fda", name: "FDA approval", color: c.neutral, style: "rectRot" },
    { key: "fr", name: "France: HAS opinion", color: Atlas.cssVar("--country-fr"), style: "circle", date: "fr_date" },
    { key: "de", name: "Germany: G-BA decision", color: Atlas.cssVar("--country-de"), style: "circle", date: "gba_date" },
    { key: "en", name: "England: NICE guidance", color: Atlas.cssVar("--country-en"), style: "circle", date: "en_date" },
    { key: "it", name: "Italy: reimbursement", color: Atlas.cssVar("--country-it"), style: "circle", date: "it_date" },
  ];
  const point = (r, m) => {
    if (m.key === "fda") {
      return r.lag === null ? null : { x: -r.lag, y: name(r), reached: true, date: r.fda_date };
    }
    const pair = r.km[m.key];
    return pair ? { x: pair[0], y: name(r), reached: pair[1] === 1, date: r[m.date] } : null;
  };
  let chart = null;

  function drawChart(sel) {
    el("cmp-box").style.height = `${90 + sel.length * 70}px`;
    const datasets = MILESTONES.map(m => {
      const pts = sel.map(r => point(r, m)).filter(Boolean);
      return {
        label: m.name, data: pts, pointStyle: m.style, pointRadius: 8, pointHoverRadius: 10,
        borderColor: m.color, borderWidth: 2.5,
        backgroundColor: pts.map(p => (p.reached ? m.color : c.surface)),
      };
    });
    const config = {
      type: "scatter",
      data: { datasets },
      options: {
        maintainAspectRatio: false, layout: { padding: { right: 12 } },
        scales: {
          x: { grid: { color: c.grid }, border: { display: false },
               title: { display: true, text: "Days after European Commission approval" },
               ticks: { callback: v => v.toLocaleString("en-US") } },
          y: { type: "category", labels: sel.map(name), offset: true, grid: { color: c.grid }, border: { display: false },
               ticks: { color: c.text, font: { weight: 600 } } },
        },
        plugins: { tooltip: {
          backgroundColor: c.text, titleColor: c.surface, bodyColor: c.surface, padding: 10,
          callbacks: {
            title: items => items[0].raw.y,
            label: item => {
              const m = MILESTONES[item.datasetIndex], p = item.raw;
              if (!p.reached) return ` ${m.name}: not yet, ${p.x.toLocaleString("en-US")} days after EU approval when checked`;
              const when = p.x < 0 ? `${(-p.x).toLocaleString("en-US")} days before EU approval`
                                   : `${p.x.toLocaleString("en-US")} days after EU approval`;
              return ` ${m.name}: ${when}${p.date ? ` (${Atlas.fmtDate(p.date)})` : ""}`;
            },
          },
        } },
      },
    };
    if (chart) chart.destroy();
    chart = new Chart(el("chart-compare"), config);
  }

  // ---- Table -----------------------------------------------------------------------------------
  const na = '<span class="muted">n/a</span>';
  const days = n => `${n.toLocaleString("en-US")} days`;
  const RATING = { "major": "Major", "considerable": "Considerable", "minor": "Minor",
                   "non-quantifiable": "Non-quantifiable", "no added benefit": "No added benefit", "lesser": "Lesser" };
  const ROWS = [
    ["Drug", r => `<a href="${Atlas.briefUrl(r.id)}">${Atlas.esc(name(r))}</a>${r.cohort === "reference" ? ' <span class="pill">Ref.</span>' : ""}`],
    ["Active ingredient", r => Atlas.esc(r.inn)],
    ["Company", r => Atlas.esc(r.company)],
    ["Therapy area", r => Atlas.esc(r.area)],
    ["Orphan", r => [r.us_orphan === "yes" ? "US" : null, r.eu_orphan === "yes" ? "EU" : null].filter(Boolean).join(" + ") || "No"],
    ["FDA approval", r => Atlas.fmtDate(r.fda_date)],
    ["EU approval", r => Atlas.fmtDate(r.ec_date) + (r.eu_conditional === "yes" ? '<br><span class="muted small">conditional</span>' : "")
      + (r.eu_status && r.eu_status !== "Authorised" ? `<br><span class="muted small">EU: ${Atlas.esc(r.eu_status.toLowerCase())}</span>` : "")],
    ["US→EU lag", r => (r.lag === null ? na : r.lag < 0 ? `EU first by ${days(-r.lag)}` : days(r.lag))],
    ["Italy", r => (r.it_lag !== null ? `Reimbursed (class ${Atlas.esc(r.it_class)})<br><span class="muted small">${days(r.it_lag)} after EU approval</span>`
      : r.it_status === "not reimbursed" ? `Not reimbursed<br><span class="muted small">${days(r.it_waiting)} so far, class ${Atlas.esc(r.it_class)}</span>` : na)],
    ["Germany (G-BA)", r => (RATING[r.gba_rating] ? `${RATING[r.gba_rating]}${r.gba_orphan === "yes" ? " (orphan rules)" : ""}`
      + (r.gba_lag !== null ? `<br><span class="muted small">${days(r.gba_lag)} after EU approval</span>` : "")
      : r.gba_rating === "not assessed" ? "Not assessed" : r.gba_pending ? "In progress" : na)],
    ["France (HAS)", r => (r.fr_verdict ? (r.fr_verdict.startsWith("SMR") ? "SMR insufficient" : `ASMR ${r.fr_verdict}`)
      + (r.fr_lag !== null ? `<br><span class="muted small">${days(r.fr_lag)} after EU approval</span>` : "")
      : r.fr_pending ? "No opinion yet" : na)],
    ["England (NICE)", r => (r.en_decision ? Atlas.esc(r.en_decision.charAt(0).toUpperCase() + r.en_decision.slice(1))
      + (r.en_lag !== null ? `<br><span class="muted small">${r.en_lag < 0 ? `${days(-r.en_lag)} before` : `${days(r.en_lag)} after`} EU approval</span>` : "")
      : r.en_pending ? "In progress" : na)],
    ["Medicare price", r => (r.cms_selected === "yes" && r.cms_mfp ? `$${r.cms_mfp.toLocaleString("en-US")} per 30 days from ${r.cms_ipay}` : '<span class="muted">Not negotiated</span>')],
  ];
  function drawTable(sel) {
    el("compare-table").innerHTML = `<caption class="visually-hidden">Selected drugs compared side by side</caption>
      <thead><tr><th scope="col"><span class="visually-hidden">Measure</span></th>${sel.map(r => `<th scope="col">${Atlas.esc(name(r))}</th>`).join("")}</tr></thead>
      <tbody>${ROWS.slice(1).map(([lab, fn]) => `<tr><th scope="row">${lab}</th>${sel.map(r => `<td>${fn(r)}</td>`).join("")}</tr>`).join("")}
      <tr><th scope="row">Brief</th>${sel.map(r => `<td>${ROWS[0][1](r)}</td>`).join("")}</tr></tbody>`;
  }

  // ---- Render ------------------------------------------------------------------------------------
  function render() {
    const sel = ids.map(id => byId[id]);
    el("chips").innerHTML = sel.map(r => `<li class="chip">${Atlas.esc(name(r))}
      <button type="button" data-id="${r.id}" aria-label="Remove ${Atlas.esc(name(r))}">×</button></li>`).join("");
    el("compare-empty").hidden = sel.length > 0;
    el("compare-body").hidden = sel.length === 0;
    el("pick-input").disabled = el("pick-add").disabled = sel.length >= MAX;
    el("pick-input").placeholder = sel.length >= MAX ? `Up to ${MAX} drugs` : "Brand or ingredient";
    history.replaceState(null, "", sel.length ? `?ids=${ids.join(",")}` : location.pathname);
    if (sel.length) { drawChart(sel); drawTable(sel); }
  }
  render();
})();
