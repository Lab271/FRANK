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

// --- tabs and token -------------------------------------------------------

for (const b of document.querySelectorAll("nav button")) {
  b.addEventListener("click", () => {
    for (const o of document.querySelectorAll("nav button")) o.setAttribute("aria-selected", o === b);
    for (const p of document.querySelectorAll("main section")) p.hidden = p.id !== b.dataset.tab;
  });
}

async function whoami() {
  try {
    const me = await (await api("/v1/whoami")).json();
    $("tier").textContent = me.label ? `${me.tier} · ${me.label}` : me.tier;
  } catch (e) {
    $("tier").textContent = `rejected: ${e.message}`;
  }
  loadStats();
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

function bars(title, cells) {
  const max = Math.max(1, ...cells.map((c) => c.count));
  const card = el("div", { class: "card" }, el("h3", {}, title));
  if (!cells.length) card.append(el("p", { class: "note" }, "nothing above the threshold"));
  for (const c of cells) {
    const fill = el("div", { class: "fill" });
    fill.style.width = `${(100 * c.count) / max}%`;
    card.append(el("div", { class: "bar" },
      el("span", { class: "label", title: c.key }, c.key), el("span", { class: "n" }, c.count.toLocaleString()),
      el("div", { class: "track" }, fill)));
  }
  return card;
}

async function loadStats() {
  try {
    const s = await (await api(`/v1/statistics?days=${$("days").value}`)).json();
    show($("tiles"), tile("sightings", s.sightings), tile("observations", s.observations), tile("distinct IoCs (retained)", s.iocs));
    const sections = [
      ["by_ioc_type", "IoC types"], ["by_severity", "Severity"], ["by_target_sector", "Target sectors"],
      ["top_rules", "SIGMA rules"], ["top_techniques", "ATT&CK techniques"], ["top_campaigns", "Campaigns"],
    ];
    show($("breakdowns"), ...sections.filter(([k]) => s[k]).map(([k, t]) => bars(t, s[k])));
    $("stats-note").textContent = s.min_cell > 1
      ? `Cells under ${s.min_cell} are suppressed at the ${s.tier} tier.`
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
    const iso = (ns) => new Date(ns / 1e6).toISOString().replace(".000", "");
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

whoami();
