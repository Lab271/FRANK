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
// A user's role (#175), apart from its status: null, "admin" or "superadmin".
let role = null;
const hasRole = (r) => role !== null && (role === r || role === "superadmin");

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
  let tab = document.getElementById(name || "stats") ? (name || "stats") : "stats";
  if (tab === "admin" && !role) tab = "stats";
  showTab(tab);
  if (tab === "explore") {
    lastExplore = location.hash.slice(1);
    loadExplore(new URLSearchParams(qs || ""));
  } else {
    closePane();
  }
  if (tab === "about") loadAbout();
  if (tab === "api") loadApi();
  if (tab === "admin") loadAdmin();
}
window.addEventListener("hashchange", route);

async function whoami() {
  try {
    const me = await (await api("/v1/whoami")).json();
    tier = me.tier;
    role = me.role || null;
    $("tier").textContent = (me.label ? `${me.tier} · ${me.label}` : me.tier) + (role ? ` · ${role}` : "");
  } catch (e) {
    tier = "public";
    role = null;
    $("tier").textContent = `rejected: ${e.message}`;
  }
  document.querySelector('nav [data-tab="admin"]').hidden = !role;
  adminOrg = "";
  apiDone = false;
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
  ex.submission.sighting.sighting_id = crypto.randomUUID();
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

/** Gives each sighting without a `sighting_id` a new one, in the form
 * itself: the id is the sender's (#159), so sending the same form again
 * is recognised as a resend. */
function nameSightings() {
  let doc;
  try { doc = JSON.parse($("submission").value); } catch { return; }
  let added = false;
  for (const item of Array.isArray(doc) ? doc : [doc]) {
    const s = (item?.submission ?? item)?.sighting;
    if (s && typeof s === "object" && !s.sighting_id) { s.sighting_id = crypto.randomUUID(); added = true; }
  }
  if (added) $("submission").value = JSON.stringify(doc, null, 2);
}

/** JSON (also a STIX bundle) when the text starts like JSON, else YAML. */
const contentType = (text) => (/^\s*[[{]/.test(text) ? "application/json" : "application/yaml");

$("do-submit").addEventListener("click", async () => {
  if (!(await doPreview())) return;
  nameSightings();
  try {
    const r = await (await api("/v1/sightings", {
      method: "POST", headers: { "content-type": contentType($("submission").value) }, body: $("submission").value,
    })).json();
    const created = r.receipts.filter((x) => x.status === "created").length;
    const resent = r.receipts.length - created;
    $("submit-out").prepend(el("p", {},
      `Stored ${created} sighting(s), ${r.rows} row(s)` + (resent ? `; ${resent} already registered (resend)` : "") + ": ",
      el("code", {}, r.receipts.map((x) => x.sighting_id).join(", "))));
    loadStats();
  } catch (e) {
    $("submit-out").prepend(errorNode(e));
  }
});

// --- lookup ---------------------------------------------------------------

/** The lookup result stays compact; its rows open the side pane (#182):
 *  the IoC, one day of it, or a rule. */
async function lookup(type, value) {
  const out = $("lookup-out");
  try {
    const r = await (await api(`/v1/iocs?${new URLSearchParams({ type, value })}`)).json();
    if (!r.known) {
      show(out, el("p", {}, `${r.ioc.type} ${r.ioc.value}: not seen in the retained days.`));
      closePane();
      return;
    }
    const key = `${r.ioc.type}:${r.ioc.value}`;
    show(out,
      el("p", {}, linkTo(`${r.ioc.type} ${r.ioc.value}`, () => openPane("ioc", key), "label"),
        `: seen ${r.count}× by ${r.reporters} reporter(s), first ${iso(r.first_seen)}, last ${iso(r.last_seen)}.`),
      table(["day", "count", "first", "last"],
        r.days.map((d) => [linkTo(d.day, () => openPane("ioc", key, d.day), "label"), d.count, iso(d.first_ts), iso(d.last_ts)])),
      table(["SIGMA rule", "rows"],
        r.rules.map((x) => [linkTo(x.rule_id, () => openPane("rule", x.rule_id), "label"), x.count])));
    openPane("ioc", key);
  } catch (e) {
    show(out, errorNode(e));
  }
}

$("ioc-form").addEventListener("submit", (ev) => {
  ev.preventDefault();
  lookup($("ioc-type").value, $("ioc-value").value);
});

$("cidr-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  try {
    const r = await (await api(`/v1/iocs/range?${new URLSearchParams({ cidr: $("cidr").value })}`)).json();
    const pick = (a) => () => {
      const type = a.includes(":") ? "ipv6" : "ipv4";
      $("ioc-type").value = type;
      $("ioc-value").value = a;
      lookup(type, a);
    };
    show($("lookup-out"), el("p", {}, `${r.addresses.length} address(es) in ${r.cidr}`),
      table(["address", "count"], r.addresses.map((a) => [linkTo(a.value, pick(a.value), "label"), a.count])));
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
    const head = el("tr", {}, ...[DIMENSION_LABEL[group], "sightings", "reporters", "first seen", "last seen"].map((c) => el("th", {}, c)));
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

$("pane-close").addEventListener("click", () => {
  if (!location.hash.startsWith("#explore")) return closePane(); // opened from lookup
  const p = current(); p.delete("pane"); go(p);
});
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
async function openPane(kind, key, day) {
  $("pane").classList.add("open");
  $("pane").setAttribute("aria-hidden", "false");
  $("pane-kind").textContent = ({ rule: "SIGMA rule", ioc: "IoC", sighting: "sighting" }[kind] || kind) + (day ? ` · ${day}` : "");
  show($("pane-body"), el("p", { class: "note" }, "loading…"));
  const seq = ++paneSeq;
  // From Explore the pane follows the URL; from lookup it stays on the tab
  // and narrows Explore on what the pane shows.
  const inExplore = location.hash.startsWith("#explore");
  const base = () => inExplore ? current()
    : new URLSearchParams({ group: "rule", [kind === "ioc" ? "ioc" : "rule"]: key });
  const filterOn = (dim) => (v) => { const p = base(); p.set(dim, v); p.delete("pane"); go(p); };
  const openOther = (k) => (v) => {
    if (!inExplore) return openPane(k, v);
    const p = current(); p.set("pane", `${k}:${v}`); go(p);
  };
  try {
    let nodes;
    if (kind === "sighting") {
      nodes = await sightingNodes(key, filterOn, openOther);
    } else if (kind === "rule") {
      const days = current().get("days") || "30";
      const r = await (await api(`/v1/rules/${encodeURIComponent(key)}?days=${days}`)).json();
      nodes = !r.known
        ? [el("h2", {}, key), el("p", { class: "note" }, "Not seen by enough reporters in this window to show.")]
        : [el("h2", {}, r.rule),
          kpis([["sightings", r.count], ["reporters", r.reporters]]),
          el("p", { class: "note" }, `first ${iso(r.first_seen)} · last ${iso(r.last_seen)}`),
          el("h3", {}, `per day, last ${r.trend.length} days`), spark(r.trend),
          ...sightingsList("rule", key),
          ...linkList("IoCs", r.iocs, openOther("ioc")),
          ...linkList("target sectors", r.sectors, filterOn("sector")),
          ...linkList("severity", r.severities, filterOn("severity")),
          ...linkList("techniques", r.techniques, filterOn("technique")),
          ...linkList("campaigns", r.campaigns, filterOn("campaign"))];
    } else {
      const sep = key.indexOf(":");
      const q = new URLSearchParams({ type: key.slice(0, sep), value: key.slice(sep + 1) });
      if (day) q.set("day", day);
      const r = await (await api(`/v1/iocs?${q}`)).json();
      const panels = [
        ...linkList("SIGMA rules", r.panels?.rules, openOther("rule")),
        ...linkList("target sectors", r.panels?.sectors, filterOn("sector")),
        ...linkList("severity", r.panels?.severities, filterOn("severity")),
        ...linkList("techniques", r.panels?.techniques, filterOn("technique")),
        ...linkList("campaigns", r.panels?.campaigns, filterOn("campaign"))];
      const thin = el("p", { class: "note" }, "Not seen by enough reporters to show a breakdown.");
      const d = day && r.days.find((x) => x.day === day);
      nodes = !r.known
        ? [el("h2", {}, key), el("p", { class: "note" }, "Not seen in the retained days.")]
        : day
        ? [el("h2", {}, `${r.ioc.type} ${r.ioc.value}`),
          el("p", { class: "note" }, d ? `${day}: ${d.count} sighting(s), first ${iso(d.first_ts)} · last ${iso(d.last_ts)}` : `not seen on ${day}`),
          ...(panels.length ? panels : [thin]),
          linkTo("all days", () => openPane("ioc", key), "label")]
        : [el("h2", {}, `${r.ioc.type} ${r.ioc.value}`),
          kpis([["sightings", r.count], ["reporters", r.reporters]]),
          el("p", { class: "note" }, `first ${iso(r.first_seen)} · last ${iso(r.last_seen)}`),
          el("h3", {}, `per day, last ${r.trend.length} days`), spark(r.trend),
          ...sightingsList("ioc", key),
          ...panels,
          el("h3", {}, "days seen"),
          table(["day", "sightings", "first", "last"],
            r.days.map((x) => [linkTo(x.day, () => openPane("ioc", key, x.day), "label"), x.count, iso(x.first_ts), iso(x.last_ts)]))];
    }
    if (seq === paneSeq) show($("pane-body"), ...nodes);
  } catch (e) {
    if (seq === paneSeq) show($("pane-body"), errorNode(e));
  }
}

// --- sightings ----------------------------------------------------------------
// From a rule or IoC pane down to single sightings (#160): the records that
// match the pane and Explore's filters, newest first; one record as YAML.
// Partners and core see everyone's, contributors their own.

/** The pane's "sightings" section: filled in after the pane opens. */
function sightingsList(kind, key) {
  if (!atLeast("contributor")) return [];
  const mine = !atLeast("partner");
  const box = el("div", {}, el("p", { class: "note" }, "loading…"));
  const p = current();
  const days = Number(p.get("days") || "30");
  const q = new URLSearchParams([...p].filter(([k]) => k in DIMENSION_TIER && k !== kind));
  q.set(kind, key);
  q.set("since", new Date(Date.now() - days * 86_400_000).toISOString());
  q.set("order", "desc");
  q.set("limit", "20");
  if (mine) q.set("mine", "true");
  const seq = paneSeq; // openPane has counted this pane
  const rows = el("tbody");
  const more = el("button", { class: "lab-btn lab-btn--secondary", type: "button" }, "more");
  async function page(cursor) {
    if (cursor) q.set("cursor", cursor);
    try {
      const r = await (await api(`/v1/sightings?${q}`)).json();
      if (seq !== paneSeq) return;
      for (const s of r.sightings) {
        const rec = s.record;
        const tr = el("tr", { class: "go", tabindex: "0" },
          el("td", {}, rec.timestamp.replace(/:\d\d(\.\d+)?Z$/, "Z")), el("td", { class: "num" }, rec.count),
          el("td", { class: "num" }, rec.confidence), el("td", {}, rec.tlp), el("td", {}, s.reporter.slice(10, 18)));
        const open = () => { const h = current(); h.set("pane", `sighting:${s.sighting_id}`); go(h); };
        tr.addEventListener("click", open);
        tr.addEventListener("keydown", (e) => { if (e.key === "Enter") open(); });
        rows.append(tr);
      }
      more.hidden = !r.next_cursor;
      more.onclick = () => page(r.next_cursor);
      show(box, rows.children.length
        ? el("div", { class: "table-wrap" }, el("table", {},
          el("thead", {}, el("tr", {}, ...["time", "count", "conf.", "TLP", "reporter"].map((c) => el("th", {}, c)))), rows))
        : el("p", { class: "note" }, "No records in this window. Records exist for sightings stored since 0.15."), more);
    } catch (e) {
      if (seq === paneSeq) show(box, errorNode(e));
    }
  }
  page();
  return [el("h3", {}, mine ? "your sightings, newest first" : "sightings, newest first"), box];
}

/** A JSON value as YAML lines: block style, strings quoted when plain
 * YAML would read them as something else. */
function yamlLines(v, indent = "") {
  const scalar = (x) => {
    if (typeof x !== "string") return String(x);
    const plain = /^[\w./@+-][\w ./@:+-]*$/.test(x) && !/: |:$| #/.test(x) && !/\s$/.test(x)
      && !/^(true|false|null|~|[-+]?(\d[\d_]*)?\.?\d+([eE][-+]?\d+)?)$/i.test(x);
    return plain ? x : JSON.stringify(x);
  };
  const out = [];
  const nested = (x) => x && typeof x === "object" && Object.keys(x).length > 0;
  if (Array.isArray(v)) {
    for (const x of v) {
      if (nested(x)) {
        const inner = yamlLines(x, `${indent}  `);
        out.push(`${indent}- ${inner[0].trimStart()}`, ...inner.slice(1));
      } else {
        out.push(`${indent}- ${scalar(x)}`);
      }
    }
    return out;
  }
  for (const [k, x] of Object.entries(v)) {
    if (nested(x)) out.push(`${indent}${k}:`, ...yamlLines(x, `${indent}  `));
    else if (x && typeof x === "object") out.push(`${indent}${k}: ${Array.isArray(x) ? "[]" : "{}"}`);
    else out.push(`${indent}${k}: ${scalar(x)}`);
  }
  return out;
}

// The record's keys in reading order: what it is, what was seen, against
// whom, the evidence last; any other key before the evidence, by name.
const RECORD_ORDER = ["format", "sighting_id", "timestamp", "tlp", "severity", "confidence", "count",
  "reporter_sector", "sighting_of", "target"];
const ordered = (rec) => {
  const rank = (k) => (RECORD_ORDER.includes(k) ? RECORD_ORDER.indexOf(k) : k === "evidence" ? 2e9 : 1e9);
  return Object.fromEntries(Object.entries(rec).sort(([a], [b]) => rank(a) - rank(b) || a.localeCompare(b)));
};

/** The record as YAML or JSON (a switch, remembered per browser), with a
 * copy button for the text shown. */
function recordView(rec) {
  const data = ordered(rec);
  const lines = { yaml: yamlLines(data), json: JSON.stringify(data, null, 2).split("\n") };
  const highlight = { yaml: yamlLine, json: jsonLine };
  let mode = "yaml";
  try { if (localStorage.getItem("frank.record") === "json") mode = "json"; } catch { /* no storage */ }
  const pre = el("pre", { class: "yaml" });
  const chip = (m) => el("button", { class: "lab-chip", type: "button" }, m.toUpperCase());
  const chips = { yaml: chip("yaml"), json: chip("json") };
  const copy = el("button", { class: "lab-chip", type: "button" }, "copy");
  const render = () => {
    pre.replaceChildren(...lines[mode].map((line) => el("span", { class: "y-line" }, ...highlight[mode](line))));
    for (const [m, c] of Object.entries(chips)) c.setAttribute("aria-pressed", String(m === mode));
  };
  for (const [m, c] of Object.entries(chips)) {
    c.addEventListener("click", () => {
      mode = m;
      try { localStorage.setItem("frank.record", m); } catch { /* no storage */ }
      render();
    });
  }
  copy.addEventListener("click", () => {
    navigator.clipboard.writeText(`${lines[mode].join("\n")}\n`).then(
      () => { copy.textContent = "copied"; },
      () => { copy.textContent = "copy failed"; },
    ).finally(() => setTimeout(() => { copy.textContent = "copy"; }, 1500));
  });
  render();
  return [el("div", { class: "rec-head" }, el("h3", {}, "record (frank/1)"), chips.yaml, chips.json, copy), pre];
}

/** One line of indented JSON as highlighted nodes, coloured as yamlLine
 * colours YAML. Text only, never HTML. */
function jsonLine(line) {
  const [, indent, key, value, comma] = /^(\s*)(?:("(?:[^"\\]|\\.)*"): )?(.*?)(,?)$/.exec(line);
  const out = [indent];
  if (key) out.push(el("span", { class: "y-key" }, key), ": ");
  if (/^[[\]{}]/.test(value)) out.push(el("span", { class: "y-dash" }, value));
  else if (value) {
    const bare = value.replace(/^"(.*)"$/, "$1");
    out.push(el("span", { class: `y-val${yamlType(bare) || (value.startsWith("\"") ? " y-str" : "")}` }, value));
  }
  if (comma) out.push(el("span", { class: "y-dash" }, comma));
  return [el("span", { class: "y-code" }, ...out)];
}

async function sightingNodes(id, filterOn, openOther) {
  const s = await (await api(`/v1/sightings/${encodeURIComponent(id)}`)).json();
  const rec = s.record;
  const rule = rec.sighting_of?.rule;
  const iocs = [...new Map((rec.evidence || []).map((o) => [`${o.type}:${o.value}`, o])).keys()];
  const back = el("button", { class: "lab-btn lab-btn--secondary", type: "button" }, "back");
  back.addEventListener("click", () => history.back());
  return [
    back,
    el("h2", {}, rule?.title || rule?.id || s.sighting_id),
    kpis([["count", rec.count], ["confidence", rec.confidence]]),
    el("p", { class: "note" }, `${rec.tlp.toUpperCase()} · seen ${rec.timestamp} · received ${s.received} · from ${s.reporter}`),
    ...(rule?.id ? linkList("rule", [{ key: rule.id, count: rule.level || "" }], openOther("rule")) : []),
    ...linkList("IoCs", iocs.map((k) => ({ key: k, count: "" })), openOther("ioc")),
    ...linkList("techniques", (rec.sighting_of?.techniques || []).map((t) => ({ key: t, count: "" })), filterOn("technique")),
    ...recordView(rec),
  ];
}

// --- about ------------------------------------------------------------------
// What each status may do and see (ADR-002, #149, #160). The field marks are
// kept by hand next to DIMENSION_TIER, which encodes the same rules.

const STATUS_TEXT = {
  public: "No token. Platform totals of TLP:CLEAR sightings.",
  observer: "Breakdowns by IoC type, severity and target sector; cells with fewer than three reporters are left out.",
  contributor: "Sends sightings. Sees rules, techniques, campaigns and IoC lookups, and lists its own sightings.",
  partner: "Sees exact cells and full records, lists all sightings, downloads the sighting files and analyses them locally.",
  core: "Runs the platform. Sees the participants by name.",
};
const TLP_MIN = [["TLP:CLEAR", "public"], ["TLP:GREEN", "observer"], ["TLP:AMBER", "contributor"],
  ["TLP:AMBER+STRICT", "partner"], ["TLP:RED", null]];

// [line, lowest status that sees it ("never": not stored; "": structure)].
const ANNOTATED = [
  ["submission:", ""],
  ["  submitter:", ""],
  ["    organisation_id: identity-f431f809-377b-45e0-aa1c-6a4751cae5ff", "never"],
  ["    sector: cybersecurity_services", "partner"],
  ["  hit_target:", ""],
  ["    organisation_id: identity-c9b5d123-8877-4422-9966-112233445566", "never"],
  ["    sector: energy", "observer"],
  ["    organisation_size: large", "partner"],
  ["    region: nl_north_holland", "partner"],
  ["  sighting:", ""],
  ["    sighting_id: 0f8fad5b-d9cb-469f-a165-70867728950e", "partner"],
  ["    tlp_level: TLP:AMBER    # decides who sees any of this", "public"],
  ["    last_observed: 2026-10-22T10:00:00Z", "partner"],
  ["    observation_count: 12", "public"],
  ["    confidence: 80", "partner"],
  ["    severity: high", "observer"],
  ["    description: PowerShell download cradle beaconing to a fresh domain.", "partner"],
  ["    sigma_detection:", ""],
  ["      rule_id: 3b6ab547-8ec2-4991-b9d2-2b06702a48d7", "contributor"],
  ["      rule_name: PowerShell Download Cradle", "partner"],
  ["      level: high", "partner"],
  ["    threat_context:", ""],
  ["      campaign: { name: npm_worm }", "contributor"],
  ["      mitre_attack:", ""],
  ["        techniques: [T1059.001, T1071.001]", "contributor"],
  ["    observables:", ""],
  ["      network:", ""],
  ["        - type: ipv4", "observer"],
  ["          value: 198.51.100.23", "contributor"],
  ["          role: c2_server    # kept as sent, never a filter", "partner"],
  ["          port: 443", "partner"],
];
const MARKS = ["public", "observer", "contributor", "partner", "never"];

/** The highlight class of a scalar value: number, true/false/null, quoted
 * string, time, id (`sighting--…`, `identity-…`, a UUID), else none. */
function yamlType(v) {
  if (/^[-+]?\d+(\.\d+)?$/.test(v)) return " y-num";
  if (/^(true|false|null|~)$/.test(v)) return " y-bool";
  if (/^"/.test(v)) return " y-str";
  if (/^\d{4}-\d\d-\d\dT/.test(v)) return " y-time";
  if (/^([a-z]+--?)?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-/i.test(v)) return " y-id";
  return "";
}

/** One YAML line as highlighted nodes: indent, list dash, key, value,
 * comment, in one inline span: as flex items of `.y-line` the indent
 * (whitespace only) would not render, and a copy would split the line.
 * Text only, never HTML. */
function yamlLine(line) {
  const out = [];
  const m = /^(\s*)(- )?(?:([^\s:#][^:#]*?):(?=\s|$))?(.*)$/.exec(line);
  const [, indent, dash, key, rest] = m || ["", "", "", "", line];
  out.push(indent);
  if (dash) out.push(el("span", { class: "y-dash" }, dash));
  if (key) out.push(el("span", { class: "y-key" }, key), ":");
  const hash = /^\s*"/.test(rest) ? -1 : rest.search(/\s#/);
  const value = hash < 0 ? rest : rest.slice(0, hash);
  out.push(el("span", { class: `y-val${yamlType(value.trim())}` }, value));
  if (hash >= 0) out.push(el("span", { class: "y-com" }, rest.slice(hash)));
  return [el("span", { class: "y-code" }, ...out)];
}

let aboutDone = false;
function loadAbout() {
  if (aboutDone) return;
  aboutDone = true;
  show($("about-statuses"), ...TIERS.map((t) =>
    el("div", { class: "card" }, el("h3", {}, t), el("p", {}, STATUS_TEXT[t]))));
  show($("about-tlp"), table(["level", ...TIERS], TLP_MIN.map(([level, min]) =>
    [level, ...TIERS.map((t) => (min && TIERS.indexOf(t) >= TIERS.indexOf(min) ? "✓" : "–"))])));
  show($("about-legend"), ...MARKS.map((m) =>
    el("span", { class: `mark mark-${m}` }, m === "never" ? "never stored" : `${m} and up`)));
  show($("about-yaml"), ...ANNOTATED.map(([line, mark]) => {
    const row = el("span", { class: `y-line${mark ? ` mark-${mark}` : ""}` }, ...yamlLine(line));
    if (mark) row.append(el("span", { class: "y-mark" }, mark === "never" ? "never stored" : mark));
    return row;
  }));
}

// --- api --------------------------------------------------------------------
// Rendered from /v1/openapi.json (docs/openapi.yaml).

const FORMATS = [
  ["application/json", "sighting.json", "Phase 2's submission format or frank/1; one sighting or a list."],
  ["application/yaml", "sighting.yaml", "The same documents as YAML. Anchors and aliases are not accepted."],
  ["application/stix+json", "sighting.stix.json",
    "A STIX 2.1 bundle: each sighting with its SIGMA indicator and the SCOs of its observed-data. Identities and relationships are ignored."],
];

function curl(method, path, secured, extra = []) {
  const parts = ["curl"];
  if (method !== "get") parts.push(`-X ${method.toUpperCase()}`);
  if (secured) parts.push('-H "Authorization: Bearer $FRANK_TOKEN"');
  parts.push(...extra, `"${location.origin}${path}"`);
  return parts.join(" \\\n  ");
}

let apiDone = false;
async function loadApi() {
  if (apiDone) return;
  try {
    const doc = await (await api("/v1/openapi.json")).json();
    apiDone = true;
    show($("api-formats"), ...FORMATS.map(([type, file, text]) => el("div", { class: "card endpoint" },
      el("h3", {}, type), el("p", {}, text),
      el("pre", { class: "curl" }, curl("post", "/v1/sightings", true,
        [`-H "Content-Type: ${type}"`, `--data-binary @examples/formats/${file}`])))));
    const resolve = (p) => (p.$ref ? p.$ref.split("/").slice(1).reduce((o, k) => o?.[k], doc) : p);
    const groups = (doc.tags || []).map((t) => {
      const ops = [];
      for (const [path, item] of Object.entries(doc.paths)) {
        for (const [method, op] of Object.entries(item)) {
          if ((op.tags || []).includes(t.name)) ops.push([path, method, op]);
        }
      }
      return [t, ops];
    });
    show($("api-out"), ...groups.flatMap(([t, ops]) => [
      el("h3", { class: "api-tag" }, `${t.name} \\ ${t.description || ""}`),
      ...ops.map(([path, method, op]) => {
        const min = op["x-min-status"] || "public";
        const needs = op["x-role"];
        const example = op.requestBody?.content?.["application/json"]?.example;
        const secured = !(Array.isArray(op.security) && op.security.length === 0);
        const params = (op.parameters || []).map(resolve);
        const open = atLeast(min) && (!needs || hasRole(needs));
        return el("div", { class: "card endpoint" },
          el("div", { class: "endpoint-head" },
            el("span", { class: "method" }, method.toUpperCase()), el("code", {}, path),
            el("span", { class: `lab-label pill${open ? "" : " locked"}` }, needs ? `${min}+ · ${needs}` : `${min}+`)),
          el("p", {}, op.summary || ""),
          ...(op.description ? [el("p", { class: "note" }, op.description)] : []),
          ...(params.length ? [table(["parameter", "in", "", "description"], params.map((p) =>
            [p.name, p.in, p.required ? "required" : "", p.description || ""]))] : []),
          el("pre", { class: "curl" }, example
            ? curl(method, path, secured, ['-H "Content-Type: application/json"', `-d '${JSON.stringify(example)}'`])
            : method === "post"
              ? curl(method, path, secured, ['-H "Content-Type: application/json"', "--data-binary @sighting.json"])
              : curl(method, path, secured)));
      }),
    ]));
  } catch (e) {
    show($("api-out"), errorNode(e));
  }
}

// --- admin (#175) -------------------------------------------------------------
// For users with a role. An admin manages its own organisation; a superadmin
// picks one. A new token is shown once, in the message area, and not kept.

let adminOrg = "";

const sendJson = (path, method, body) => api(path, {
  method, headers: { "content-type": "application/json" }, body: JSON.stringify(body),
});

function adminMessage(node) {
  show($("adm-msg"), ...(node ? [node] : []));
}

// Runs a change, then reloads the tab. A node the change returns (a new
// token) or an error stays in the message area.
async function adminAct(change) {
  adminMessage(null);
  try {
    const node = await change();
    await loadAdmin(false);
    if (node instanceof Node) adminMessage(node);
  } catch (e) {
    adminMessage(errorNode(e));
  }
}

function tokenCard(t) {
  const copy = el("button", { class: "lab-btn lab-btn--secondary" }, "copy");
  copy.addEventListener("click", () => navigator.clipboard?.writeText(t.token));
  return el("div", { class: "card" },
    el("h3", {}, `new token for ${t.user} \\ shown once`),
    el("pre", { class: "curl" }, t.token), copy);
}

function roleSelect(u) {
  const choices = ["", "admin", ...(hasRole("superadmin") ? ["superadmin"] : [])];
  const s = el("select", { class: "lab-input", "aria-label": `Role of ${u.name}` },
    ...choices.map((r) => el("option", { value: r }, r || "no role")));
  if (u.role === "superadmin" && !hasRole("superadmin")) s.append(el("option", { value: "superadmin" }, "superadmin"));
  s.value = u.role || "";
  s.disabled = u.kind !== "human" || (u.role === "superadmin" && !hasRole("superadmin"));
  s.addEventListener("change", () => adminAct(() =>
    sendJson(`/v1/admin/users/${encodeURIComponent(u.name)}`, "PATCH", { role: s.value || null })));
  return s;
}

// An active user: new token, disable. A disabled one: enable, remove.
function userActions(u, activeTokens) {
  const button = (text, onClick) => {
    const b = el("button", { class: "lab-btn lab-btn--secondary" }, text);
    b.addEventListener("click", onClick);
    return b;
  };
  const path = `/v1/admin/users/${encodeURIComponent(u.name)}`;
  if (u.disabled) {
    return el("span", { class: "row" },
      button("enable", () => adminAct(() => api(`${path}/enable`, { method: "POST" }))),
      button("remove", () => {
        if (!confirm(`Remove ${u.name} with its role and ${activeTokens} token(s)? This cannot be undone.`)) return;
        adminAct(() => api(path, { method: "DELETE" }));
      }));
  }
  return el("span", { class: "row" },
    button("new token", () => adminAct(async () =>
      tokenCard(await (await sendJson("/v1/admin/tokens", "POST", { user: u.name })).json()))),
    button("disable", () => {
      if (!confirm(`Disable ${u.name}? Its ${activeTokens} active token(s) stop working until it is enabled.`)) return;
      adminAct(() => api(`${path}/disable`, { method: "POST" }));
    }));
}

function tokenRow(t) {
  if (t.revoked) return [`${t.prefix}…`, t.user, "revoked", ""];
  const revoke = el("button", { class: "lab-btn lab-btn--secondary" }, "revoke");
  revoke.addEventListener("click", () => {
    if (!confirm(`Revoke ${t.prefix}… of ${t.user}? Clients using it stop working.`)) return;
    adminAct(() => api(`/v1/admin/tokens/${t.prefix}`, { method: "DELETE" }));
  });
  return [`${t.prefix}…`, t.user, "active", revoke];
}

async function loadAdmin(clearMessage = true) {
  if (!role) return;
  if (clearMessage) adminMessage(null);
  const superadmin = hasRole("superadmin");
  $("adm-status-ctl").hidden = !superadmin;
  $("adm-orgs-new").hidden = !superadmin;
  $("adm-user-super").hidden = !superadmin;
  $("adm-user-super").disabled = !superadmin;
  try {
    const { organisations } = await (await api("/v1/admin/organisations")).json();
    if (!organisations.some((o) => o.id === adminOrg)) adminOrg = organisations[0]?.id || "";
    show($("adm-org"), ...organisations.map((o) => el("option", { value: o.id }, o.name)));
    $("adm-org").value = adminOrg;
    $("adm-org").disabled = organisations.length < 2;
    const org = organisations.find((o) => o.id === adminOrg);
    $("adm-org-status").textContent = org?.status || "";
    $("adm-status").value = org?.status || "contributor";
    const q = `?participant=${encodeURIComponent(adminOrg)}`;
    const [{ users }, { tokens }, { lines }] = await Promise.all([
      api(`/v1/admin/users${q}`).then((r) => r.json()),
      api(`/v1/admin/tokens${q}`).then((r) => r.json()),
      api(`/v1/admin/audit?days=${$("adm-days").value}`).then((r) => r.json()),
    ]);
    const active = (name) => tokens.filter((t) => t.user === name && !t.revoked).length;
    show($("adm-users"), table(["user", "kind", "role", "state", ""], users.map((u) =>
      [u.name, u.kind, roleSelect(u), u.disabled ? "disabled" : "active", userActions(u, active(u.name))])));
    show($("adm-tokens"), table(["token", "user", "state", ""], tokens.map(tokenRow)));
    show($("adm-audit"), lines.length
      ? table(["at", "by", "action", "details"], lines.map(({ at, by, action, ...rest }) =>
        [at, by, action, JSON.stringify(rest)]))
      : el("p", { class: "note" }, "nothing in this window"));
  } catch (e) {
    adminMessage(errorNode(e));
  }
}

$("adm-org").addEventListener("change", () => { adminOrg = $("adm-org").value; loadAdmin(); });
$("adm-days").addEventListener("change", () => loadAdmin(false));
$("adm-status-set").addEventListener("click", () => adminAct(() =>
  sendJson(`/v1/admin/organisations/${encodeURIComponent(adminOrg)}`, "PATCH", { status: $("adm-status").value })));
$("adm-user-add").addEventListener("submit", (ev) => {
  ev.preventDefault();
  adminAct(async () => {
    await sendJson("/v1/admin/users", "POST", {
      participant: adminOrg, name: $("adm-user-name").value.trim(),
      kind: $("adm-user-kind").value, role: $("adm-user-role").value || null,
    });
    $("adm-user-name").value = "";
  });
});
$("adm-org-add").addEventListener("submit", (ev) => {
  ev.preventDefault();
  adminAct(async () => {
    const o = await (await sendJson("/v1/admin/organisations", "POST", {
      name: $("adm-org-name").value.trim(), status: $("adm-org-new-status").value,
      type: $("adm-org-type").value, sector: $("adm-org-sector").value.trim() || null,
    })).json();
    adminOrg = o.id;
    $("adm-org-name").value = "";
    $("adm-org-sector").value = "";
  });
});

whoami();
