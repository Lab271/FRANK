//! FRANK's wire model (ADR-016): a submission comes in as a normalised
//! [`Sighting`] (`frank/1`, #160), shared sighting rows go out. Shared by
//! the server and the browser (WASM), so a contributor sees exactly the
//! rows that will be shared before sending.
//!
//! The shared rows are anonymous by schema: [`SightingRow`] has no column
//! for the submitter's or the target's identity. The [`Sighting`] keeps
//! the target's id as the sender gave it, for Core only; the submitter is
//! never part of it (the server knows the participant).

pub mod formats;
pub mod model;
pub mod observable;
pub mod stix;
pub mod tier;
pub mod tlp;
pub mod yaml;

pub use formats::Format;
pub use model::{Digest, Error, Observable, Sighting, SightingBuilder, SightingId, SightingRow};
pub use observable::{Ioc, IocType};
pub use tier::Tier;
pub use tlp::Tlp;

/// The smallest count a public or observer answer shows for one cell
/// (sector, type, ...); smaller cells are suppressed (k-anonymity).
pub const MIN_CELL: i64 = 3;

/// `s` as an SQL string literal: quotes doubled. The only escape SQLite's
/// grammar (and db-core's) has; values are normalised before they get here.
#[must_use]
pub fn sql_quote(s: &str) -> String {
    format!("'{}'", s.replace('\'', "''"))
}

/// `bytes` as an SQL blob literal, `x'…'` (#200).
#[must_use]
pub fn sql_blob(bytes: &[u8]) -> String {
    format!("x'{}'", hex(bytes))
}

/// `bytes` in lower-case hex.
#[must_use]
pub fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

/// The bytes of a hex string (either case); `None` for anything else.
#[must_use]
pub fn unhex(s: &str) -> Option<Vec<u8>> {
    // Checked first: `from_str_radix` takes a leading `+`.
    if s.len() % 2 != 0 || !s.bytes().all(|b| b.is_ascii_hexdigit()) {
        return None;
    }
    (0..s.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&s[i..i + 2], 16).ok())
        .collect()
}

#[cfg(test)]
#[allow(non_snake_case)] // mcdc__<id>__v<N>_<what> (ADR-025)
mod tests {
    use super::*;

    // MC/DC of `unhex`'s guard: odd length || a non-hex byte (ADR-025).
    #[test]
    fn mcdc__lib_unhex_72fb6839__v1_even_and_hex_is_decoded() {
        assert_eq!(unhex("0aFf"), Some(vec![0x0a, 0xff]));
    }

    #[test]
    fn mcdc__lib_unhex_72fb6839__v2_odd_length_is_refused() {
        assert_eq!(unhex("0af"), None);
    }

    #[test]
    fn mcdc__lib_unhex_72fb6839__v3_a_non_hex_byte_is_refused() {
        // `+a` would pass `from_str_radix`; the guard refuses it first.
        assert_eq!(unhex("+a"), None);
    }

    #[test]
    fn sql_quote_doubles_quotes() {
        assert_eq!(sql_quote("a'b"), "'a''b'");
        assert_eq!(sql_quote("x' OR '1'='1"), "'x'' OR ''1''=''1'");
    }

    #[test]
    fn hex_round_trips() {
        assert_eq!(hex(&[0x0f, 0xab]), "0fab");
        assert_eq!(unhex("0FaB"), Some(vec![0x0f, 0xab]));
        assert_eq!(sql_blob(&[0x0f, 0xab]), "x'0fab'");
        assert_eq!(unhex("0fa"), None);
        assert_eq!(unhex("0g"), None);
        assert_eq!(
            unhex("aé0"),
            None,
            "not hex, and no panic on a char boundary"
        );
        assert_eq!(unhex("+f"), None, "from_str_radix would take it");
    }
}
