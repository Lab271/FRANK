//! The FRANK server (ADR-016): sightings in a striped Parquet table, IoCs
//! in a row table, an HTTP API with tiered access, a static web UI.

pub mod api;
pub mod auth;
pub mod explore;
pub mod reporter;
pub mod store;
