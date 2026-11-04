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

  const share = (pos, n) => (n ? `${Math.round((100 * pos) / n)}%<br><span class="muted small">${pos} of ${n}</span>`
                               : '<span class="muted">n/a</span>');
  const italy = c => {
    if (!c.it_n) return '<span class="muted">n/a</span>';
    const waiting = c.it_waiting ? `, ${c.it_waiting} waiting` : "";
    const value = c.it_median !== null ? c.it_median.toLocaleString("en-US") : "not yet";
    return `${value}<br><span class="muted small">${c.it_n} drugs${waiting}</span>`;
  };

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
        <td class="num" data-label="Drugs"><span>${c.n}</span></td>
        <td class="num" data-label="US→EU lag, median days"><span>${c.lag_median !== null ? Math.floor(c.lag_median + 0.5).toLocaleString("en-US") : "n/a"}
          ${c.eu_first ? `<br><span class="muted small">${c.eu_first} EU first</span>` : ""}</span></td>
        <td class="num" data-label="Italy: half reimbursed within (days)"><span>${italy(c)}</span></td>
        <td class="num" data-label="Germany: added benefit"><span>${share(c.de_pos, c.de_n)}</span></td>
        <td class="num" data-label="France: improvement"><span>${share(c.fr_pos, c.fr_n)}</span></td>
        <td class="num" data-label="England: positive"><span>${share(c.en_pos, c.en_n)}</span></td>
      </tr>`).join("");
    el("sc-count").textContent = `Showing ${visible.length} of ${companies.length} companies`;

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
