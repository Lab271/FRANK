# ADR-026: The SSO admin group makes its members admins in one organisation

- **Status:** Accepted
- **Date:** 2026-11-14
- **Decision Makers:** Ilja Heitlager
- **Related:** [ADR-020](020-sso-with-openid-connect.md) (supersedes the "SSO never grants a role" of decision 5 for this one mapping), [ADR-017](017-user-roles-for-identity-administration.md) (roles), [spec 012](../../specs/012-sso/spec.md), #321, test-frank#2

## Context

ADR-020 creates every person who signs in for the first time in one organisation, with no role, and links an existing user only by a **verified** e-mail. To make an Okta user an admin, an operator had to create the FRANK user first and have the person's first sign-in link to it.

On STACKIT with Lab271's Okta (`sbplabs`) that does not work: the ID token says `email_verified: false`, so the link is refused (`… exists and the identity's e-mail is not verified`), and the person cannot sign in at all. FRANK's admins are already one Okta group, `frank-admins`. Okta is where people join and leave that group, so it is the right place to say who is an admin.

Trusting the e-mail without `email_verified` was considered and not chosen: it is only safe where people cannot change their own e-mail at the provider, and with the group nobody needs to be created in advance, so linking by e-mail becomes rare and keeps its check.

## Decision

1. **Two optional settings, both or neither:** `FRANK_SSO_ADMIN_GROUP` (a group name as the provider sends it) and `FRANK_SSO_ADMIN_ORGANISATION` (name or id; it must exist when `frank serve` starts). One without the other, or either without the other SSO settings, refuses to start.
2. **The ID token's `groups` claim** (an array of strings) is read with the other claims. Nothing else in it is used. The provider must put the group there: in Okta, a `groups` claim on the authorization server, in the ID token, filtered to the group.
3. **At every sign-in**, after the user is found, linked or provisioned and before its session starts:
   - A **member** without a role, or with the role the group gave it, is moved to the admin organisation and made **admin** (ADR-017: its own organisation's users and tokens). A new member therefore lands there at the first sign-in.
   - A user who is **no longer a member** and holds the role the group gave loses it and goes back to `FRANK_SSO_ORGANISATION`.
   - Which roles the group gave is kept in a new table, `sso_roles` (`user`, `at`), created like ADR-017's tables in files that lack it.
4. **A role set by hand is never touched.** A superadmin, or an admin made with `frank user set-role` or `user add --role`, stays as it is whether or not the user is in the group. Setting a role by hand also takes it out of `sso_roles`: from then on it is the command line's. Removing a user removes its row.
5. **Audit lines** `role_granted` and `role_revoked`, by `sso`, with the user, the role, the organisation and the group; then `sso_login` as before.
6. Only `admin` is granted. Superadmin stays a deliberate step on the command line, made after the person's first sign-in.

## Consequences

- **Okta decides who is an admin of the admin organisation**, within one sign-in. A person removed from the group keeps the role until they next sign in, at most their session's eight hours if they do not; their bearer tokens are unaffected by the group either way.
- **Bootstrapping the first superadmin:** sign in (admin through the group), then `frank user set-role <e-mail> superadmin` on the host.
- **Moving between organisations changes what a user sees** (its organisation's status, ADR-002): leaving the group also leaves the admin organisation's tier.
- Other provider groups are still not mapped; a general mapping of groups to organisations stays out of scope.
