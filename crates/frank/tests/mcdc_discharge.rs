//! MC/DC bookkeeping (ADR-025, #317), ported from db-core's
//! `tests/unit/mcdc_discharge_test.rs`. `cargo-mvl-mcdc harvest` joins tests
//! named `mcdc__<id>__v<N>_<what>` to the decisions in the committed snapshot
//! (`tests/mcdc/obligations.json`) by id alone, so two silent failures are
//! checked here, under a plain `cargo test` and without the tool installed:
//! a tagged test whose id is gone (an edit changed the decision, its hash and
//! so its id; the test still passes but no longer counts), and one id in two
//! files (both `lib.rs` of frank-core and frank-wasm have the slug `lib`).

use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::{Path, PathBuf};

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../..")
}

/// `(id, file)` of every decision in the snapshot.
fn obligations() -> Vec<(String, String)> {
    let path = root().join("tests/mcdc/obligations.json");
    let raw = fs::read_to_string(&path)
        .unwrap_or_else(|e| panic!("{}: {e}; run make mcdc-obligations", path.display()));
    let all: Vec<serde_json::Value> = serde_json::from_str(&raw).unwrap();
    all.iter()
        .map(|o| {
            let field = |k: &str| o[k].as_str().unwrap().to_string();
            (field("id"), field("file"))
        })
        .collect()
}

/// Every `.rs` file of the workspace's crates, sources and tests.
fn rust_files() -> Vec<PathBuf> {
    fn walk(dir: &Path, out: &mut Vec<PathBuf>) {
        for entry in fs::read_dir(dir).into_iter().flatten().flatten() {
            let path = entry.path();
            if path.is_dir() {
                walk(&path, out);
            } else if path.extension().is_some_and(|e| e == "rs") {
                out.push(path);
            }
        }
    }
    let mut out = Vec::new();
    walk(&root().join("crates"), &mut out);
    out
}

/// The ids named by `fn mcdc__<id>__v<N>...`: `__v` and a digit end the id,
/// so an `_` inside it does not.
fn tagged_ids(source: &str) -> Vec<String> {
    source
        .match_indices("fn mcdc__")
        .filter_map(|(at, m)| {
            let rest = &source[at + m.len()..];
            let end = rest.find("__v")?;
            let digit = rest[end + 3..].starts_with(|c: char| c.is_ascii_digit());
            digit.then(|| rest[..end].to_string())
        })
        .collect()
}

#[test]
fn every_tagged_test_names_a_decision_in_the_snapshot() {
    let known: HashSet<String> = obligations().into_iter().map(|(id, _)| id).collect();
    let mut stale = Vec::new();
    for path in rust_files() {
        let source = fs::read_to_string(&path).unwrap();
        for id in tagged_ids(&source) {
            if !known.contains(&id) {
                stale.push(format!("{}: mcdc__{id}__", path.display()));
            }
        }
    }
    assert!(
        stale.is_empty(),
        "these tests name a decision the snapshot does not have: the decision changed \
         (rename the test to its new id) or the snapshot is stale (make mcdc-obligations):\n{}",
        stale.join("\n")
    );
}

#[test]
fn no_decision_id_is_shared_by_two_files() {
    let mut files: HashMap<String, HashSet<String>> = HashMap::new();
    for (id, file) in obligations() {
        files.entry(id).or_default().insert(file);
    }
    let mut shared: Vec<String> = files
        .into_iter()
        .filter(|(_, f)| f.len() > 1)
        .map(|(id, f)| format!("{id}: {f:?}"))
        .collect();
    shared.sort();
    assert!(
        shared.is_empty(),
        "harvest joins tests to decisions by id alone, so these would count for each other:\n{}",
        shared.join("\n")
    );
}

#[test]
fn a_tagged_name_yields_its_id() {
    // Built, so the walk above does not read this file's own literal as a tag.
    let src = [
        "fn ",
        "mcdc__lib_unhex_1f__v2_odd_length() {}\nfn ",
        "mcdc__x__vague() {}",
    ]
    .concat();
    assert_eq!(tagged_ids(&src), ["lib_unhex_1f"]);
}
