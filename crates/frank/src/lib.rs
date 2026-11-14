//! The FRANK server (ADR-016): sightings in a striped Parquet table, IoCs
//! in a row table, an HTTP API with tiered access, a static web UI.

pub mod admin;
pub mod api;
pub mod audit;
pub mod auth;
pub mod cli;
pub mod explore;
pub mod geo;
pub mod lists;
pub mod live;
pub mod mcp;
pub mod mmdb;
pub mod objects;
pub mod records;
pub mod serve;
pub mod sso;
pub mod store;
