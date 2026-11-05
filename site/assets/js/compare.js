/* Compare page: up to four drugs on one milestone chart and in one table.
   The selection lives in the URL (?ids=leqembi,kisunla) so a comparison can be shared.
   Every value comes from data/atlas.json; sources are on each drug's brief. */

(async () => {
  const { rows } = await Atlas.load();
  const byId = Object.fromEntries(rows.map(r => [r.id, r]));
  const MAX = 4;
  const PRESETS = [
    { label: Atlas.t("js.cmp.p_alz"), ids: ["leqembi", "kisunla"] },
    { label: Atlas.t("js.cmp.p_sema"), ids: ["rybelsus", "wegovy"] },
    { label: Atlas.t("js.cmp.p_cart"), ids: ["abecma", "carvykti"] },
    { label: Atlas.t("js.cmp.p_bisp"), ids: ["tecvayli", "elrexfio", "talvey"] },
    { label: Atlas.t("js.cmp.p_sma"), ids: ["zolgensma", "evrysdi"] },
    { label: Atlas.t("js.cmp.p_pso"), ids: ["bimzelx", "sotyktu", "skyrizi"] },
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
    if (!r) { msg.textContent = Atlas.t("js.cmp.no_match"); return; }
    if (ids.includes(r.id)) { msg.textContent = Atlas.t("js.cmp.already", { name: name(r) }); return; }
    if (ids.length >= MAX) { msg.textContent = Atlas.t("js.cmp.max", { n: MAX }); return; }
    ids.push(r.id); el("pick-input").value = ""; msg.textContent = Atlas.t("js.cmp.added", { name: name(r) }); render();
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
    { key: "fda", name: Atlas.t("js.cmp.fda"), color: c.neutral, style: "rectRot" },
    { key: "fr", name: `${Atlas.t("js.country.fr")}: ${Atlas.t("js.ms.fr")}`, color: Atlas.cssVar("--country-fr"), style: "circle", date: "fr_date" },
    { key: "de", name: `${Atlas.t("js.country.de")}: ${Atlas.t("js.ms.de")}`, color: Atlas.cssVar("--country-de"), style: "circle", date: "gba_date" },
    { key: "en", name: `${Atlas.t("js.country.en")}: ${Atlas.t("js.ms.en")}`, color: Atlas.cssVar("--country-en"), style: "circle", date: "en_date" },
    { key: "it", name: `${Atlas.t("js.country.it")}: ${Atlas.t("js.ms.it")}`, color: Atlas.cssVar("--country-it"), style: "circle", date: "it_date" },
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
               title: { display: true, text: Atlas.t("js.axis_days_after_ec") },
               ticks: { callback: v => Atlas.num(v) } },
          y: { type: "category", labels: sel.map(name), offset: true, grid: { color: c.grid }, border: { display: false },
               ticks: { color: c.text, font: { weight: 600 } } },
        },
        plugins: { tooltip: {
          backgroundColor: c.text, titleColor: c.surface, bodyColor: c.surface, padding: 10,
          callbacks: {
            title: items => items[0].raw.y,
            label: item => {
              const m = MILESTONES[item.datasetIndex], p = item.raw;
              if (!p.reached) return ` ${m.name}: ${Atlas.t("js.cmp.tip_waiting", { n: Atlas.num(p.x) })}`;
              const when = p.x < 0 ? Atlas.t("js.days_before_ec", { n: Atlas.num(-p.x) }) : Atlas.t("js.days_after_ec", { n: Atlas.num(p.x) });
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
  const na = `<span class="muted">${Atlas.t("na")}</span>`;
  const days = n => Atlas.t("js.n_days", { n: Atlas.num(n) });
  const sub = text => `<br><span class="muted small">${text}</span>`;
  const RATING = Object.fromEntries(["major", "considerable", "minor", "non-quantifiable", "no added benefit", "lesser"]
    .map(k => [k, Atlas.t(`gba.${k}`)]));
  const ROWS = [
    [Atlas.t("js.cmp.r_drug"), r => `<a href="${Atlas.briefUrl(r.id)}">${Atlas.esc(name(r))}</a>${r.cohort === "reference" ? ` <span class="pill">${Atlas.t("js.ref")}</span>` : ""}`],
    [Atlas.t("js.cmp.r_inn"), r => Atlas.esc(r.inn)],
    [Atlas.t("js.cmp.r_company"), r => Atlas.esc(r.company)],
    [Atlas.t("js.cmp.r_area"), r => Atlas.esc(Atlas.label(r.area))],
    [Atlas.t("js.cmp.r_orphan"), r => [r.us_orphan === "yes" ? "US" : null, r.eu_orphan === "yes" ? "EU" : null].filter(Boolean).join(" + ") || Atlas.t("js.cmp.no")],
    [Atlas.t("js.cmp.r_fda"), r => Atlas.fmtDate(r.fda_date)],
    [Atlas.t("js.cmp.r_ec"), r => Atlas.fmtDate(r.ec_date) + (r.eu_conditional === "yes" ? sub(Atlas.t("js.cmp.conditional")) : "")
      + (r.eu_status && r.eu_status !== "Authorised" ? sub(Atlas.t("js.cmp.eu_status", { status: Atlas.esc(Atlas.label(r.eu_status)) })) : "")],
    [Atlas.t("js.cmp.r_lag"), r => (r.lag === null ? na : r.lag < 0 ? Atlas.t("js.cmp.eu_first_by", { d: days(-r.lag) }) : days(r.lag))],
    [Atlas.t("js.country.it"), r => (r.it_lag !== null ? Atlas.t("js.cmp.it_reimb", { cls: Atlas.esc(r.it_class) }) + sub(Atlas.t("js.days_after_ec", { n: Atlas.num(r.it_lag) }))
      : r.it_status === "not reimbursed" ? Atlas.t("js.cmp.it_not") + sub(Atlas.t("js.cmp.it_so_far", { d: days(r.it_waiting), cls: Atlas.esc(r.it_class) })) : na)],
    [Atlas.t("js.cmp.r_de"), r => (RATING[r.gba_rating] ? `${RATING[r.gba_rating]}${r.gba_orphan === "yes" ? Atlas.t("js.cmp.orphan_rules") : ""}`
      + (r.gba_lag !== null ? sub(Atlas.t("js.days_after_ec", { n: Atlas.num(r.gba_lag) })) : "")
      : r.gba_rating === "not assessed" ? Atlas.t("gba.not assessed") : r.gba_pending ? Atlas.t("js.cmp.in_progress") : na)],
    [Atlas.t("js.cmp.r_fr"), r => (r.fr_verdict ? Atlas.t(`asmr.${r.fr_verdict}`)
      + (r.fr_lag !== null ? sub(Atlas.t("js.days_after_ec", { n: Atlas.num(r.fr_lag) })) : "")
      : r.fr_pending ? Atlas.t("js.cmp.no_opinion") : na)],
    [Atlas.t("js.cmp.r_en"), r => (r.en_decision ? Atlas.esc(Atlas.t(`nice.${r.en_decision}`))
      + (r.en_lag !== null ? sub(r.en_lag < 0 ? Atlas.t("js.days_before_ec", { n: Atlas.num(-r.en_lag) }) : Atlas.t("js.days_after_ec", { n: Atlas.num(r.en_lag) })) : "")
      : r.en_pending ? Atlas.t("js.cmp.in_progress") : na)],
    [Atlas.t("js.cmp.r_cms"), r => (r.cms_selected === "yes" && r.cms_mfp ? Atlas.t("js.cmp.cms", { p: Atlas.num(r.cms_mfp), y: r.cms_ipay }) : `<span class="muted">${Atlas.t("js.cmp.not_negotiated")}</span>`)],
  ];
  function drawTable(sel) {
    el("compare-table").innerHTML = `<caption class="visually-hidden">${Atlas.t("js.cmp.caption")}</caption>
      <thead><tr><th scope="col"><span class="visually-hidden">${Atlas.t("js.cmp.measure")}</span></th>${sel.map(r => `<th scope="col">${Atlas.esc(name(r))}</th>`).join("")}</tr></thead>
      <tbody>${ROWS.slice(1).map(([lab, fn]) => `<tr><th scope="row">${lab}</th>${sel.map(r => `<td>${fn(r)}</td>`).join("")}</tr>`).join("")}
      <tr><th scope="row">${Atlas.t("js.cmp.r_brief")}</th>${sel.map(r => `<td>${ROWS[0][1](r)}</td>`).join("")}</tr></tbody>`;
  }

  // ---- Render ------------------------------------------------------------------------------------
  function render() {
    const sel = ids.map(id => byId[id]);
    el("chips").innerHTML = sel.map(r => `<li class="chip">${Atlas.esc(name(r))}
      <button type="button" data-id="${r.id}" aria-label="${Atlas.esc(Atlas.t("js.cmp.remove", { name: name(r) }))}">×</button></li>`).join("");
    el("compare-empty").hidden = sel.length > 0;
    el("compare-body").hidden = sel.length === 0;
    el("pick-input").disabled = el("pick-add").disabled = sel.length >= MAX;
    el("pick-input").placeholder = sel.length >= MAX ? Atlas.t("js.cmp.up_to", { n: MAX }) : Atlas.t("js.cmp.placeholder");
    history.replaceState(null, "", sel.length ? `?ids=${ids.join(",")}` : location.pathname);
    if (sel.length) { drawChart(sel); drawTable(sel); }
  }
  render();
})();
