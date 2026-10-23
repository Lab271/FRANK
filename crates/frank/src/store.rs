//! FRANK's stores (ADR-016):
//!
//! ```text
//! <data>/sightings/                 striped Parquet table (db-core ingest)
//! <data>/iocs.db                    row table, one row per IoC per day
//! <data>/registry.db                row table: resend index (participant, sighting id → digest)
//! <participants>/participants.db    row tables: organisations, users, tokens (#159)
//! ```
//!
//! The participants sit apart from the data: wiping the data keeps them.

pub mod iocs;
pub mod participants;
pub mod registry;
pub mod rowdb;
pub mod sightings;

pub use iocs::Iocs;
pub use participants::Participants;
pub use registry::Registry;
pub use sightings::Sightings;
