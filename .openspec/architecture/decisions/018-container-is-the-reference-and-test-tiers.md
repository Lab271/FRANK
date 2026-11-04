# ADR-018: The container image is the reference; four test tiers

- **Status:** accepted
- **Date:** 2026-11-03
- **Decision Makers:** Ilja Heitlager
- **Related:** [ADR-005](005-three-layer-testing-strategy.md), [ADR-013](013-testing-philosophy.md) (Phase 2 testing), [ADR-016](016-phase3-rust-on-db-core.md) (three deployments, one image), #201, #208

## Context

FRANK runs three ways (ADR-016, item 8): `frank serve` on a machine (`make run`), the image in podman (`make up`), and the image on a VM in a cloud. Until #208 there was one test tier, `make test`: unit tests and the API tests in `crates/frank/tests/api.rs`, which drive the real router in-process on a few sightings. Nothing tested at volume, nothing tested the image before CI pushed it to `latest`, and nothing checked a running deployment.

#201 shows the cost. An IoC filter on `/v1/sightings` crashed the server once about 1,000 sightings matched; the API tests had 4. It was found by hand, and whether a db-core upgrade fixed it could only be answered by hand too.

FRANK is to become open source, and its deployments (a trial, the Enablement Platform) live in other, private repositories. Those need a check they can run after each deploy without FRANK knowing their URLs or tokens.

## Decision

1. **A local server is the development loop; the container image is the reference.** `make run` and `cargo test` stay, for fast iteration. Anything that claims "it works" (end-to-end checks, CI, every deployment) runs against the image, because the image is what gets deployed.
2. **Four test tiers**, as Makefile targets:

   | Target | What | Against | Writes data |
   |---|---|---|---|
   | `make test` | unit and in-process API tests | nothing running | temp dirs |
   | `make test-slow` | Rust tests marked `#[ignore = "slow"]`: volume and paging | nothing running | temp dirs |
   | `make smoke` | `scripts/smoke.py`, read-only | a running FRANK: `FRANK_URL`, `TOKEN` | never |
   | `make e2e` | `scripts/e2e.sh`: a throwaway container, generated data, `smoke.py --writable` | `127.0.0.1:18080` | yes, then removed |

3. **Smoke checks never write to a server they did not start.** Sightings cannot be deleted, so submitting is behind `--writable`, which only `make e2e` passes. Read-only checks ask `/v1/whoami` for each token's status and check what that status may read and what it may not.
4. **`smoke.py` is Python 3.9 or later, standard library only,** so it runs on macOS's own `python3`, on a CI runner and on a bastion host without a virtual environment. This departs from the house default (Python 3.12 with `uv`) on purpose; `PYTHON=` picks another interpreter, `uv` included.
5. **The end-to-end container runs without Caddy.** TLS, certificates and the HTTP redirect belong to a deployment; `make smoke` checks them there (`TLS=1` for the podman deployment, an `https://` URL for a cloud one).
6. **CI runs `test-slow` in the Rust job and `e2e` on the built image before it is pushed,** so a broken image never becomes `latest`.
7. **Deployment repositories call `smoke.py` from a pinned FRANK tag** with their own URL and token. FRANK holds no environment's details.
8. **The image has no third-party runtime base (#211).**
   - `frank` is a static musl binary on `FROM scratch`, next to `web/` and a minimal `/etc/passwd` for uid 65532. This works because FRANK has no C dependencies and no TLS stack, so it needs no libc, CA certificates or tzdata.
   - The build image is pinned by its multi-arch index digest, and Dependabot's `docker` ecosystem proposes the bumps.
   - The same commit therefore builds the same layers, and nobody else's userland ships with FRANK.

## Consequences

- **Positive:** #201's shape (more than 2,000 sightings on one IoC, filtered and paged) is a repeatable check. Against 0.26.0 `make e2e` reports the server down and prints its `stack overflow`; against 0.28.0 it passes, in about 8 seconds.
- **Positive:** a deployment is checked the same way locally, in CI and in the cloud.
- **Cost:** CI builds the Rust workspace a second time in release mode for `test-slow`, and runs the image once more before pushing it.
- **Cost:** two languages in the tests, Rust and Python. The Python is limited to HTTP checks against a URL; anything that needs FRANK's internals is a Rust test.
- **Cost:** musl's allocator is slower than glibc's under many threads. If that ever shows in `test-slow` or `e2e`, the fix is a Rust allocator such as `mimalloc`, not a return to a distro base image.
- **Limit:** a scratch image has no shell. Debug from the host, with `podman exec` running `frank` itself or with `podman cp`.
- **Limit:** `make smoke` on a production server is read-only, so it cannot show that submitting works there. A deployment that wants that needs a sender whose sightings it accepts as permanent.
