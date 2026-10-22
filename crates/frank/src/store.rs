//! FRANK's two stores under one data directory (ADR-016):
//!
//! ```text
//! <data>/sightings/   striped Parquet table (db-core ingest)
//! <data>/iocs.db      row table, one row per IoC per day
//! ```

pub mod iocs;
pub mod sightings;

pub use iocs::Iocs;
pub use sightings::Sightings;
