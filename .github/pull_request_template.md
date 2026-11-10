## Description

<!-- What changes and why -->

## Related Issues

Closes #

## Checklist

- [ ] `make test` and `make lint` pass (fmt, clippy native and wasm32, qualified-subset gate)
- [ ] `make test-slow` / `make e2e` run, if storage, paging or the image changed (ADR-018)
- [ ] Spec updated: requirements and scenarios in `.openspec/specs/`, with `**Implementation:**` and `**Tests:**` links to the code and tests
- [ ] `make check-assurance` passes (no dead spec links)
- [ ] ADR added or marked superseded, if this changes a decision; `decisions/index.md` updated
- [ ] README and `docs/openapi.yaml` updated, if users or API callers see the change
- [ ] CHANGELOG.md and version updated (`feat`: minor, `fix`: patch)

## Test plan

<!-- Commands run and what they showed -->

## Reviewer notes

<!-- Anything to look at in particular -->
