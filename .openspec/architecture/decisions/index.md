# Architecture decisions

Phase 3 (the Rust build, ADR-016 onwards) supersedes most of the Phase 2 decisions; those stay here as history. The Phase 2 code and documents are at the tag `phase2-final`.

Status is one of Accepted, Proposed, Superseded by ADR-NNN, Deprecated, written as `- **Status:** ...` under the title.

| ADR | Title | Status | Date |
|---|---|---|---|
| [001](001-single-code-library.md) | Single Code Library Across All Infrastructure Stages | Superseded by [ADR-016](016-phase3-rust-on-db-core.md) | 2026-02-12 |
| [002](002-tiered-access-control.md) | Tiered Access Control Model | Accepted | 2026-02-12 |
| [003](003-four-stage-infrastructure-evolution.md) | Four-Stage Infrastructure Evolution | Superseded by [ADR-016](016-phase3-rust-on-db-core.md) | 2026-01-23 |
| [004](004-repository-pattern-database-abstraction.md) | Repository Pattern for Database Abstraction | Superseded by [ADR-016](016-phase3-rust-on-db-core.md) | 2026-01-23 |
| [005](005-three-layer-testing-strategy.md) | Three-Layer Testing Strategy | Superseded by [ADR-018](018-container-is-the-reference-and-test-tiers.md) | 2026-01-23 |
| [006](006-cognito-authentication.md) | AWS Cognito Authentication Strategy | Superseded by [ADR-016](016-phase3-rust-on-db-core.md) | 2026-01-29 |
| [007](007-admin-mvc-architecture.md) | MVC Architecture for Admin Module | Superseded by [ADR-016](016-phase3-rust-on-db-core.md) | 2026-01-29 |
| [008](008-forgiving-input-strong-output.md) | Forgiving Input, Strong Output | Accepted | 2026-01-28 |
| [009](009-explicit-error-communication.md) | Explicit Error Communication | Accepted | 2026-01-28 |
| [010](010-postgresql-management-api.md) | PostgreSQL for Management API Data Storage | Superseded by [ADR-016](016-phase3-rust-on-db-core.md) | 2026-01-31 |
| [011](011-stages-vs-environments.md) | Stages vs Environments Architecture | Superseded by [ADR-016](016-phase3-rust-on-db-core.md) | 2026-01-31 |
| [012](012-spike-integration-process.md) | Spike Integration Process | Deprecated | 2026-01-31 |
| [013](013-testing-philosophy.md) | Testing Philosophy and Local Services | Superseded by [ADR-018](018-container-is-the-reference-and-test-tiers.md) | 2026-01-31 |
| [014](014-asynchronous-background-task-processing.md) | Asynchronous Background Task Processing | Deprecated | 2026-02-06 |
| [015](015-c4-model-architecture-visualization.md) | C4 Model for Architecture Visualization | Deprecated | 2026-02-06 |
| [016](016-phase3-rust-on-db-core.md) | Phase 3 in Rust on db-core: striped Parquet sightings, a row table for IoCs, a WASM client | Accepted, revised 2026-10-23 (participants, #159) and 2026-11-10 (target identities, #256) | 2026-10-22 |
| [017](017-user-roles-for-identity-administration.md) | User roles for identity administration, apart from the participant status | Accepted | 2026-10-27 |
| [018](018-container-is-the-reference-and-test-tiers.md) | The container image is the reference; four test tiers | Accepted | 2026-11-03 |
| [019](019-sightings-in-s3-state-on-a-volume.md) | Sightings in S3, the rest of the state on a volume | Accepted | 2026-11-07 |
| [021](021-spec-links-checked-in-ci.md) | Spec links are checked in CI | Accepted | 2026-11-10 |
