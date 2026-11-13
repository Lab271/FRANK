# Sign in with SSO Specification

**Domain:** API Security / Authentication
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-11-10

**Owner:** Platform Team
- **Related ADR:** [ADR-020](../../architecture/decisions/020-sso-with-openid-connect.md), [ADR-017](../../architecture/decisions/017-user-roles-for-identity-administration.md), [ADR-002](../../architecture/decisions/002-tiered-access-control.md)
- **Issues:** #241 (epic), #234, #235, #236, #237, #238, #239, #240
**Implementation:** `crates/frank/src/sso.rs`, `crates/frank/src/store/participants.rs::sign_in`
**Tests:** `crates/frank/tests/sso.rs`, `crates/frank/src/sso.rs`, `crates/frank/src/store/participants.rs`, `scripts/sso_check.py`

## Overview

People sign in to FRANK's web UI with OpenID Connect (Okta in production, a local stub in development) instead of pasting a bearer token. SSO is optional; bearer tokens stay the API credential and behave exactly as before. It replaces the Cognito direction of the Phase 2 authentication spec that held number 012 (removed in #248, at the tag `phase2-final`), which the Rust server never implemented.

### Philosophy

- **Off unless configured**: without its settings FRANK behaves as before.
- **Tokens first**: the `Authorization` header always decides when present; a session cookie only names a caller without one.
- **One secret, in a file**: the OIDC client secret, never in the environment, a log, an audit line or a response.
- **Status decides what you see, an admin decides what you manage**: SSO creates users without a role.

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## Requirements

### Requirement 1: Configuration, off by default [MUST]

`frank serve` MUST take `FRANK_SSO_ISSUER`, `FRANK_SSO_CLIENT_ID`, `FRANK_SSO_CLIENT_SECRET_FILE`, `FRANK_SSO_REDIRECT_URL` and `FRANK_SSO_ORGANISATION`. With none of them SSO MUST be off. With some but not all, `frank serve` MUST refuse to start and name the missing settings. The issuer and redirect URL MUST be `https://`, except for `localhost`. The organisation MUST exist at startup.

**Implementation:** `crates/frank/src/sso.rs::from_settings`, `crates/frank/src/main.rs`

#### Scenario: No settings

- GIVEN none of the five settings
- WHEN the configuration is read
- THEN SSO is off, every `/v1/sso` route but `GET /v1/sso` answers 404 and session cookies are ignored

**Tests:** `crates/frank/src/sso.rs::none_given_is_off`, `crates/frank/tests/sso.rs::without_settings_sso_is_off_and_cookies_mean_nothing`

#### Scenario: Partial settings

- GIVEN an issuer but no client id and no organisation
- WHEN the configuration is read
- THEN it is refused, naming `FRANK_SSO_CLIENT_ID` and `FRANK_SSO_ORGANISATION`

**Tests:** `crates/frank/src/sso.rs::partial_settings_name_what_is_missing`

#### Scenario: Plain HTTP

- GIVEN an issuer `http://lab271.okta.com`
- WHEN the configuration is read
- THEN it is refused: only `localhost` may be `http://`

**Tests:** `crates/frank/src/sso.rs::http_only_for_localhost`

### Requirement 2: The client secret [MUST]

The client secret MUST be read from the file `FRANK_SSO_CLIENT_SECRET_FILE` names, never from an environment variable or the command line. An empty or unreadable file MUST be refused. The secret MUST NOT appear in a log, an audit line, a response or a `Debug` print.

**Implementation:** `crates/frank/src/sso.rs::from_settings`, `crates/frank/src/sso.rs::expose`

#### Scenario: The secret is never printed

- GIVEN a configuration with a secret
- WHEN it is formatted with `Debug` and `Display`
- THEN the secret's value does not appear

**Tests:** `crates/frank/src/sso.rs::the_secret_is_never_printed`, `crates/frank/src/sso.rs::an_empty_or_missing_secret_file_is_refused`, `crates/frank/tests/sso.rs::the_callback_refuses_a_foreign_state_and_a_wrong_verifier`

### Requirement 3: Authorization code flow with PKCE [MUST]

`GET /v1/sso/login` MUST redirect to the provider's authorize endpoint with `response_type=code`, the client id, the redirect URL, `scope=openid email profile`, a random `state` and `nonce`, and a PKCE S256 challenge. It MUST bind the `state` to the browser in an HttpOnly, SameSite=Lax cookie that lasts ten minutes. The code exchange MUST authenticate the client (`client_secret_basic`) and send the PKCE verifier.

**Implementation:** `crates/frank/src/sso.rs::begin`, `crates/frank/src/sso.rs::finish`

#### Scenario: Login

- GIVEN SSO is on
- WHEN a browser calls `GET /v1/sso/login`
- THEN it is redirected (303) to the authorize endpoint with PKCE S256, `state` and `nonce`
- AND it gets the `frank_sso_state` cookie

**Tests:** `crates/frank/tests/sso.rs::login_sends_the_browser_with_pkce_state_and_nonce`

### Requirement 4: The ID token is checked completely [MUST]

The callback MUST refuse, with a redirect to `/?sso=refused` and an `sso_refused` audit line, unless: the `state` is known, unused, under ten minutes old and equal to the browser's state cookie; the code exchange succeeds; the ID token is RS256 and verifies against the provider's JWKS; `iss` equals the issuer; `aud` contains the client id (and `azp`, if present, equals it); `exp` is in the future; `nonce` equals the one sent; `sub` is present.

**Implementation:** `crates/frank/src/sso.rs::check`, `crates/frank/src/sso.rs::callback`

#### Scenario: A bad token

- GIVEN a login in progress
- WHEN the ID token has another issuer, audience or azp, has expired, has another nonce, has no `sub`, is not RS256, or its signature does not verify
- THEN the callback is refused and no session cookie is set

**Tests:** `crates/frank/tests/sso.rs::the_callback_refuses_every_bad_token`

#### Scenario: A foreign or replayed state, a wrong verifier

- GIVEN a login in progress
- WHEN the callback carries another browser's state cookie, no code, a provider error, a used state, or the token endpoint refuses the verifier
- THEN the callback is refused

**Tests:** `crates/frank/tests/sso.rs::the_callback_refuses_a_foreign_state_and_a_wrong_verifier`, `crates/frank/tests/sso.rs::a_first_sign_in_provisions_the_user_and_starts_a_session`

### Requirement 5: Users provisioned on first sign-in [MUST]

A person MUST be identified by the issuer and `sub`. On first sign-in, a human user whose name is the lower-cased `email` MUST be created in `FRANK_SSO_ORGANISATION` with no role, unless an existing human user has that name and the e-mail is verified, which MUST be linked and keep its organisation and role. A user linked to another identity MUST NOT be linked again. Machine users and disabled users MUST be refused. Each outcome MUST write an audit line (`user_provisioned`, `sso_login`, `sso_refused`).

**Implementation:** `crates/frank/src/store/participants.rs::sign_in`

#### Scenario: First and second sign-in

- GIVEN a new identity
- WHEN it signs in twice
- THEN one human user without a role exists in the default organisation, and one `user_provisioned` line

**Tests:** `crates/frank/src/store/participants.rs::first_sign_in_provisions_a_human_without_a_role`, `crates/frank/tests/sso.rs::a_first_sign_in_provisions_the_user_and_starts_a_session`

#### Scenario: Linking an existing user

- GIVEN a superadmin made on the command line with the person's e-mail as its name
- WHEN the person signs in with a verified e-mail
- THEN the identity is linked and the user keeps its organisation and role; an unverified e-mail or a second identity is refused

**Tests:** `crates/frank/src/store/participants.rs::a_verified_email_links_an_existing_human_and_keeps_its_role`, `crates/frank/src/store/participants.rs::machines_disabled_users_and_bad_names_are_refused`

### Requirement 6: Sessions after the bearer token [MUST]

A session MUST be a random 32-byte value in an HttpOnly, SameSite=Lax cookie (`frank_session`, Secure on https), stored only as its SHA-256, for eight hours. It MUST name the caller only when the request has no `Authorization` header; an unknown or expired session MUST be the public tier. A disabled user's sessions MUST stop working; removing a user MUST delete them.

**Implementation:** `crates/frank/src/api.rs::require`, `crates/frank/src/store/participants.rs::add_session`, `crates/frank/src/store/participants.rs::session_caller`

#### Scenario: The header comes first

- GIVEN a valid session cookie
- WHEN the request also carries an unknown bearer token
- THEN it is refused with 401; with a valid token, the token's user is the caller

**Tests:** `crates/frank/tests/sso.rs::the_authorization_header_comes_before_the_session`, `crates/frank/src/store/participants.rs::sessions_name_their_user_until_they_end`, `crates/frank/src/store/participants.rs::machine_users_get_no_session_and_removal_clears_sso_rows`

### Requirement 7: Cross-site request forgery [MUST]

A `POST`, `PUT`, `PATCH` or `DELETE` that carries the session cookie MUST have an `Origin` equal to the redirect URL's origin (default ports left out), or be refused with 403. Requests without the cookie MUST NOT need one.

**Implementation:** `crates/frank/src/sso.rs::csrf`

#### Scenario: Logout from another site

- GIVEN a signed-in browser
- WHEN `POST /v1/sso/logout` arrives with the cookie and no or another `Origin`
- THEN it is refused with 403 and the session still works; with FRANK's own `Origin` the session ends

**Tests:** `crates/frank/tests/sso.rs::writes_with_a_session_cookie_need_frank_s_origin`, `crates/frank/src/sso.rs::origins_leave_out_default_ports`

### Requirement 8: A local stand-in for the provider [SHOULD]

Development SHOULD use a stub of the provider's OIDC endpoints that runs only through `make up` (unless `SSO=0`) or `SSO=1 scripts/e2e.sh`, is never deployed, and signs with a key made at every start.

**Implementation:** `deploy/podman/sso-stub/stub.py`, `deploy/podman/compose.sso.yaml`

#### Scenario: Sign in and out through the stub

- GIVEN FRANK's image and the stub in FRANK's network
- WHEN a browser signs in through the stub and out again
- THEN every step of requirements 3 to 7 holds against the real HTTP client

**Tests:** `scripts/sso_check.py`, `deploy/podman/sso-stub/test_stub.py::test_the_id_token_verifies_against_the_jwks`

---

## Out of scope

- **SCIM** (provisioning and deprovisioning pushed by the provider): a separate story. Until then a person removed in the provider keeps their FRANK user until an admin disables it.
- **Provider logout**: signing out of FRANK leaves the provider's session.
- **Group mapping**: every new user lands in one organisation; mapping provider groups to organisations or roles is a later story.
