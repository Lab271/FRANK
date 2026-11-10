# ADR-020: Sign in with OpenID Connect, users provisioned on first login, bearer tokens unchanged

- **Status:** Accepted
- **Date:** 2026-11-10
- **Decision Makers:** Ilja Heitlager
- **Related:** [ADR-002](002-tiered-access-control.md) (statuses), [ADR-016](016-phase3-rust-on-db-core.md) (participants), [ADR-017](017-user-roles-for-identity-administration.md) (roles), #241, #234; replaces the Cognito direction of [ADR-006](006-cognito-authentication.md) and the Phase 2 spec 012 (removed in #248)

## Context

A person reaches FRANK's web UI by pasting a bearer token, which an admin issued and which the browser keeps in `sessionStorage`. Lab271 runs Okta; its people should sign in with their Okta account instead, and FRANK should know them without an operator adding each one first.

Four things had to stay true:

1. **Bearer tokens stay the API credential.** Feeds, scripts and `make stream` send `Authorization: Bearer …` and must not notice SSO at all.
2. **SSO is optional.** Without its settings FRANK behaves exactly as before: local development, tests and deployments without an identity provider.
3. **What a user may see is still its organisation's status** (ADR-002, ADR-016); what it may manage is still its role (ADR-017).
4. **We develop for production.** The design must hold on the production deployment, not only in the local podman stack.

## Decision

1. **OpenID Connect, not SAML.** The authorization code flow with PKCE (S256), as a confidential client. Okta speaks both protocols; we chose OIDC because:
   - SAML assertions are XML signed with XML-DSig. Validating them is a long-standing source of vulnerabilities (signature wrapping, canonicalisation, XXE), and Rust has no mature SAML library, so that code would be ours.
   - An ID token is a JWT: base64url JSON with an RS256 signature, checked with `ring`, which FRANK already links through rustls. No new crypto crate.
   - The local stand-in for Okta (#238) needs four small endpoints (discovery, authorize, token, JWKS) instead of signed XML, metadata and POST bindings; and RP-initiated logout is simpler than SAML single logout.
   - Nothing we need from Okta (email, name, groups) exists only in SAML.

   Nothing protocol-specific leaks past the callback: provisioning and sessions take an issuer, a subject and claims, so a SAML adapter could be added later without changing them.

2. **Off unless fully configured.** `frank serve` takes `FRANK_SSO_ISSUER`, `FRANK_SSO_CLIENT_ID`, `FRANK_SSO_CLIENT_SECRET_FILE`, `FRANK_SSO_REDIRECT_URL` and `FRANK_SSO_ORGANISATION`. None set: no SSO, no `/v1/sso` behaviour beyond "not configured". Some set: FRANK refuses to start and names the missing setting. The issuer and redirect URL must be `https://`, except for `localhost` and `*.local` hosts, which the local stub uses. Discovery and the JWKS are fetched at the first login and cached (the JWKS again for an unknown `kid`), so an identity provider that is down cannot stop FRANK from starting.

3. **One secret, read from a file.** The Okta client secret is the only secret SSO adds. It is read from the file `FRANK_SSO_CLIENT_SECRET_FILE` names (a podman secret, a mounted file), never from an environment variable, which `podman inspect` and process listings show. It is never logged, audited or returned. The in-flight login state (`state`, `nonce`, the PKCE verifier) lives in the server's memory for ten minutes, so no signing key is needed for it; a restart only breaks logins in progress.

4. **The callback checks the ID token completely** before anything else happens: RS256 signature against the issuer's JWKS, `iss` equal to the configured issuer, `aud` containing the client id, `exp` in the future, `nonce` equal to the one sent, and the `state` of the redirect known and unexpired. Any failure is a refusal and an `sso_refused` audit line with the reason, never a partial login.

5. **Users are provisioned on first login (JIT).** A person is identified by issuer and `sub`, kept in a new `sso_subjects` table (`subject`, `user`, `created`), where `subject` is the issuer and `sub` one space apart, because the row engine keys on one column; the `email` claim, in lower case, is the user's name.
   - A known subject signs in as its user.
   - An unknown subject whose `email` is verified (`email_verified`) and names an existing **human** user is linked to that user, which keeps its organisation and role: an operator made with the CLI keeps being superadmin when signing in with Okta.
   - Otherwise a new human user is created in `FRANK_SSO_ORGANISATION`, **with no role**. SSO never grants a role; admins do, as in ADR-017.
   - A disabled user is refused. A machine user is never linked or signed in.
   - Audit lines: `user_provisioned`, `sso_login`, `sso_refused`, `sso_logout`, `by` the user, never a token or secret.

6. **A session is a random value in an HttpOnly cookie, stored as its SHA-256.** `frank_session` (`HttpOnly; Secure; SameSite=Lax; Path=/`) holds 32 random bytes; `participants.db` keeps only their hash in a new `sessions` table (`hash`, `user`, `created`, `expires`), eight hours. Logout deletes it. A disabled user's sessions stop working, as its tokens do; removing the user deletes them. Both tables follow the ADR-017 pattern: created in files that lack them, no migration.

7. **The `Authorization` header first, then the cookie.** The web UI calls the same `/v1` routes as every other client, so a session must name the caller there too. `require()` looks at the `Authorization` header exactly as before; only when there is none does it look at the cookie. A `POST`, `PUT`, `PATCH` or `DELETE` named by the cookie needs an `Origin` header equal to the redirect URL's origin, against cross-site request forgery. A bearer request never needs one.

## Consequences

- **Okta becomes a dependency of signing in, not of FRANK.** Tokens keep working when Okta is down; only new SSO logins fail.
- **Okta's view of a person is not pushed to FRANK.** A person removed from Okta keeps their FRANK user until an admin disables it; their session ends within eight hours. SCIM, which would push those changes, is a separate story.
- **The server writes `participants.db` on every login** (a session row, and the user on the first). Each is one transaction through the store functions the CLI uses.
- **HTTP calls to the identity provider** go through `ureq` with rustls, now a regular dependency rather than only the `tls` feature's.
- **Local development** gets a Python stand-in for Okta (#238), started only by `make up-sso`, never deployed; production setup of the Okta application is tracked in GitLab (`Labs/deployments/test-frank`).
