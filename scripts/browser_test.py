"""Browser checks of the web UI (spec 030, ADR-022).

Drives FRANK's page in Obscura, a headless browser over the Chrome DevTools
Protocol, from Playwright. `scripts/e2e.sh` with BROWSER=1 starts both and
runs this; on its own:

    OBSCURA_CDP_TOKEN=… uv run --no-project --with playwright==1.64.1 \\
      python scripts/browser_test.py --url http://localhost:8080 --cdp ws://127.0.0.1:9222 \\
      --contributor … --admin …

`--url` is FRANK as the browser sees it (inside Obscura's network). Tokens
are never printed. Each test gets a fresh browser context.

Shown and hidden are checked on the `hidden` property the page sets, not
with Playwright's visibility, which needs layout: Obscura's layout at times
gives a rendered element no size.
"""

import argparse
import json
import os
import re
import threading
import time
import traceback
import uuid

from playwright.sync_api import Page, expect, sync_playwright

TIMEOUT_MS = 10_000
DEADLINE_S = 300  # the whole run, retries included: a stall must not hang CI


def sign_in(page: Page, token: str) -> None:
    """Enter a token in the header and wait until whoami has answered.
    The page's own whoami at startup goes first: then app.js is running and
    its answer is known (#tier, before the token's)."""
    tier = page.locator("#tier")
    expect(tier).not_to_have_text("", timeout=TIMEOUT_MS)
    before = tier.inner_text()
    page.fill("#token", token)
    page.press("#token", "Enter")
    expect(tier).not_to_have_text(before, timeout=TIMEOUT_MS)


def state(page: Page) -> str:
    """What the page shows, for a failure's log line: there is no screenshot
    to look at in CI, and most failures are a tab or a call that did not
    arrive."""
    try:
        return str(page.evaluate("""() => {
            const text = (id) => document.getElementById(id)?.textContent?.trim().slice(0, 120) ?? null;
            const tab = [...document.querySelectorAll("main section")].find((s) => !s.hidden);
            return {
                hash: location.hash, tab: tab?.id ?? null, tier: text("tier"),
                tables: document.querySelectorAll("#adm-users table").length,
                adm_msg: text("adm-msg"), submit_out: text("submit-out"),
                live_status: text("live-status"), theme: document.documentElement.dataset.theme,
            };
        }"""))
    except Exception as e:  # noqa: BLE001 - diagnostics must never mask the failure
        return f"<unreadable: {type(e).__name__}>"


def submission(ioc_type: str, value: str) -> str:
    """A one-sighting JSON submission without a sighting_id."""
    return json.dumps({"submission": {
        "submitter": {"sector": "energy"},
        "hit_target": {"sector": "energy", "organisation_size": "large"},
        "sighting": {
            "sigma_detection": {"rule_id": "sigma-rule-browser-test"},
            "observables": {"network": [{"type": ioc_type, "value": value}]},
        },
    }})


def posts_to_sightings(page: Page) -> list[str]:
    """The URLs of POST /v1/sightings the page makes from now on."""
    seen: list[str] = []
    page.on("request", lambda r: seen.append(r.url)
            if r.method == "POST" and r.url.endswith("/v1/sightings") else None)
    return seen


# --- Requirement 1 ----------------------------------------------------------

def test_unparseable_submission_is_not_sent(page: Page, args) -> None:
    page.goto(f"{args.url}/#submit")
    sign_in(page, args.contributor)
    posts = posts_to_sightings(page)
    page.fill("#submission", "{ this is not a submission")
    page.click("#do-submit")
    expect(page.locator("#submit-out .error")).to_be_attached(timeout=TIMEOUT_MS)
    page.wait_for_timeout(500)
    assert posts == [], f"sent despite the preview error: {posts}"


# --- Requirement 2 ----------------------------------------------------------

def test_same_form_twice_is_a_resend(page: Page, args) -> None:
    page.goto(f"{args.url}/#submit")
    sign_in(page, args.contributor)
    page.fill("#submission", submission("domain", f"resend-{uuid.uuid4().hex[:8]}.example"))
    out = page.locator("#submit-out")
    page.click("#do-submit")
    expect(out).to_contain_text("Stored 1 sighting(s)", timeout=TIMEOUT_MS)
    named = json.loads(page.input_value("#submission"))["submission"]["sighting"]
    assert named.get("sighting_id"), "the form was not given a sighting_id"
    page.click("#do-submit")
    expect(out).to_contain_text("1 already registered (resend)", timeout=TIMEOUT_MS)
    expect(out).to_contain_text(named["sighting_id"])


# --- Requirement 6 ----------------------------------------------------------

def test_rejected_token_falls_back_to_public(page: Page, args) -> None:
    page.goto(f"{args.url}/#stats")
    sign_in(page, "Bearer not-a-frank-token")
    expect(page.locator("#tier")).to_have_text(re.compile(r"^rejected: "), timeout=TIMEOUT_MS)
    assert page.input_value("#token") == "not-a-frank-token", "a pasted 'Bearer ' was kept"
    # Explore dimensions above public are disabled.
    disabled = page.eval_on_selector_all("#ex-group option", "os => os.filter(o => o.disabled).map(o => o.value)")
    assert "rule" in disabled, f"rule is selectable for public: disabled={disabled}"


# --- Requirement 7 ----------------------------------------------------------

def test_admin_tab_needs_a_role(page: Page, args) -> None:
    page.goto(f"{args.url}/#admin")
    sign_in(page, args.contributor)
    expect(page.locator("#stats")).to_have_js_property("hidden", False, timeout=TIMEOUT_MS)
    expect(page.locator("#admin")).to_have_js_property("hidden", True)
    expect(page.locator('nav [data-tab="admin"]')).to_have_js_property("hidden", True)


def test_public_sees_a_short_menu(page: Page, args) -> None:
    page.goto(f"{args.url}/#submit")
    expect(page.locator("#tier")).to_have_text(re.compile(r"^public\b"), timeout=TIMEOUT_MS)
    expect(page.locator("#stats")).to_have_js_property("hidden", False, timeout=TIMEOUT_MS)
    expect(page.locator("#submit")).to_have_js_property("hidden", True)
    shown = page.eval_on_selector_all("nav button", "bs => bs.filter(b => !b.hidden).map(b => b.dataset.tab)")
    assert shown == ["stats", "lookup", "about", "api"], f"public menu: {shown}"


def set_hidden(page: Page, hidden: bool) -> int:
    """Obscura has no CDP call that hides a page; the test sets what the
    page reads (document.hidden, visibilityState) and fires the event.
    Returns the page's count of live polls at that moment."""
    return page.evaluate("""(h) => {
        Object.defineProperty(document, 'hidden', { configurable: true, get: () => h });
        Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => h ? 'hidden' : 'visible' });
        document.dispatchEvent(new Event('visibilitychange'));
        return window.livePolls;
    }""", hidden)


def test_live_view_stops_when_hidden(page: Page, args) -> None:
    # Playwright's fake clock overflows Obscura's stack; the page's 15 s
    # poll is shortened to 300 ms instead, before any of its scripts run.
    # The page counts its own polls, so hiding and counting are one step.
    page.add_init_script("""{
        const real = window.setTimeout;
        window.setTimeout = (fn, ms, ...rest) => real(fn, ms === 15000 ? 300 : ms, ...rest);
        const fetch = window.fetch;
        window.livePolls = 0;
        window.fetch = (url, ...rest) => {
            if (String(url).startsWith("/v1/live?")) window.livePolls++;
            return fetch(url, ...rest);
        };
    }""")
    polls = lambda: page.evaluate("window.livePolls")
    page.goto(f"{args.url}/#live")
    sign_in(page, args.contributor)
    expect(page.locator("#live-status")).to_contain_text("every 15 s", timeout=TIMEOUT_MS)
    page.wait_for_function("window.livePolls >= 3", timeout=TIMEOUT_MS)  # polling
    at_hide = set_hidden(page, True)
    page.wait_for_timeout(1500)
    assert polls() == at_hide, f"polled while hidden: {polls() - at_hide} time(s)"
    set_hidden(page, False)
    # Resumed: one poll on being shown, and the next from the timer again.
    page.wait_for_function("(n) => window.livePolls >= n", arg=at_hide + 2, timeout=TIMEOUT_MS)


# --- Requirement 8 ----------------------------------------------------------

def test_admin_sees_no_superadmin_controls(page: Page, args) -> None:
    page.goto(f"{args.url}/#admin")
    sign_in(page, args.admin)
    expect(page.locator("#tier")).to_contain_text("admin", timeout=TIMEOUT_MS)
    expect(page.locator("#admin")).to_have_js_property("hidden", False, timeout=TIMEOUT_MS)
    expect(page.locator("#adm-users table")).to_be_attached(timeout=TIMEOUT_MS)
    for control in ("#adm-status-ctl", "#adm-orgs-new", "#adm-user-super", "#adm-files-box"):
        expect(page.locator(control)).to_have_js_property("hidden", True)


# --- Requirement 9 ----------------------------------------------------------

def test_markup_ioc_stays_text(page: Page, args) -> None:
    value = f"http://markup-{uuid.uuid4().hex[:8]}.example/<script>window.pwned=1</script><img src=x onerror=window.pwned=2>"
    page.goto(f"{args.url}/#submit")
    sign_in(page, args.contributor)
    page.fill("#submission", submission("url", value))
    page.click("#do-submit")
    expect(page.locator("#submit-out")).to_contain_text("Stored 1 sighting(s)", timeout=TIMEOUT_MS)
    expect(page.locator("#submit-out td", has_text=value)).to_have_count(1)
    # The lookup table and its side pane.
    page.evaluate("location.hash = 'lookup'")
    page.select_option("#ioc-type", "url")
    page.fill("#ioc-value", value)
    page.press("#ioc-value", "Enter")
    expect(page.locator("#lookup-out")).to_contain_text(value, timeout=TIMEOUT_MS)
    expect(page.locator("#pane")).to_contain_text(value, timeout=TIMEOUT_MS)
    for area in ("#submit-out", "#lookup-out", "#pane"):
        n = page.eval_on_selector(area, "a => a.querySelectorAll('script, img').length")
        assert n == 0, f"markup became elements in {area}: {n}"
    assert page.evaluate("window.pwned") is None, "the IoC's markup ran"


# --- Requirement 10 ---------------------------------------------------------

def test_theme_survives_reload(page: Page, args) -> None:
    page.emulate_media(color_scheme="light")
    page.goto(f"{args.url}/#stats")  # a new context: nothing stored yet
    button, html = page.locator("#theme"), page.locator("html")
    expect(button).to_have_text("theme: auto")
    button.click()  # auto -> light
    expect(button).to_have_text("theme: light")
    button.click()  # light -> dark
    expect(button).to_have_text("theme: dark")
    page.reload()
    expect(button).to_have_text("theme: dark")
    expect(html).to_have_attribute("data-theme", "dark")
    button.click()  # dark -> auto
    expect(button).to_have_text("theme: auto")
    expect(html).to_have_attribute("data-theme", "light")
    page.emulate_media(color_scheme="dark")
    expect(html).to_have_attribute("data-theme", "dark")
    page.reload()
    expect(button).to_have_text("theme: auto")
    expect(html).to_have_attribute("data-theme", "dark")


TESTS = [
    test_unparseable_submission_is_not_sent,
    test_same_form_twice_is_a_resend,
    test_rejected_token_falls_back_to_public,
    test_admin_tab_needs_a_role,
    test_public_sees_a_short_menu,
    test_live_view_stops_when_hidden,
    test_admin_sees_no_superadmin_controls,
    test_markup_ioc_stays_text,
    test_theme_survives_reload,
]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--url", required=True, help="FRANK as the browser sees it")
    p.add_argument("--cdp", default="ws://127.0.0.1:9222", help="Obscura's CDP endpoint")
    p.add_argument("--contributor", required=True, help="a contributor's token, no role")
    p.add_argument("--admin", required=True, help="a token of a user with role admin")
    p.add_argument("-k", default="", help="run only tests whose name contains one of these (comma separated)")
    args = p.parse_args()
    cdp_token = os.environ.get("OBSCURA_CDP_TOKEN", "")
    headers = {"Authorization": f"Bearer {cdp_token}"} if cdp_token else {}

    def give_up() -> None:
        print(f"browser: no result after {DEADLINE_S} s; Obscura stalled", flush=True)
        os._exit(1)
    threading.Timer(DEADLINE_S, give_up).start()

    failed = ran = flaky = 0
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(args.cdp, headers=headers)
        for test in (t for t in TESTS if any(k in t.__name__ for k in args.k.split(","))):
            ran += 1
            start = time.monotonic()
            # Twice at most: Obscura is young, and a test that passes on the
            # retry is reported as flaky, not green and not a failure.
            for attempt in (1, 2):
                context = browser.new_context()
                context.set_default_timeout(TIMEOUT_MS)
                page = context.new_page()
                try:
                    test(page, args)
                    took = time.monotonic() - start
                    if attempt == 1:
                        print(f"ok    {test.__name__}  ({took:.1f}s)")
                    else:
                        flaky += 1
                        print(f"FLAKY {test.__name__}: passed on the retry  ({took:.1f}s)")
                    break
                except Exception as e:  # noqa: BLE001 - report every test, then fail
                    if attempt == 1:
                        print(f"retry {test.__name__}: {str(e).strip().splitlines()[0]}", flush=True)
                        print(f"      page: {state(page)}", flush=True)
                        continue
                    failed += 1
                    lines = str(e).strip().splitlines() or [type(e).__name__]
                    where = [f for f in traceback.extract_tb(e.__traceback__) if f.filename == __file__][-1]
                    got = next((x.strip() for x in lines if x.strip().startswith(("Actual", "Received"))), "")
                    print(f"FAIL  {test.__name__}: {lines[0]} {got} (line {where.lineno})")
                    print(f"      page: {state(page)}", flush=True)
                finally:
                    context.close()
        browser.close()
    tail = f", {flaky} flaky (passed on a retry)" if flaky else ""
    print(f"browser: {ran - failed - flaky} passed, {failed} failed{tail}", flush=True)
    os._exit(1 if failed else 0)  # also ends the deadline timer


if __name__ == "__main__":
    main()
