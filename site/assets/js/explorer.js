/* Drug explorer: filterable, sortable table. Filters and sort live in the
   URL (?area=Oncology&sort=lag) so a filtered view can be shared as a link. */

(async () => {
  const { rows } = await Atlas.load();
  const RATING_ORDER = ["major", "considerable", "minor", "non-quantifiable", "no added benefit", "lesser", "not assessed"];

  // Helper values used only for sorting.
  rows.forEach(r => {
    r.it_sort = r.it_lag ?? (r.it_waiting !== null ? 100000 + r.it_waiting : null); // waiting sorts last
    r.gba_sort = r.gba_rating ? RATING_ORDER.indexOf(r.gba_rating) : null;
    r.innov_sort = r.it_innov ? ["full", "conditional", "not recognised"].indexOf(r.it_innov) : null;
    r.fr_sort = r.fr_verdict ? ["I", "II", "III", "IV", "V", "SMR insufficient"].indexOf(r.fr_verdict) : null;
  });

  const el = id => document.getElementById(id);
  const controls = { search: el("f-search"), area: el("f-area"), company: el("f-company"),
                     orphan: el("f-orphan"), year: el("f-year") };

  // Fill the dropdowns from the data.
  const fillSelect = (select, values, show = v => v) => values.forEach(v => select.add(new Option(show(v), v)));
  fillSelect(controls.area, [...new Set(rows.map(r => r.area))].sort(), Atlas.label);
  fillSelect(controls.company, [...new Set(rows.map(r => r.company))].sort());
  fillSelect(controls.year, [...new Set(rows.map(r => r.first_year))].sort());

  // Restore state from the URL.
  const params = new URLSearchParams(location.search);
  Object.entries(controls).forEach(([k, input]) => { if (params.get(k)) input.value = params.get(k); });
  let sortKey = params.get("sort") || "brand_us";
  let sortDir = params.get("dir") || "asc";

  const ratingPill = r => {
    if (!r.gba_rating) return r.gba_pending ? `<span class="pill">${Atlas.t("js.in_progress")}</span>` : `<span class="muted">${Atlas.t("na")}</span>`;
    const cls = ["major", "considerable"].includes(r.gba_rating) ? "pill pill-accent" : "pill";
    return `<span class="${cls}">${Atlas.esc(Atlas.t(`gba.${r.gba_rating}`))}</span>`;
  };
  const italyCell = r => {
    if (r.it_lag !== null) return Atlas.num(r.it_lag);
    if (r.it_waiting !== null) return `<span class="pill">${Atlas.t("js.waiting_so_far", { n: Atlas.num(r.it_waiting) })}</span>`;
    return `<span class="muted">${Atlas.t("na")}</span>`;
  };
  const orphanCell = r => {
    const parts = [r.us_orphan === "yes" ? "US" : null, r.eu_orphan === "yes" ? "EU" : null].filter(Boolean);
    return parts.length ? parts.join(" + ") : `<span class="muted">${Atlas.t("js.no")}</span>`;
  };

  // Card labels on phones (the column headers are hidden there).
  const L = Object.fromEntries(["area", "company", "fda", "ec", "lag", "it", "innov", "de", "fr", "en", "orphan"]
    .map(k => [k, Atlas.esc(Atlas.t(`js.ex.${k}`))]));

  function render() {
    const q = controls.search.value.trim().toLowerCase();
    const visible = rows.filter(r =>
      (!q || [r.brand_us, r.brand_eu, r.inn, r.company].join(" ").toLowerCase().includes(q)) &&
      (!controls.area.value || r.area === controls.area.value) &&
      (!controls.company.value || r.company === controls.company.value) &&
      (!controls.orphan.value || r.orphan_any === controls.orphan.value) &&
      (!controls.year.value || r.first_year === controls.year.value));

    // Sort; empty values always go to the bottom.
    visible.sort((a, b) => {
      const x = a[sortKey], y = b[sortKey];
      if (x === null || x === undefined) return 1;
      if (y === null || y === undefined) return -1;
      const cmp = typeof x === "number" ? x - y : String(x).localeCompare(String(y));
      return sortDir === "asc" ? cmp : -cmp;
    });

    el("explorer-body").innerHTML = visible.map(r => `
      <tr>
        <th scope="row"><a href="${Atlas.briefUrl(r.id)}">${Atlas.esc(Atlas.drugName(r))}</a>
          ${r.cohort === "reference" ? ` <span class="pill">${Atlas.t("js.ref")}</span>` : ""}
          <br><span class="muted small">${Atlas.esc(r.inn)}</span></th>
        <td data-label="${L.area}">${Atlas.esc(Atlas.label(r.area))}</td>
        <td data-label="${L.company}">${Atlas.esc(r.company)}</td>
        <td data-label="${L.fda}" style="white-space:nowrap">${Atlas.fmtDate(r.fda_date)}</td>
        <td data-label="${L.ec}" style="white-space:nowrap">${Atlas.fmtDate(r.ec_date)}</td>
        <td class="num" data-label="${L.lag}">${r.lag === null ? Atlas.t("na") : Atlas.num(r.lag)}</td>
        <td class="num" data-label="${L.it}">${italyCell(r)}</td>
        <td data-label="${L.innov}">${r.it_innov ? Atlas.esc(Atlas.t(`innov.${r.it_innov}`)) : `<span class="muted">${Atlas.t("na")}</span>`}</td>
        <td data-label="${L.de}">${ratingPill(r)}</td>
        <td data-label="${L.fr}">${r.fr_verdict ? Atlas.esc(Atlas.t(`asmr.${r.fr_verdict}`))
              : r.fr_pending ? `<span class="pill">${Atlas.t("js.no_opinion_yet")}</span>` : `<span class="muted">${Atlas.t("na")}</span>`}</td>
        <td data-label="${L.en}">${r.en_decision ? Atlas.esc(Atlas.t(`nice.${r.en_decision}`)) : r.en_pending ? `<span class="pill">${Atlas.t("js.in_progress")}</span>` : `<span class="muted">${Atlas.t("na")}</span>`}</td>
        <td data-label="${L.orphan}">${orphanCell(r)}</td>
      </tr>`).join("") || `<tr><td colspan="12">${Atlas.t("js.no_match")}</td></tr>`;

    el("result-count").textContent = Atlas.t("js.showing", { n: visible.length, total: rows.length });

    // Tell screen readers which column is sorted.
    document.querySelectorAll("#explorer th[data-key]").forEach(th => {
      if (th.dataset.key === sortKey) th.setAttribute("aria-sort", sortDir === "asc" ? "ascending" : "descending");
      else th.removeAttribute("aria-sort");
    });

    // Keep the URL in sync (without reloading) so the view can be shared.
    const p = new URLSearchParams();
    Object.entries(controls).forEach(([k, input]) => { if (input.value) p.set(k, input.value); });
    if (sortKey !== "brand_us" || sortDir !== "asc") { p.set("sort", sortKey); p.set("dir", sortDir); }
    history.replaceState(null, "", p.toString() ? `?${p}` : location.pathname);
  }

  document.querySelectorAll("#explorer th[data-key] .sort-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const key = btn.parentElement.dataset.key;
      sortDir = key === sortKey && sortDir === "asc" ? "desc" : "asc";
      sortKey = key;
      render();
    });
  });
  Object.values(controls).forEach(input => input.addEventListener("input", render));
  // Phones hide the column headers, so a menu offers the same sorts.
  el("f-sort").addEventListener("input", e => { [sortKey, sortDir] = e.target.value.split(":"); render(); });
  el("filters").addEventListener("reset", () => { sortKey = "brand_us"; sortDir = "asc"; setTimeout(render, 0); });
  render();
})();
