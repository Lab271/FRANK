# FRANK glossary

Terms as Phase 3 uses them ([ADR-016](../.openspec/architecture/decisions/016-phase3-rust-on-db-core.md)). The Phase 2 glossary (Cognito, member and target organisations, service accounts) is at the tag `phase2-final`.

**Participant.** A known organisation, registered in `participants.db` with an opaque id `identity--{uuid4}`, a name, a type (`cyber_partner` or `customer`), sector, region and contact. Only the id reaches the shared data.

**Status** (ADR-002, `crates/frank-core/src/tier.rs::Tier`). What a participant may see and do: *observer*, *contributor*, *partner* or *core*; *public* is the caller without a token. Contributors and above send sightings ("give to get"). The code calls it a tier.

**User.** A person or a machine identity (API client) of one participant. A user has no status of its own: it inherits the participant's.

**Role** (ADR-017, `crates/frank/src/auth.rs::Role`). What a user may administer: *admin* manages its own organisation's users and tokens, *superadmin* (core only) every organisation. Apart from the status.

**Token.** A bearer token of a user. Only its SHA-256 is stored; audit lines show a 12-hex-digit prefix.

**Sighting.** One report that something was seen: when, by which rule or campaign, with which ATT&CK techniques, which observables, at which TLP. Stored as one row per sighting × IoC in the striped Parquet table `data/sightings/`, under the participant's id (`reporter`), never under a user.

**Observable / IoC.** An indicator in a sighting (IP address, domain, URL, hash, …), normalised per type by `crates/frank-core/src/observable.rs`. `iocs.db` holds one row per IoC per day for lookups.

**Reporter threshold** (#148). Below the partner status, a result cell with fewer than 3 distinct reporters is dropped.

**TLP** (#149, `crates/frank-core/src/tlp.rs`). The submitter's disclosure marking per row: CLEAR is public, GREEN observer, AMBER contributor, AMBER+STRICT partner. GREEN is the default; RED is refused.

**Receipt.** The answer to a submission, per sighting: its `sighting_id` (chosen by the sender), `digest` and whether it was created or a duplicate. Resending the same sighting returns the original receipt.

**Hour file / day.** The striped table flushes each closed hour to `live/date=…/hour=…/` and merges closed days into `archive/date=…/`; retention drops whole days.
