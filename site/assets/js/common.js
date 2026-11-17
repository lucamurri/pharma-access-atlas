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

// Quick drug search in the header: type a brand or ingredient, pick a result, open its brief.
// Accessible combobox: arrow keys move, Enter opens, Escape closes; "/" focuses the box from anywhere.
(() => {
  const form = document.querySelector(".site-search");
  if (!form) return;
  const input = form.querySelector("input"), list = form.querySelector("[role=listbox]");
  const plain = s => String(s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
  let index = null, items = [], active = -1;

  const load = async () => {
    if (index) return index;
    const res = await fetch(form.dataset.index);
    index = (await res.json()).map(d => ({ ...d, k: [d.b, d.e, d.n, d.c].map(plain) }));
    return index;
  };
  const score = (d, q) => {
    const [b, e, n, c] = d.k;
    if (b.startsWith(q) || e.startsWith(q)) return 0;
    if (n.startsWith(q)) return 1;
    if (b.includes(q) || e.includes(q) || n.includes(q)) return 2;
    if (c.includes(q)) return 3;
    return -1;
  };
  const close = () => { list.hidden = true; input.setAttribute("aria-expanded", "false"); input.removeAttribute("aria-activedescendant"); active = -1; };
  const highlight = i => {
    active = i;
    [...list.children].forEach((li, j) => li.setAttribute("aria-selected", j === i ? "true" : "false"));
    if (i >= 0 && list.children[i]) { input.setAttribute("aria-activedescendant", list.children[i].id); list.children[i].scrollIntoView({ block: "nearest" }); }
  };
  const go = d => { location.href = `${form.dataset.pages}drugs/${d.i}.html`; };

  input.addEventListener("input", async () => {
    const q = plain(input.value.trim());
    if (q.length < 2) { close(); return; }
    const all = await load();
    items = all.map(d => [score(d, q), d]).filter(([s]) => s >= 0)
      .sort((x, y) => x[0] - y[0] || x[1].b.localeCompare(y[1].b)).slice(0, 8).map(([, d]) => d);
    const esc = Atlas.esc;
    list.innerHTML = items.length
      ? items.map((d, j) => `<li id="ss-${j}" role="option" aria-selected="false" data-j="${j}">
          <span class="ss-name">${esc(d.b === d.e ? d.b : `${d.b} / ${d.e}`)}</span>
          <span class="ss-meta">${esc(d.n)} · ${esc(d.c)}</span></li>`).join("")
      : `<li class="ss-none" role="option" aria-disabled="true">${esc(form.dataset.none)}</li>`;
    list.hidden = false; input.setAttribute("aria-expanded", "true"); highlight(items.length ? 0 : -1);
  });
  input.addEventListener("keydown", e => {
    if (list.hidden) return;
    if (e.key === "ArrowDown") { e.preventDefault(); highlight(Math.min(active + 1, items.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); highlight(Math.max(active - 1, 0)); }
    else if (e.key === "Enter" && items[active]) { e.preventDefault(); go(items[active]); }
    else if (e.key === "Escape") { close(); }
  });
  list.addEventListener("mousedown", e => {
    const li = e.target.closest("li[data-j]");
    if (li) { e.preventDefault(); go(items[Number(li.dataset.j)]); }
  });
  input.addEventListener("blur", () => setTimeout(close, 120));
  document.addEventListener("keydown", e => {
    const typing = /^(input|textarea|select)$/i.test(document.activeElement?.tagName || "");
    if (e.key === "/" && !typing && !e.metaKey && !e.ctrlKey) { e.preventDefault(); input.focus(); }
  });
})();

// "On this page": built from the page's section headings. On the overview it is a sticky bar above
// the figures; on Insights and Methodology a sticky contents column in the empty right margin.
(() => {
  const page = document.body.dataset.page;
  const main = document.getElementById("main");
  let heads = [];
  if (page === "index") heads = [...main.querySelectorAll(":scope > .chart-card > h2")];
  else if (page === "insights") heads = [...main.querySelectorAll(".findings section > h2")];
  else if (page === "methodology") heads = [...main.querySelectorAll("h2")].filter(h => !h.closest("table, details"));
  if (heads.length < 3) return;

  heads.forEach((h, i) => { if (!h.id) h.id = `section-${i + 1}`; });
  const nav = document.createElement("nav");
  nav.className = `page-toc page-toc-${page === "index" ? "bar" : "rail"}`;
  nav.setAttribute("aria-label", document.body.dataset.toc || "On this page");
  const label = page === "index" ? "" : `<p class="page-toc-label">${Atlas.esc(document.body.dataset.toc || "")}</p>`;
  nav.innerHTML = `${label}<ol>${heads.map(h => {
    const num = h.querySelector(".finding-num");
    const text = num ? h.textContent.replace(num.textContent, "").trim() : h.textContent.trim();
    return `<li><a href="#${h.id}">${num ? `<span class="toc-num">${Atlas.esc(num.textContent)}</span>` : ""}${Atlas.esc(text)}</a></li>`;
  }).join("")}</ol>`;
  if (page === "index") main.insertBefore(nav, heads[0].closest(".chart-card"));
  else main.prepend(nav);
  document.body.classList.add("has-toc");

  // Mark the section being read.
  const links = new Map(heads.map(h => [h.id, nav.querySelector(`a[href="#${h.id}"]`)]));
  const seen = new Set();
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => (e.isIntersecting ? seen.add(e.target.id) : seen.delete(e.target.id)));
    const current = heads.find(h => seen.has(h.id)) || null;
    if (!current) return;
    links.forEach((a, id) => (id === current.id ? a.setAttribute("aria-current", "true") : a.removeAttribute("aria-current")));
  }, { rootMargin: "-10% 0px -70% 0px" });
  heads.forEach(h => obs.observe(h.closest("section") || h));
})();

// Explorer and scorecard: clicking anywhere on a row opens it (the link in the first cell stays the
// keyboard target). Text selection and clicks on other links or buttons are left alone.
document.addEventListener("click", e => {
  const row = e.target.closest("#explorer tbody tr, #scorecard tbody tr");
  if (!row || e.target.closest("a, button, input, select, summary")) return;
  if (String(window.getSelection?.() || "").length) return;
  const link = row.querySelector("th a, td a");
  if (!link) return;
  if (e.metaKey || e.ctrlKey) window.open(link.href, "_blank", "noopener");
  else location.href = link.href;
});
