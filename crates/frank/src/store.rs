//! FRANK's stores under one data directory (ADR-016):
//!
//! ```text
//! <data>/sightings/        striped Parquet table (db-core ingest)
//! <data>/iocs.db           row table, one row per IoC per day
//! <data>/participants.db   row tables: organisations, users, tokens (#159)
//! ```

pub mod iocs;
pub mod participants;
pub mod rowdb;
pub mod sightings;

pub use iocs::Iocs;
pub use participants::Participants;
pub use sightings::Sightings;
