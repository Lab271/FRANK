//! STIX 2.1 bundles in (#160), simple observations only. Each `sighting`
//! object is one sighting: what it is a sighting of (an `indicator` with
//! `pattern_type: sigma`) and what was observed (the SCOs of its
//! `observed-data`). Other pattern types, relationships and identities
//! (`where_sighted_refs`, `created_by_ref`) are ignored, so a bundle never
//! names the reporter or the target.

use std::collections::HashMap;

use serde_json::{Map, Value};

use crate::model::{time_field, Error, SightingBuilder};
use crate::observable::IocType;
use crate::tlp::Tlp;
use crate::yaml;

/// The TLP marking definitions by their well-known ids: TLP 2.0, then
/// STIX 2.1's TLP 1.0 (WHITE is CLEAR).
const TLP_MARKINGS: [(&str, Tlp); 9] = [
    (
        "marking-definition--94868c89-83c2-464b-929b-a1a8aa3c8487",
        Tlp::Clear,
    ),
    (
        "marking-definition--bab4a63c-aed9-4cf5-a766-dfca5abac2bb",
        Tlp::Green,
    ),
    (
        "marking-definition--55d920b0-5e8b-4f79-9ee9-91f868d9b421",
        Tlp::Amber,
    ),
    (
        "marking-definition--939a9414-2ddd-4d32-a0cd-375ea402b003",
        Tlp::AmberStrict,
    ),
    (
        "marking-definition--e828b379-4e03-4974-9ac4-e53a884c97c1",
        Tlp::Red,
    ),
    (
        "marking-definition--613f2e26-407d-48c7-9eca-b8e91df99dc9",
        Tlp::Clear,
    ),
    (
        "marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da",
        Tlp::Green,
    ),
    (
        "marking-definition--f88d31f6-486f-44da-b317-01333bde0b82",
        Tlp::Amber,
    ),
    (
        "marking-definition--5e57c739-391a-4eb3-b6be-7d15ca92d5ed",
        Tlp::Red,
    ),
];

type Objects<'a> = HashMap<&'a str, &'a Value>;

/// Whether `v` is a STIX bundle.
#[must_use]
pub fn is_bundle(v: &Value) -> bool {
    type_of(v) == Some("bundle")
}

/// A builder per `sighting` object of `bundle`, in bundle order.
///
/// # Errors
///
/// [`Error::Malformed`] for a bundle without objects or sightings,
/// [`Error::Invalid`] for a sighting property of the wrong type.
pub fn sightings(bundle: &Value) -> Result<Vec<SightingBuilder>, Error> {
    let objects = bundle
        .get("objects")
        .and_then(Value::as_array)
        .ok_or_else(|| Error::Malformed("a STIX bundle needs `objects`".into()))?;
    let by_id: Objects = objects
        .iter()
        .filter_map(|o| Some((o.get("id")?.as_str()?, o)))
        .collect();
    let out = objects
        .iter()
        .filter(|o| type_of(o) == Some("sighting"))
        .map(|s| sighting(s, &by_id))
        .collect::<Result<Vec<_>, _>>()?;
    if out.is_empty() {
        return Err(Error::Malformed("the STIX bundle has no `sighting`".into()));
    }
    Ok(out)
}

fn sighting(s: &Value, by_id: &Objects) -> Result<SightingBuilder, Error> {
    let mut b = SightingBuilder::new();
    if let Some(id) = s.get("id").and_then(Value::as_str) {
        b.sighting_id(id);
    }
    if let Some(t) = time_field(s, "first_seen")? {
        b.first_seen(t);
    }
    if let Some(t) = time_field(s, "last_seen")? {
        b.last_seen(t);
    }
    if let Some(n) = s.get("count").filter(|n| !n.is_null()) {
        let n = n
            .as_u64()
            .and_then(|n| u32::try_from(n).ok())
            .ok_or_else(|| Error::Invalid("count must be a whole number >= 1".into()))?;
        b.count(n);
    }
    if let Some(c) = s.get("confidence").filter(|c| !c.is_null()) {
        let c = c
            .as_u64()
            .and_then(|c| u8::try_from(c).ok())
            .ok_or_else(|| Error::Invalid("confidence must be 0-100".into()))?;
        b.confidence(c);
    }
    if let Some(d) = s.get("description").and_then(Value::as_str) {
        b.description(d);
    }
    b.tlp(tlp(s, by_id)?);
    let of = s
        .get("sighting_of_ref")
        .and_then(Value::as_str)
        .and_then(|id| by_id.get(id));
    if let Some(indicator) = of.filter(|o| type_of(o) == Some("indicator")) {
        sigma(&mut b, indicator);
    }
    for od in refs(s, "observed_data_refs", by_id) {
        for sco in observed(od, by_id) {
            observable(&mut b, sco);
        }
    }
    Ok(b)
}

/// The first TLP marking among `object_marking_refs`: a
/// `marking-definition` in the bundle (by its `name`, such as
/// `TLP:AMBER`, or its TLP 1.0 `definition`), else a well-known id.
/// Other markings are ignored; GREEN when there is none.
fn tlp(s: &Value, by_id: &Objects) -> Result<Tlp, Error> {
    let ids = s
        .get("object_marking_refs")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(Value::as_str);
    for id in ids {
        if let Some((_, t)) = TLP_MARKINGS.iter().find(|(k, _)| *k == id) {
            return Ok(*t);
        }
        let Some(m) = by_id.get(id) else {
            continue;
        };
        let named = m
            .get("name")
            .and_then(Value::as_str)
            .filter(|n| n.to_ascii_uppercase().starts_with("TLP:"))
            .or_else(|| m.pointer("/definition/tlp").and_then(Value::as_str));
        if let Some(name) = named {
            return Tlp::parse(name);
        }
    }
    Ok(Tlp::Green)
}

/// The rule of a SIGMA indicator: `id`, `title`, `level` and the
/// `attack.tNNNN` tags of the rule in its `pattern`, falling back to the
/// indicator's own `id` and `name`. Another pattern type is ignored.
fn sigma(b: &mut SightingBuilder, indicator: &Value) {
    if indicator.get("pattern_type").and_then(Value::as_str) != Some("sigma") {
        return;
    }
    if let Some(id) = indicator.get("id").and_then(Value::as_str) {
        b.rule_id(id);
    }
    if let Some(name) = indicator.get("name").and_then(Value::as_str) {
        b.rule_title(name);
    }
    let rule = indicator
        .get("pattern")
        .and_then(Value::as_str)
        .and_then(|p| yaml::to_json(p).ok())
        .unwrap_or(Value::Null);
    if let Some(id) = rule.get("id").and_then(Value::as_str) {
        b.rule_id(id);
    }
    if let Some(title) = rule.get("title").and_then(Value::as_str) {
        b.rule_title(title);
    }
    if let Some(level) = rule.get("level").and_then(Value::as_str) {
        b.rule_level(level);
    }
    for tag in rule
        .get("tags")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
    {
        if let Some(t) = tag.strip_prefix("attack.") {
            b.technique(t);
        }
    }
}

/// The SCOs an `observed-data` object refers to (`object_refs`), or the
/// ones it embeds (`objects`, deprecated in 2.1).
fn observed<'a>(od: &'a Value, by_id: &Objects<'a>) -> Vec<&'a Value> {
    let mut out = refs(od, "object_refs", by_id);
    if let Some(embedded) = od.get("objects").and_then(Value::as_object) {
        out.extend(embedded.values());
    }
    out
}

/// One SCO as observables: an address, domain, URL or e-mail address by
/// its `value`, a file by each of its hashes with its name and size as
/// context. Other SCO types are ignored.
fn observable(b: &mut SightingBuilder, sco: &Value) {
    let Some(t) = type_of(sco) else {
        return;
    };
    if t == "file" {
        let mut context = Map::new();
        if let Some(name) = sco.get("name") {
            context.insert("name".into(), name.clone());
        }
        if let Some(size) = sco.get("size") {
            context.insert("size_bytes".into(), size.clone());
        }
        for h in sco
            .get("hashes")
            .and_then(Value::as_object)
            .into_iter()
            .flatten()
            .filter_map(|(_, h)| h.as_str())
        {
            b.observable(IocType::FileHash, h, None, &context);
        }
        return;
    }
    let value = sco.get("value").and_then(Value::as_str);
    if let (Some(t), Some(v)) = (IocType::parse(t), value) {
        b.observable(t, v, None, &Map::new());
    }
}

fn refs<'a>(o: &Value, key: &str, by_id: &Objects<'a>) -> Vec<&'a Value> {
    o.get(key)
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(|id| by_id.get(id.as_str()?).copied())
        .collect()
}

fn type_of(v: &Value) -> Option<&str> {
    v.get("type").and_then(Value::as_str)
}
