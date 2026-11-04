/* Shared helpers for the Pharma Access Atlas pages. No libraries needed. */

const Atlas = (() => {
  // Pages in sub-folders (drug briefs) set data-root="../" on <body>.
  const root = document.body.dataset.root || "";

  async function load() {
    const response = await fetch(root + "data/atlas.json");
    if (!response.ok) throw new Error("Could not load data/atlas.json");
    return response.json();
  }

  // Read a colour from the stylesheet so charts follow light/dark mode.
  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  function fmtDate(iso) {
    if (!iso) return "n/a";
    const [y, m, d] = iso.split("-").map(Number);
    return `${d} ${MONTHS[m - 1]} ${y}`;
  }

  function esc(text) {
    return String(text ?? "").replace(/[&<>"']/g, c => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function briefUrl(id) {
    return `${root}drugs/${id}.html`;
  }

  function drugName(row) {
    return row.brand_us === row.brand_eu ? row.brand_us : `${row.brand_us} / ${row.brand_eu}`;
  }

  // Build a simple accessible HTML table from column definitions.
  function table(rows, columns) {
    const head = columns.map(c => `<th scope="col"${c.num ? ' class="num"' : ""}>${esc(c.label)}</th>`).join("");
    const body = rows.map(r => "<tr>" + columns.map((c, i) => {
      const value = c.html ? c.html(r) : esc(c.value(r));
      const tag = i === 0 ? 'th scope="row"' : "td";
      return `<${tag}${c.num ? ' class="num"' : ""}>${value}</${tag.split(" ")[0]}>`;
    }).join("") + "</tr>").join("");
    return `<table class="data-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  }

  return { load, cssVar, fmtDate, esc, briefUrl, drugName, table, root };
})();
