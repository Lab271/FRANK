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
pub use model::{Error, Observable, Sighting, SightingBuilder, SightingRow};
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sql_quote_doubles_quotes() {
        assert_eq!(sql_quote("a'b"), "'a''b'");
        assert_eq!(sql_quote("x' OR '1'='1"), "'x'' OR ''1''=''1'");
    }
}
