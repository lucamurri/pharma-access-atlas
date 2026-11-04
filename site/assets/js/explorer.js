/* Drug explorer: filterable, sortable table. Filters and sort live in the
   URL (?area=Oncology&sort=lag) so a filtered view can be shared as a link. */

(async () => {
  const { rows } = await Atlas.load();
  const RATING_ORDER = ["major", "considerable", "minor", "non-quantifiable", "no added benefit", "lesser", "not assessed"];

  // Helper values used only for sorting.
  rows.forEach(r => {
    r.it_sort = r.it_lag ?? (r.it_waiting !== null ? 100000 + r.it_waiting : null); // waiting sorts last
    r.gba_sort = r.gba_rating ? RATING_ORDER.indexOf(r.gba_rating) : null;
  });

  const el = id => document.getElementById(id);
  const controls = { search: el("f-search"), area: el("f-area"), company: el("f-company"),
                     orphan: el("f-orphan"), year: el("f-year") };

  // Fill the dropdowns from the data.
  const fillSelect = (select, values) => values.forEach(v => select.add(new Option(v, v)));
  fillSelect(controls.area, [...new Set(rows.map(r => r.area))].sort());
  fillSelect(controls.company, [...new Set(rows.map(r => r.company))].sort());
  fillSelect(controls.year, [...new Set(rows.map(r => r.first_year))].sort());

  // Restore state from the URL.
  const params = new URLSearchParams(location.search);
  Object.entries(controls).forEach(([k, input]) => { if (params.get(k)) input.value = params.get(k); });
  let sortKey = params.get("sort") || "brand_us";
  let sortDir = params.get("dir") || "asc";

  const ratingPill = r => {
    if (!r.gba_rating) return '<span class="muted">n/a</span>';
    const cls = ["major", "considerable"].includes(r.gba_rating) ? "pill pill-accent" : "pill";
    return `<span class="${cls}">${Atlas.esc(r.gba_rating)}</span>`;
  };
  const italyCell = r => {
    if (r.it_lag !== null) return String(r.it_lag);
    if (r.it_waiting !== null) return `<span class="pill">waiting, ${r.it_waiting} so far</span>`;
    return '<span class="muted">n/a</span>';
  };
  const orphanCell = r => {
    const parts = [r.us_orphan === "yes" ? "US" : null, r.eu_orphan === "yes" ? "EU" : null].filter(Boolean);
    return parts.length ? parts.join(" + ") : '<span class="muted">no</span>';
  };

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
          <br><span class="muted small">${Atlas.esc(r.inn)}</span></th>
        <td>${Atlas.esc(r.area)}</td>
        <td>${Atlas.esc(r.company)}</td>
        <td style="white-space:nowrap">${Atlas.fmtDate(r.fda_date)}</td>
        <td style="white-space:nowrap">${Atlas.fmtDate(r.ec_date)}</td>
        <td class="num">${r.lag ?? "n/a"}</td>
        <td class="num">${italyCell(r)}</td>
        <td>${ratingPill(r)}</td>
        <td>${orphanCell(r)}</td>
      </tr>`).join("") || '<tr><td colspan="9">No drugs match these filters.</td></tr>';

    el("result-count").textContent = `Showing ${visible.length} of ${rows.length} drugs`;

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
  el("filters").addEventListener("reset", () => setTimeout(render, 0));
  render();
})();
