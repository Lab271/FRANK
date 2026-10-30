//! FRANK's stores (ADR-016):
//!
//! ```text
//! <data>/sightings/                 striped Parquet table (db-core ingest)
//! <data>/iocs.db                    row table, one row per IoC per day
//! <data>/geo.db                     row table: country and ASN per IP address (#191)
//! <data>/geoip/geolite2/            MaxMind's GeoLite2 databases (`make geoip`), read only
//! <data>/registry.db                row table: resend index (participant, sighting id → digest)
//! <data>/audit/                     JSON lines: who did what ([`crate::audit`])
//! <participants>/participants.db    row tables: organisations, users, tokens (#159)
//! ```
//!
//! The participants sit apart from the data: wiping the data keeps them.

pub mod geo;
pub mod iocs;
pub mod participants;
pub mod registry;
pub mod rowdb;
pub mod sightings;

pub use iocs::Iocs;
pub use participants::Participants;
pub use registry::Registry;
pub use sightings::Sightings;
