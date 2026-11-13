# ADR-022: Browser tests in Obscura, from Playwright, in `make e2e`

- **Status:** Accepted
- **Date:** 2026-11-12
- **Decision Makers:** Ilja Heitlager
- **Related:** [ADR-018](018-container-is-the-reference-and-test-tiers.md) (test tiers), [ADR-021](021-spec-links-checked-in-ci.md) (spec links), [spec 030](../../specs/030-browser-client/spec.md), #254

## Context

ADR-018's tiers test the server, not the web UI. Eight of the fifteen scenarios of spec 030 live in `web/app.js` and `web/theme.js` (a submission that does not parse is not sent, a resend, a rejected token, the admin tab, the live view, markup in an IoC, the theme), so they stayed `(planned)` and kept `make check-assurance` at 195 of 203.

A browser test needs a browser. Headless Chromium is the usual one: about 150 MB to download, several hundred MB of memory, and its own update cycle. [Obscura](https://github.com/h4ckf0r0day/obscura) is a headless browser written in Rust on V8 that speaks the Chrome DevTools Protocol (CDP), so Playwright drives it as it drives Chromium. It ships as a distroless image that runs as a non-root user.

A probe on 2026-11-12 (Obscura 0.2.6) found what spec 030 needs working: `sessionStorage` and `localStorage` across a reload, `hashchange`, `fetch` with request interception, WebAssembly, `prefers-color-scheme` emulation, and `textContent` keeping markup as text. Two gaps: CDP cannot hide a page (`Page.setWebLifecycleState` is unknown), and Playwright's fake clock overflows its stack.

## Decision

1. **The web UI is tested in Obscura, driven by Playwright for Python over CDP.** The tests are `scripts/browser_test.py`, one function per spec 030 scenario. The spec links them as its tests (ADR-021).
2. **They run inside `make e2e`, with `BROWSER=1`, on the image** (ADR-018: the image is the reference). `scripts/e2e.sh` starts Obscura in the FRANK container's network, so the browser reaches FRANK on `http://localhost:8080`. CDP is published on loopback on the same port inside and out, because Obscura checks the `Host` header. It also sets a random 32-byte `OBSCURA_CDP_TOKEN` per run, which is never printed.
3. **The image is pinned by its index digest,** as the build image is (ADR-018, item 8). Playwright is pinned too (`playwright==1.64.1`). Locally `uv` runs it; CI installs it in a venv.
4. **CI runs the browser tests in the image job,** with the end-to-end checks, before the image is pushed.
5. **What Obscura cannot do, the test does in the page, and says so.** The live view's hidden tab is a `visibilitychange` event with `document.hidden` set. The 15 s poll is shortened to 300 ms by an init script, in place of a fake clock.
6. **Shown and hidden are checked on the `hidden` property the page sets,** not with Playwright's visibility. Visibility needs layout, and Obscura's layout at times gives a rendered element no size; that could also pass a shown control as hidden.
7. **A failing test is run once more, and a failure prints what the page showed** (tab, tier, the message areas). There is no screenshot to look at in CI, and most failures so far were a tab or a call that had not arrived. A test that passes on the retry is reported as `FLAKY`, not as green: the run still says so in its last line, so a browser that needs retries is visible rather than hidden. A test that fails twice fails the run.
8. **A run has a deadline of 300 s,** retries included. A stalled CDP call ends the run with a failure; it does not hang CI.

## Consequences

- **Positive:** spec 030 is tested in full, and `make check-assurance` covers every scenario.
- **Positive:** the browser tier adds an image of about 60 MB compressed and about 10 MB of memory, not a Chromium download. The eight tests take about 11 seconds.
- **Positive:** the first runs found a real ordering bug. `web/theme.js` listened for `DOMContentLoaded` on `window`, and Obscura does not always pass that event on to `window`, so the theme button lost its handler in about a third of page loads. The listener is now on `document`, which is equally correct in every browser.
- **Positive:** they also found a race in `web/app.js`. The page's own `whoami` at startup, sent without a token, could answer after the one for a token just entered, and drop the user back to public. A newer call now supersedes an older one still in flight.
- **Cost:** a third-party browser that is younger than Chromium, at 0.2.x. A test that fails only in Obscura may be Obscura's fault. Running the same script against Chromium (`connect_over_cdp` to a headless Chrome) tells the two apart.
- **Cost:** the first CI runs were flaky where the laptop was not, twice over a window that was long enough locally. Waiting for a condition rather than a fixed time fixed one; the retry covers what is left. If `FLAKY` keeps appearing, the test or Obscura is at fault and the line says which test to look at.
- **Cost:** Python with a dependency (Playwright) in the tests. `smoke.py` stays standard library only (ADR-018, item 4); `browser_test.py` is the one script that needs a virtual environment.
- **Limit:** the hidden tab and the poll interval are simulated in the page, so the tests do not show that a real browser fires `visibilitychange` when a tab is hidden.
- **Limit:** layout, rendering and accessibility are not tested; the tests check behaviour and the DOM.
