#!/usr/bin/env python3
"""
Specification Coverage Tool

Measures what percentage of the codebase has specification coverage.
"""

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set


@dataclass
class CoverageStats:
    """Coverage statistics for a component."""

    component_name: str
    total_files: int = 0
    spec_files: int = 0
    uncovered_files: List[str] = field(default_factory=list)

    @property
    def coverage_percentage(self) -> float:
        """Calculate coverage percentage."""
        if self.total_files == 0:
            return 0.0
        return (self.spec_files / self.total_files) * 100

    @property
    def is_complete(self) -> bool:
        """Check if component has full coverage."""
        return self.coverage_percentage == 100.0


class SpecCoverageChecker:
    """Checks specification coverage across the codebase."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.specs_dir = project_root / "specs"
        self.src_dir = project_root / "src" / "frank"

    def get_all_spec_names(self) -> Set[str]:
        """Get all specification file names (without .spec.md extension)."""
        spec_names = set()

        for spec_file in self.specs_dir.rglob("*.spec.md"):
            if spec_file.name == "_template.spec.md":
                continue

            # Remove .spec.md extension
            spec_name = spec_file.stem.replace(".spec", "")
            spec_names.add(spec_name)

        return spec_names

    def check_component_coverage(self, component_dir: Path, component_name: str) -> CoverageStats:
        """Check spec coverage for a specific component directory."""
        stats = CoverageStats(component_name=component_name)

        if not component_dir.exists():
            return stats

        # Get all Python files in component (excluding __init__ and private files)
        for py_file in component_dir.rglob("*.py"):
            if py_file.name.startswith("_"):
                continue

            stats.total_files += 1

            # Check if there's a corresponding spec
            file_stem = py_file.stem
            has_spec = self._has_spec(file_stem)

            if has_spec:
                stats.spec_files += 1
            else:
                rel_path = py_file.relative_to(self.project_root)
                stats.uncovered_files.append(str(rel_path))

        return stats

    def _has_spec(self, file_name: str) -> bool:
        """Check if a source file has a corresponding spec."""
        # Check for exact match
        exact_match = (self.specs_dir / "core" / f"{file_name}.spec.md").exists() or \
                      (self.specs_dir / "storage" / f"{file_name}.spec.md").exists() or \
                      (self.specs_dir / "apis" / f"{file_name}.spec.md").exists()

        if exact_match:
            return True

        # Check for partial match (spec name contains file name)
        for spec_file in self.specs_dir.rglob("*.spec.md"):
            if spec_file.name == "_template.spec.md":
                continue

            spec_name = spec_file.stem.replace(".spec", "")

            if file_name in spec_name or spec_name in file_name:
                return True

        return False

    def check_full_coverage(self) -> Dict[str, CoverageStats]:
        """Check spec coverage for all components."""
        coverage = {}

        # Check core components
        core_stats = self.check_component_coverage(
            self.src_dir / "core",
            "Core Data Models"
        )
        coverage["core"] = core_stats

        # Check storage components
        storage_stats = self.check_component_coverage(
            self.src_dir / "storage",
            "Storage Layer"
        )
        coverage["storage"] = storage_stats

        # Check util components
        util_stats = self.check_component_coverage(
            self.src_dir / "util",
            "Utilities"
        )
        coverage["util"] = util_stats

        # Check API components (if exists)
        if (self.src_dir / "apis").exists():
            api_stats = self.check_component_coverage(
                self.src_dir / "apis",
                "APIs"
            )
            coverage["apis"] = api_stats

        return coverage

    def calculate_overall_coverage(self, coverage: Dict[str, CoverageStats]) -> float:
        """Calculate overall spec coverage percentage."""
        total_files = sum(stats.total_files for stats in coverage.values())
        spec_files = sum(stats.spec_files for stats in coverage.values())

        if total_files == 0:
            return 0.0

        return (spec_files / total_files) * 100

    def generate_report(self, coverage: Dict[str, CoverageStats]) -> str:
        """Generate human-readable coverage report."""
        lines = []
        lines.append("=" * 80)
        lines.append("FRANK Specification Coverage Report")
        lines.append("=" * 80)
        lines.append("")

        # Overall coverage
        overall_coverage = self.calculate_overall_coverage(coverage)
        total_files = sum(stats.total_files for stats in coverage.values())
        spec_files = sum(stats.spec_files for stats in coverage.values())

        coverage_icon = "✅" if overall_coverage >= 80 else ("⚠️" if overall_coverage >= 50 else "❌")

        lines.append(f"{coverage_icon} Overall Coverage: {overall_coverage:.1f}%")
        lines.append(f"   Files with Specs: {spec_files}/{total_files}")
        lines.append("")

        # Component-level coverage
        lines.append("-" * 80)
        lines.append("COVERAGE BY COMPONENT")
        lines.append("-" * 80)
        lines.append("")

        # Sort components by coverage (lowest first)
        sorted_components = sorted(coverage.items(), key=lambda x: x[1].coverage_percentage)

        for component_key, stats in sorted_components:
            coverage_pct = stats.coverage_percentage

            if coverage_pct == 100:
                icon = "✅"
            elif coverage_pct >= 80:
                icon = "🟢"
            elif coverage_pct >= 50:
                icon = "🟡"
            else:
                icon = "🔴"

            lines.append(f"{icon} {stats.component_name}: {coverage_pct:.1f}%")
            lines.append(f"   Files: {stats.spec_files}/{stats.total_files} have specs")

            if stats.uncovered_files:
                lines.append(f"   Uncovered Files:")
                for uncovered_file in stats.uncovered_files:
                    lines.append(f"     - {uncovered_file}")

            lines.append("")

        # Recommendations
        lines.append("-" * 80)
        lines.append("RECOMMENDATIONS")
        lines.append("-" * 80)
        lines.append("")

        if overall_coverage >= 80:
            lines.append("✅ Excellent spec coverage! Keep it up.")
        elif overall_coverage >= 50:
            lines.append("⚠️  Good progress, but aim for ≥80% coverage.")
            lines.append("   Focus on components with lowest coverage first.")
        else:
            lines.append("❌ Low spec coverage. Prioritize creating specs for:")

        # Show top 3 components needing specs
        low_coverage_components = [
            (name, stats) for name, stats in sorted_components
            if stats.coverage_percentage < 80 and stats.total_files > 0
        ]

        if low_coverage_components:
            lines.append("")
            lines.append("Priority Components:")
            for i, (name, stats) in enumerate(low_coverage_components[:3], 1):
                lines.append(f"  {i}. {stats.component_name} ({stats.coverage_percentage:.1f}%)")

        lines.append("")

        # Coverage badge
        lines.append("-" * 80)
        lines.append("COVERAGE BADGE")
        lines.append("-" * 80)
        lines.append("")

        badge_color = "brightgreen" if overall_coverage >= 80 else ("yellow" if overall_coverage >= 50 else "red")
        badge_url = f"https://img.shields.io/badge/specs-{overall_coverage:.0f}%25-{badge_color}"

        lines.append(f"Badge URL: {badge_url}")
        lines.append(f"Markdown: ![Spec Coverage]({badge_url})")
        lines.append("")

        # Final summary
        lines.append("=" * 80)
        if overall_coverage >= 80:
            lines.append(f"✅ Excellent specification coverage: {overall_coverage:.1f}%")
        else:
            lines.append(f"Target: 80% | Current: {overall_coverage:.1f}% | Gap: {80-overall_coverage:.1f}%")
        lines.append("=" * 80)

        return "\n".join(lines)

    def generate_json_report(self, coverage: Dict[str, CoverageStats]) -> str:
        """Generate JSON coverage report for CI/CD integration."""
        overall_coverage = self.calculate_overall_coverage(coverage)
        total_files = sum(stats.total_files for stats in coverage.values())
        spec_files = sum(stats.spec_files for stats in coverage.values())

        report = {
            "overall": {
                "coverage_percentage": round(overall_coverage, 2),
                "total_files": total_files,
                "spec_files": spec_files,
                "uncovered_files": total_files - spec_files
            },
            "components": {}
        }

        for component_key, stats in coverage.items():
            report["components"][component_key] = {
                "name": stats.component_name,
                "coverage_percentage": round(stats.coverage_percentage, 2),
                "total_files": stats.total_files,
                "spec_files": stats.spec_files,
                "uncovered_files": stats.uncovered_files
            }

        return json.dumps(report, indent=2)


def main():
    """Main entry point for coverage checking CLI."""
    parser = argparse.ArgumentParser(
        description="Check specification coverage across FRANK codebase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check overall coverage
  python specs/coverage.py

  # Output as JSON for CI/CD
  python specs/coverage.py --json

  # Output to file
  python specs/coverage.py --output coverage.txt

  # Fail CI if below threshold
  python specs/coverage.py --min-coverage 80
        """
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Output report to file (default: stdout)"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )

    parser.add_argument(
        "--min-coverage",
        type=float,
        help="Minimum coverage percentage (exit 1 if below)"
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
    checker = SpecCoverageChecker(project_root)

    # Check coverage
    coverage = checker.check_full_coverage()

    # Generate report
    if args.json:
        report = checker.generate_json_report(coverage)
    else:
        report = checker.generate_report(coverage)

    # Output report
    if args.output:
        args.output.write_text(report, encoding="utf-8")
        print(f"Report written to: {args.output}")
    else:
        print(report)

    # Check minimum coverage threshold
    if args.min_coverage is not None:
        overall_coverage = checker.calculate_overall_coverage(coverage)
        if overall_coverage < args.min_coverage:
            print(f"\n❌ Coverage {overall_coverage:.1f}% is below minimum {args.min_coverage}%")
            exit(1)

    exit(0)


if __name__ == "__main__":
    main()
