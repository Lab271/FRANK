#!/usr/bin/env python3
"""
Specification Traceability Tool

Maps specifications to tests, code implementations, and ADRs to ensure complete coverage.
"""

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Optional


@dataclass
class TraceabilityMatrix:
    """Traceability matrix showing relationships between specs, tests, code, and ADRs."""

    spec_path: Path
    spec_name: str
    test_files: List[Path] = field(default_factory=list)
    source_files: List[Path] = field(default_factory=list)
    adr_refs: List[str] = field(default_factory=list)
    functional_requirements: List[str] = field(default_factory=list)
    implementation_status: Optional[str] = None

    @property
    def has_tests(self) -> bool:
        """Check if spec has associated test files."""
        return len(self.test_files) > 0

    @property
    def has_implementation(self) -> bool:
        """Check if spec has associated source files."""
        return len(self.source_files) > 0

    @property
    def has_documentation(self) -> bool:
        """Check if spec has associated ADRs."""
        return len(self.adr_refs) > 0

    @property
    def is_orphaned(self) -> bool:
        """Check if spec has no tests or implementation."""
        return not self.has_tests and not self.has_implementation

    @property
    def completeness_score(self) -> float:
        """Calculate completeness score (0.0 - 1.0)."""
        score = 0.0

        # 40% for having implementation
        if self.has_implementation:
            score += 0.4

        # 40% for having tests
        if self.has_tests:
            score += 0.4

        # 20% for having documentation
        if self.has_documentation:
            score += 0.2

        return score


class TraceabilityChecker:
    """Checks traceability between specs, tests, code, and ADRs."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.specs_dir = project_root / "openspec"  # Updated to use openspec directory
        self.tests_dir = project_root / "tests"
        self.src_dir = project_root / "src"
        self.docs_dir = project_root / "docs"

    def build_traceability_matrix(self, spec_path: Path) -> TraceabilityMatrix:
        """Build traceability matrix for a single spec."""
        content = spec_path.read_text(encoding="utf-8")

        matrix = TraceabilityMatrix(
            spec_path=spec_path,
            spec_name=spec_path.stem.replace(".spec", "")
        )

        # Extract functional requirements
        matrix.functional_requirements = self._extract_requirements(content)

        # Find test files
        matrix.test_files = self._find_test_files(spec_path, content)

        # Find source files
        matrix.source_files = self._find_source_files(spec_path, content)

        # Extract ADR references
        matrix.adr_refs = self._extract_adr_refs(content)

        # Extract implementation status
        matrix.implementation_status = self._extract_implementation_status(content)

        return matrix

    def _extract_requirements(self, content: str) -> List[str]:
        """Extract functional requirement titles from spec."""
        requirements = []

        # Find functional requirements section
        fr_match = re.search(r'## 2\. Functional Requirements(.*?)(?=## 3\.|\Z)', content, re.DOTALL)
        if not fr_match:
            return requirements

        fr_section = fr_match.group(1)

        # Extract requirement titles
        req_matches = re.findall(r'### Requirement \d+: (.+)', fr_section)
        requirements.extend(req_matches)

        return requirements

    def _find_test_files(self, spec_path: Path, content: str) -> List[Path]:
        """Find test files related to this spec."""
        test_files = []

        # First, check for explicit test file references in spec
        test_refs = re.findall(r'tests/(unit|integration|spikes)/[^\s\)]+\.py', content)
        for test_ref in test_refs:
            test_path = self.project_root / test_ref
            if test_path.exists():
                test_files.append(test_path)

        # Second, infer test files from spec name
        spec_name = spec_path.stem.replace(".spec", "")

        # Try unit tests
        unit_test_patterns = [
            f"test_{spec_name}.py",
            f"test_{spec_name}_*.py",
        ]

        for pattern in unit_test_patterns:
            for test_file in (self.tests_dir / "unit").rglob(pattern):
                if test_file not in test_files:
                    test_files.append(test_file)

        # Try integration tests
        integration_patterns = [
            f"{spec_name}.feature",
            f"*{spec_name}*.feature",
        ]

        for pattern in integration_patterns:
            for feature_file in (self.tests_dir / "integration").rglob(pattern):
                if feature_file not in test_files:
                    test_files.append(feature_file)

        return sorted(set(test_files))

    def _find_source_files(self, spec_path: Path, content: str) -> List[Path]:
        """Find source files implementing this spec."""
        source_files = []

        # First, check for explicit source file references
        src_refs = re.findall(r'src/frank/[^\s\)]+\.py', content)
        for src_ref in src_refs:
            src_path = self.project_root / src_ref
            if src_path.exists():
                source_files.append(src_path)

        # Second, infer source files from spec name and location
        spec_name = spec_path.stem.replace(".spec", "")
        spec_category = spec_path.parent.name

        # Try to find corresponding source file
        if spec_category == "core":
            potential_paths = [
                self.src_dir / "frank" / "core" / f"{spec_name}.py",
                self.src_dir / "frank" / f"{spec_name}.py",
            ]
        elif spec_category == "apis":
            potential_paths = [
                self.src_dir / "frank" / "apis" / f"{spec_name}.py",
                self.src_dir / "frank" / "api" / f"{spec_name}.py",
            ]
        elif spec_category == "storage":
            potential_paths = [
                self.src_dir / "frank" / "storage" / f"{spec_name}.py",
            ]
        else:
            potential_paths = []

        for src_path in potential_paths:
            if src_path.exists() and src_path not in source_files:
                source_files.append(src_path)

        return sorted(set(source_files))

    def _extract_adr_refs(self, content: str) -> List[str]:
        """Extract ADR references from spec."""
        adr_refs = []

        # Find all ADR links
        adr_matches = re.findall(r'\[ADR[-\s](\d+)[^\]]*\]', content)
        for adr_num in adr_matches:
            adr_refs.append(f"ADR-{adr_num}")

        return sorted(set(adr_refs))

    def _extract_implementation_status(self, content: str) -> Optional[str]:
        """Extract implementation status from spec."""
        status_match = re.search(r'\*\*Status:\*\*.*?(DRAFT|REVIEW|APPROVED|IMPLEMENTED|SUPERSEDED)', content)
        if status_match:
            return status_match.group(1)
        return None

    def check_orphaned_code(self) -> List[Path]:
        """Find source files with no corresponding spec."""
        orphaned = []

        # Get all spec files
        spec_files = set()
        for spec_file in self.specs_dir.rglob("*.spec.md"):
            if spec_file.name != "_template.spec.md":
                spec_files.add(spec_file.stem.replace(".spec", ""))

        # Check each source file
        for src_file in (self.src_dir / "frank").rglob("*.py"):
            # Skip __init__ and private files
            if src_file.name.startswith("_"):
                continue

            src_name = src_file.stem

            # Check if there's a corresponding spec
            has_spec = any(src_name in spec_name for spec_name in spec_files)

            if not has_spec:
                orphaned.append(src_file)

        return sorted(orphaned)

    def check_orphaned_tests(self) -> List[Path]:
        """Find test files with no corresponding spec."""
        orphaned = []

        # Get all spec files
        spec_files = set()
        for spec_file in self.specs_dir.rglob("*.spec.md"):
            if spec_file.name != "_template.spec.md":
                spec_files.add(spec_file.stem.replace(".spec", ""))

        # Check unit tests
        for test_file in (self.tests_dir / "unit").rglob("test_*.py"):
            test_name = test_file.stem.replace("test_", "")

            has_spec = any(test_name in spec_name for spec_name in spec_files)

            if not has_spec:
                orphaned.append(test_file)

        return sorted(orphaned)

    def generate_report(self, matrices: List[TraceabilityMatrix]) -> str:
        """Generate traceability report."""
        lines = []
        lines.append("=" * 80)
        lines.append("FRANK Specification Traceability Report")
        lines.append("=" * 80)
        lines.append("")

        # Summary statistics
        total_specs = len(matrices)
        specs_with_tests = sum(1 for m in matrices if m.has_tests)
        specs_with_impl = sum(1 for m in matrices if m.has_implementation)
        specs_with_docs = sum(1 for m in matrices if m.has_documentation)
        orphaned_specs = sum(1 for m in matrices if m.is_orphaned)

        avg_completeness = sum(m.completeness_score for m in matrices) / total_specs if total_specs > 0 else 0.0

        lines.append(f"Total Specifications: {total_specs}")
        lines.append(f"Specs with Tests: {specs_with_tests} ({specs_with_tests/total_specs*100:.1f}%)")
        lines.append(f"Specs with Implementation: {specs_with_impl} ({specs_with_impl/total_specs*100:.1f}%)")
        lines.append(f"Specs with Documentation: {specs_with_docs} ({specs_with_docs/total_specs*100:.1f}%)")
        lines.append(f"Orphaned Specs: {orphaned_specs} ({orphaned_specs/total_specs*100:.1f}%)")
        lines.append(f"Average Completeness: {avg_completeness*100:.1f}%")
        lines.append("")

        # Sort by completeness (least complete first)
        sorted_matrices = sorted(matrices, key=lambda m: m.completeness_score)

        # Detailed traceability
        lines.append("-" * 80)
        lines.append("DETAILED TRACEABILITY MATRIX")
        lines.append("-" * 80)
        lines.append("")

        for matrix in sorted_matrices:
            rel_path = matrix.spec_path.relative_to(self.specs_dir)

            completeness = f"{matrix.completeness_score*100:.0f}%"
            status_icon = "✅" if matrix.completeness_score >= 0.8 else ("⚠️" if matrix.completeness_score >= 0.4 else "❌")

            lines.append(f"{status_icon} {rel_path} ({completeness} complete)")
            lines.append(f"   Status: {matrix.implementation_status or 'UNKNOWN'}")

            if matrix.functional_requirements:
                lines.append(f"   Requirements: {len(matrix.functional_requirements)}")

            if matrix.test_files:
                lines.append(f"   Tests: {len(matrix.test_files)}")
                for test_file in matrix.test_files:
                    rel_test = test_file.relative_to(self.project_root)
                    lines.append(f"     - {rel_test}")
            else:
                lines.append("   Tests: ❌ NONE")

            if matrix.source_files:
                lines.append(f"   Implementation: {len(matrix.source_files)}")
                for src_file in matrix.source_files:
                    rel_src = src_file.relative_to(self.project_root)
                    lines.append(f"     - {rel_src}")
            else:
                lines.append("   Implementation: ❌ NONE")

            if matrix.adr_refs:
                lines.append(f"   ADRs: {', '.join(matrix.adr_refs)}")

            lines.append("")

        # Orphaned code section
        orphaned_code = self.check_orphaned_code()
        if orphaned_code:
            lines.append("-" * 80)
            lines.append("ORPHANED CODE (No Spec)")
            lines.append("-" * 80)
            lines.append("")
            for code_file in orphaned_code:
                rel_path = code_file.relative_to(self.project_root)
                lines.append(f"  ⚠️  {rel_path}")
            lines.append("")

        # Orphaned tests section
        orphaned_tests = self.check_orphaned_tests()
        if orphaned_tests:
            lines.append("-" * 80)
            lines.append("ORPHANED TESTS (No Spec)")
            lines.append("-" * 80)
            lines.append("")
            for test_file in orphaned_tests:
                rel_path = test_file.relative_to(self.project_root)
                lines.append(f"  ⚠️  {rel_path}")
            lines.append("")

        # Final summary
        lines.append("=" * 80)
        if avg_completeness >= 0.8:
            lines.append(f"✅ Excellent traceability! Average completeness: {avg_completeness*100:.1f}%")
        elif avg_completeness >= 0.5:
            lines.append(f"⚠️  Good traceability, but room for improvement: {avg_completeness*100:.1f}%")
        else:
            lines.append(f"❌ Poor traceability. Many specs lack tests or implementation: {avg_completeness*100:.1f}%")
        lines.append("=" * 80)

        return "\n".join(lines)


def main():
    """Main entry point for traceability checking CLI."""
    parser = argparse.ArgumentParser(
        description="Check traceability between specs, tests, code, and ADRs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check traceability for all specs
  python specs/trace.py

  # Check specific directory
  python specs/trace.py --dir specs/core

  # Output report to file
  python specs/trace.py --output traceability.txt

  # Show orphaned code only
  python specs/trace.py --orphaned-only
        """
    )

    parser.add_argument(
        "--dir",
        type=Path,
        help="Directory to check (default: specs/)"
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Output report to file (default: stdout)"
    )

    parser.add_argument(
        "--orphaned-only",
        action="store_true",
        help="Show only orphaned code and tests"
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
    checker = TraceabilityChecker(project_root)

    # Build traceability matrices
    matrices = []

    if args.dir:
        spec_dir = args.dir.resolve()
    else:
        spec_dir = checker.specs_dir

    for spec_file in spec_dir.rglob("*.spec.md"):
        if spec_file.name == "_template.spec.md":
            continue

        matrix = checker.build_traceability_matrix(spec_file)
        matrices.append(matrix)

    # Generate report
    if args.orphaned_only:
        orphaned_code = checker.check_orphaned_code()
        orphaned_tests = checker.check_orphaned_tests()

        lines = []
        lines.append("ORPHANED CODE (No Spec):")
        for code_file in orphaned_code:
            rel_path = code_file.relative_to(project_root)
            lines.append(f"  - {rel_path}")

        lines.append("")
        lines.append("ORPHANED TESTS (No Spec):")
        for test_file in orphaned_tests:
            rel_path = test_file.relative_to(project_root)
            lines.append(f"  - {rel_path}")

        report = "\n".join(lines)
    else:
        report = checker.generate_report(matrices)

    # Output report
    if args.output:
        args.output.write_text(report, encoding="utf-8")
        print(f"Report written to: {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
