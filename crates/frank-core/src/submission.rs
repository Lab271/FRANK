//! A submission (the Phase 2 wire format, spec 001/003) and the sighting
//! rows derived from it.
//!
//! Parsing is forgiving (ADR-008): unknown fields are ignored, STIX type
//! names are accepted, `organization_` and `organisation_` both work. What
//! comes out is strict: normalised IoCs, validated times and ranges.

use serde::Serialize;
use serde_json::Value;
use time::format_description::well_known::Rfc3339;
use time::OffsetDateTime;

use crate::observable::{Ioc, IocType};
use crate::tlp::Tlp;

/// Most IoCs one submission may carry.
pub const MAX_IOCS: usize = 1000;
/// How far ahead of the server's clock a sighting may be dated.
pub const MAX_CLOCK_SKEW_NS: i64 = 5 * 60 * 1_000_000_000;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Error {
    /// Not JSON, or not shaped like a submission.
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

/// What FRANK keeps of a submission. No organisation identity: see the
/// crate docs.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Submission {
    /// The sender's id for this sighting, `sighting--{uuid}` (lower case):
    /// with the participant, the key it is registered under (#159).
    pub sighting_id: Option<String>,
    /// When the threat was observed, ns since the epoch (UTC).
    pub ts_ns: i64,
    /// Whether `ts_ns` came from the submission rather than the clock.
    #[serde(skip)]
    pub ts_given: bool,
    pub confidence: u8,
    pub observations: u32,
    pub severity: Option<String>,
    pub rule_id: Option<String>,
    pub techniques: Vec<String>,
    pub campaign: Option<String>,
    pub reporter_sector: Option<String>,
    pub target_sector: Option<String>,
    pub target_size: Option<String>,
    /// The submitter's disclosure level; GREEN when not given.
    pub tlp: Tlp,
    pub iocs: Vec<Ioc>,
}

/// One row of the shared `sightings` table: a sighting × one of its IoCs
/// (or the sighting alone when it carries none).
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct SightingRow {
    pub ts_ns: i64,
    pub sighting_id: String,
    pub rule_id: Option<String>,
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
    /// Who reported it, as a pseudonym the server assigns (#148): never
    /// taken from the submission, empty until the server sets it.
    #[serde(skip_serializing_if = "String::is_empty")]
    pub reporter: String,
}

impl Submission {
    /// Parses one submission, with or without the `{"submission": ...}`
    /// envelope. `now_ns` dates a sighting that gives no time and bounds
    /// clock skew.
    ///
    /// # Errors
    ///
    /// [`Error::Malformed`] for input that is not a submission,
    /// [`Error::Invalid`] for out-of-range or malformed values.
    pub fn parse(json: &str, now_ns: i64) -> Result<Submission, Error> {
        let v: Value = serde_json::from_str(json).map_err(|e| Error::Malformed(e.to_string()))?;
        Submission::from_value(&v, now_ns)
    }

    /// As [`Submission::parse`], over an already parsed JSON value.
    ///
    /// # Errors
    ///
    /// As [`Submission::parse`].
    pub fn from_value(v: &Value, now_ns: i64) -> Result<Submission, Error> {
        let root = v.get("submission").unwrap_or(v);
        if !root.is_object() {
            return Err(Error::Malformed("expected a JSON object".into()));
        }
        let sighting = root
            .get("sighting")
            .filter(|s| s.is_object())
            .ok_or_else(|| Error::Malformed("no `sighting` object".into()))?;
        let submitter = root.get("submitter");
        let target = root.get("hit_target");

        let first = time_field(sighting, "first_observed")?;
        let last = time_field(sighting, "last_observed")?;
        if let (Some(f), Some(l)) = (first, last) {
            if f > l {
                return Err(Error::Invalid(
                    "first_observed is after last_observed".into(),
                ));
            }
        }
        let given = time_field(sighting, "timestamp")?
            .or(last)
            .or(first)
            .or(time_field(
                root.get("metadata").unwrap_or(&Value::Null),
                "timestamp",
            )?);
        let ts_ns = given.unwrap_or(now_ns);
        if ts_ns > now_ns.saturating_add(MAX_CLOCK_SKEW_NS) {
            return Err(Error::Invalid("sighting is dated in the future".into()));
        }

        let confidence = match sighting.get("confidence") {
            None | Some(Value::Null) => 69,
            Some(c) => confidence(c)?,
        };
        let observations = match sighting.get("observation_count") {
            None | Some(Value::Null) => 1,
            Some(n) => n
                .as_u64()
                .filter(|n| (1..=u64::from(u32::MAX)).contains(n))
                .and_then(|n| u32::try_from(n).ok())
                .ok_or_else(|| {
                    Error::Invalid("observation_count must be a whole number >= 1".into())
                })?,
        };

        let sigma = sighting.get("sigma_detection");
        let context = sighting.get("threat_context");
        let techniques: Vec<String> = context
            .and_then(|c| c.pointer("/mitre_attack/techniques"))
            .and_then(Value::as_array)
            .map(|ts| {
                ts.iter()
                    .filter_map(|t| t.get("technique").or(Some(t)).and_then(Value::as_str))
                    .filter_map(technique)
                    .take(16)
                    .collect()
            })
            .unwrap_or_default();

        let tlp = tlp_level(sighting, root)?;
        let iocs = observables(sighting.get("observables"))?;
        let rule_id = sigma.and_then(|s| text(s, "rule_id"));
        if iocs.is_empty() && rule_id.is_none() {
            return Err(Error::Invalid(
                "a sighting needs at least one observable or a SIGMA rule_id".into(),
            ));
        }

        let sighting_id = match sighting.get("sighting_id") {
            None | Some(Value::Null) => None,
            Some(v) => Some(sighting_id(v)?),
        };

        Ok(Submission {
            sighting_id,
            ts_ns,
            ts_given: given.is_some(),
            confidence,
            observations,
            severity: sighting
                .get("severity")
                .and_then(Value::as_str)
                .and_then(severity),
            rule_id,
            techniques,
            campaign: context
                .and_then(|c| c.get("campaign"))
                .and_then(|c| text(c, "name")),
            reporter_sector: submitter.and_then(|s| label(s, "sector")),
            target_sector: target.and_then(|t| label(t, "sector")),
            target_size: target.and_then(|t| {
                label(t, "organisation_size").or_else(|| label(t, "organization_size"))
            }),
            tlp,
            iocs,
        })
    }

    /// The rows this submission adds to `sightings`, tagged `sighting_id`.
    #[must_use]
    pub fn rows(&self, sighting_id: &str) -> Vec<SightingRow> {
        let row = |ioc: Option<&Ioc>| SightingRow {
            ts_ns: self.ts_ns,
            sighting_id: sighting_id.to_string(),
            rule_id: self.rule_id.clone(),
            technique: self.techniques.first().cloned(),
            campaign: self.campaign.clone(),
            ioc_type: ioc.map(|i| i.ioc_type),
            ioc_value: ioc.map(|i| i.value.clone()),
            reporter_sector: self.reporter_sector.clone(),
            target_sector: self.target_sector.clone(),
            target_size: self.target_size.clone(),
            severity: self.severity.clone(),
            confidence: self.confidence,
            observations: self.observations,
            tlp: self.tlp,
            reporter: String::new(),
        };
        if self.iocs.is_empty() {
            vec![row(None)]
        } else {
            self.iocs.iter().map(|i| row(Some(i))).collect()
        }
    }
}

/// A sighting id: a UUID, bare or with the STIX `sighting--` prefix (or
/// Phase 2's `sighting-`), stored as `sighting--{uuid}` in lower case.
fn sighting_id(v: &Value) -> Result<String, Error> {
    let bad = || Error::Invalid("sighting_id must be a UUID (or sighting--<uuid>)".into());
    let s = v.as_str().ok_or_else(bad)?.trim().to_ascii_lowercase();
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

/// The TLP level: `tlp_level` (or `tlp`) on the sighting, the submission
/// or its `metadata`, the first found; GREEN when none is given (spec 001).
/// TLP:RED is refused: it is meant for named people, not for a platform.
fn tlp_level(sighting: &Value, root: &Value) -> Result<Tlp, Error> {
    let given = [sighting, root, root.get("metadata").unwrap_or(&Value::Null)]
        .into_iter()
        .flat_map(|v| [v.get("tlp_level"), v.get("tlp")])
        .flatten()
        .find_map(Value::as_str);
    let tlp = given.map_or(Ok(Tlp::Green), Tlp::parse)?;
    if tlp == Tlp::Red {
        return Err(Error::Invalid(
            "TLP:RED is not shared on FRANK: it is meant for named recipients only".into(),
        ));
    }
    Ok(tlp)
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

/// A short free-text field: trimmed, at most 200 characters.
fn text(v: &Value, key: &str) -> Option<String> {
    let s = v.get(key)?.as_str()?.trim();
    (!s.is_empty() && s.len() <= 200 && !s.chars().any(char::is_control)).then(|| s.to_string())
}

/// A category label (sector, size): `[a-z0-9_]`, at most 64 characters.
fn label(v: &Value, key: &str) -> Option<String> {
    let s = v.get(key)?.as_str()?.trim().to_ascii_lowercase();
    (!s.is_empty() && s.len() <= 64 && s.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'_'))
        .then_some(s)
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

/// Every IoC in `observables`: typed entries (`{"type", "value"}`) in any
/// list, plus the hash fields of `files` entries and the addresses of
/// `email` entries. Untyped entries and blank values are skipped (a form
/// left empty, ADR-008); a malformed value is an error. Duplicates are
/// dropped.
fn observables(obs: Option<&Value>) -> Result<Vec<Ioc>, Error> {
    let mut out = Vec::new();
    let Some(obs) = obs.and_then(Value::as_object) else {
        return Ok(out);
    };
    fn present(v: Option<&Value>) -> Option<&str> {
        v.and_then(Value::as_str).filter(|s| !s.trim().is_empty())
    }
    for (section, entries) in obs {
        let Some(entries) = entries.as_array() else {
            continue;
        };
        for e in entries {
            let typed = e
                .get("type")
                .and_then(Value::as_str)
                .and_then(IocType::parse);
            if let (Some(t), Some(v)) = (typed, present(e.get("value"))) {
                out.push(Ioc::new(t, v)?);
            }
            if section == "files" {
                for key in ["hash_md5", "hash_sha1", "hash_sha256", "hash_sha512"] {
                    if let Some(h) = present(e.get(key)) {
                        out.push(Ioc::new(IocType::FileHash, h)?);
                    }
                }
            }
            if section == "email" {
                if let Some(s) = present(e.get("sender")) {
                    out.push(Ioc::new(IocType::Email, s)?);
                }
                if let Some(ip) = present(e.get("sender_ip")) {
                    let t = if ip.contains(':') {
                        IocType::Ipv6
                    } else {
                        IocType::Ipv4
                    };
                    out.push(Ioc::new(t, ip)?);
                }
            }
        }
    }
    out.sort();
    out.dedup();
    if out.len() > MAX_IOCS {
        return Err(Error::Invalid(format!("more than {MAX_IOCS} observables")));
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    const NOW: i64 = 1_800_000_000_000_000_000;
    const MINIMAL: &str = include_str!("../../../examples/minimal.json");

    #[test]
    fn parses_the_phase2_minimal_example() {
        let s = Submission::parse(MINIMAL, NOW).unwrap();
        assert_eq!(s.confidence, 87);
        assert_eq!(s.ts_ns, 1_737_383_422_000_000_000);
        let keys: Vec<String> = s.iocs.iter().map(Ioc::key).collect();
        assert_eq!(
            keys,
            ["ipv4:185.220.102.45", "domain:secure-bank-verify.nl"]
        );
    }

    #[test]
    fn rows_carry_no_organisation_identity() {
        let s = Submission::parse(MINIMAL, NOW).unwrap();
        let rows = serde_json::to_string(&s.rows("s-1")).unwrap();
        assert!(!rows.contains("identity-f431f809"), "{rows}");
        assert!(!rows.contains("organisation"), "{rows}");
    }

    #[test]
    fn reads_rules_sectors_files_and_email() {
        let json = r#"{"submitter": {"organization_id": "identity-x", "sector": "Energy"},
            "hit_target": {"sector": "financial_services", "organisation_size": "medium"},
            "sighting": {"severity": "HIGH", "observation_count": 23,
              "first_observed": "2025-01-20T13:15:00Z", "last_observed": "2025-01-20T14:25:00Z",
              "sigma_detection": {"rule_id": "sigma-rule-0123"},
              "threat_context": {"campaign": {"name": "npm_worm"},
                "mitre_attack": {"techniques": [{"technique": "T1195.001 "}, {"technique": "bogus"}]}},
              "observables": {
                "files": [{"type": "executable", "hash_md5": "A1B2C3D4E5F6789012345678901234AB"}],
                "email": [{"sender": "Security@Trusted-Bank.nl", "sender_ip": "185.220.102.45"}]}}}"#;
        let s = Submission::parse(json, NOW).unwrap();
        assert_eq!(s.rule_id.as_deref(), Some("sigma-rule-0123"));
        assert_eq!(s.reporter_sector.as_deref(), Some("energy"));
        assert_eq!(s.target_size.as_deref(), Some("medium"));
        assert_eq!(s.severity.as_deref(), Some("high"));
        assert_eq!(s.techniques, ["T1195.001"]);
        assert_eq!(s.observations, 23);
        assert_eq!(s.ts_ns, 1_737_383_100_000_000_000, "last_observed dates it");
        assert_eq!(s.iocs.len(), 3);
        assert_eq!(s.rows("x").len(), 3);
    }

    #[test]
    fn a_rule_without_observables_is_one_row() {
        let s = Submission::parse(
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
        let bad = |json: &str| Submission::parse(json, NOW).unwrap_err();
        assert!(matches!(bad("[]"), Error::Malformed(_)));
        assert!(matches!(bad(r#"{"submitter": {}}"#), Error::Malformed(_)));
        assert!(
            matches!(bad(r#"{"sighting": {}}"#), Error::Invalid(_)),
            "nothing to share"
        );
        let with = |field: &str| {
            format!(r#"{{"sighting": {{{field}, "sigma_detection": {{"rule_id": "r"}}}}}}"#)
        };
        assert!(matches!(
            bad(&with(r#""confidence": 1.5"#)),
            Error::Invalid(_)
        ));
        assert!(matches!(
            bad(&with(r#""confidence": 101"#)),
            Error::Invalid(_)
        ));
        assert!(matches!(
            bad(&with(r#""observation_count": 0"#)),
            Error::Invalid(_)
        ));
        assert!(matches!(
            bad(&with(r#""timestamp": "yesterday""#)),
            Error::Invalid(_)
        ));
        assert!(matches!(
            bad(&with(r#""timestamp": "2099-01-01T00:00:00Z""#)),
            Error::Invalid(_)
        ));
        assert!(matches!(
            bad(&with(
                r#""first_observed": "2025-01-02T00:00:00Z", "last_observed": "2025-01-01T00:00:00Z""#
            )),
            Error::Invalid(_)
        ));
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
        assert_eq!(Submission::parse(&with(""), NOW).unwrap().tlp, Tlp::Green);
        assert_eq!(
            Submission::parse(&with(r#""tlp_level": "TLP:AMBER","#), NOW)
                .unwrap()
                .tlp,
            Tlp::Amber
        );
        let meta = r#"{"submission": {"metadata": {"tlp": "amber+strict"}, "sighting": {"sigma_detection": {"rule_id": "r"}}}}"#;
        assert_eq!(Submission::parse(meta, NOW).unwrap().tlp, Tlp::AmberStrict);
        let sighting_wins = r#"{"tlp_level": "amber", "sighting": {"tlp_level": "clear", "sigma_detection": {"rule_id": "r"}}}"#;
        assert_eq!(
            Submission::parse(sighting_wins, NOW).unwrap().tlp,
            Tlp::Clear
        );
        assert!(
            matches!(Submission::parse(&with(r#""tlp_level": "RED","#), NOW), Err(Error::Invalid(m)) if m.contains("TLP:RED"))
        );
        assert!(matches!(
            Submission::parse(&with(r#""tlp_level": "purple","#), NOW),
            Err(Error::Invalid(_))
        ));
        let s = Submission::parse(&with(r#""tlp_level": "amber","#), NOW).unwrap();
        assert!(s.rows("x").iter().all(|r| r.tlp == Tlp::Amber));
    }

    #[test]
    fn blank_observables_are_skipped() {
        let json = r#"{"sighting": {"observables": {"network": [
            {"type": "ipv4", "value": ""}, {"type": "ipv4", "value": "  "},
            {"type": "domain", "value": "evil.example"}],
            "files": [{"hash_md5": ""}]}}}"#;
        let s = Submission::parse(json, NOW).unwrap();
        assert_eq!(s.iocs.len(), 1);
        let only_blank =
            r#"{"sighting": {"observables": {"network": [{"type": "ipv4", "value": ""}]}}}"#;
        assert!(
            matches!(Submission::parse(only_blank, NOW), Err(Error::Invalid(_))),
            "nothing left to share"
        );
    }

    #[test]
    fn a_score_is_scaled_to_percent() {
        let s = Submission::parse(
            r#"{"sighting": {"confidence": 0.85, "sigma_detection": {"rule_id": "r"}}}"#,
            NOW,
        )
        .unwrap();
        assert_eq!(s.confidence, 85);
    }

    #[test]
    fn labels_that_could_carry_free_text_are_dropped() {
        let s = Submission::parse(
            r#"{"submitter": {"sector": "ACME Corp, Utrecht"}, "sighting": {"sigma_detection": {"rule_id": "r"}}}"#,
            NOW,
        )
        .unwrap();
        assert_eq!(s.reporter_sector, None);
    }

    #[test]
    fn the_sender_names_the_sighting() {
        let with = |id: &str| {
            Submission::parse(
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
        let s = Submission::parse(MINIMAL, NOW).unwrap();
        assert!(s.ts_given);
        let bare = Submission::parse(
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
