#!/usr/bin/env python3
"""
Seed demo data into FRANK instances.

Run with: uv run python seed_data.py
"""

import json
import httpx
from pathlib import Path

# FRANK API endpoints
FRANK_CENTRAL = "http://localhost:8000"
FRANK_SBP = "http://localhost:8001"
FRANK_PARTNER = "http://localhost:8002"


def load_seed_data():
    """Load seed data from JSON files."""
    data_dir = Path(__file__).parent / "data"

    with open(data_dir / "seed_sightings.json") as f:
        sightings = json.load(f)

    with open(data_dir / "march_iocs.json") as f:
        iocs = json.load(f)

    return sightings, iocs


def seed_organizations(client: httpx.Client, base_url: str, orgs: list):
    """Seed organizations into a FRANK instance."""
    print(f"  Seeding {len(orgs)} organizations...")
    for org in orgs:
        try:
            resp = client.post(f"{base_url}/v1/organizations", json=org)
            if resp.status_code in (200, 201):
                print(f"    ✓ {org['name']}")
            elif resp.status_code == 409:
                print(f"    - {org['name']} (exists)")
            else:
                print(f"    ✗ {org['name']}: {resp.status_code}")
        except Exception as e:
            print(f"    ✗ {org['name']}: {e}")


def seed_sightings(client: httpx.Client, base_url: str, sightings: list):
    """Seed sightings into a FRANK instance."""
    print(f"  Seeding {len(sightings)} sightings...")
    for sight in sightings:
        try:
            resp = client.post(f"{base_url}/v1/sightings", json=sight)
            if resp.status_code in (200, 201):
                print(f"    ✓ {sight['observable']['value'][:30]}...")
            else:
                print(f"    ✗ {sight['id']}: {resp.status_code}")
        except Exception as e:
            print(f"    ✗ {sight['id']}: {e}")


def check_health(client: httpx.Client, base_url: str, name: str) -> bool:
    """Check if a FRANK instance is healthy."""
    try:
        resp = client.get(f"{base_url}/v1/health", timeout=5)
        if resp.status_code == 200:
            print(f"  ✓ {name} is healthy")
            return True
    except Exception:
        pass
    print(f"  ✗ {name} is not responding")
    return False


def main():
    print("=" * 60)
    print("FRANK Demo — Seeding Data")
    print("=" * 60)
    print()

    # Load data
    sightings_data, iocs_data = load_seed_data()

    with httpx.Client(timeout=30) as client:
        # Check health
        print("Checking FRANK instances...")
        central_ok = check_health(client, FRANK_CENTRAL, "FRANK Central")
        sbp_ok = check_health(client, FRANK_SBP, "FRANK SBP")
        partner_ok = check_health(client, FRANK_PARTNER, "FRANK Partner")
        print()

        if not any([central_ok, sbp_ok, partner_ok]):
            print("No FRANK instances available. Run: make up")
            return

        # Seed FRANK Central (scenarios 1-3)
        if central_ok:
            print("Seeding FRANK Central (scenarios 1-3)...")
            seed_organizations(client, FRANK_CENTRAL, sightings_data["organizations"])
            seed_sightings(client, FRANK_CENTRAL, sightings_data["demo_sightings"])
            print()

        # Seed FRANK SBP (scenarios 4-5)
        if sbp_ok:
            print("Seeding FRANK SBP (scenarios 4-5)...")
            # SBP gets a subset focused on MDR customers
            sbp_orgs = [o for o in sightings_data["organizations"] if o["id"] == "org-sbp"]
            seed_organizations(client, FRANK_SBP, sbp_orgs)
            print()

        # Seed FRANK Partner (scenarios 4-5)
        if partner_ok:
            print("Seeding FRANK Partner (scenarios 4-5)...")
            # Partner gets external organizations
            partner_orgs = [o for o in sightings_data["organizations"]
                          if o["id"] not in ("org-sbp",)]
            seed_organizations(client, FRANK_PARTNER, partner_orgs[:2])
            print()

    print("=" * 60)
    print("Seeding complete!")
    print()
    print("Next: Run 'make demo' to start the demo launcher")
    print("=" * 60)


if __name__ == "__main__":
    main()
