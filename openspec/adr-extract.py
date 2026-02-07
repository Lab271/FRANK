#!/usr/bin/env python3
"""
ADR Extraction Tool

Extracts architectural decisions from change proposal design.md files and generates
ADR drafts with bidirectional links to specifications.
"""

import argparse
import re
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional


class ADRExtractor:
    """Extract ADRs from change proposal design documents."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.specs_dir = project_root / "specs"
        self.adr_dir = project_root / "docs" / "adr"
        self.adr_template = self.adr_dir / "0000-template.md"

    def find_next_adr_number(self) -> int:
        """Find the next available ADR number."""
        existing_adrs = [
            int(adr.stem.split("-")[0])
            for adr in self.adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md")
            if adr.stem != "0000-template"
        ]

        if not existing_adrs:
            return 1

        return max(existing_adrs) + 1

    def extract_from_design(self, design_path: Path) -> Dict[str, any]:
        """Extract ADR-relevant content from design.md file."""
        if not design_path.exists():
            raise FileNotFoundError(f"Design file not found: {design_path}")

        content = design_path.read_text(encoding="utf-8")

        # Extract title from proposal directory name
        proposal_dir = design_path.parent
        proposal_id = proposal_dir.name

        # Try to extract title from design.md
        title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).replace("Design Document:", "").strip()
        else:
            title = proposal_id.replace("-", " ").title()

        # Extract context/problem (from proposal.md if available)
        proposal_path = proposal_dir / "proposal.md"
        context = ""
        if proposal_path.exists():
            proposal_content = proposal_path.read_text(encoding="utf-8")

            # Extract "Problem Statement" section
            problem_match = re.search(
                r'## Problem Statement\n+(.*?)(?=\n##|\Z)',
                proposal_content,
                re.DOTALL
            )
            if problem_match:
                context = problem_match.group(1).strip()

        # Extract alternatives from design.md
        alternatives = self._extract_alternatives(content)

        # Extract chosen solution
        chosen_solution = self._extract_chosen_solution(content, alternatives)

        # Extract consequences
        consequences = self._extract_consequences(content)

        return {
            "title": title,
            "proposal_id": proposal_id,
            "context": context,
            "alternatives": alternatives,
            "chosen_solution": chosen_solution,
            "consequences": consequences,
            "proposal_path": proposal_path,
            "design_path": design_path,
        }

    def _extract_alternatives(self, content: str) -> List[Dict[str, str]]:
        """Extract alternative solutions from design.md."""
        alternatives = []

        # Look for sections like "## Alternative 1:", "## Alternative 2:", etc.
        alt_pattern = r'## Alternative (\d+): (.+?)\n+(.*?)(?=## Alternative|\Z)'
        matches = re.finditer(alt_pattern, content, re.DOTALL)

        for match in matches:
            alt_num = match.group(1)
            alt_title = match.group(2).strip()
            alt_content = match.group(3).strip()

            # Extract pros/cons
            pros = []
            cons = []

            # Look for "Pros:" or "**Pros**:" section
            pros_match = re.search(r'\*\*Pros\*\*:\s*\n+(.*?)(?=\n\*\*Cons\*\*:|\Z)', alt_content, re.DOTALL)
            if pros_match:
                pros_text = pros_match.group(1)
                pros = [p.strip("- ").strip() for p in pros_text.split("\n") if p.strip().startswith("-")]

            # Look for "Cons:" or "**Cons**:" section
            cons_match = re.search(r'\*\*Cons\*\*:\s*\n+(.*?)(?=\n\*\*|\Z)', alt_content, re.DOTALL)
            if cons_match:
                cons_text = cons_match.group(1)
                cons = [c.strip("- ").strip() for c in cons_text.split("\n") if c.strip().startswith("-")]

            # Look for decision status (rejected, accepted, etc.)
            decision_match = re.search(r'\*\*Decision\*\*: (.+)', alt_content)
            decision = decision_match.group(1).strip() if decision_match else None

            alternatives.append({
                "number": alt_num,
                "title": alt_title,
                "description": alt_content[:200],  # First 200 chars
                "pros": pros,
                "cons": cons,
                "decision": decision,
            })

        return alternatives

    def _extract_chosen_solution(self, content: str, alternatives: List[Dict]) -> Optional[str]:
        """Identify the chosen solution from alternatives."""
        # Look for "Decision: ✅ Accepted" or similar
        for alt in alternatives:
            if alt.get("decision") and ("accept" in alt["decision"].lower() or "✅" in alt["decision"]):
                return alt["title"]

        # If no explicit acceptance, check for patterns in main design doc
        chosen_match = re.search(r'## Chosen Solution\n+(.+?)(?=\n##|\Z)', content, re.DOTALL)
        if chosen_match:
            return chosen_match.group(1).strip()[:100]

        return None

    def _extract_consequences(self, content: str) -> Dict[str, List[str]]:
        """Extract consequences (positive and negative) from design.md."""
        consequences = {"positive": [], "negative": []}

        # Look for consequences in ADR if it exists
        adr_match = re.search(
            r'## Consequences\n+### Positive\n+(.*?)(?=### Negative|\Z)',
            content,
            re.DOTALL
        )
        if adr_match:
            pos_text = adr_match.group(1)
            consequences["positive"] = [
                p.strip("- ").strip()
                for p in pos_text.split("\n")
                if p.strip().startswith("-") or p.strip().startswith("*")
            ]

        neg_match = re.search(
            r'### Negative\n+(.*?)(?=\n##|\Z)',
            content,
            re.DOTALL
        )
        if neg_match:
            neg_text = neg_match.group(1)
            consequences["negative"] = [
                n.strip("- ").strip()
                for n in neg_text.split("\n")
                if n.strip().startswith("-") or n.strip().startswith("*")
            ]

        return consequences

    def generate_adr(
        self,
        extracted_data: Dict,
        adr_number: Optional[int] = None,
        author: str = "Architecture Team"
    ) -> str:
        """Generate ADR markdown from extracted data."""
        if adr_number is None:
            adr_number = self.find_next_adr_number()

        adr_num_str = f"{adr_number:04d}"
        title = extracted_data["title"]
        proposal_id = extracted_data["proposal_id"]

        # Generate ADR slug
        adr_slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')

        lines = []
        lines.append(f"# ADR-{adr_num_str}: {title}")
        lines.append("")
        lines.append(f"- **Status:** Proposed")
        lines.append(f"- **Date:** {date.today().isoformat()}")
        lines.append(f"- **Decision Makers:** {author}")
        lines.append(f"- **Related:** [Change Proposal {proposal_id}](../../specs/changes/{proposal_id}/proposal.md)")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Context
        lines.append("## Context and Problem Statement")
        lines.append("")
        if extracted_data["context"]:
            lines.append(extracted_data["context"])
        else:
            lines.append(f"See [Change Proposal {proposal_id}](../../specs/changes/{proposal_id}/proposal.md) for full context.")
        lines.append("")

        # Decision Drivers (if available)
        lines.append("## Decision Drivers")
        lines.append("")
        lines.append("- [To be extracted from proposal]")
        lines.append("")

        # Considered Options
        lines.append("## Considered Options")
        lines.append("")
        for alt in extracted_data["alternatives"]:
            lines.append(f"- {alt['title']}")
        if not extracted_data["alternatives"]:
            lines.append("- [option 1]")
            lines.append("- [option 2]")
        lines.append("")

        # Decision Outcome
        lines.append("## Decision Outcome")
        lines.append("")
        if extracted_data["chosen_solution"]:
            lines.append(f'Chosen option: "{extracted_data["chosen_solution"]}", because [justification].')
        else:
            lines.append('Chosen option: "[option 1]", because [justification].')
        lines.append("")

        # Consequences
        lines.append("### Positive Consequences")
        lines.append("")
        if extracted_data["consequences"]["positive"]:
            for pos in extracted_data["consequences"]["positive"]:
                lines.append(f"- {pos}")
        else:
            lines.append("- [positive consequence]")
        lines.append("")

        lines.append("### Negative Consequences")
        lines.append("")
        if extracted_data["consequences"]["negative"]:
            for neg in extracted_data["consequences"]["negative"]:
                lines.append(f"- {neg}")
        else:
            lines.append("- [negative consequence]")
        lines.append("")

        # Pros and Cons of Options
        lines.append("## Pros and Cons of the Options")
        lines.append("")

        for alt in extracted_data["alternatives"]:
            lines.append(f"### {alt['title']}")
            lines.append("")
            if alt.get("description"):
                lines.append(alt["description"][:200] + "...")
                lines.append("")

            if alt["pros"]:
                for pro in alt["pros"]:
                    lines.append(f"- Good, because {pro}")

            if alt["cons"]:
                for con in alt["cons"]:
                    lines.append(f"- Bad, because {con}")

            if not alt["pros"] and not alt["cons"]:
                lines.append("- Good, because [argument]")
                lines.append("- Bad, because [argument]")

            lines.append("")

        # Related Specifications
        lines.append("## Related Specifications")
        lines.append("")
        lines.append(f"- **Originating Spec**: [Change Proposal {proposal_id}](../../specs/changes/{proposal_id}/proposal.md)")
        lines.append(f"- **Design Document**: [Design Doc](../../specs/changes/{proposal_id}/design.md)")
        lines.append("- **Implementing Specs**: [To be added after implementation]")
        lines.append("")

        # References
        lines.append("## References")
        lines.append("")
        lines.append(f"- [Change Proposal {proposal_id}](../../specs/changes/{proposal_id}/)")
        lines.append(f"- [Design Document](../../specs/changes/{proposal_id}/design.md)")
        if extracted_data.get("proposal_path") and extracted_data["proposal_path"].exists():
            lines.append(f"- [Proposal Document](../../specs/changes/{proposal_id}/proposal.md)")
        lines.append("")

        return "\n".join(lines)

    def create_adr_file(
        self,
        extracted_data: Dict,
        adr_number: Optional[int] = None,
        author: str = "Architecture Team",
        dry_run: bool = False
    ) -> Path:
        """Create ADR file from extracted data."""
        if adr_number is None:
            adr_number = self.find_next_adr_number()

        adr_content = self.generate_adr(extracted_data, adr_number, author)

        # Generate filename
        title = extracted_data["title"]
        adr_slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        adr_filename = f"{adr_number:04d}-{adr_slug}.md"
        adr_path = self.adr_dir / adr_filename

        if dry_run:
            print("=" * 80)
            print(f"DRY RUN: Would create {adr_path}")
            print("=" * 80)
            print(adr_content)
            print("=" * 80)
            return adr_path

        # Create ADR file
        adr_path.write_text(adr_content, encoding="utf-8")
        print(f"✅ Created ADR: {adr_path}")

        return adr_path


def main():
    """Main entry point for ADR extraction CLI."""
    parser = argparse.ArgumentParser(
        description="Extract ADR from change proposal design document",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract ADR from change proposal
  python specs/adr-extract.py specs/changes/001-background-tasks/design.md

  # Specify ADR number
  python specs/adr-extract.py specs/changes/001-background-tasks/design.md --number 15

  # Dry run (preview without creating file)
  python specs/adr-extract.py specs/changes/001-background-tasks/design.md --dry-run

  # Specify author
  python specs/adr-extract.py specs/changes/001-background-tasks/design.md --author "Backend Team"
        """
    )

    parser.add_argument(
        "design_file",
        type=Path,
        help="Path to design.md file in change proposal"
    )

    parser.add_argument(
        "--number",
        type=int,
        help="ADR number (default: auto-increment)"
    )

    parser.add_argument(
        "--author",
        default="Architecture Team",
        help="Decision makers / authors (default: Architecture Team)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview ADR without creating file"
    )

    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root directory (default: current directory)"
    )

    args = parser.parse_args()

    # Initialize extractor
    project_root = args.project_root.resolve()
    extractor = ADRExtractor(project_root)

    # Extract from design.md
    design_path = args.design_file.resolve()
    print(f"📖 Reading design document: {design_path}")

    try:
        extracted_data = extractor.extract_from_design(design_path)
        print(f"✅ Extracted data:")
        print(f"   Title: {extracted_data['title']}")
        print(f"   Alternatives: {len(extracted_data['alternatives'])}")
        print(f"   Chosen: {extracted_data['chosen_solution']}")
        print()

        # Create ADR
        adr_path = extractor.create_adr_file(
            extracted_data,
            adr_number=args.number,
            author=args.author,
            dry_run=args.dry_run
        )

        if not args.dry_run:
            print()
            print("Next steps:")
            print(f"1. Review and edit: {adr_path}")
            print(f"2. Update change proposal with ADR link:")
            print(f"   - Add to proposal.md: Related ADR: ADR-{args.number or extractor.find_next_adr_number():04d}")
            print(f"3. Commit both files together")

    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
