/* Shared helpers for the Pharma Access Atlas pages. No libraries needed. */

const Atlas = (() => {
  // data-root leads back to the site root (assets, data); data-pages to this language's top folder.
  const root = document.body.dataset.root || "";
  const pages = document.body.dataset.pages || "";
  const lang = document.body.dataset.lang || "en";
  let strings = {}, locale = "en-GB";

  async function load() {
    const response = await fetch(`${root}data/atlas.${lang}.json`);
    if (!response.ok) throw new Error(`Could not load data/atlas.${lang}.json`);
    const data = await response.json();
    strings = data.t || {};
    locale = data.locale || locale;
    return data;
  }

  // Interface text in the page's language: t("js.key", {n: 3}) fills {n}. Falls back to the key.
  function t(key, vars) {
    const text = strings[key] ?? key;
    return vars ? text.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m)) : text;
  }
  // Data labels (therapy areas, EU status) translated when a translation exists.
  const label = text => strings[`label.${text}`] ?? text;
  // Whole numbers the local way: 1,234 / 1.234 / 1 234.
  const num = n => (n === null || n === undefined ? t("na") : Number(n).toLocaleString(locale, { maximumFractionDigits: 1 }));
  // Decimals kept, the local way (0.038 -> 0,038): for p-values.
  const dec = (n, digits = 3) => (n === null || n === undefined ? t("na") : Number(n).toLocaleString(locale, { maximumFractionDigits: digits }));

  // Read a colour from the stylesheet so charts follow light/dark mode.
  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function fmtDate(iso) {
    if (!iso) return t("na");
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  }

  function esc(text) {
    return String(text ?? "").replace(/[&<>"']/g, c => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function briefUrl(id) {
    return `${pages}drugs/${id}.html`;
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

  return { load, cssVar, fmtDate, esc, briefUrl, drugName, table, root, pages, lang, t, label, num, dec };
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
        box.setAttribute("aria-label", caption ? caption.textContent.trim() : Atlas.t("js.table_scrolls"));
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
