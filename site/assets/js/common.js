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

// Keyboard access for tables wider than their box: a box that scrolls sideways gets a focus
// stop and a label, so it can be scrolled with the arrow keys (WCAG 2.1.1). Re-checked when
// page scripts fill tables in, when <details> table views open, and on resize.
(() => {
  let pending = false;
  const update = () => {
    pending = false;
    document.querySelectorAll(".table-scroll").forEach(box => {
      const scrolls = box.scrollWidth > box.clientWidth + 1;
      if (scrolls && !box.hasAttribute("tabindex")) {
        box.setAttribute("tabindex", "0");
        box.setAttribute("role", "region");
        const caption = box.querySelector("caption");
        box.setAttribute("aria-label", caption ? caption.textContent.trim() : "Table, scrolls sideways");
      } else if (!scrolls && box.getAttribute("tabindex") === "0") {
        ["tabindex", "role", "aria-label"].forEach(a => box.removeAttribute(a));
      }
    });
  };
  const schedule = () => { if (!pending) { pending = true; requestAnimationFrame(update); } };
  new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
  document.addEventListener("toggle", schedule, true);
  window.addEventListener("resize", schedule);
  schedule();
})();
