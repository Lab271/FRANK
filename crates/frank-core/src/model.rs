//! The normalised sighting (`frank/1`, #160) and the rows of the shared
//! `sightings` table derived from it.
//!
//! A FRANK sighting packs three STIX concepts: what fired (a SIGMA rule, a
//! campaign, ATT&CK techniques: [`SightingOf`]), what was observed
//! ([`Observable`]s, count, first and last seen) and the sighting itself
//! (when, how confident, which TLP). [`SightingBuilder`] takes it in,
//! forgiving on input (ADR-008): unknown fields are ignored, Phase 2's
//! format and STIX type names are accepted, `organization_` and
//! `organisation_` both work. What [`SightingBuilder::build`] returns is
//! strict: normalised IoCs, validated times and ranges.
//!
//! FRANK passes on what participants send and does not judge it (ADR-016):
//! every observable is kept, with the sender's `role` and context as given.

use std::collections::BTreeMap;

use serde::{Serialize, Serializer};
use serde_json::Value;
use time::format_description::well_known::Rfc3339;
use time::OffsetDateTime;

use crate::observable::{Ioc, IocType};
use crate::tlp::Tlp;

/// The `format` of a normalised sighting.
pub const FORMAT: &str = "frank/1";
/// Most observables one sighting may carry.
pub const MAX_IOCS: usize = 1000;
/// Most ATT&CK techniques one sighting may carry.
pub const MAX_TECHNIQUES: usize = 16;
/// Most context fields one observable may carry.
pub const MAX_CONTEXT: usize = 32;
/// How far ahead of the server's clock a sighting may be dated.
pub const MAX_CLOCK_SKEW_NS: i64 = 5 * 60 * 1_000_000_000;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Error {
    /// Not JSON, or not shaped like a sighting.
    Malformed(String),
    /// Shaped right, but a value is out of range or malformed.
    Invalid(String),
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Error::Malformed(m) => write!(f, "malformed submission: {m}"),
            Error::Invalid(m) => write!(f, "invalid submission: {m}"),
        }
    }
}

impl std::error::Error for Error {}

/// One sighting, normalised: the single thing FRANK stores of a
/// submission. Serialises as the `frank/1` format, which
/// [`SightingBuilder::from_json`] reads back.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Sighting {
    /// Always [`FORMAT`].
    pub format: &'static str,
    /// The sender's id for this sighting, `sighting--{uuid}` (lower case):
    /// with the participant, the key it is registered under (#159).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sighting_id: Option<String>,
    /// When the threat was observed, ns since the epoch (UTC).
    #[serde(rename = "timestamp", serialize_with = "rfc3339")]
    pub ts_ns: i64,
    /// Whether `ts_ns` came from the sender rather than the clock.
    #[serde(skip)]
    pub ts_given: bool,
    #[serde(
        rename = "first_seen",
        serialize_with = "rfc3339_opt",
        skip_serializing_if = "Option::is_none"
    )]
    pub first_seen_ns: Option<i64>,
    #[serde(
        rename = "last_seen",
        serialize_with = "rfc3339_opt",
        skip_serializing_if = "Option::is_none"
    )]
    pub last_seen_ns: Option<i64>,
    /// How often it was observed (`observation_count`), at least 1.
    pub count: u32,
    /// 0-100.
    pub confidence: u8,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub severity: Option<String>,
    /// The sender's disclosure level; GREEN when not given.
    pub tlp: Tlp,
    pub sighting_of: SightingOf,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reporter_sector: Option<String>,
    #[serde(skip_serializing_if = "Target::is_empty")]
    pub target: Target,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub evidence: Vec<Observable>,
}

/// What the sighting is a sighting of, besides its observables.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize)]
pub struct SightingOf {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rule: Option<Rule>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub campaign: Option<String>,
    /// ATT&CK technique ids, in the order sent, without repeats.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub techniques: Vec<String>,
}

/// The detection rule that fired (STIX: an indicator with
/// `pattern_type: sigma`).
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize)]
pub struct Rule {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub title: Option<String>,
    /// SIGMA's `level`: informational, low, medium, high or critical.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub level: Option<String>,
}

/// The organisation that was hit. `id` identifies it: only Core sees it
/// (#160); the shared rows carry the categories only.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize)]
pub struct Target {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sector: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub size: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub region: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub id: Option<String>,
}

impl Target {
    fn is_empty(&self) -> bool {
        *self == Target::default()
    }
}

/// One observable as the sender described it: the normalised IoC, the
/// sender's `role` for it (kept, never used to filter) and its other
/// scalar fields (port, protocol, file name, ...).
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Observable {
    #[serde(flatten)]
    pub ioc: Ioc,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub role: Option<String>,
    #[serde(skip_serializing_if = "BTreeMap::is_empty")]
    pub context: BTreeMap<String, Value>,
}

/// One row of the shared `sightings` table: a sighting × one of its IoCs
/// (or the sighting alone when it carries none). Count sightings with
/// `count(DISTINCT sighting_id)` and observations over `seq = 0` rows:
/// every row repeats the sighting's fields (#160).
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct SightingRow {
    pub ts_ns: i64,
    pub sighting_id: String,
    pub rule_id: Option<String>,
    /// All ATT&CK techniques, comma-separated, for display and filtering;
    /// ranking reads the `sighting_techniques` table.
    pub technique: Option<String>,
    pub campaign: Option<String>,
    pub ioc_type: Option<IocType>,
    pub ioc_value: Option<String>,
    pub reporter_sector: Option<String>,
    pub target_sector: Option<String>,
    pub target_size: Option<String>,
    pub severity: Option<String>,
    pub confidence: u8,
    pub observations: u32,
    pub tlp: Tlp,
    /// Who reported it: the participant id, set by the server (#159),
    /// never taken from the submission; empty until set.
    #[serde(skip_serializing_if = "String::is_empty")]
    pub reporter: String,
    /// SHA-256 of the normalised sighting (#159): with `reporter` and
    /// `sighting_id` the registration. Set by the server.
    #[serde(skip_serializing_if = "String::is_empty")]
    pub digest: String,
    /// When the server first stored it, ns since the epoch; 0 until set.
    #[serde(skip_serializing_if = "is_zero")]
    pub received_ns: i64,
    /// The IoC's position in the sighting, 0 for the first (or only) row.
    pub seq: u32,
    /// The normalised sighting as JSON ([`Sighting::detail`]), on the
    /// `seq = 0` row only.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub detail: Option<String>,
}

fn is_zero(n: &i64) -> bool {
    *n == 0
}

fn rfc3339<S: Serializer>(ns: &i64, s: S) -> Result<S::Ok, S::Error> {
    let t = OffsetDateTime::from_unix_timestamp_nanos(i128::from(*ns))
        .map_err(serde::ser::Error::custom)?;
    s.serialize_str(&t.format(&Rfc3339).map_err(serde::ser::Error::custom)?)
}

#[allow(clippy::ref_option)]
fn rfc3339_opt<S: Serializer>(ns: &Option<i64>, s: S) -> Result<S::Ok, S::Error> {
    match ns {
        Some(ns) => rfc3339(ns, s),
        None => s.serialize_none(),
    }
}

impl Sighting {
    /// Parses one submission (Phase 2's format or `frank/1`), with or
    /// without the `{"submission": ...}` envelope. `now_ns` dates a
    /// sighting that gives no time and bounds clock skew.
    ///
    /// # Errors
    ///
    /// [`Error::Malformed`] for input that is not a sighting,
    /// [`Error::Invalid`] for out-of-range or malformed values.
    pub fn parse(json: &str, now_ns: i64) -> Result<Sighting, Error> {
        let v: Value = serde_json::from_str(json).map_err(|e| Error::Malformed(e.to_string()))?;
        Sighting::from_value(&v, now_ns)
    }

    /// As [`Sighting::parse`], over an already parsed JSON value.
    ///
    /// # Errors
    ///
    /// As [`Sighting::parse`].
    pub fn from_value(v: &Value, now_ns: i64) -> Result<Sighting, Error> {
        SightingBuilder::from_json(v)?.build(now_ns)
    }

    /// The distinct IoCs of the evidence, in key order.
    #[must_use]
    pub fn iocs(&self) -> Vec<Ioc> {
        let mut iocs: Vec<Ioc> = self.evidence.iter().map(|o| o.ioc.clone()).collect();
        iocs.sort();
        iocs.dedup();
        iocs
    }

    /// The sighting as stored for partners, as `frank/1` JSON under
    /// `sighting_id`: everything but the target's identity, since the
    /// table's files are handed to partners whole.
    #[must_use]
    pub fn detail(&self, sighting_id: &str) -> String {
        let mut s = self.clone();
        s.sighting_id = Some(sighting_id.to_string());
        s.target.id = None;
        serde_json::to_string(&s).unwrap_or_default()
    }

    /// The rows this sighting adds to `sightings`, tagged `sighting_id`:
    /// one per distinct IoC (`seq` 0, 1, ...), the first carrying the
    /// detail.
    #[must_use]
    pub fn rows(&self, sighting_id: &str) -> Vec<SightingRow> {
        let of = &self.sighting_of;
        let techniques = (!of.techniques.is_empty()).then(|| of.techniques.join(","));
        let row = |seq: usize, ioc: Option<&Ioc>| SightingRow {
            ts_ns: self.ts_ns,
            sighting_id: sighting_id.to_string(),
            rule_id: of.rule.as_ref().and_then(|r| r.id.clone()),
            technique: techniques.clone(),
            campaign: of.campaign.clone(),
            ioc_type: ioc.map(|i| i.ioc_type),
            ioc_value: ioc.map(|i| i.value.clone()),
            reporter_sector: self.reporter_sector.clone(),
            target_sector: self.target.sector.clone(),
            target_size: self.target.size.clone(),
            severity: self.severity.clone(),
            confidence: self.confidence,
            observations: self.count,
            tlp: self.tlp,
            reporter: String::new(),
            digest: String::new(),
            received_ns: 0,
            seq: u32::try_from(seq).unwrap_or(u32::MAX),
            detail: (seq == 0).then(|| self.detail(sighting_id)),
        };
        let iocs = self.iocs();
        if iocs.is_empty() {
            vec![row(0, None)]
        } else {
            iocs.iter()
                .enumerate()
                .map(|(i, ioc)| row(i, Some(ioc)))
                .collect()
        }
    }
}

/// Builds a [`Sighting`]. Setters normalise what they are given; a value
/// that cannot be used is either dropped (a label that could carry free
/// text, an unknown severity or technique: ADR-008) or remembered as the
/// error [`SightingBuilder::build`] returns (a malformed IoC or id, an
/// out-of-range number). The first error wins.
#[derive(Debug, Clone)]
pub struct SightingBuilder {
    s: Sighting,
    ts: Option<i64>,
    error: Option<Error>,
}

impl Default for SightingBuilder {
    fn default() -> Self {
        SightingBuilder::new()
    }
}

impl SightingBuilder {
    #[must_use]
    pub fn new() -> SightingBuilder {
        SightingBuilder {
            s: Sighting {
                format: FORMAT,
                sighting_id: None,
                ts_ns: 0,
                ts_given: false,
                first_seen_ns: None,
                last_seen_ns: None,
                count: 1,
                confidence: 69,
                severity: None,
                tlp: Tlp::Green,
                sighting_of: SightingOf::default(),
                description: None,
                reporter_sector: None,
                target: Target::default(),
                evidence: Vec::new(),
            },
            ts: None,
            error: None,
        }
    }

    fn fail(&mut self, e: Error) -> &mut Self {
        self.error.get_or_insert(e);
        self
    }

    /// A UUID, bare or with the STIX `sighting--` prefix (or Phase 2's
    /// `sighting-`), kept as `sighting--{uuid}` in lower case.
    pub fn sighting_id(&mut self, id: &str) -> &mut Self {
        match sighting_id(id) {
            Ok(id) => self.s.sighting_id = Some(id),
            Err(e) => {
                self.fail(e);
            }
        }
        self
    }

    /// When it was observed (ns since the epoch). Without it, the last or
    /// first seen time dates the sighting, else the clock.
    pub fn timestamp(&mut self, ns: i64) -> &mut Self {
        self.ts = Some(ns);
        self
    }

    pub fn first_seen(&mut self, ns: i64) -> &mut Self {
        self.s.first_seen_ns = Some(ns);
        self
    }

    pub fn last_seen(&mut self, ns: i64) -> &mut Self {
        self.s.last_seen_ns = Some(ns);
        self
    }

    /// How often it was observed, at least 1.
    pub fn count(&mut self, n: u32) -> &mut Self {
        if n == 0 {
            return self.fail(Error::Invalid(
                "observation_count must be a whole number >= 1".into(),
            ));
        }
        self.s.count = n;
        self
    }

    /// 0-100; 69 when not given (Phase 2's default).
    pub fn confidence(&mut self, percent: u8) -> &mut Self {
        if percent > 100 {
            return self.fail(Error::Invalid("confidence must be 0-100".into()));
        }
        self.s.confidence = percent;
        self
    }

    /// info, low, medium, high or critical; anything else is dropped.
    pub fn severity(&mut self, s: &str) -> &mut Self {
        self.s.severity = severity(s);
        self
    }

    /// TLP:RED is refused by [`SightingBuilder::build`]: it is meant for
    /// named people, not for a platform.
    pub fn tlp(&mut self, tlp: Tlp) -> &mut Self {
        self.s.tlp = tlp;
        self
    }

    pub fn rule_id(&mut self, id: &str) -> &mut Self {
        self.rule().id = clean_text(id);
        self
    }

    pub fn rule_title(&mut self, title: &str) -> &mut Self {
        self.rule().title = clean_text(title);
        self
    }

    /// SIGMA's `level`; anything else is dropped.
    pub fn rule_level(&mut self, level: &str) -> &mut Self {
        let l = level.trim().to_ascii_lowercase();
        self.rule().level = matches!(
            l.as_str(),
            "informational" | "low" | "medium" | "high" | "critical"
        )
        .then_some(l);
        self
    }

    fn rule(&mut self) -> &mut Rule {
        self.s.sighting_of.rule.get_or_insert_with(Rule::default)
    }

    pub fn campaign(&mut self, name: &str) -> &mut Self {
        self.s.sighting_of.campaign = clean_text(name);
        self
    }

    /// An ATT&CK technique id such as `T1195.001`; anything else is
    /// dropped, as are repeats and techniques past [`MAX_TECHNIQUES`].
    pub fn technique(&mut self, t: &str) -> &mut Self {
        let ts = &mut self.s.sighting_of.techniques;
        if let Some(t) = technique(t) {
            if ts.len() < MAX_TECHNIQUES && !ts.contains(&t) {
                ts.push(t);
            }
        }
        self
    }

    /// Free text, at most 4000 characters; line breaks are kept.
    pub fn description(&mut self, d: &str) -> &mut Self {
        let d = d.trim();
        self.s.description = (!d.is_empty()
            && d.chars().count() <= 4000
            && !d.chars().any(|c| c.is_control() && c != '\n' && c != '\t'))
        .then(|| d.to_string());
        self
    }

    pub fn reporter_sector(&mut self, s: &str) -> &mut Self {
        self.s.reporter_sector = label(s);
        self
    }

    pub fn target_sector(&mut self, s: &str) -> &mut Self {
        self.s.target.sector = label(s);
        self
    }

    pub fn target_size(&mut self, s: &str) -> &mut Self {
        self.s.target.size = label(s);
        self
    }

    pub fn target_region(&mut self, s: &str) -> &mut Self {
        self.s.target.region = label(s);
        self
    }

    /// The sender's id for the organisation that was hit.
    pub fn target_id(&mut self, id: &str) -> &mut Self {
        self.s.target.id = clean_text(id);
        self
    }

    /// One observable; `value` is normalised for `ioc_type`. Context
    /// values other than strings, numbers and booleans are dropped, as are
    /// keys that are not labels and fields past [`MAX_CONTEXT`].
    pub fn observable(
        &mut self,
        ioc_type: IocType,
        value: &str,
        role: Option<&str>,
        context: &serde_json::Map<String, Value>,
    ) -> &mut Self {
        let ioc = match Ioc::new(ioc_type, value) {
            Ok(ioc) => ioc,
            Err(e) => return self.fail(e),
        };
        let context = context
            .iter()
            .filter_map(|(k, v)| Some((label(k)?, context_value(v)?)))
            .take(MAX_CONTEXT)
            .collect();
        self.s.evidence.push(Observable {
            ioc,
            role: role.and_then(label),
            context,
        });
        self
    }

    /// The sighting. `now_ns` dates a sighting that gives no time and
    /// bounds clock skew.
    ///
    /// # Errors
    ///
    /// The first error a setter remembered, else [`Error::Invalid`] for
    /// times out of order or in the future, TLP:RED, more than
    /// [`MAX_IOCS`] observables, or a sighting with neither an observable
    /// nor a rule id.
    pub fn build(&self, now_ns: i64) -> Result<Sighting, Error> {
        if let Some(e) = &self.error {
            return Err(e.clone());
        }
        let mut s = self.s.clone();
        if let (Some(f), Some(l)) = (s.first_seen_ns, s.last_seen_ns) {
            if f > l {
                return Err(Error::Invalid("first_seen is after last_seen".into()));
            }
        }
        let given = self.ts.or(s.last_seen_ns).or(s.first_seen_ns);
        s.ts_ns = given.unwrap_or(now_ns);
        s.ts_given = given.is_some();
        if s.ts_ns > now_ns.saturating_add(MAX_CLOCK_SKEW_NS) {
            return Err(Error::Invalid("sighting is dated in the future".into()));
        }
        if s.tlp == Tlp::Red {
            return Err(Error::Invalid(
                "TLP:RED is not shared on FRANK: it is meant for named recipients only".into(),
            ));
        }
        if s.sighting_of.rule == Some(Rule::default()) {
            s.sighting_of.rule = None;
        }
        // One canonical order, so the same evidence sent in another order
        // is the same record.
        s.evidence.sort_by(|a, b| {
            (&a.ioc, &a.role)
                .cmp(&(&b.ioc, &b.role))
                .then_with(|| context_key(a).cmp(&context_key(b)))
        });
        s.evidence.dedup();
        if s.evidence.len() > MAX_IOCS {
            return Err(Error::Invalid(format!("more than {MAX_IOCS} observables")));
        }
        let rule_id = s.sighting_of.rule.as_ref().and_then(|r| r.id.as_ref());
        if s.evidence.is_empty() && rule_id.is_none() {
            return Err(Error::Invalid(
                "a sighting needs at least one observable or a SIGMA rule_id".into(),
            ));
        }
        Ok(s)
    }

    /// A builder over one submission: `frank/1` when it says so, else
    /// Phase 2's format (spec 001/003), with or without the
    /// `{"submission": ...}` envelope.
    ///
    /// # Errors
    ///
    /// [`Error::Malformed`] for input that is not a sighting,
    /// [`Error::Invalid`] for a value of the wrong type.
    pub fn from_json(v: &Value) -> Result<SightingBuilder, Error> {
        let root = v.get("submission").unwrap_or(v);
        if !root.is_object() {
            return Err(Error::Malformed("expected a JSON object".into()));
        }
        match root.get("format") {
            None | Some(Value::Null) => phase2(root),
            Some(f) if f.as_str() == Some(FORMAT) => frank1(root),
            Some(f) => Err(Error::Malformed(format!(
                "unknown format {f}: expected {FORMAT:?} or none"
            ))),
        }
    }
}

/// Phase 2's submission (spec 001/003, `docs/design/submission_message.md`).
fn phase2(root: &Value) -> Result<SightingBuilder, Error> {
    let sighting = root
        .get("sighting")
        .filter(|s| s.is_object())
        .ok_or_else(|| Error::Malformed("no `sighting` object".into()))?;
    let mut b = SightingBuilder::new();
    if let Some(id) = present(sighting, "sighting_id")? {
        b.sighting_id(id);
    }
    let first = time_field(sighting, "first_observed")?;
    let last = time_field(sighting, "last_observed")?;
    first.map(|t| b.first_seen(t));
    last.map(|t| b.last_seen(t));
    // The sighting's own time, else last or first observed, else the
    // submission's metadata.
    let meta = root.get("metadata").unwrap_or(&Value::Null);
    let ts = match time_field(sighting, "timestamp")? {
        None if last.is_none() && first.is_none() => time_field(meta, "timestamp")?,
        ts => ts,
    };
    ts.map(|t| b.timestamp(t));
    common(&mut b, sighting)?;
    b.tlp(tlp_level(&[sighting, root, meta])?);

    if let Some(sigma) = sighting.get("sigma_detection") {
        text_of(sigma, "rule_id").map(|v| b.rule_id(v));
        text_of(sigma, "rule_name")
            .or_else(|| text_of(sigma, "title"))
            .map(|v| b.rule_title(v));
        text_of(sigma, "level")
            .map(str::to_string)
            .or_else(|| sigma_yaml_level(sigma))
            .map(|v| b.rule_level(&v));
    }
    if let Some(context) = sighting.get("threat_context") {
        context
            .get("campaign")
            .and_then(|c| text_of(c, "name"))
            .map(|v| b.campaign(v));
        if let Some(ts) = context
            .pointer("/mitre_attack/techniques")
            .and_then(Value::as_array)
        {
            for t in ts {
                if let Some(t) = t.get("technique").or(Some(t)).and_then(Value::as_str) {
                    b.technique(t);
                }
            }
        }
    }
    text_of(sighting, "description").map(|v| b.description(v));
    if let Some(s) = root.get("submitter").and_then(|s| text_of(s, "sector")) {
        b.reporter_sector(s);
    }
    if let Some(t) = root.get("hit_target") {
        text_of(t, "sector").map(|v| b.target_sector(v));
        text_of(t, "organisation_size")
            .or_else(|| text_of(t, "organization_size"))
            .map(|v| b.target_size(v));
        text_of(t, "region").map(|v| b.target_region(v));
        text_of(t, "organisation_id")
            .or_else(|| text_of(t, "organization_id"))
            .map(|v| b.target_id(v));
    }
    if let Some(obs) = sighting.get("observables").and_then(Value::as_object) {
        for (section, entries) in obs {
            for e in entries.as_array().into_iter().flatten() {
                phase2_observable(&mut b, section, e);
            }
        }
    }
    Ok(b)
}

/// The observables of one Phase 2 entry: a typed `{"type", "value"}` in
/// any section, plus the hash fields of a `files` entry and the addresses
/// of an `email` entry. The entry's other scalar fields are the context
/// of each. An entry with nothing typed is skipped, as are blank values
/// (a form left empty, ADR-008).
fn phase2_observable(b: &mut SightingBuilder, section: &str, e: &Value) {
    let Some(entry) = e.as_object() else {
        return;
    };
    let typed = entry
        .get("type")
        .and_then(Value::as_str)
        .and_then(IocType::parse);
    let mut found: Vec<(IocType, &str, &str)> = Vec::new();
    if let (Some(t), Some(v)) = (typed, filled(e, "value")) {
        found.push((t, v, "value"));
    }
    if section == "files" {
        for key in ["hash_md5", "hash_sha1", "hash_sha256", "hash_sha512"] {
            if let Some(h) = filled(e, key) {
                found.push((IocType::FileHash, h, key));
            }
        }
    }
    if section == "email" {
        if let Some(s) = filled(e, "sender") {
            found.push((IocType::Email, s, "sender"));
        }
        if let Some(ip) = filled(e, "sender_ip") {
            let t = if ip.contains(':') {
                IocType::Ipv6
            } else {
                IocType::Ipv4
            };
            found.push((t, ip, "sender_ip"));
        }
    }
    if found.is_empty() {
        return;
    }
    let mut context = entry.clone();
    context.remove("id");
    context.remove("role");
    if typed.is_some() {
        context.remove("type");
    }
    for (_, _, key) in &found {
        context.remove(*key);
    }
    let role = text_of(e, "role");
    for (t, v, _) in found {
        b.observable(t, v, role, &context);
    }
}

/// The `frank/1` format: what [`Sighting`] serialises to.
fn frank1(root: &Value) -> Result<SightingBuilder, Error> {
    let mut b = SightingBuilder::new();
    if let Some(id) = present(root, "sighting_id")? {
        b.sighting_id(id);
    }
    time_field(root, "timestamp")?.map(|t| b.timestamp(t));
    time_field(root, "first_seen")?.map(|t| b.first_seen(t));
    time_field(root, "last_seen")?.map(|t| b.last_seen(t));
    common(&mut b, root)?;
    b.tlp(tlp_level(&[root])?);
    if let Some(of) = root.get("sighting_of") {
        if let Some(rule) = of.get("rule") {
            text_of(rule, "id").map(|v| b.rule_id(v));
            text_of(rule, "title").map(|v| b.rule_title(v));
            text_of(rule, "level").map(|v| b.rule_level(v));
        }
        text_of(of, "campaign").map(|v| b.campaign(v));
        for t in of
            .get("techniques")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
        {
            t.as_str().map(|t| b.technique(t));
        }
    }
    text_of(root, "description").map(|v| b.description(v));
    text_of(root, "reporter_sector").map(|v| b.reporter_sector(v));
    if let Some(t) = root.get("target") {
        text_of(t, "sector").map(|v| b.target_sector(v));
        text_of(t, "size").map(|v| b.target_size(v));
        text_of(t, "region").map(|v| b.target_region(v));
        text_of(t, "id").map(|v| b.target_id(v));
    }
    let empty = serde_json::Map::new();
    for e in root
        .get("evidence")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
    {
        let Some(t) = e.get("type").and_then(Value::as_str) else {
            continue;
        };
        let t = IocType::parse(t)
            .ok_or_else(|| Error::Invalid(format!("evidence: unknown type {t:?}")))?;
        if let Some(v) = filled(e, "value") {
            let context = e
                .get("context")
                .and_then(Value::as_object)
                .unwrap_or(&empty);
            b.observable(t, v, text_of(e, "role"), context);
        }
    }
    Ok(b)
}

/// The fields Phase 2 and `frank/1` name alike.
fn common(b: &mut SightingBuilder, v: &Value) -> Result<(), Error> {
    match v.get("confidence") {
        None | Some(Value::Null) => {}
        Some(c) => {
            b.confidence(confidence(c)?);
        }
    }
    match v.get("observation_count").or_else(|| v.get("count")) {
        None | Some(Value::Null) => {}
        Some(n) => {
            let n = n
                .as_u64()
                .and_then(|n| u32::try_from(n).ok())
                .ok_or_else(|| {
                    Error::Invalid("observation_count must be a whole number >= 1".into())
                })?;
            b.count(n);
        }
    }
    text_of(v, "severity").map(|s| b.severity(s));
    Ok(())
}

/// A sighting id: a UUID, bare or with the STIX `sighting--` prefix (or
/// Phase 2's `sighting-`), stored as `sighting--{uuid}` in lower case.
fn sighting_id(s: &str) -> Result<String, Error> {
    let bad = || Error::Invalid("sighting_id must be a UUID (or sighting--<uuid>)".into());
    let s = s.trim().to_ascii_lowercase();
    let u = s
        .strip_prefix("sighting--")
        .or_else(|| s.strip_prefix("sighting-"))
        .unwrap_or(&s);
    let groups: Vec<&str> = u.split('-').collect();
    let ok = groups.iter().map(|g| g.len()).eq([8, 4, 4, 4, 12])
        && groups
            .iter()
            .all(|g| g.bytes().all(|b| b.is_ascii_hexdigit()));
    if ok {
        Ok(format!("sighting--{u}"))
    } else {
        Err(bad())
    }
}

/// A string field that is set and not blank. A non-string is an error.
fn present<'a>(v: &'a Value, key: &str) -> Result<Option<&'a str>, Error> {
    match v.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(s)) => Ok((!s.trim().is_empty()).then_some(s.as_str())),
        Some(_) => Err(Error::Invalid(format!("{key}: expected a string"))),
    }
}

/// A string field that is set and not blank, or nothing: the forgiving
/// read for observables (a form left empty, ADR-008).
fn filled<'a>(v: &'a Value, key: &str) -> Option<&'a str> {
    text_of(v, key).filter(|s| !s.trim().is_empty())
}

/// A string field, or nothing: the forgiving read for optional context.
fn text_of<'a>(v: &'a Value, key: &str) -> Option<&'a str> {
    v.get(key)?.as_str()
}

fn time_field(v: &Value, key: &str) -> Result<Option<i64>, Error> {
    match v.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(s)) => OffsetDateTime::parse(s, &Rfc3339)
            .ok()
            .and_then(|t| i64::try_from(t.unix_timestamp_nanos()).ok())
            .map(Some)
            .ok_or_else(|| Error::Invalid(format!("{key}: not an RFC 3339 time: {s:?}"))),
        Some(_) => Err(Error::Invalid(format!(
            "{key}: expected an RFC 3339 string"
        ))),
    }
}

/// The TLP level: `tlp_level` (or `tlp`) on the first of `places` that
/// gives one; GREEN when none does (spec 001).
fn tlp_level(places: &[&Value]) -> Result<Tlp, Error> {
    places
        .iter()
        .flat_map(|v| [v.get("tlp_level"), v.get("tlp")])
        .flatten()
        .find_map(Value::as_str)
        .map_or(Ok(Tlp::Green), Tlp::parse)
}

/// 0-100, or a 0.0-1.0 score as Phase 2's API took it.
fn confidence(c: &Value) -> Result<u8, Error> {
    let bad = || Error::Invalid("confidence must be 0-100 (or a 0.0-1.0 score)".into());
    if let Some(n) = c.as_u64() {
        return u8::try_from(n).ok().filter(|n| *n <= 100).ok_or_else(bad);
    }
    match c.as_f64() {
        #[allow(clippy::cast_possible_truncation, clippy::cast_sign_loss)]
        Some(f) if (0.0..=1.0).contains(&f) => Ok((f * 100.0).round() as u8),
        _ => Err(bad()),
    }
}

/// The top-level `level:` of an embedded SIGMA rule.
fn sigma_yaml_level(sigma: &Value) -> Option<String> {
    text_of(sigma, "sigma_yaml")?
        .lines()
        .find_map(|l| l.strip_prefix("level:"))
        .map(|l| l.trim().trim_matches(['"', '\'']).to_string())
}

/// A short free-text field: trimmed, at most 200 characters.
fn clean_text(s: &str) -> Option<String> {
    let s = s.trim();
    (!s.is_empty() && s.chars().count() <= 200 && !s.chars().any(char::is_control))
        .then(|| s.to_string())
}

/// A category label (sector, size, role, context key): `[a-z0-9_]`, at
/// most 64 characters.
fn label(s: &str) -> Option<String> {
    let s = s.trim().to_ascii_lowercase();
    (!s.is_empty() && s.len() <= 64 && s.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'_'))
        .then_some(s)
}

/// A context value: a short string, a number or a boolean.
fn context_value(v: &Value) -> Option<Value> {
    match v {
        Value::Bool(_) | Value::Number(_) => Some(v.clone()),
        Value::String(s) => clean_text(s).map(Value::String),
        _ => None,
    }
}

fn context_key(o: &Observable) -> String {
    serde_json::to_string(&o.context).unwrap_or_default()
}

fn severity(s: &str) -> Option<String> {
    let s = s.trim().to_ascii_lowercase();
    matches!(s.as_str(), "info" | "low" | "medium" | "high" | "critical").then_some(s)
}

/// An ATT&CK technique id such as `T1195.001`.
fn technique(s: &str) -> Option<String> {
    let t = s.trim().to_ascii_uppercase();
    let (head, sub) = t
        .split_once('.')
        .map_or((t.as_str(), None), |(h, s)| (h, Some(s)));
    let ok = head.len() == 5
        && head.starts_with('T')
        && head[1..].bytes().all(|b| b.is_ascii_digit())
        && sub.is_none_or(|s| s.len() == 3 && s.bytes().all(|b| b.is_ascii_digit()));
    ok.then_some(t)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    const NOW: i64 = 1_800_000_000_000_000_000;
    const MINIMAL: &str = include_str!("../../../examples/minimal.json");

    fn rule(s: &Sighting) -> Option<&str> {
        s.sighting_of.rule.as_ref()?.id.as_deref()
    }

    fn keys(s: &Sighting) -> Vec<String> {
        s.iocs().iter().map(Ioc::key).collect()
    }

    #[test]
    fn parses_the_phase2_minimal_example() {
        let s = Sighting::parse(MINIMAL, NOW).unwrap();
        assert_eq!(s.confidence, 87);
        assert_eq!(s.ts_ns, 1_737_383_422_000_000_000);
        assert_eq!(
            keys(&s),
            ["ipv4:185.220.102.45", "domain:secure-bank-verify.nl"]
        );
    }

    #[test]
    fn rows_carry_no_organisation_identity() {
        let s = Sighting::parse(
            r#"{"submitter": {"organisation_id": "identity-a"},
                "hit_target": {"organisation_id": "identity-b", "sector": "energy"},
                "sighting": {"sigma_detection": {"rule_id": "r"}}}"#,
            NOW,
        )
        .unwrap();
        assert_eq!(s.target.id.as_deref(), Some("identity-b"), "kept for Core");
        let rows = serde_json::to_string(&s.rows("s-1")).unwrap();
        assert!(!rows.contains("identity-"), "{rows}");
        assert!(!rows.contains("organisation"), "{rows}");
        let record = serde_json::to_string(&s).unwrap();
        assert!(!record.contains("identity-a"), "the sender is not content");
    }

    #[test]
    fn reads_rules_sectors_files_and_email() {
        let json = r#"{"submitter": {"organization_id": "identity-x", "sector": "Energy"},
            "hit_target": {"sector": "financial_services", "organisation_size": "medium", "region": "nl_north_holland"},
            "sighting": {"severity": "HIGH", "observation_count": 23, "description": "Two lines:\nhere.",
              "first_observed": "2025-01-20T13:15:00Z", "last_observed": "2025-01-20T14:25:00Z",
              "sigma_detection": {"rule_id": "sigma-rule-0123", "rule_name": "Banking pattern",
                "sigma_yaml": "title: Banking pattern\nlevel: high\n"},
              "threat_context": {"campaign": {"name": "npm_worm"},
                "mitre_attack": {"techniques": [{"technique": "T1195.001 "}, {"technique": "bogus"}, "T1071.001", "t1195.001"]}},
              "observables": {
                "files": [{"type": "executable", "name": "update.exe", "hash_md5": "A1B2C3D4E5F6789012345678901234AB"}],
                "email": [{"sender": "Security@Trusted-Bank.nl", "sender_ip": "185.220.102.45", "subject": "Verify"}]}}}"#;
        let s = Sighting::parse(json, NOW).unwrap();
        assert_eq!(rule(&s), Some("sigma-rule-0123"));
        let r = s.sighting_of.rule.as_ref().unwrap();
        assert_eq!(r.title.as_deref(), Some("Banking pattern"));
        assert_eq!(r.level.as_deref(), Some("high"), "from the SIGMA YAML");
        assert_eq!(s.reporter_sector.as_deref(), Some("energy"));
        assert_eq!(s.target.size.as_deref(), Some("medium"));
        assert_eq!(s.target.region.as_deref(), Some("nl_north_holland"));
        assert_eq!(s.severity.as_deref(), Some("high"));
        assert_eq!(s.description.as_deref(), Some("Two lines:\nhere."));
        assert_eq!(
            s.sighting_of.techniques,
            ["T1195.001", "T1071.001"],
            "all of them, once each"
        );
        assert_eq!(s.count, 23);
        assert_eq!(s.ts_ns, 1_737_383_100_000_000_000, "last_observed dates it");
        assert_eq!(s.first_seen_ns, Some(1_737_378_900_000_000_000));
        assert_eq!(s.evidence.len(), 3);
        let file = s
            .evidence
            .iter()
            .find(|o| o.ioc.ioc_type == IocType::FileHash)
            .unwrap();
        assert_eq!(file.context["name"], "update.exe");
        assert_eq!(file.context["type"], "executable");
        let ip = s
            .evidence
            .iter()
            .find(|o| o.ioc.ioc_type == IocType::Ipv4)
            .unwrap();
        assert_eq!(ip.context["subject"], "Verify");
        assert!(!ip.context.contains_key("sender_ip"));
        assert_eq!(s.rows("x").len(), 3);
    }

    #[test]
    fn role_and_context_are_kept_and_never_filter() {
        let s = Sighting::parse(
            r#"{"sighting": {"observables": {"network": [
                {"id": "x", "type": "ipv4", "value": "185.220.102.45", "role": "C2_server", "port": 443,
                 "protocol": "https", "registrar_suspicious": true, "nested": {"a": 1}},
                {"type": "ipv4", "value": "185.220.102.45", "role": "victim"},
                {"type": "domain", "value": "example.org", "role": "benign"}]}}}"#,
            NOW,
        )
        .unwrap();
        assert_eq!(
            s.evidence.len(),
            3,
            "one IoC in two roles is two observables"
        );
        assert_eq!(keys(&s).len(), 2, "but one IoC");
        let c2 = s
            .evidence
            .iter()
            .find(|o| o.role.as_deref() == Some("c2_server"))
            .unwrap();
        assert_eq!(c2.context["port"], 443);
        assert_eq!(c2.context["protocol"], "https");
        assert_eq!(c2.context["registrar_suspicious"], true);
        assert!(!c2.context.contains_key("id"));
        assert!(!c2.context.contains_key("nested"), "scalars only");
        assert!(
            s.evidence
                .iter()
                .any(|o| o.role.as_deref() == Some("benign")),
            "FRANK does not judge"
        );
        assert_eq!(s.rows("x").len(), 2, "rows stay one per IoC");
    }

    #[test]
    fn frank1_reads_back_what_it_writes() {
        let json = r#"{"submission": {"metadata": {"tlp": "amber"},
            "submitter": {"sector": "energy"},
            "hit_target": {"organisation_id": "identity-b", "sector": "health", "organisation_size": "large"},
            "sighting": {"sighting_id": "0f8fad5b-d9cb-469f-a165-70867728950e", "severity": "low",
              "timestamp": "2025-01-20T14:30:22.5Z", "first_observed": "2025-01-20T13:15:00Z",
              "confidence": 0.85, "observation_count": 4, "description": "seen",
              "sigma_detection": {"rule_id": "r1", "rule_name": "R one", "level": "medium"},
              "threat_context": {"campaign": {"name": "c"}, "mitre_attack": {"techniques": ["T1059", "T1071.001"]}},
              "observables": {"network": [{"type": "url", "value": "https://e.example/A", "role": "landing", "port": 443}]}}}}"#;
        let s = Sighting::parse(json, NOW).unwrap();
        let record = serde_json::to_value(&s).unwrap();
        assert_eq!(record["format"], FORMAT);
        assert_eq!(record["timestamp"], "2025-01-20T14:30:22.5Z");
        assert_eq!(record["sighting_of"]["techniques"][1], "T1071.001");
        assert_eq!(record["evidence"][0]["context"]["port"], 443);
        let again = Sighting::from_value(&record, NOW).unwrap();
        assert_eq!(again, s);
        assert_eq!(serde_json::to_value(&again).unwrap(), record);
    }

    #[test]
    fn an_unknown_format_is_refused() {
        let err = Sighting::parse(r#"{"format": "frank/2"}"#, NOW).unwrap_err();
        assert!(matches!(err, Error::Malformed(m) if m.contains("frank/2")));
        let err = Sighting::parse(
            r#"{"format": "frank/1", "evidence": [{"type": "bogus", "value": "x"}]}"#,
            NOW,
        )
        .unwrap_err();
        assert!(matches!(err, Error::Invalid(_)));
    }

    #[test]
    fn the_builder_validates_its_setters() {
        let mut b = SightingBuilder::new();
        b.rule_id("r").confidence(101).count(0);
        assert!(
            matches!(b.build(NOW), Err(Error::Invalid(m)) if m.contains("confidence")),
            "the first error wins"
        );
        let mut b = SightingBuilder::new();
        b.observable(IocType::Ipv4, "1.2.3", None, &serde_json::Map::new());
        assert!(b.build(NOW).is_err());
        let mut b = SightingBuilder::new();
        b.rule_id("r")
            .technique("T1059")
            .technique("T1059")
            .technique("x");
        let s = b.build(NOW).unwrap();
        assert_eq!(s.sighting_of.techniques, ["T1059"]);
        assert_eq!(
            (s.ts_ns, s.ts_given, s.count, s.confidence),
            (NOW, false, 1, 69)
        );
    }

    #[test]
    fn rows_are_one_per_ioc_with_the_detail_on_the_first() {
        let s = Sighting::parse(
            r#"{"hit_target": {"organisation_id": "identity-victim", "sector": "energy"},
                "sighting": {"observation_count": 10,
                "threat_context": {"mitre_attack": {"techniques": ["T1059", "T1071.001"]}},
                "observables": {"network": [{"type": "ipv4", "value": "198.51.100.1"},
                  {"type": "ipv4", "value": "198.51.100.2"}, {"type": "domain", "value": "a.example"}]}}}"#,
            NOW,
        )
        .unwrap();
        let id = "sighting--0f8fad5b-d9cb-469f-a165-70867728950e";
        let rows = s.rows(id);
        assert_eq!(rows.iter().map(|r| r.seq).collect::<Vec<_>>(), [0, 1, 2]);
        assert!(rows
            .iter()
            .all(|r| r.technique.as_deref() == Some("T1059,T1071.001")));
        assert!(rows[1..].iter().all(|r| r.detail.is_none()));
        let detail: Value = serde_json::from_str(rows[0].detail.as_ref().unwrap()).unwrap();
        assert_eq!(detail["sighting_id"], id);
        assert_eq!(detail["count"], 10);
        assert_eq!(detail["target"], json!({"sector": "energy"}), "no identity");
        assert_eq!(
            Sighting::from_value(&detail, NOW).unwrap().iocs(),
            s.iocs(),
            "the detail reads back"
        );
    }

    #[test]
    fn a_rule_without_observables_is_one_row() {
        let s = Sighting::parse(
            r#"{"sighting": {"sigma_detection": {"rule_id": "r1"}}}"#,
            NOW,
        )
        .unwrap();
        let rows = s.rows("x");
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0].ioc_type, None);
        assert_eq!(rows[0].ts_ns, NOW, "undated: the server's clock");
        assert_eq!(rows[0].confidence, 69, "Phase 2's default");
    }

    #[test]
    fn refuses_what_phase2_refused() {
        let bad = |json: &str| Sighting::parse(json, NOW).unwrap_err();
        assert!(matches!(bad("[]"), Error::Malformed(_)));
        assert!(matches!(bad(r#"{"submitter": {}}"#), Error::Malformed(_)));
        assert!(
            matches!(bad(r#"{"sighting": {}}"#), Error::Invalid(_)),
            "nothing to share"
        );
        assert!(
            matches!(
                bad(r#"{"sighting": {"sigma_detection": {"rule_name": "no id"}}}"#),
                Error::Invalid(_)
            ),
            "a rule needs an id to count"
        );
        let with = |field: &str| {
            format!(r#"{{"sighting": {{{field}, "sigma_detection": {{"rule_id": "r"}}}}}}"#)
        };
        for field in [
            r#""confidence": 1.5"#,
            r#""confidence": 101"#,
            r#""observation_count": 0"#,
            r#""observation_count": "3""#,
            r#""timestamp": "yesterday""#,
            r#""timestamp": "2099-01-01T00:00:00Z""#,
            r#""first_observed": "2025-01-02T00:00:00Z", "last_observed": "2025-01-01T00:00:00Z""#,
            r#""sighting_id": 7"#,
        ] {
            assert!(matches!(bad(&with(field)), Error::Invalid(_)), "{field}");
        }
        assert!(matches!(
            bad(
                r#"{"sighting": {"observables": {"network": [{"type": "ipv4", "value": "1.2.3"}]}}}"#
            ),
            Error::Invalid(_)
        ));
    }

    #[test]
    fn tlp_defaults_to_green_and_red_is_refused() {
        let with = |tlp: &str| {
            format!(
                r#"{{"submission": {{{tlp} "sighting": {{"sigma_detection": {{"rule_id": "r"}}}}}}}}"#
            )
        };
        assert_eq!(Sighting::parse(&with(""), NOW).unwrap().tlp, Tlp::Green);
        assert_eq!(
            Sighting::parse(&with(r#""tlp_level": "TLP:AMBER","#), NOW)
                .unwrap()
                .tlp,
            Tlp::Amber
        );
        let meta = r#"{"submission": {"metadata": {"tlp": "amber+strict"}, "sighting": {"sigma_detection": {"rule_id": "r"}}}}"#;
        assert_eq!(Sighting::parse(meta, NOW).unwrap().tlp, Tlp::AmberStrict);
        let sighting_wins = r#"{"tlp_level": "amber", "sighting": {"tlp_level": "clear", "sigma_detection": {"rule_id": "r"}}}"#;
        assert_eq!(Sighting::parse(sighting_wins, NOW).unwrap().tlp, Tlp::Clear);
        assert!(
            matches!(Sighting::parse(&with(r#""tlp_level": "RED","#), NOW), Err(Error::Invalid(m)) if m.contains("TLP:RED"))
        );
        assert!(matches!(
            Sighting::parse(&with(r#""tlp_level": "purple","#), NOW),
            Err(Error::Invalid(_))
        ));
        let s = Sighting::parse(&with(r#""tlp_level": "amber","#), NOW).unwrap();
        assert!(s.rows("x").iter().all(|r| r.tlp == Tlp::Amber));
    }

    #[test]
    fn blank_observables_are_skipped() {
        let json = r#"{"sighting": {"observables": {"network": [
            {"type": "ipv4", "value": ""}, {"type": "ipv4", "value": "  "},
            {"type": "domain", "value": "evil.example"}, {"type": "hostname", "value": "x"}],
            "files": [{"hash_md5": ""}]}}}"#;
        let s = Sighting::parse(json, NOW).unwrap();
        assert_eq!(s.evidence.len(), 1);
        let only_blank =
            r#"{"sighting": {"observables": {"network": [{"type": "ipv4", "value": ""}]}}}"#;
        assert!(
            matches!(Sighting::parse(only_blank, NOW), Err(Error::Invalid(_))),
            "nothing left to share"
        );
    }

    #[test]
    fn evidence_order_is_not_content() {
        let a = Sighting::parse(
            r#"{"sighting": {"observables": {"network": [{"type": "ipv4", "value": "198.51.100.1", "port": 80},
                {"type": "domain", "value": "a.example"}]}}}"#,
            NOW,
        )
        .unwrap();
        let b = Sighting::parse(
            r#"{"sighting": {"observables": {"network": [{"value": "A.example", "type": "domain"},
                {"port": 80, "type": "ipv4", "value": "198.51.100.1"}, {"type": "domain", "value": "a.example"}]}}}"#,
            NOW,
        )
        .unwrap();
        assert_eq!(a, b, "order, case and repeats");
    }

    #[test]
    fn a_score_is_scaled_to_percent() {
        let s = Sighting::parse(
            r#"{"sighting": {"confidence": 0.85, "sigma_detection": {"rule_id": "r"}}}"#,
            NOW,
        )
        .unwrap();
        assert_eq!(s.confidence, 85);
    }

    #[test]
    fn labels_that_could_carry_free_text_are_dropped() {
        let s = Sighting::parse(
            r#"{"submitter": {"sector": "ACME Corp, Utrecht"}, "sighting": {"sigma_detection": {"rule_id": "r"}}}"#,
            NOW,
        )
        .unwrap();
        assert_eq!(s.reporter_sector, None);
    }

    #[test]
    fn the_sender_names_the_sighting() {
        let with = |id: &str| {
            Sighting::parse(
                &format!(
                    r#"{{"sighting": {{"sighting_id": "{id}", "sigma_detection": {{"rule_id": "r"}}}}}}"#
                ),
                NOW,
            )
        };
        let want = Some("sighting--0f8fad5b-d9cb-469f-a165-70867728950e".to_string());
        assert_eq!(
            with("0F8FAD5B-D9CB-469F-A165-70867728950E")
                .unwrap()
                .sighting_id,
            want
        );
        assert_eq!(
            with("sighting--0f8fad5b-d9cb-469f-a165-70867728950e")
                .unwrap()
                .sighting_id,
            want
        );
        assert_eq!(
            with("sighting-0f8fad5b-d9cb-469f-a165-70867728950e")
                .unwrap()
                .sighting_id,
            want,
            "Phase 2 spelling"
        );
        assert!(with("not-a-uuid").is_err());
        assert!(with("sight_789").is_err());
        assert!(
            with("0f8fad5b-d9cb-469f-a165-70867728950").is_err(),
            "one digit short"
        );
        let s = Sighting::parse(MINIMAL, NOW).unwrap();
        assert!(s.ts_given);
        let bare = Sighting::parse(
            r#"{"sighting": {"sigma_detection": {"rule_id": "r"}}}"#,
            NOW,
        )
        .unwrap();
        assert_eq!(
            (bare.sighting_id, bare.ts_ns, bare.ts_given),
            (None, NOW, false)
        );
    }
}
