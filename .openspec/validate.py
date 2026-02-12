#!/usr/bin/env python3
"""
Specification Validation Tool

Validates FRANK specification files for completeness, structure, and reference integrity.
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Optional


@dataclass
class ValidationResult:
    """Result of validating a single specification file."""

    spec_path: Path
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Specification is valid if it has no errors."""
        return len(self.errors) == 0

    @property
    def severity_score(self) -> int:
        """Calculate severity score (higher = worse)."""
        return len(self.errors) * 10 + len(self.warnings)


@dataclass
class SpecMetadata:
    """Extracted metadata from a specification."""

    status: Optional[str] = None
    version: Optional[str] = None
    owner: Optional[str] = None
    issue: Optional[str] = None
    related_adrs: List[str] = field(default_factory=list)
    github_pr: Optional[str] = None


class SpecValidator:
    """Validates FRANK specification files."""

    # Support both old and new format status values
    VALID_STATUSES = {
        # Old format
        "DRAFT", "REVIEW", "APPROVED", "IMPLEMENTED", "SUPERSEDED",
        # New OpenSpec format
        "Draft", "Proposed", "Implemented", "Deprecated"
    }

    # Support both old (numbered) and new (unnumbered) section headers
    REQUIRED_SECTIONS_OLD = [
        "## 1. Purpose",
        "## 2. Functional Requirements",
        "## 3. Non-Functional Requirements",
        "## 4. Data Model / API Contract",
        "## 5. Test Coverage Requirements",
        "## 6. Implementation Status",
        "## 7. Evolution Path Across FRANK Stages",
        "## 8. References",
    ]

    REQUIRED_SECTIONS_NEW = [
        "## Overview",
        "## ADDED Requirements",
        "## Non-Functional Requirements",
        "## Data Model",
        "## Test Coverage Requirements",
        "## Implementation Status",
    ]

    OPTIONAL_SECTIONS = [
        "## 9. Open Questions & Decisions Pending",
        "## 10. Appendix: Examples",
        "## Document History",
    ]

    def __init__(self, project_root: Path):
        self.project_root = project_root
        # Support both .openspec and openspec directory names
        if (project_root / ".openspec" / "specs").exists():
            self.specs_dir = project_root / ".openspec" / "specs"
        elif (project_root / "openspec" / "specs").exists():
            self.specs_dir = project_root / "openspec" / "specs"
        else:
            self.specs_dir = project_root / "openspec"  # fallback to old structure
        self.docs_dir = project_root / "docs"
        self.tests_dir = project_root / "tests"
        self.src_dir = project_root / "src"

    def validate_spec(self, spec_path: Path) -> ValidationResult:
        """Validate a single specification file."""
        result = ValidationResult(spec_path=spec_path)

        if not spec_path.exists():
            result.errors.append(f"File not found: {spec_path}")
            return result

        content = spec_path.read_text(encoding="utf-8")

        # Extract metadata
        metadata = self._extract_metadata(content)

        # Run validation checks
        self._check_metadata(metadata, result)
        self._check_required_sections(content, result)
        self._check_references(content, metadata, result)
        self._check_test_coverage(content, result)
        self._check_acceptance_criteria(content, result)

        return result

    def _extract_metadata(self, content: str) -> SpecMetadata:
        """Extract metadata from specification header (supports both old and new OpenSpec formats)."""
        metadata = SpecMetadata()

        # Extract status - support both formats:
        # Old: - **Status:** APPROVED
        # New: **Status:** Implemented
        status_match = re.search(
            r'(?:- )?\*\*Status:\*\*\s*(.+?)(?:\n|$)',
            content,
            re.IGNORECASE | re.MULTILINE
        )
        if status_match:
            status_value = status_match.group(1).strip()
            # Extract just the status word (handles both "APPROVED" and "Implemented")
            status_word_match = re.search(r'\b(DRAFT|REVIEW|APPROVED|IMPLEMENTED|SUPERSEDED|Draft|Proposed|Implemented|Deprecated)\b', status_value, re.IGNORECASE)
            if status_word_match:
                metadata.status = status_word_match.group(1)

        # Extract version - support both formats:
        # Old: - **Version:** 1.0
        # New: **Version:** 1.0.0
        version_match = re.search(r'(?:- )?\*\*Version:\*\*\s*([\d.]+)', content)
        if version_match:
            metadata.version = version_match.group(1)

        # Extract owner - support both formats:
        # Old: - **Owner:** ⭐ Team Name
        # New: **Owner:** FRANK Core Team (in FRANK-Specific Metadata section)
        owner_match = re.search(r'(?:- )?\*\*Owner:\*\*\s*(?:⭐\s*)?(.+?)(?:\n|$)', content)
        if owner_match:
            metadata.owner = owner_match.group(1).strip()

        # Extract issue number (old format only)
        issue_match = re.search(r'- \*\*Issue:\*\* ⭐ #(\d+)', content)
        if issue_match:
            metadata.issue = issue_match.group(1)

        # Extract related ADRs
        adr_matches = re.findall(r'\[ADR[-\s]?(\d+)[^\]]*\]\(([^)]+)\)', content)
        metadata.related_adrs = [adr_path for _, adr_path in adr_matches]

        # Extract GitHub PR
        pr_match = re.search(r'- \*\*GitHub PR:\*\* \[.*?\]\(([^)]+)\)', content)
        if pr_match:
            metadata.github_pr = pr_match.group(1)

        return metadata

    def _check_metadata(self, metadata: SpecMetadata, result: ValidationResult):
        """Check metadata completeness and validity."""
        # Check required fields
        if not metadata.status:
            result.warnings.append("Missing field: Status")
        elif metadata.status not in self.VALID_STATUSES:
            result.warnings.append(f"Non-standard status: '{metadata.status}'. Recommended: {', '.join(sorted(self.VALID_STATUSES))}")

        if not metadata.owner:
            result.warnings.append("Missing field: Owner")
        elif metadata.owner.startswith("[") or "responsible" in metadata.owner.lower():
            result.warnings.append("Owner field appears to be placeholder text")

        # Issue field is optional for new OpenSpec format
        if not metadata.issue:
            result.info.append("No Issue number specified (optional for OpenSpec format)")

        # Check optional fields
        if not metadata.version:
            result.warnings.append("Missing recommended field: Version")

        if metadata.status == "IMPLEMENTED" and not metadata.github_pr:
            result.warnings.append("Implemented spec should have GitHub PR link")

    def _check_required_sections(self, content: str, result: ValidationResult):
        """Check that all required sections are present (supports both old and new formats)."""
        # Check if spec uses old or new format
        uses_old_format = "## 1. Purpose" in content
        uses_new_format = "## Overview" in content

        if not uses_old_format and not uses_new_format:
            result.errors.append("Could not determine spec format (missing both '## 1. Purpose' and '## Overview')")
            return

        # Check appropriate required sections
        required_sections = self.REQUIRED_SECTIONS_OLD if uses_old_format else self.REQUIRED_SECTIONS_NEW
        missing_sections = []

        for section in required_sections:
            if section not in content:
                missing_sections.append(section)

        if missing_sections:
            result.warnings.append(f"Missing {len(missing_sections)} sections: {', '.join(missing_sections[:3])}{'...' if len(missing_sections) > 3 else ''}")

        # Check for purpose/overview content
        if uses_old_format and "## 1. Purpose" in content:
            purpose_section = self._extract_section(content, "## 1. Purpose", "## 2.")
            if len(purpose_section.strip()) < 100:
                result.warnings.append("Purpose section seems too short (< 100 chars)")
        elif uses_new_format and "## Overview" in content:
            overview_section = self._extract_section(content, "## Overview", "## ADDED Requirements")
            if overview_section and len(overview_section.strip()) < 100:
                result.warnings.append("Overview section seems too short (< 100 chars)")

    def _extract_section(self, content: str, start_marker: str, end_marker: str) -> str:
        """Extract content between two section markers."""
        try:
            start_idx = content.index(start_marker) + len(start_marker)
            end_idx = content.index(end_marker, start_idx)
            return content[start_idx:end_idx]
        except ValueError:
            return ""

    def _check_references(self, content: str, metadata: SpecMetadata, result: ValidationResult):
        """Check that all references point to existing files."""
        # Check ADR references
        for adr_path in metadata.related_adrs:
            # Normalize path to project-root-relative format
            normalized_path = adr_path

            # Convert old relative paths (../../.openspec/architecture/decisions/) to project-root relative (.openspec/architecture/decisions/)
            if normalized_path.startswith("../../.openspec/architecture/decisions/"):
                normalized_path = normalized_path.replace("../../.openspec/architecture/decisions/", ".openspec/architecture/decisions/")
            elif normalized_path.startswith("../../"):
                # Strip leading ../../
                normalized_path = normalized_path.replace("../../", "")

            # Remove leading slash if present
            normalized_path = normalized_path.lstrip("/")

            # Resolve full path from project root
            full_path = self.project_root / normalized_path

            if not full_path.exists():
                result.warnings.append(f"ADR reference not found: {adr_path} (looking for: {normalized_path})")

        # Check test file references (improved regex to avoid capturing markdown artifacts)
        # Match: tests/unit/... or tests/integration/... or tests/spikes/...
        # Stop at whitespace, ), ], or backtick
        test_refs = re.findall(r'(tests/(?:unit|integration|spikes)/[^\s\)\]\`]+?\.(?:py|md|feature))', content)
        for test_ref in test_refs:
            # Clean up any trailing punctuation
            test_ref = test_ref.rstrip('.,;:')
            test_path = self.project_root / test_ref
            if not test_path.exists():
                result.warnings.append(f"Test file reference not found: {test_ref}")

        # Check source file references (improved regex)
        src_refs = re.findall(r'(src/frank/[^\s\)\]\`]+?\.py)', content)
        for src_ref in src_refs:
            # Clean up any line number anchors (#L123)
            src_ref_clean = re.sub(r'#L\d+.*$', '', src_ref)
            src_path = self.project_root / src_ref_clean
            if not src_path.exists():
                result.warnings.append(f"Source file reference not found: {src_ref_clean}")

    def _check_test_coverage(self, content: str, result: ValidationResult):
        """Check test coverage requirements are defined."""
        if "## 5. Test Coverage Requirements" not in content:
            return

        test_section = self._extract_section(content, "## 5. Test Coverage Requirements", "## 6.")

        # Check for test types
        test_types = ["Unit Tests", "Integration Tests"]
        for test_type in test_types:
            if test_type not in test_section:
                result.warnings.append(f"Test coverage section missing {test_type} subsection")

        # Check for coverage target
        if "≥85%" not in test_section and ">=85%" not in test_section:
            result.warnings.append("Test coverage target (≥85%) not explicitly mentioned")

        # Check for test location references
        if "tests/unit/" not in test_section and "tests/integration/" not in test_section:
            result.warnings.append("Test coverage section should reference test file locations")

    def _check_acceptance_criteria(self, content: str, result: ValidationResult):
        """Check that functional requirements have acceptance criteria."""
        if "## 2. Functional Requirements" not in content:
            return

        fr_section = self._extract_section(content, "## 2. Functional Requirements", "## 3.")

        # Count requirement subsections
        req_count = len(re.findall(r'### Requirement \d+:', fr_section))

        if req_count == 0:
            result.warnings.append("No functional requirements defined (expected ### Requirement N: format)")

        # Check each requirement has acceptance criteria
        ac_count = len(re.findall(r'\*\*Acceptance Criteria\*\*:', fr_section))

        if req_count > 0 and ac_count < req_count:
            result.warnings.append(f"Some functional requirements missing acceptance criteria ({ac_count}/{req_count} have criteria)")

    def validate_directory(self, spec_dir: Path) -> List[ValidationResult]:
        """Validate all spec files in a directory."""
        results = []

        # Support both *.spec.md and spec.md patterns
        for pattern in ["*.spec.md", "spec.md"]:
            for spec_file in spec_dir.rglob(pattern):
                # Skip template file
                if spec_file.name == "_template.spec.md" or "_template" in str(spec_file):
                    continue

                # Avoid duplicates (some files might match both patterns)
                if not any(r.spec_path == spec_file for r in results):
                    result = self.validate_spec(spec_file)
                    results.append(result)

        return results

    def generate_report(self, results: List[ValidationResult]) -> str:
        """Generate a human-readable validation report."""
        lines = []
        lines.append("=" * 80)
        lines.append("FRANK Specification Validation Report")
        lines.append("=" * 80)
        lines.append("")

        # Summary statistics
        total_specs = len(results)
        valid_specs = sum(1 for r in results if r.is_valid)
        total_errors = sum(len(r.errors) for r in results)
        total_warnings = sum(len(r.warnings) for r in results)

        lines.append(f"Total Specifications: {total_specs}")
        if total_specs > 0:
            lines.append(f"Valid Specifications: {valid_specs} ({valid_specs/total_specs*100:.1f}%)")
        else:
            lines.append(f"Valid Specifications: 0 (0.0%)")
        lines.append(f"Total Errors: {total_errors}")
        lines.append(f"Total Warnings: {total_warnings}")
        lines.append("")

        # Sort results by severity
        sorted_results = sorted(results, key=lambda r: r.severity_score, reverse=True)

        # Detailed results
        for result in sorted_results:
            rel_path = result.spec_path.relative_to(self.specs_dir)

            if result.is_valid:
                status = "✅ VALID"
            else:
                status = "❌ INVALID"

            lines.append("-" * 80)
            lines.append(f"{status}: {rel_path}")
            lines.append("-" * 80)

            if result.errors:
                lines.append("ERRORS:")
                for error in result.errors:
                    lines.append(f"  ❌ {error}")
                lines.append("")

            if result.warnings:
                lines.append("WARNINGS:")
                for warning in result.warnings:
                    lines.append(f"  ⚠️  {warning}")
                lines.append("")

            if result.info:
                lines.append("INFO:")
                for info in result.info:
                    lines.append(f"  ℹ️  {info}")
                lines.append("")

        # Final summary
        lines.append("=" * 80)
        if total_errors == 0:
            lines.append("✅ All specifications are valid!")
        else:
            lines.append(f"❌ Validation failed with {total_errors} error(s)")
        lines.append("=" * 80)

        return "\n".join(lines)


def main():
    """Main entry point for spec validation CLI."""
    parser = argparse.ArgumentParser(
        description="Validate FRANK specification files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate all specs
  python specs/validate.py

  # Validate specific directory
  python specs/validate.py --dir specs/core

  # Validate single file
  python specs/validate.py --file specs/core/observable.spec.md

  # Output report to file
  python specs/validate.py --output report.txt

  # Fail CI if any errors
  python specs/validate.py --strict
        """
    )

    parser.add_argument(
        "--dir",
        type=Path,
        help="Directory to validate (default: specs/)"
    )

    parser.add_argument(
        "--file",
        type=Path,
        help="Single spec file to validate"
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Output report to file (default: stdout)"
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error code if any validation errors found"
    )

    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root directory (default: current directory)"
    )

    args = parser.parse_args()

    # Determine project root
    project_root = args.project_root.resolve()
    validator = SpecValidator(project_root)

    # Validate specs
    if args.file:
        # Validate single file
        results = [validator.validate_spec(args.file.resolve())]
    elif args.dir:
        # Validate directory
        results = validator.validate_directory(args.dir.resolve())
    else:
        # Validate all specs
        results = validator.validate_directory(validator.specs_dir)

    # Generate report
    report = validator.generate_report(results)

    # Output report
    if args.output:
        args.output.write_text(report, encoding="utf-8")
        print(f"Report written to: {args.output}")
    else:
        print(report)

    # Exit with error if strict mode and errors found
    if args.strict:
        total_errors = sum(len(r.errors) for r in results)
        if total_errors > 0:
            sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
