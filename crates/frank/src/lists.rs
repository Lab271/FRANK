//! IoC lists FRANK annotates with (#192, #193), imported from files under
//! `data/lists/` (`make lists`, or files put there by hand):
//!
//! ```text
//! data/lists/warning/<name>.json     MISP warninglist (cidr, string, hostname)
//! data/lists/warning/<name>.txt      one address, range, domain or URL a line
//! data/lists/reference/<name>.csv    abuse.ch: urlhaus*, threatfox*, feodo*
//! data/lists/reference/<name>.txt    as for warnings
//! ```
//!
//! A **warning** list marks common infrastructure, such as public DNS
//! resolvers, so it does not crowd out the signal: marked IoCs are left
//! out of the converging list and Explore's IoC ranking by default. A
//! **reference** list says what an outside source lists. Neither changes
//! a sighting or a count: FRANK does not judge, it shows who says what.
//!
//! Without files there are no annotations, and everything works as
//! before. The directory is checked at most once a minute; a changed file
//! replaces its list, a removed one drops it, and a file that does not
//! parse is warned about and left as it was.

use std::net::IpAddr;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use frank_core::observable::ip_hex;
use frank_core::{Ioc, IocType};
use serde_json::Value;

use crate::store::lists::{Entry, ListDb, Listed, Probe};

pub const DIR: &str = "lists";
const CHECK_NS: i64 = 60 * 1_000_000_000;

/// The lists and when the directory was last checked.
pub struct Lists {
    dir: PathBuf,
    db: ListDb,
    checked: Mutex<i64>,
}

impl Lists {
    pub fn open(data: &Path, now: i64) -> Result<Lists, String> {
        let l = Lists {
            dir: data.join(DIR),
            db: ListDb::open(data)?,
            checked: Mutex::new(i64::MIN),
        };
        l.refresh(now);
        Ok(l)
    }

    /// Imports the files that are new or changed and drops the lists of
    /// files that went away, checking at most once a minute.
    pub fn refresh(&self, now: i64) {
        {
            let mut c = self
                .checked
                .lock()
                .unwrap_or_else(std::sync::PoisonError::into_inner);
            if now.saturating_sub(*c) < CHECK_NS {
                return;
            }
            *c = now;
        }
        let known = match self.db.files() {
            Ok(k) => k,
            Err(e) => return tracing::warn!("lists: {e}"),
        };
        let mut seen = Vec::new();
        for kind in ["warning", "reference"] {
            let Ok(dir) = std::fs::read_dir(self.dir.join(kind)) else {
                continue;
            };
            for f in dir.flatten() {
                let path = f.path();
                let Some((stem, ext)) = name(&path) else {
                    continue;
                };
                let shown = path.display().to_string();
                seen.push(shown.clone());
                let stamp = f
                    .metadata()
                    .and_then(|m| m.modified())
                    .ok()
                    .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
                    .map_or(0, |d| i64::try_from(d.as_nanos()).unwrap_or(i64::MAX));
                if known.get(&shown) == Some(&stamp) {
                    continue;
                }
                let parsed = std::fs::read_to_string(&path)
                    .map_err(|e| e.to_string())
                    .and_then(|text| parse(kind, &stem, &ext, &text));
                match parsed {
                    Ok((source, entries)) => {
                        let n = entries.len();
                        match self.db.replace(
                            kind,
                            stem.clone(),
                            source,
                            entries,
                            shown,
                            stamp,
                            now,
                        ) {
                            Ok(()) => tracing::info!(entries = n, "{kind} list {stem} imported"),
                            Err(e) => tracing::warn!("{kind} list {stem}: {e}"),
                        }
                    }
                    Err(e) => tracing::warn!("{shown} not imported, the list stays as it was: {e}"),
                }
            }
        }
        for path in known.keys().filter(|p| !seen.contains(p)) {
            if let Some((stem, _)) = name(Path::new(path)) {
                if let Err(e) = self.db.remove(stem.clone(), path.clone()) {
                    tracing::warn!("list {stem}: {e}");
                } else {
                    tracing::info!("list {stem} dropped: {path} is gone");
                }
            }
        }
    }

    /// What the lists say about each `(type, value)`, in order. Never
    /// fails a caller: on an error nothing is annotated.
    pub fn annotate(&self, iocs: &[(String, String)]) -> Vec<Vec<Listed>> {
        let probes = iocs.iter().map(|(t, v)| probe(t, v)).collect();
        self.db.matches(probes).unwrap_or_else(|e| {
            tracing::warn!("lists: {e}");
            vec![Vec::new(); iocs.len()]
        })
    }

    /// For `/health`: entries per list.
    pub fn status(&self) -> Value {
        match self.db.counts() {
            Ok(c) => c
                .into_iter()
                .map(|(kind, list, n)| serde_json::json!({ "kind": kind, "list": list, "entries": n }))
                .collect(),
            Err(_) => Value::Null,
        }
    }
}

/// Whether `listed` holds a warning.
#[must_use]
pub fn warned(listed: &[Listed]) -> bool {
    listed.iter().any(|l| l.kind == "warning")
}

/// A list file's stem and extension, for the formats read.
fn name(path: &Path) -> Option<(String, String)> {
    let stem = path.file_stem()?.to_str()?.to_string();
    let ext = path.extension()?.to_str()?.to_ascii_lowercase();
    (matches!(ext.as_str(), "json" | "txt" | "csv") && !stem.starts_with('.'))
        .then_some((stem, ext))
}

/// What to look up for one IoC.
#[must_use]
pub fn probe(ioc_type: &str, value: &str) -> Probe {
    let mut p = Probe {
        exact: vec![value.to_string()],
        ..Probe::default()
    };
    let host = match IocType::parse(ioc_type) {
        Some(IocType::Ipv4 | IocType::Ipv6) => {
            p.ip_hex = value.parse::<IpAddr>().ok().map(ip_hex);
            None
        }
        Some(IocType::Domain) => Some(value.to_string()),
        Some(IocType::Url) => url_host(value),
        Some(IocType::Email) => value.rsplit_once('@').map(|(_, d)| d.to_string()),
        _ => None,
    };
    if let Some(h) = host.map(|h| h.to_ascii_lowercase()) {
        // The host and each parent domain, not the bare top-level one.
        let labels: Vec<&str> = h.split('.').collect();
        p.hosts = (0..labels.len().saturating_sub(1))
            .map(|i| labels[i..].join("."))
            .collect();
        if let Ok(ip) = h.trim_matches(['[', ']']).parse::<IpAddr>() {
            p.ip_hex = Some(ip_hex(ip));
            p.exact.push(ip.to_string());
        }
    }
    p
}

fn url_host(url: &str) -> Option<String> {
    let rest = url.split_once("://").map_or(url, |(_, r)| r);
    let authority = rest.split(['/', '?', '#']).next()?;
    let host = authority.rsplit_once('@').map_or(authority, |(_, h)| h);
    let host = if host.starts_with('[') {
        host.split_once(']').map(|(h, _)| format!("{h}]"))?
    } else {
        host.split(':').next()?.to_string()
    };
    (!host.is_empty()).then_some(host)
}

/// A list's source label and entries.
fn parse(kind: &str, stem: &str, ext: &str, text: &str) -> Result<(String, Vec<Entry>), String> {
    match ext {
        "json" => misp(text),
        "csv" if kind == "reference" => abuse_ch(stem, text),
        _ => Ok((
            format!("local: {stem}"),
            text.lines().filter_map(line).collect(),
        )),
    }
}

/// One line of a text list: an address, a CIDR range, a URL or a domain.
fn line(l: &str) -> Option<Entry> {
    let v = l.split('#').next()?.trim();
    if v.is_empty() {
        return None;
    }
    entry(v, None, None)
}

/// An entry for `v`: an address or range, a URL (exact), else a host name.
fn entry(v: &str, tags: Option<String>, first_listed: Option<i64>) -> Option<Entry> {
    let mut e = if let Some(r) = cidr(v) {
        r
    } else if v.contains("://") {
        exact(v.to_string())
    } else if v.contains('/') || v.contains(char::is_whitespace) || !v.contains('.') {
        // Not an address, URL or host name (one has a dot): a header, say.
        return None;
    } else {
        Entry {
            mtype: "hostname",
            value: v.trim_start_matches("*.").trim_matches('.').to_lowercase(),
            range: None,
            tags: None,
            first_listed: None,
        }
    };
    e.tags = tags;
    e.first_listed = first_listed;
    Some(e)
}

fn exact(value: String) -> Entry {
    Entry {
        mtype: "exact",
        value,
        range: None,
        tags: None,
        first_listed: None,
    }
}

/// An address (an exact entry, normalised) or a CIDR range.
fn cidr(v: &str) -> Option<Entry> {
    let (addr, len) = match v.split_once('/') {
        Some((a, l)) => (a.parse::<IpAddr>().ok()?, Some(l.parse::<u32>().ok()?)),
        None => (v.parse::<IpAddr>().ok()?, None),
    };
    let full = if addr.is_ipv4() { 32 } else { 128 };
    match len {
        None => Some(exact(addr.to_string())),
        Some(l) if l == full => Some(exact(addr.to_string())),
        Some(l) if l < full => {
            let (lo, hi) = crate::api::cidr_bounds(v)?;
            Some(Entry {
                mtype: "cidr",
                value: v.to_string(),
                range: Some((lo, hi)),
                tags: None,
                first_listed: None,
            })
        }
        Some(_) => None,
    }
}

/// A MISP warninglist: `cidr` and `string` entries match exactly or by
/// range, `hostname` ones by domain; `substring` and `regex` are skipped.
fn misp(text: &str) -> Result<(String, Vec<Entry>), String> {
    let v: Value =
        serde_json::from_str(text).map_err(|e| format!("not a MISP warninglist: {e}"))?;
    let list = v["list"]
        .as_array()
        .ok_or("not a MISP warninglist: no `list`")?;
    let name = v["name"].as_str().unwrap_or("unnamed");
    let kind = v["type"].as_str().unwrap_or("string");
    let values = list.iter().filter_map(Value::as_str);
    let entries = match kind {
        "cidr" => values.filter_map(cidr).collect(),
        "hostname" => values
            .filter_map(|h| entry(h, None, None))
            .filter(|e| e.mtype == "hostname")
            .collect(),
        "string" => values
            .map(|s| cidr(s).unwrap_or_else(|| exact(s.to_lowercase())))
            .collect(),
        _ => Vec::new(),
    };
    Ok((format!("MISP warninglists: {name}"), entries))
}

/// The abuse.ch CSV exports, by file name: URLhaus (`url`), ThreatFox
/// (`ioc_value`, `ioc_type`) and Feodo Tracker (`dst_ip`).
fn abuse_ch(stem: &str, text: &str) -> Result<(String, Vec<Entry>), String> {
    let rows = text
        .lines()
        .filter(|l| !l.starts_with('#') && !l.trim().is_empty())
        .map(csv_fields);
    let s = stem.to_ascii_lowercase();
    let time = |f: Option<&String>| f.and_then(|t| utc(t));
    let entries: Vec<Entry> = if s.starts_with("urlhaus") {
        // id, dateadded, url, url_status, last_online, threat, tags, ...
        rows.filter_map(|f| {
            let tags = [f.get(5), f.get(6)]
                .into_iter()
                .flatten()
                .filter(|t| !t.is_empty())
                .cloned()
                .collect::<Vec<_>>();
            Some(Entry {
                tags: Some(tags.join(",")).filter(|t| !t.is_empty()),
                first_listed: time(f.get(1)),
                ..exact(f.get(2)?.clone())
            })
        })
        .collect()
    } else if s.starts_with("threatfox") {
        // first_seen_utc, ioc_id, ioc_value, ioc_type, threat_type, fk_malware, ...
        rows.filter_map(|f| {
            let (value, t) = (f.get(2)?, f.get(3)?);
            let value = match t.as_str() {
                "ip:port" => value
                    .rsplit_once(':')
                    .map_or(value.as_str(), |(ip, _)| ip)
                    .to_string(),
                "md5_hash" | "sha1_hash" | "sha256_hash" => {
                    Ioc::new(IocType::FileHash, value).ok()?.value
                }
                _ => value.clone(),
            };
            entry(
                &value,
                f.get(5).filter(|m| !m.is_empty()).cloned(),
                time(f.first()),
            )
            .or_else(|| Some(exact(value)))
        })
        .collect()
    } else if s.starts_with("feodo") {
        // first_seen_utc, dst_ip, dst_port, c2_status, last_online, malware
        rows.filter_map(|f| {
            let ip = f.get(1).filter(|v| v.parse::<IpAddr>().is_ok())?;
            entry(ip, f.get(5).cloned(), time(f.first()))
        })
        .collect()
    } else {
        return Err(format!(
            "{stem}.csv: not a known abuse.ch export (urlhaus*, threatfox*, feodo*)"
        ));
    };
    let source = if s.starts_with("urlhaus") {
        "abuse.ch URLhaus"
    } else if s.starts_with("threatfox") {
        "abuse.ch ThreatFox"
    } else {
        "abuse.ch Feodo Tracker"
    };
    Ok((source.into(), entries))
}

/// The fields of one CSV line, `"` quoted with `""` escapes.
fn csv_fields(l: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut f = String::new();
    let mut quoted = false;
    let mut chars = l.chars().peekable();
    while let Some(c) = chars.next() {
        match c {
            '"' if quoted && chars.peek() == Some(&'"') => {
                f.push('"');
                chars.next();
            }
            '"' => quoted = !quoted,
            ',' if !quoted => out.push(std::mem::take(&mut f).trim().to_string()),
            _ => f.push(c),
        }
    }
    out.push(f.trim().to_string());
    out
}

/// `YYYY-MM-DD HH:MM:SS` (UTC) as nanoseconds.
fn utc(t: &str) -> Option<i64> {
    let fmt = time::macros::format_description!("[year]-[month]-[day] [hour]:[minute]:[second]");
    let dt = time::PrimitiveDateTime::parse(t.trim(), fmt).ok()?;
    i64::try_from(dt.assume_utc().unix_timestamp_nanos()).ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn probes_try_the_host_and_its_parents() {
        let p = probe("url", "https://a.cdn.Example.com:8443/x?y");
        assert_eq!(
            p.hosts,
            ["a.cdn.example.com", "cdn.example.com", "example.com"]
        );
        assert_eq!(p.exact, ["https://a.cdn.Example.com:8443/x?y"]);
        let p = probe("email", "x@mail.example.org");
        assert_eq!(p.hosts, ["mail.example.org", "example.org"]);
        let p = probe("ipv4", "8.8.8.8");
        assert!(p.ip_hex.is_some() && p.hosts.is_empty());
        let p = probe("url", "http://198.51.100.7/a");
        assert!(p.ip_hex.is_some() && p.exact.contains(&"198.51.100.7".to_string()));
    }

    #[test]
    fn text_and_misp_lists_parse() {
        let (_, e) = parse("warning", "local", "txt", "# common\n8.8.8.8\n10.0.0.0/8  # private\n*.Example.com\n\nhttps://x.example/a\nnot valid/\n").unwrap();
        let kinds: Vec<(&str, &str)> = e.iter().map(|e| (e.mtype, e.value.as_str())).collect();
        assert_eq!(
            kinds,
            [
                ("exact", "8.8.8.8"),
                ("cidr", "10.0.0.0/8"),
                ("hostname", "example.com"),
                ("exact", "https://x.example/a")
            ]
        );
        let (src, e) = misp(r#"{"name": "List of known IPv4 public DNS resolvers", "type": "cidr", "list": ["1.1.1.1/32", "2001:4860:4860::8888", "9.9.9.0/24"]}"#).unwrap();
        assert!(src.contains("public DNS"));
        assert_eq!(
            e.iter().map(|e| e.mtype).collect::<Vec<_>>(),
            ["exact", "exact", "cidr"]
        );
        assert!(misp(r#"{"name": "r", "type": "regex", "list": [".*"]}"#)
            .unwrap()
            .1
            .is_empty());
        assert!(misp("nope").is_err());
    }

    #[test]
    fn abuse_ch_exports_parse() {
        let urlhaus = "# URLhaus\n\"1\",\"2026-10-28 12:00:00\",\"http://bad.example/x\",\"online\",\"\",\"malware_download\",\"elf,mirai\",\"https://urlhaus\",\"r\"\n";
        let (src, e) = abuse_ch("urlhaus", urlhaus).unwrap();
        assert_eq!(src, "abuse.ch URLhaus");
        assert_eq!(
            (e[0].mtype, e[0].value.as_str(), e[0].tags.as_deref()),
            (
                "exact",
                "http://bad.example/x",
                Some("malware_download,elf,mirai")
            )
        );
        assert!(e[0].first_listed.is_some());
        let tf = "# ThreatFox\n\"2026-10-28 10:00:00\", \"1\", \"203.0.113.9:443\", \"ip:port\", \"botnet_cc\", \"win.cobalt_strike\"\n\"2026-10-28 10:00:00\", \"2\", \"evil.example\", \"domain\", \"botnet_cc\", \"x\"\n";
        let (_, e) = abuse_ch("threatfox_recent", tf).unwrap();
        assert_eq!(
            (e[0].value.as_str(), e[0].tags.as_deref()),
            ("203.0.113.9", Some("win.cobalt_strike"))
        );
        assert_eq!(
            (e[1].mtype, e[1].value.as_str()),
            ("hostname", "evil.example")
        );
        let feodo = "# Feodo\nfirst_seen_utc,dst_ip,dst_port,c2_status,last_online,malware\n2026-10-01 00:00:00,198.51.100.66,443,online,2026-10-28,QakBot\n";
        let (_, e) = abuse_ch("feodo_ipblocklist", feodo).unwrap();
        assert_eq!(
            (e.len(), e[0].value.as_str()),
            (1, "198.51.100.66"),
            "the header line is not an address"
        );
        assert!(abuse_ch("other", "a,b").is_err());
    }
}
