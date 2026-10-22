// FRANK web UI. Plain DOM: every value from the API or a file is written
// with textContent, never as HTML (IoC values are attacker-controlled).
import init, { preview, Analyst } from "./pkg/frank_wasm.js";

const $ = (id) => document.getElementById(id);
const wasm = init();
let token = "";
try { token = sessionStorage.getItem("frank-token") || ""; } catch { /* storage blocked */ }

function el(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  for (const c of children) e.append(c instanceof Node ? c : document.createTextNode(String(c ?? "")));
  return e;
}

function show(target, ...nodes) {
  target.replaceChildren(...nodes);
}

function errorNode(e) {
  return el("p", { class: "error" }, e?.message || String(e));
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (token) headers.authorization = `Bearer ${token}`;
  const resp = await fetch(path, { ...options, headers });
  if (!resp.ok) {
    let msg = `${resp.status} ${resp.statusText}`;
    try { msg = (await resp.json()).error || msg; } catch { /* not JSON */ }
    throw new Error(msg);
  }
  return resp;
}

function table(columns, rows) {
  const head = el("tr", {}, ...columns.map((c) => el("th", {}, c)));
  const body = rows.map((r) => el("tr", {}, ...r.map((v) =>
    el("td", typeof v === "number" ? { class: "num" } : {}, v === null ? "∅" : v))));
  return el("div", { class: "table-wrap" }, el("table", {}, el("thead", {}, head), el("tbody", {}, ...body)));
}

const iso = (ns) => new Date(ns / 1e6).toISOString().replace(".000", "");
const isoDay = (ns) => iso(ns).slice(0, 10);

// --- tabs, routing and token ----------------------------------------------
// The URL hash is the state: "#stats", "#explore?group=rule&sector=energy&pane=rule:r1".

const TIERS = ["public", "observer", "contributor", "partner", "core"];
let tier = "public";
const atLeast = (t) => TIERS.indexOf(tier) >= TIERS.indexOf(t);

function showTab(name) {
  for (const b of document.querySelectorAll("nav button")) b.setAttribute("aria-selected", b.dataset.tab === name);
  for (const p of document.querySelectorAll("main section")) p.hidden = p.id !== name;
}

let lastExplore = "";
for (const b of document.querySelectorAll("nav button")) {
  b.addEventListener("click", () => {
    location.hash = b.dataset.tab === "explore" ? (lastExplore || `explore?group=${defaultGroup()}`) : b.dataset.tab;
  });
}

function route() {
  const [name, qs] = location.hash.slice(1).split("?");
  const tab = document.getElementById(name || "stats") ? (name || "stats") : "stats";
  showTab(tab);
  if (tab === "explore") {
    lastExplore = location.hash.slice(1);
    loadExplore(new URLSearchParams(qs || ""));
  } else {
    closePane();
  }
}
window.addEventListener("hashchange", route);

async function whoami() {
  try {
    const me = await (await api("/v1/whoami")).json();
    tier = me.tier;
    $("tier").textContent = me.label ? `${me.tier} · ${me.label}` : me.tier;
  } catch (e) {
    tier = "public";
    $("tier").textContent = `rejected: ${e.message}`;
  }
  for (const o of $("ex-group").options) o.disabled = !atLeast(DIMENSION_TIER[o.value]);
  loadStats();
  route();
}

$("token").value = token;
$("auth").addEventListener("submit", (ev) => {
  ev.preventDefault();
  // Accept a pasted "Bearer <token>" as well as the bare token.
  token = $("token").value.trim().replace(/^bearer\s+/i, "");
  $("token").value = token;
  try { sessionStorage.setItem("frank-token", token); } catch { /* storage blocked */ }
  whoami();
});

// --- statistics -----------------------------------------------------------

function tile(k, v) {
  return el("div", { class: "tile" }, el("div", { class: "v" }, Number(v ?? 0).toLocaleString()), el("div", { class: "k" }, k));
}

function bars(title, cells, dim) {
  const max = Math.max(1, ...cells.map((c) => c.count));
  const card = el("div", { class: "card" }, el("h3", {}, title));
  if (!cells.length) card.append(el("p", { class: "note" }, "nothing above the threshold"));
  for (const c of cells) {
    const fill = el("div", { class: "fill" });
    fill.style.width = `${(100 * c.count) / max}%`;
    card.append(el("div", { class: "bar" },
      linkTo(c.key, () => seed(dim, c.key), "label"), el("span", { class: "n" }, c.count.toLocaleString()),
      el("div", { class: "track" }, fill)));
  }
  return card;
}

async function loadStats() {
  try {
    const s = await (await api(`/v1/statistics?days=${$("days").value}`)).json();
    show($("tiles"), tile("sightings", s.sightings), tile("observations", s.observations), tile("distinct IoCs (retained)", s.iocs));
    const sections = [
      ["by_ioc_type", "IoC types", "ioc_type"], ["by_severity", "Severity", "severity"],
      ["by_target_sector", "Target sectors", "sector"], ["top_rules", "SIGMA rules", "rule"],
      ["top_techniques", "ATT&CK techniques", "technique"], ["top_campaigns", "Campaigns", "campaign"],
    ];
    show($("breakdowns"), ...sections.filter(([k]) => s[k]).map(([k, t, d]) => bars(t, s[k], d)));
    $("stats-note").textContent = s.min_cell > 1
      ? `Cells with fewer than ${s.min_cell} reporters are suppressed at the ${s.tier} tier. Click a bar to explore.`
      : s.tier === "public" ? "Public tier: totals only. A token shows more." : "";
  } catch (e) {
    show($("breakdowns"), errorNode(e));
  }
}
$("refresh").addEventListener("click", loadStats);
$("days").addEventListener("change", loadStats);

// --- submit ---------------------------------------------------------------

const EXAMPLE = {
  submission: {
    submitter: { organisation_id: "identity-f431f809-377b-45e0-aa1c-6a4751cae5ff", sector: "cybersecurity_services" },
    hit_target: { sector: "energy", organisation_size: "large" },
    sighting: {
      confidence: 87, severity: "high", observation_count: 3,
      sigma_detection: { rule_id: "sigma-rule-npm-postinstall-exfil" },
      threat_context: { campaign: { name: "npm_worm_shai_hulud_2025_q4" },
        mitre_attack: { techniques: [{ technique: "T1195.001" }] } },
      observables: { network: [
        { type: "ipv4", value: "178.63.67.106" },
        { type: "domain", value: "webhook.site" } ] },
    },
  },
};

$("example").addEventListener("click", () => {
  const ex = structuredClone(EXAMPLE);
  ex.submission.sighting.timestamp = new Date().toISOString();
  $("submission").value = JSON.stringify(ex, null, 2);
});

const ROW_COLUMNS = ["ts_ns", "rule_id", "technique", "campaign", "ioc_type", "ioc_value",
  "reporter_sector", "target_sector", "target_size", "severity", "confidence", "observations", "tlp"];

async function doPreview() {
  await wasm;
  try {
    const out = JSON.parse(preview($("submission").value, Date.now()));
    show($("submit-out"), el("p", { class: "note" }, `${out.rows.length} row(s) would be shared:`),
      table(ROW_COLUMNS, out.rows.map((r) => ROW_COLUMNS.map((c) => r[c]))));
    return true;
  } catch (e) {
    show($("submit-out"), errorNode(e));
    return false;
  }
}
$("do-preview").addEventListener("click", doPreview);

$("do-submit").addEventListener("click", async () => {
  if (!(await doPreview())) return;
  try {
    const r = await (await api("/v1/sightings", {
      method: "POST", headers: { "content-type": "application/json" }, body: $("submission").value,
    })).json();
    $("submit-out").prepend(el("p", {}, `Stored ${r.rows} row(s): ${r.sighting_ids.join(", ")}`));
    loadStats();
  } catch (e) {
    $("submit-out").prepend(errorNode(e));
  }
});

// --- lookup ---------------------------------------------------------------

$("ioc-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const q = new URLSearchParams({ type: $("ioc-type").value, value: $("ioc-value").value });
  try {
    const r = await (await api(`/v1/iocs?${q}`)).json();
    if (!r.known) {
      show($("lookup-out"), el("p", {}, `${r.ioc.type} ${r.ioc.value}: not seen in the retained days.`));
      return;
    }
    show($("lookup-out"),
      el("p", {}, `${r.ioc.type} ${r.ioc.value}: seen ${r.count}×, first ${iso(r.first_seen)}, last ${iso(r.last_seen)}.`),
      table(["day", "count", "first", "last"], r.days.map((d) => [d.day, d.count, iso(d.first_ts), iso(d.last_ts)])),
      table(["SIGMA rule", "rows"], r.rules.map((x) => [x.rule_id, x.count])));
  } catch (e) {
    show($("lookup-out"), errorNode(e));
  }
});

$("cidr-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  try {
    const r = await (await api(`/v1/iocs/range?${new URLSearchParams({ cidr: $("cidr").value })}`)).json();
    show($("lookup-out"), el("p", {}, `${r.addresses.length} address(es) in ${r.cidr}`),
      table(["address", "count"], r.addresses.map((a) => [a.value, a.count])));
  } catch (e) {
    show($("lookup-out"), errorNode(e));
  }
});

// --- local analysis -------------------------------------------------------

let analyst = null;

$("load-files").addEventListener("click", async () => {
  await wasm;
  const status = $("files-status");
  try {
    const list = await (await api("/v1/files")).json();
    analyst = new Analyst();
    let rows = 0, bytes = 0;
    for (const [i, f] of list.files.entries()) {
      status.textContent = `downloading ${i + 1}/${list.files.length}…`;
      const buf = new Uint8Array(await (await api(`/v1/files/${f.path}`)).arrayBuffer());
      rows += analyst.add(f.path, buf);
      bytes += buf.length;
    }
    status.textContent = list.files.length
      ? `${list.files.length} file(s), ${rows.toLocaleString()} rows, ${(bytes / 1024).toFixed(0)} KiB in browser memory`
      : "no sightings yet";
  } catch (e) {
    status.textContent = "";
    show($("sql-out"), errorNode(e));
  }
});

$("run-sql").addEventListener("click", () => {
  if (!analyst || analyst.is_empty()) {
    show($("sql-out"), errorNode("Download the files first."));
    return;
  }
  const t0 = performance.now();
  try {
    const r = JSON.parse(analyst.query($("sql").value));
    $("sql-status").textContent = `${r.rows.length} row(s) in ${(performance.now() - t0).toFixed(1)} ms` +
      (r.merged ? ", merged across files" : ", per file");
    show($("sql-out"), table(r.columns, r.rows));
  } catch (e) {
    $("sql-status").textContent = "";
    show($("sql-out"), errorNode(e));
  }
});

// --- explore ----------------------------------------------------------------
// One list grouped by a dimension, filtered by others; a sliding pane for one
// rule or IoC. The server runs fixed queries only (#157).

const DIMENSION_TIER = {
  rule: "contributor", ioc: "contributor", campaign: "contributor", technique: "contributor",
  sector: "observer", ioc_type: "observer", severity: "observer",
};
const DIMENSION_LABEL = {
  rule: "SIGMA rule", ioc: "IoC", campaign: "campaign", technique: "technique",
  sector: "sector", ioc_type: "IoC type", severity: "severity",
};
const defaultGroup = () => (atLeast("contributor") ? "rule" : "sector");

function linkTo(text, onClick, cls = "") {
  const b = el("button", { class: `link ${cls}`.trim(), type: "button", title: text }, text);
  b.addEventListener("click", onClick);
  return b;
}

function go(params) {
  location.hash = `explore?${params}`;
}

function current() {
  return new URLSearchParams(location.hash.split("?")[1] || "");
}

/** From the dashboard: open Explore filtered on one value. */
function seed(dim, key) {
  if (dim === "rule") {
    go(new URLSearchParams({ group: "ioc", rule: key, pane: `rule:${key}` }));
    return;
  }
  const group = atLeast("contributor") ? "rule" : (dim === "sector" ? "ioc_type" : "sector");
  go(new URLSearchParams({ group, [dim]: key }));
}

/** From a list row: open the entity, or narrow to it. */
function drill(group, key) {
  const p = current();
  if (group === "rule" || group === "ioc") {
    p.set("pane", `${group}:${key}`);
  } else {
    p.set(group, key);
    p.set("group", atLeast("contributor") ? "rule" : (group === "sector" ? "ioc_type" : "sector"));
  }
  go(p);
}

let exploreSeq = 0;
async function loadExplore(params) {
  const group = params.get("group") || defaultGroup();
  $("ex-group").value = group;
  $("ex-days").value = params.get("days") || "30";
  const filters = [...params].filter(([k]) => k in DIMENSION_TIER);
  show($("ex-filters"), ...filters.map(([k, v]) => {
    const chip = el("button", { class: "chip", type: "button", title: "remove filter" }, `${DIMENSION_LABEL[k]}: ${v}`);
    chip.addEventListener("click", () => { const p = current(); p.delete(k); go(p); });
    return chip;
  }));
  const pane = params.get("pane");
  if (pane) openPane(pane.slice(0, pane.indexOf(":")), pane.slice(pane.indexOf(":") + 1));
  else closePane();

  const query = new URLSearchParams([["group", group], ["days", $("ex-days").value], ...filters]);
  const seq = ++exploreSeq;
  try {
    const r = await (await api(`/v1/explore?${query}`)).json();
    if (seq !== exploreSeq) return;
    const rows = r.rows.map((x) => {
      const tr = el("tr", { class: "go", tabindex: "0" },
        el("td", {}, x.key), el("td", { class: "num" }, x.count.toLocaleString()),
        el("td", { class: "num" }, x.reporters), el("td", {}, isoDay(x.first_seen)), el("td", {}, isoDay(x.last_seen)));
      const open = () => drill(group, x.key);
      tr.addEventListener("click", open);
      tr.addEventListener("keydown", (e) => { if (e.key === "Enter") open(); });
      return tr;
    });
    const head = el("tr", {}, ...[DIMENSION_LABEL[group], "rows", "reporters", "first seen", "last seen"].map((c) => el("th", {}, c)));
    show($("ex-list"), rows.length
      ? el("div", { class: "table-wrap" }, el("table", {}, el("thead", {}, head), el("tbody", {}, ...rows)))
      : el("p", { class: "note" }, "Nothing above the threshold for these filters."));
    $("ex-note").textContent = r.min_cell > 1
      ? `Groups with fewer than ${r.min_cell} reporters are hidden at the ${tier} tier.` : "";
  } catch (e) {
    if (seq === exploreSeq) show($("ex-list"), errorNode(e));
  }
}

for (const id of ["ex-group", "ex-days"]) {
  $(id).addEventListener("change", () => {
    const p = current();
    p.set(id === "ex-group" ? "group" : "days", $(id).value);
    p.delete("pane");
    go(p);
  });
}

// --- detail pane ---------------------------------------------------------------

function closePane() {
  $("pane").classList.remove("open");
  $("pane").setAttribute("aria-hidden", "true");
}

$("pane-close").addEventListener("click", () => { const p = current(); p.delete("pane"); go(p); });
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && $("pane").classList.contains("open")) $("pane-close").click();
});

function spark(trend) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  const w = 6, gap = 2, h = 48, max = Math.max(1, ...trend.map((d) => d[1]));
  svg.setAttribute("viewBox", `0 0 ${trend.length * (w + gap)} ${h}`);
  svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("class", "spark");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `per day, ${trend[0]?.[0]} to ${trend.at(-1)?.[0]}`);
  trend.forEach(([day, n], i) => {
    const r = document.createElementNS(ns, "rect");
    const bh = n ? Math.max(2, (h * n) / max) : 1;
    r.setAttribute("x", i * (w + gap)); r.setAttribute("y", h - bh);
    r.setAttribute("width", w); r.setAttribute("height", bh);
    if (!n) r.setAttribute("class", "zero");
    const t = document.createElementNS(ns, "title");
    t.textContent = `${day}: ${n}`;
    r.append(t);
    svg.append(r);
  });
  return svg;
}

function kpis(pairs) {
  return el("div", { class: "kpis" }, ...pairs.map(([k, v]) => tile(k, v)));
}

/** A short list whose items narrow Explore or open another pane. */
function linkList(title, cells, onPick) {
  if (!cells?.length) return [];
  return [el("h3", {}, title), el("div", {}, ...cells.map((c) =>
    el("div", { class: "bar" }, linkTo(c.key, () => onPick(c.key), "label"),
      el("span", { class: "n" }, c.reporters === undefined ? `${c.count}` : `${c.count} · ${c.reporters} rep.`))))];
}

let paneSeq = 0;
async function openPane(kind, key) {
  $("pane").classList.add("open");
  $("pane").setAttribute("aria-hidden", "false");
  $("pane-kind").textContent = kind === "rule" ? "SIGMA rule" : "IoC";
  show($("pane-body"), el("p", { class: "note" }, "loading…"));
  const seq = ++paneSeq;
  const filterOn = (dim) => (v) => { const p = current(); p.set(dim, v); p.delete("pane"); go(p); };
  const openOther = (k) => (v) => { const p = current(); p.set("pane", `${k}:${v}`); go(p); };
  try {
    let nodes;
    if (kind === "rule") {
      const days = current().get("days") || "30";
      const r = await (await api(`/v1/rules/${encodeURIComponent(key)}?days=${days}`)).json();
      nodes = !r.known
        ? [el("h2", {}, key), el("p", { class: "note" }, "Not seen by enough reporters in this window to show.")]
        : [el("h2", {}, r.rule),
          kpis([["rows", r.count], ["reporters", r.reporters]]),
          el("p", { class: "note" }, `first ${iso(r.first_seen)} · last ${iso(r.last_seen)}`),
          el("h3", {}, `per day, last ${r.trend.length} days`), spark(r.trend),
          ...linkList("IoCs", r.iocs, openOther("ioc")),
          ...linkList("target sectors", r.sectors, filterOn("sector")),
          ...linkList("severity", r.severities, filterOn("severity")),
          ...linkList("techniques", r.techniques, filterOn("technique")),
          ...linkList("campaigns", r.campaigns, filterOn("campaign"))];
    } else {
      const sep = key.indexOf(":");
      const q = new URLSearchParams({ type: key.slice(0, sep), value: key.slice(sep + 1) });
      const r = await (await api(`/v1/iocs?${q}`)).json();
      nodes = !r.known
        ? [el("h2", {}, key), el("p", { class: "note" }, "Not seen in the retained days.")]
        : [el("h2", {}, `${r.ioc.type} ${r.ioc.value}`),
          kpis([["rows", r.count], ["reporters", r.reporters]]),
          el("p", { class: "note" }, `first ${iso(r.first_seen)} · last ${iso(r.last_seen)}`),
          el("h3", {}, `per day, last ${r.trend.length} days`), spark(r.trend),
          ...linkList("SIGMA rules", r.rules.map((x) => ({ key: x.rule_id, count: x.count })), openOther("rule")),
          el("h3", {}, "days seen"),
          table(["day", "rows", "first", "last"], r.days.map((d) => [d.day, d.count, iso(d.first_ts), iso(d.last_ts)]))];
    }
    if (seq === paneSeq) show($("pane-body"), ...nodes);
  } catch (e) {
    if (seq === paneSeq) show($("pane-body"), errorNode(e));
  }
}

whoami();
