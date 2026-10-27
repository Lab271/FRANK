# ADR-017: User roles for identity administration, apart from the participant status

- **Status:** accepted
- **Date:** 2026-10-27
- **Decision Makers:** Ilja Heitlager
- **Related:** [ADR-002](002-tiered-access-control.md) (statuses), [ADR-016](016-phase3-rust-on-db-core.md) (participants), #175

## Context

Since #159 (ADR-016, revised) a participant is an organisation with one status, and its users inherit that status. Organisations, users and tokens could only be managed from the command line on the host (`frank participant|user|token`). Nobody but the operator could add a colleague, issue a token for an API client or revoke a leaked one, and nobody could see who had which token without shell access.

Two things had to stay true:

1. **What a user may see is the organisation's status.** ADR-016 says users have no level of their own, and the shared data is stored under the organisation.
2. **Machine clients must not manage identities.** An organisation's API client inherits its status. If managing identities came with the status, a feed's token could issue tokens.

## Decision

1. **A role is held by a user, not by an organisation.** It decides what the user may *manage*; the organisation's status still decides what it may *see*. There are two roles:
   - **admin:** manages the users and tokens of its own organisation, and reads the audit lines about it. Held in a contributor, partner or core organisation.
   - **superadmin:** manages every organisation, including adding organisations and changing their status. Held in a core organisation only.
2. **Only people hold a role.** A `machine` user can never be given one, from the CLI or the API.
3. **Roles live in `participants.db`, in a `roles` table** (`user`, `role`), not in a column on `users`. db-core's row engine cannot add a column to an existing table yet (grammar V8), so a new table is created in files that lack it. Existing files need no migration.
4. **Users are disabled before they are removed.** A disabled user's tokens stop working but are not revoked; enabling the user brings them back. Only a disabled user can be removed, which deletes it with its role and tokens. Its sightings stay, because they are stored under the organisation. The `disabled` table (`user`, `at`) follows the same pattern as `roles`.
5. **`/v1/admin/…` is the API, and the web UI has an admin tab** shown only to users with a role. To an admin, another organisation's objects answer 404, as if they did not exist. Only a superadmin grants, takes, disables or removes a superadmin.
6. **Guards keep the platform manageable.** Refused through the API:
   - taking the role of an organisation's last working admin, or the platform's last working superadmin, by a role change or by disabling the user (disabled users do not count as working);
   - disabling oneself;
   - removing a user that is not disabled;
   - revoking the caller's own last token;
   - changing an organisation's status so that one of its users holds a role the status does not allow.

   The CLI stays the operator's tool. It applies the role rules (2 and the status rule) and the disable-before-remove rule, but not the last-admin guards, so it can always recover a platform.
7. **Every change is audited.** The server writes the same audit lines as the CLI (`role_set`, `user_disabled`, `user_enabled`, `user_removed`, `token_issued`, `token_revoked`, `participant_added`, `status_set`), with `by` set to `user@organisation`. A token appears only as the first 12 hex digits of its hash; the plain token is in the one response that issues it (`Cache-Control: no-store`).

## Consequences

- **The server now writes `participants.db`.** Until 0.16 only the CLI did, and the server reloaded the file when it changed. Server writes go through the same store functions, each in one transaction, and one lock serialises the server's own check-then-write steps. The CLI can still write at the same time; SQLite's locking keeps both safe, but a guard checked by the server can be overtaken by a CLI change made in the same instant.
- **Bootstrapping needs the CLI once:** the first superadmin is made with `frank user add <core organisation> <name> --role superadmin` or `frank user set-role <name> superadmin`.
- **User names are unique on the platform.** An admin who picks a name taken in another organisation is told it exists, which reveals that the name is in use somewhere. The names are not secrets; if that changes, names become unique per organisation.
- **A removed user's name can be used again.** Audit lines before and after a removal can name the same user; their timestamps tell them apart.
- **Observer organisations have no admin.** They cannot submit; their users and tokens are managed by a superadmin. This can be opened up by lowering the admin rule to observer.
