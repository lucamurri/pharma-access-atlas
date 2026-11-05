/* Company scorecard: sortable table built from summary.companies (computed in pipeline/analysis.py).
   The "companies shown" choice and the sort live in the URL so a view can be shared. */

(async () => {
  const { summary } = await Atlas.load();
  const companies = summary.companies.map(c => ({
    ...c,
    it_sort: c.it_median ?? (c.it_n ? 100000 : null), // "not reached yet" sorts after every number
  }));

  const el = id => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  if (params.get("min")) el("sc-min").value = params.get("min");
  let sortKey = params.get("sort") || "n";
  let sortDir = params.get("dir") || "desc";

  const share = (pos, n) => (n ? `${Atlas.t("js.pct", { n: Math.round((100 * pos) / n) })}<br><span class="muted small">${Atlas.t("js.x_of_y", { x: pos, y: n })}</span>`
                               : `<span class="muted">${Atlas.t("na")}</span>`);
  const italy = c => {
    if (!c.it_n) return `<span class="muted">${Atlas.t("na")}</span>`;
    const waiting = c.it_waiting ? Atlas.t("js.sc_waiting", { n: c.it_waiting }) : "";
    const value = c.it_median !== null ? Atlas.num(c.it_median) : Atlas.t("js.not_yet");
    return `${value}<br><span class="muted small">${Atlas.t("js.n_drugs", { n: c.it_n })}${waiting}</span>`;
  };

  // Card labels on phones (the column headers are hidden there).
  const L = Object.fromEntries(["drugs", "lag", "it", "de", "fr", "en"].map(k => [k, Atlas.esc(Atlas.t(`js.sc.${k}`))]));

  function render() {
    const min = Number(el("sc-min").value);
    const visible = companies.filter(c => c.n >= min);
    visible.sort((a, b) => {
      const x = a[sortKey], y = b[sortKey];
      if (x === null || x === undefined) return 1;
      if (y === null || y === undefined) return -1;
      const cmp = typeof x === "number" ? x - y : String(x).localeCompare(String(y));
      return (sortDir === "asc" ? cmp : -cmp) || b.n - a.n;
    });
    el("scorecard-body").innerHTML = visible.map(c => `
      <tr>
        <th scope="row"><a href="explorer.html?company=${encodeURIComponent(c.company)}">${Atlas.esc(c.company)}</a>
          <br><span class="muted small">${Atlas.esc(c.drugs.join(", "))}</span></th>
        <td class="num" data-label="${L.drugs}"><span>${c.n}</span></td>
        <td class="num" data-label="${L.lag}"><span>${c.lag_median !== null ? Atlas.num(Math.floor(c.lag_median + 0.5)) : Atlas.t("na")}
          ${c.eu_first ? `<br><span class="muted small">${Atlas.t("js.sc_eu_first", { n: c.eu_first })}</span>` : ""}</span></td>
        <td class="num" data-label="${L.it}"><span>${italy(c)}</span></td>
        <td class="num" data-label="${L.de}"><span>${share(c.de_pos, c.de_n)}</span></td>
        <td class="num" data-label="${L.fr}"><span>${share(c.fr_pos, c.fr_n)}</span></td>
        <td class="num" data-label="${L.en}"><span>${share(c.en_pos, c.en_n)}</span></td>
      </tr>`).join("");
    el("sc-count").textContent = Atlas.t("js.sc_showing", { n: visible.length, total: companies.length });

    document.querySelectorAll("#scorecard th[data-key]").forEach(th => {
      if (th.dataset.key === sortKey) th.setAttribute("aria-sort", sortDir === "asc" ? "ascending" : "descending");
      else th.removeAttribute("aria-sort");
    });
    const p = new URLSearchParams();
    if (el("sc-min").selectedIndex !== 0) p.set("min", el("sc-min").value);
    if (sortKey !== "n" || sortDir !== "desc") { p.set("sort", sortKey); p.set("dir", sortDir); }
    history.replaceState(null, "", p.toString() ? `?${p}` : location.pathname);
  }

  document.querySelectorAll("#scorecard th[data-key] .sort-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const key = btn.parentElement.dataset.key;
      // Names sort A-Z first; numbers sort high-to-low first, except days (lower is faster).
      const firstDir = key === "company" || key === "lag_median" || key === "it_sort" ? "asc" : "desc";
      sortDir = key === sortKey ? (sortDir === "asc" ? "desc" : "asc") : firstDir;
      sortKey = key;
      render();
    });
  });
  el("sc-min").addEventListener("input", render);
  // Phones hide the column headers, so a menu offers the same sorts.
  el("sc-sort").addEventListener("input", e => { [sortKey, sortDir] = e.target.value.split(":"); render(); });
  render();
})();
