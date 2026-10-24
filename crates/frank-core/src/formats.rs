//! The three input formats (#160): JSON (Phase 2's or `frank/1`), YAML
//! (the same documents) and STIX 2.1 bundles. One body holds one
//! sighting, a list of them, or a bundle.

use serde_json::Value;

use crate::model::{Error, Sighting, SightingBuilder};
use crate::{stix, yaml};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Format {
    Json,
    Yaml,
    Stix,
}

impl Format {
    /// The format a `Content-Type` names: `application/json`,
    /// `application/yaml` (also `application/x-yaml`, `text/yaml`) or
    /// `application/stix+json`. Parameters such as `charset` or
    /// `version=2.1` are ignored.
    #[must_use]
    pub fn from_content_type(ct: &str) -> Option<Format> {
        let media = ct
            .split(';')
            .next()
            .unwrap_or("")
            .trim()
            .to_ascii_lowercase();
        match media.as_str() {
            "application/json" => Some(Format::Json),
            "application/yaml" | "application/x-yaml" | "text/yaml" | "text/x-yaml" => {
                Some(Format::Yaml)
            }
            "application/stix+json" => Some(Format::Stix),
            _ => None,
        }
    }

    /// The format of `text` when nothing names it: JSON when it starts
    /// with `{` or `[`, else YAML. A STIX bundle is JSON.
    #[must_use]
    pub fn sniff(text: &str) -> Format {
        match text.trim_start().as_bytes().first() {
            Some(b'{' | b'[') => Format::Json,
            _ => Format::Yaml,
        }
    }
}

/// Every sighting in `text`, in order. JSON and YAML hold one sighting or
/// a list; a STIX bundle is read as STIX whichever format named it. An
/// error names the sighting it is about: `[1] confidence must be 0-100`.
///
/// # Errors
///
/// [`Error::Malformed`] for text that is not of `format` or not shaped
/// like sightings, [`Error::Invalid`] for a value that cannot be used.
pub fn parse(text: &str, format: Format, now_ns: i64) -> Result<Vec<Sighting>, Error> {
    let v: Value = match format {
        Format::Json | Format::Stix => {
            serde_json::from_str(text).map_err(|e| Error::Malformed(e.to_string()))?
        }
        Format::Yaml => yaml::to_json(text)?,
    };
    let builders: Vec<SightingBuilder> = if stix::is_bundle(&v) {
        stix::sightings(&v)?
    } else if format == Format::Stix {
        return Err(Error::Malformed("expected a STIX bundle".into()));
    } else {
        match &v {
            Value::Array(items) => items
                .iter()
                .enumerate()
                .map(|(i, item)| SightingBuilder::from_json(item).map_err(|e| at(i, e)))
                .collect::<Result<_, _>>()?,
            item => vec![SightingBuilder::from_json(item).map_err(|e| at(0, e))?],
        }
    };
    builders
        .iter()
        .enumerate()
        .map(|(i, b)| b.build(now_ns).map_err(|e| at(i, e)))
        .collect()
}

fn at(i: usize, e: Error) -> Error {
    match e {
        Error::Malformed(m) => Error::Malformed(format!("[{i}] {m}")),
        Error::Invalid(m) => Error::Invalid(format!("[{i}] {m}")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const NOW: i64 = 1_800_000_000_000_000_000;
    const JSON: &str = include_str!("../../../examples/formats/sighting.json");
    const YAML: &str = include_str!("../../../examples/formats/sighting.yaml");
    const STIX: &str = include_str!("../../../examples/formats/sighting.stix.json");

    #[test]
    fn content_types_name_formats() {
        let f = Format::from_content_type;
        assert_eq!(f("application/json; charset=utf-8"), Some(Format::Json));
        assert_eq!(f("Application/YAML"), Some(Format::Yaml));
        assert_eq!(f("text/yaml"), Some(Format::Yaml));
        assert_eq!(f("application/stix+json;version=2.1"), Some(Format::Stix));
        assert_eq!(f("text/plain"), None);
        assert_eq!(Format::sniff("  [1]"), Format::Json);
        assert_eq!(Format::sniff("sighting:\n  x: 1"), Format::Yaml);
    }

    /// #160's acceptance criterion: the same sighting as JSON, YAML and
    /// STIX is the same normalised record.
    #[test]
    fn the_same_sighting_in_three_formats_is_one_record() {
        let json = parse(JSON, Format::Json, NOW).unwrap();
        let yaml = parse(YAML, Format::Yaml, NOW).unwrap();
        let stix = parse(STIX, Format::Stix, NOW).unwrap();
        assert_eq!(json.len(), 1);
        assert_eq!(json, yaml, "YAML");
        assert_eq!(json, stix, "STIX");
        let s = &json[0];
        assert_eq!(s.sighting_of.techniques, ["T1059.001", "T1071.001"]);
        assert_eq!(s.evidence.len(), 3);
        assert_eq!(s.tlp, crate::Tlp::Amber);
        assert_eq!(
            parse(STIX, Format::Json, NOW).unwrap(),
            stix,
            "a bundle sent as plain JSON"
        );
    }

    #[test]
    fn a_bundle_holds_several_sightings_and_ignores_the_rest() {
        let mut bundle: Value = serde_json::from_str(STIX).unwrap();
        let objects = bundle["objects"].as_array_mut().unwrap();
        let mut second = objects
            .iter()
            .find(|o| o["type"] == "sighting")
            .unwrap()
            .clone();
        second["id"] = "sighting--6ba7b810-9dad-41d1-80b4-00c04fd430c8".into();
        second["where_sighted_refs"] = serde_json::json!(["identity--secret"]);
        objects.push(second);
        objects.push(
            serde_json::json!({"type": "identity", "id": "identity--secret", "name": "ACME"}),
        );
        objects.push(serde_json::json!({"type": "relationship", "id": "relationship--1"}));
        let out = parse(&bundle.to_string(), Format::Stix, NOW).unwrap();
        assert_eq!(out.len(), 2);
        assert!(!serde_json::to_string(&out).unwrap().contains("ACME"));
    }

    #[test]
    fn errors_name_the_sighting() {
        let two = r#"[{"sighting": {"sigma_detection": {"rule_id": "r"}}},
                      {"sighting": {"confidence": 101, "sigma_detection": {"rule_id": "r"}}}]"#;
        assert!(
            matches!(parse(two, Format::Json, NOW), Err(Error::Invalid(m)) if m.starts_with("[1] "))
        );
        assert!(matches!(
            parse(r#"{"sighting": {}}"#, Format::Stix, NOW),
            Err(Error::Malformed(m)) if m.contains("STIX")
        ));
        assert!(matches!(
            parse(r#"{"type": "bundle", "objects": []}"#, Format::Json, NOW),
            Err(Error::Malformed(_))
        ));
    }
}
