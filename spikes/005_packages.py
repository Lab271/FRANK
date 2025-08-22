from frank import FRANKSubmission

if __name__ == "__main__":
    # Example usage and testing
    print("FRANK Submission Library - Example Usage")
    print("=" * 50)
    
    # Create submission handler
    frank = FRANKSubmission()
    
    # Generate minimal submission
    print("1. Generating minimal submission...")
    minimal = frank.generate_minimal_submission(
        org_id="test-org-123",
        tier="partner"
    )
    print(f"   Generated submission ID: {minimal['submission']['sighting']['sighting_id']}")
    
    # Validate submission
    print("\n2. Validating submission...")
    is_valid, issues = frank.validate_submission(minimal)
    print(f"   Valid: {is_valid}")
    if issues:
        print(f"   Issues: {issues}")
    
    # Convert to different formats
    print("\n3. Format conversion...")
    yaml_output = frank.to_yaml(minimal)
    json_output = frank.to_json(minimal)
    print(f"   YAML length: {len(yaml_output)} chars")
    print(f"   JSON length: {len(json_output)} chars")
    
    # Parse back from YAML
    print("\n4. Round-trip parsing test...")
    parsed_back = frank.from_yaml(yaml_output)
    is_valid_parsed, _ = frank.validate_submission(parsed_back)
    print(f"   Round-trip valid: {is_valid_parsed}")
    
    # Generate comprehensive submission
    print("\n5. Generating comprehensive submission...")
    comprehensive = frank.generate_comprehensive_submission(
        org_id="advanced-org-456",
        tier="core_member",
        severity="high",
        confidence=92,
        observables=[
            {"id": "threat-ip-1", "type": "ipv4", "value": "203.0.113.42"},
            {"id": "threat-domain-1", "type": "domain", "value": "evil-command-control.darknet"}
        ]
    )
    print(f"   Comprehensive submission created with {len(frank.extract_observables(comprehensive))} observables")
    
    print("\n✅ Library example completed successfully!")