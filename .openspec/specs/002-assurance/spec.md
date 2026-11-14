# Assurance Specification

**Domain:** Cross-cutting / quality
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-11-14

**Owner:** Platform Team
- **Related ADR:** [ADR-021](../../architecture/decisions/021-spec-links-checked-in-ci.md), [ADR-023](../../architecture/decisions/023-coverage-and-code-quality-next-to-spec-assurance.md)
- **Issues:** #247, #250, #293, #294
**Implementation:** `scripts/assurance.py`, `scripts/coverage_metrics.py`, `scripts/quality_metrics.py`, `Makefile`
**Tests:** `scripts/test_assurance.py`, `scripts/test_coverage_metrics.py`, `scripts/test_quality_metrics.py`

## Overview

What FRANK needs to know about itself before it is trusted, in three parts, each answered by a measurement that `make assurance` and `make check-assurance` show together:

| Need | Question | Measured by | Stored |
|---|---|---|---|
| **Specs** | Does every requirement point at code that exists, and every scenario at a test that exists? | `scripts/assurance.py`, every run | nothing: read from the tree |
| **Testing** | How much of the code do the tests run? | `make coverage` (cargo llvm-cov) | `target/assurance/coverage.json` |
| **Code** | Is the code small and simple enough to review? | `make quality` (lizard) | `target/assurance/lizard.csv` |

### Philosophy

- **A stale claim is worse than none**: a link to a renamed test counts against coverage, not for it.
- **Measure apart, read together**: coverage runs every test instrumented and takes minutes; the spec check takes a second. Each slow measurement runs on its own and leaves a file; the dashboard reads the files and says how old they are.
- **Show first, gate on request**: a number becomes a gate only when a floor or ceiling is set for it, so a gate is a decision, not a side effect.
- **Leave out what cannot be measured**: a number the tool gets wrong is not shown, rather than shown with a caveat (#298).

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## Requirements

### Requirement 1: Spec links resolve [MUST]

Every `**Implementation:**` and `**Tests:**` link in a spec MUST name a file in the tree; a `path::symbol` link to a `.rs` file MUST name a `fn` in it, to another file a text it contains. A `**Tests:**` link to a `.rs` file MUST name a `#[test]` or `#[tokio::test]` function, other attributes and comments between allowed, not a helper. A link outside the tree is dead. Every relative Markdown link in `.openspec/`, `docs/`, `README.md` and `CONTRIBUTING.md` MUST resolve.

**Implementation:** `scripts/assurance.py::dead_reason`, `scripts/assurance.py::is_rust_test`, `scripts/assurance.py::dead_md_links`

#### Scenario: A Rust symbol must be a function

- GIVEN a link `src/lib.rs::add` and a file that mentions `add` only in a comment
- WHEN the link is checked
- THEN it is dead: `no fn add`

**Tests:** `scripts/test_assurance.py::test_rust_symbol_must_be_a_fn_not_a_substring`, `scripts/test_assurance.py::test_resolves_file_and_rust_fn`

#### Scenario: A missing file or a path outside the tree

- GIVEN a link to a file that does not exist, or to `../` outside the repository
- WHEN the link is checked
- THEN it is dead

**Tests:** `scripts/test_assurance.py::test_missing_file`, `scripts/test_assurance.py::test_path_outside_the_tree_is_dead`

#### Scenario: A helper is not a test

- GIVEN a `**Tests:**` link to `tests/api.rs::harness`, a fn without `#[test]`
- WHEN the link is checked
- THEN it is dead: `fn harness is not a test`, and the scenario counts against the tested total; a test under `#[ignore]`, on tokio, or behind a comment resolves

**Tests:** `scripts/test_assurance.py::test_a_tests_link_must_name_a_test_fn`, `scripts/test_assurance.py::test_a_helper_linked_as_a_test_counts_against_coverage`

#### Scenario: A dead Markdown link

- GIVEN a document under `docs/` linking to a file that does not exist
- WHEN the tree is collected
- THEN the link is reported

**Tests:** `scripts/test_assurance.py::test_dead_markdown_link_is_reported`

### Requirement 2: Specs are scored per requirement and scenario [MUST]

A requirement SHALL count as implemented when it has implementation links and all resolve. A scenario SHALL count as tested when one of its test links resolves; each dead link MUST subtract one tested scenario. A link marked `(planned)` MUST count as neither.

**Implementation:** `scripts/assurance.py::parse_spec`, `scripts/assurance.py::tested`

#### Scenario: Planned work is not counted

- GIVEN a requirement whose implementation and test are `(planned)`
- WHEN the spec is scored
- THEN it is neither implemented nor tested

**Tests:** `scripts/test_assurance.py::test_scores_scenarios_and_skips_planned`

#### Scenario: A dead link is a false claim

- GIVEN a scenario whose only test link is dead, or a requirement with a dead implementation link
- WHEN the spec is scored
- THEN the scenario counts against the tested total, and the requirement is not implemented

**Tests:** `scripts/test_assurance.py::test_dead_test_link_counts_against_coverage`, `scripts/test_assurance.py::test_dead_implementation_link_means_not_implemented`

### Requirement 3: Spec numbers and outdated specs [MUST]

Two spec folders MUST NOT share a number, outdated ones included. A spec whose `**Status:**` starts with `Outdated` SHALL be skipped and listed as such.

**Implementation:** `scripts/assurance.py::duplicate_numbers`, `scripts/assurance.py::outdated`

#### Scenario: Outdated spec

- GIVEN a spec with `**Status:** Outdated`
- WHEN the tree is collected
- THEN it is not scored and is listed as outdated

**Tests:** `scripts/test_assurance.py::test_outdated_spec_is_skipped`

#### Scenario: Duplicate number

- GIVEN `005-a` and `005-b`
- WHEN the numbers are checked
- THEN 005 is reported as used twice

**Tests:** `scripts/test_assurance.py::test_duplicate_spec_numbers_are_found`

### Requirement 4: The spec gate [MUST]

`make check-assurance` MUST first run the checker's own tests, then fail on a dead link, a duplicate spec number, tested scenarios below `ASSURANCE_MIN`, or a version that disagrees between `Cargo.toml`, both `Cargo.lock`, the README and the CHANGELOG (`scripts/version.py`, `make version`). The spec box SHALL show the version, or the places that disagree. CI MUST run it.

**Implementation:** `Makefile::check-assurance:`, `scripts/assurance.py::main`, `scripts/assurance.py::report`, `scripts/version.py::drift`

#### Scenario: Below the floor

- GIVEN the tree's tested share
- WHEN the floor is above it
- THEN the check fails and says `FAIL: tested`

**Tests:** `scripts/test_assurance.py::test_tested_scenarios_below_the_floor_fail`

#### Scenario: The version disagrees

- GIVEN the README at another version than `Cargo.toml`
- WHEN the gate runs
- THEN the box shows the version with "1 place disagrees", the place is listed as `VERSION DRIFT`, and the check fails; when all places agree, the box shows the version "in all 5 places"

**Tests:** `scripts/test_assurance.py::test_the_version_row_shows_agreement_or_drift`, `scripts/test_assurance.py::test_version_drift_fails_the_spec_gate`

### Requirement 5: Test coverage is measured on its own [MUST]

`make coverage` MUST run the workspace's tests under `cargo llvm-cov` and write its JSON summary to `target/assurance/coverage.json`. The reader MUST take lines, functions and regions from its totals and the line coverage per file, file names relative to the repository, and MUST refuse a file that is not an llvm-cov export.

**Implementation:** `Makefile::coverage:`, `scripts/coverage_metrics.py::read`

#### Scenario: Totals and files

- GIVEN an llvm-cov export with absolute file names under the repository
- WHEN it is read
- THEN the totals are (covered, count) per kind and the files are relative

**Tests:** `scripts/test_coverage_metrics.py::test_totals_and_files_relative_to_the_root`, `scripts/test_coverage_metrics.py::test_a_file_outside_the_root_keeps_its_path`

#### Scenario: Not an export

- GIVEN another JSON document
- WHEN it is read
- THEN it is refused with a pointer to `make coverage`

**Tests:** `scripts/test_coverage_metrics.py::test_another_json_is_refused`

### Requirement 6: Coverage in the dashboard [MUST]

The dashboard MUST show a coverage box after the spec box: lines, functions and regions covered, how long ago they were measured, and the least-covered files. Without the file it MUST say `not measured (make coverage)` and not fail.

**Implementation:** `scripts/assurance.py::report_coverage`, `scripts/coverage_metrics.py::least_covered`

#### Scenario: Least covered

- GIVEN files with different shares of lines covered, one without lines
- WHEN the least covered are picked
- THEN the lowest share comes first and the file without lines is left out

**Tests:** `scripts/test_coverage_metrics.py::test_lowest_share_first_and_files_without_lines_left_out`

#### Scenario: Measured or not

- GIVEN a coverage file, or none
- WHEN the dashboard runs without gates
- THEN it shows the box, or `not measured`, and passes

**Tests:** `scripts/test_assurance.py::test_measured_without_gates_passes_and_shows_both`, `scripts/test_assurance.py::test_not_measured_is_shown_not_failed`

### Requirement 7: The coverage gate [SHOULD]

With `COVERAGE_MIN` set, `make check-assurance` SHOULD fail when lines covered fall below it or coverage was not measured.

**Implementation:** `Makefile::COVERAGE_MIN`, `scripts/assurance.py::main`

#### Scenario: Below the minimum, or not measured

- GIVEN 80% of lines covered
- WHEN the minimum is 0.8, 0.9, or the file is missing
- THEN the check passes, fails, and fails

**Tests:** `scripts/test_assurance.py::test_coverage_below_the_minimum_fails`, `scripts/test_assurance.py::test_a_gate_without_its_measurement_fails`

### Requirement 8: Code quality is measured on its own [MUST]

`make quality` MUST run a pinned lizard over the Rust sources (`crates/*/src`, not the tests) and write its CSV to `target/assurance/lizard.csv`. The reader MUST take per function the file, name, CCN and length, and MUST refuse a CSV with other columns. Fan-in, fan-out and the parameter count MUST NOT be read: lizard gets them wrong for Rust (fan-in matches any token with a function's name; a tuple pattern counts each name as a parameter).

**Implementation:** `Makefile::quality:`, `scripts/quality_metrics.py::read`

#### Scenario: Signatures with commas

- GIVEN a row whose quoted signature holds commas
- WHEN the CSV is read
- THEN the row's fields are in place

**Tests:** `scripts/test_quality_metrics.py::test_rows_with_commas_in_the_signature`

#### Scenario: Other columns

- GIVEN a CSV written with `-Eio`, three columns more
- WHEN it is read
- THEN it is refused with a pointer to `make quality`

**Tests:** `scripts/test_quality_metrics.py::test_a_csv_with_other_columns_is_refused`

### Requirement 9: Code quality in the dashboard [MUST]

The dashboard MUST show a code-quality box: the number of functions and files, average and maximum CCN, the functions over the CCN and length limits and the longest file, with how long ago it was measured; then the highest CCN, the longest functions and the longest files. File lengths come from the files on disk; a file gone since is left out. Without the CSV it MUST say `not measured (make quality)` and not fail.

**Implementation:** `scripts/assurance.py::report_quality`, `scripts/quality_metrics.py::summary`, `scripts/quality_metrics.py::file_lengths`

#### Scenario: Over the limits, worst first

- GIVEN functions of CCN 2, 20 and 1, one 95 lines long, and two files
- WHEN they are summarised with limits 15 and 80
- THEN the CCN 20 function is over both, the lists are worst first, and the longer file comes first

**Tests:** `scripts/test_quality_metrics.py::test_over_the_limits_and_the_worst_first`, `scripts/test_quality_metrics.py::test_nothing_scanned`

#### Scenario: File lengths

- GIVEN two scanned files, one since removed
- WHEN their lengths are taken
- THEN the remaining file has its line count and the removed one is left out

**Tests:** `scripts/test_quality_metrics.py::test_file_lengths_from_disk_and_a_gone_file_left_out`

### Requirement 10: The quality gate [SHOULD]

With `CCN_MAX` set, `make check-assurance` SHOULD fail when a function's CCN is above it, naming each such function, or when quality was not measured. A measurement file that cannot be read MUST fail the check.

With a baseline (`CCN_BASELINE`, `.openspec/quality-baseline.csv`: file, function, CCN), a listed function MAY stay over `CCN_MAX` up to its recorded CCN; a function over it and not listed, one above its recorded CCN, and a listed one now at or under `CCN_MAX` or gone MUST fail, so the list only shrinks. A name that repeats in a file (a `new` per `impl` block) MUST count at its highest CCN. `make quality-baseline` SHALL rewrite the baseline from the current code. CI runs the gate with `CCN_MAX=15` (#301).

**Implementation:** `Makefile::CCN_MAX`, `Makefile::quality-baseline:`, `scripts/assurance.py::main`, `scripts/assurance.py::ccn_problems`, `scripts/quality_metrics.py::ratchet`, `scripts/quality_metrics.py::write_baseline`, `scripts/quality_metrics.py::read_baseline`

#### Scenario: Over the maximum

- GIVEN a function of CCN 20
- WHEN the maximum is 20, or 19
- THEN the check passes, or fails with `OVER CCN 20` and the function's name

**Tests:** `scripts/test_assurance.py::test_a_function_over_ccn_max_fails_and_is_named`

#### Scenario: The baseline only shrinks

- GIVEN a baseline that lists `big` at CCN 20
- WHEN `big` is at 20, at 17, or at 21; a new function is at 16; or a listed function is fixed or removed
- THEN the check passes, passes, fails with `GREW CCN`; fails with `OVER CCN … (not in the baseline)`; or fails with `STALE`

**Tests:** `scripts/test_quality_metrics.py::test_the_same_code_passes`, `scripts/test_quality_metrics.py::test_new_grew_and_stale`, `scripts/test_quality_metrics.py::test_better_but_still_over_passes`, `scripts/test_assurance.py::test_the_ccn_baseline_allows_what_it_lists`

#### Scenario: A name that repeats

- GIVEN two functions `new` in one file, at CCN 16 and 3
- WHEN the baseline is written and checked
- THEN it lists `new` once, at 16, and the same code passes

**Tests:** `scripts/test_quality_metrics.py::test_a_repeated_name_counts_at_its_worst`, `scripts/test_quality_metrics.py::test_written_and_read_back`

#### Scenario: Unreadable

- GIVEN a CSV with three columns
- WHEN the dashboard runs
- THEN it fails with `UNREADABLE`

**Tests:** `scripts/test_assurance.py::test_an_unreadable_measurement_fails`

### Requirement 11: MC/DC obligations are a committed snapshot [MUST]

`make mcdc-obligations` MUST write every decision of `crates/*/src` to `tests/mcdc/obligations.json` with `cargo-mvl-mcdc scan` (ADR-025), and `make check-mcdc-fresh` MUST fail when the snapshot differs from a fresh scan. A tagged test MUST name a decision of the snapshot, and no id MAY belong to two files.

**Implementation:** `Makefile::mcdc-obligations:`, `Makefile::check-mcdc-fresh:`, `crates/frank/tests/mcdc_discharge.rs`

#### Scenario: A tag whose decision is gone

- GIVEN a test named `mcdc__<id>__v<N>_<what>`
- WHEN its id is not in the snapshot
- THEN the discharge test fails and names the file

**Tests:** `crates/frank/tests/mcdc_discharge.rs::every_tagged_test_names_a_decision_in_the_snapshot`, `crates/frank/tests/mcdc_discharge.rs::a_tagged_name_yields_its_id`

#### Scenario: One id in two files

- GIVEN the snapshot
- WHEN two files have a decision with the same id
- THEN the discharge test fails and names both

**Tests:** `crates/frank/tests/mcdc_discharge.rs::no_decision_id_is_shared_by_two_files`

### Requirement 12: Every decision of two or more conditions is covered [MUST]

`make test-mcdc` MUST run the `mcdc__` tests through `cargo-mvl-mcdc harvest` into `target/assurance/mcdc.json` and fail while a decision of two or more conditions lacks a passing test for one of its vectors. Decisions of one condition and exhaustive matches are not counted.

**Implementation:** `Makefile::test-mcdc:`, `scripts/mcdc_metrics.py::main`, `scripts/mcdc_metrics.py::summary`, `scripts/mcdc_metrics.py::missing`

#### Scenario: What counts

- GIVEN decisions of two and three conditions, one of one condition and an exhaustive match
- WHEN the harvest is summarised
- THEN only the first two count, and the one with a vector open is listed

**Tests:** `scripts/test_mcdc_metrics.py::test_only_decisions_of_two_or_more_conditions_count`

#### Scenario: Open or covered

- GIVEN a decision with a vector without a passing test
- WHEN `test-mcdc` reports
- THEN it fails, names the decision and, verbose, the test to add or fix; with every vector covered it passes

**Tests:** `scripts/test_mcdc_metrics.py::test_an_open_decision_fails_and_is_named`, `scripts/test_mcdc_metrics.py::test_missing_names_each_vector_without_a_passing_test_and_each_failing_test`, `scripts/test_mcdc_metrics.py::test_all_covered_passes`

#### Scenario: Not a harvest

- GIVEN another JSON document
- WHEN it is read
- THEN it is refused with a pointer to `make test-mcdc`

**Tests:** `scripts/test_mcdc_metrics.py::test_another_json_is_refused`

### Requirement 13: MC/DC in the dashboard [SHOULD]

The dashboard SHOULD show a MC/DC box after the quality box: decisions of two or more conditions covered, the first open ones, and how long ago it was measured; `not measured (make test-mcdc)` without the file. With `MCDC_MIN` set, `make check-assurance` SHOULD fail below it or when MC/DC was not measured.

**Implementation:** `scripts/assurance.py::report_mcdc`, `Makefile::MCDC_MIN`, `scripts/assurance.py::main`

#### Scenario: Shown with its open decisions

- GIVEN one decision covered and one open
- WHEN the dashboard runs
- THEN the box shows the open one only

**Tests:** `scripts/test_assurance.py::test_mcdc_is_shown_with_its_open_decisions`, `scripts/test_assurance.py::test_not_measured_is_shown_not_failed`

#### Scenario: Below the minimum, or not measured

- GIVEN half the decisions covered
- WHEN the minimum is 0.5, 1.0, or the file is missing
- THEN the check passes, fails, and fails

**Tests:** `scripts/test_assurance.py::test_mcdc_below_the_minimum_fails`
