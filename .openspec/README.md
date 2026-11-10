# FRANK specifications and decisions

What FRANK must do (specs) and why it is built the way it is (ADRs), for Phase 3: the Rust build on db-core ([ADR-016](architecture/decisions/016-phase3-rust-on-db-core.md)). The Phase 2 specs and design documents (Python/FastAPI, Cognito, DynamoDB, PostgreSQL, ECS, the four stages) left the tree; they are at the tag `phase2-final`.

```
.openspec/
├── specs/NNN-name/spec.md        one spec per area
└── architecture/decisions/       ADRs, NNN-title.md, see index.md
```

## Specs

| Range | Area |
|---|---|
| 001–009 | Data model: submission, sighting, observable, TLP |
| 010–019 | HTTP API: sightings, management, authentication |
| 020–029 | Storage: sightings table, IoC lookups, participants |
| 030–039 | Clients and deployment: web, WASM, container |

A spec is written in RFC 2119 terms, one requirement per heading, with its scenarios and links to the code and tests that carry it ([spec 011](specs/011-management-api/spec.md) is the model):

```markdown
### Requirement 3: Organisations [MUST]

A superadmin SHALL list, create and set the status of organisations. ...

**Implementation:** `crates/frank/src/admin.rs::add_organisation`, `crates/frank/src/admin.rs::set_status`

#### Scenario: An admin cannot create an organisation

- GIVEN an admin of a contributor organisation
- WHEN it posts to /v1/admin/organisations
- THEN the answer is 403

**Tests:** `crates/frank/tests/api.rs::superadmins_and_the_guards`
```

- A link is `path` or `path::symbol`, backtick-quoted, comma-separated. For a `.rs` file the symbol must be a `fn` in that file.
- `**Implementation:**` sits in the requirement, before its first scenario. `**Tests:**` sits in the scenario it backs.
- A link suffixed `(planned)` marks work not done yet and is not counted.
- A spec whose `**Status:**` starts with `Outdated` is not counted either: it awaits a rewrite (#250).

`make assurance` shows per spec how many requirements link to existing code and how many scenarios to a test; `make assurance V=1` lists every requirement and each dead link. `make check-assurance` fails on a dead link, and CI runs it: a link to a renamed function or test is a false claim of coverage.

## Decisions

ADRs live in [architecture/decisions](architecture/decisions/index.md), numbered `NNN-title.md`, with `- **Status:**` (Accepted, Proposed, Superseded by ADR-NNN, Deprecated) and `- **Date:**` under the title. A decision that replaces another says `- **Supersedes:**`, and the replaced one is marked. Add the new ADR to `index.md`.
