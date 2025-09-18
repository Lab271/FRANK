#!/usr/bin/env python3
"""
FRANK organisation Uploader Script

Validates JSON organisations against Submitter Pydantic model and uploads to FRANK API.

Usage:
    python frank_org_uploader.py organisation.json --validate-only
    python frank_org_uploader.py organisation.json -u --host localhost --port 8000
    python frank_org_uploader.py multiple_orgs.json -u -v

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""


import argparse
import json
import sys
import requests
import yaml
from pathlib import Path
from typing import Dict, Any, List, Union
from pydantic import ValidationError
import logging

from frank.core.models import Submitter
from frank.core.enum import AccessTier


class FRANKOrgUploader:
    """Handle organisation validation and upload to FRANK API."""

    def __init__(self, host: str = "localhost", port: int = 8000, verbose: bool = False, yaml_mode: bool = False):
        self.host = host
        self.port = port
        self.verbose = verbose
        self.yaml_mode = yaml_mode
        self.base_url = f"http://{host}:{port}"
        self.logger = logging.getLogger("frank.org_uploader")
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        self.logger.handlers = []
        self.logger.addHandler(handler)
        self.logger.propagate = False
        self.logger.setLevel(logging.DEBUG if verbose else logging.CRITICAL)

    
    def validate_organisation(self, org_data: Dict[str, Any]) -> Union[Submitter, None]:
        """
    Validate organisation data against Submitter Pydantic model.
        
        Args:
            org_data: Dictionary containing organisation data
            
        Returns:
            Submitter instance if valid, None if invalid
        """
        try:
            # Create Submitter instance - this will validate the data
            if 'organisation' in org_data:
                org_data = org_data['organisation']
            if 'submission' in org_data:
                org_data = org_data['submission']
            submitter = Submitter(**org_data)
            self.logger.info(f"Validation successful for organisation: {submitter.organisation_id}")
            return submitter
        except ValidationError as e:
            self.logger.error("Validation failed for organisation:")
            self.logger.error(f"   Data: {org_data}")
            self.logger.error(f"   Message: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error during validation: {e}")
            return None
    
    def upsert_organisation(self, submitter: Submitter, auth_token: str = None) -> bool:
        """
        Upload organisation to FRANK API.
        
        Args:
            submitter: Validated Submitter instance
            auth_token: Optional authentication token
            
        Returns:
            True if successful, False otherwise
        """
        endpoint = f"{self.base_url}/v1/organisation"
        
        # Convert to dictionary for API
        org_data = {'organisation': submitter.model_dump(exclude_none=True)}
        
        # Set up headers
        headers = {"Content-Type": "application/json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        
        try:
            self.logger.info(f"Uploading to {endpoint}")
            self.logger.debug(f"Data: {json.dumps(org_data, indent=2)}")
            self.logger.debug(f"Authorization: {headers['Authorization']}")

            response = requests.post(endpoint, json=org_data, headers=headers)

            if response.status_code in [200, 201]:
                self.logger.info(f"Successfully uploaded organisation: {submitter.organisation_id}")
                return True
            else:
                self.logger.error(f"Upload failed for {submitter.organisation_id}")
                self.logger.error(f"   Status: {response.status_code}")
                self.logger.error(f"   Response: {response.text}")
                return False

        except requests.exceptions.ConnectionError:
            self.logger.error(f"Connection failed to {self.base_url}")
            self.logger.error(f"   Make sure FRANK API is running on {self.host}:{self.port}")
            return False
        except Exception as e:
            self.logger.error(f"Upload error: {e}")
            return False
    
    def process_file(self, file_path: Path, upload: bool = False, auth_token: str = None) -> bool:
        """
    Process JSON or YAML file containing organisation(s).
        
        Args:
            file_path: Path to JSON/YAML file
            upload: Whether to upload after validation
            auth_token: Optional authentication token
            
        Returns:
            True if all organisations processed successfully
        """
        try:
            with open(file_path, 'r') as f:
                if self.yaml_mode:
                    self.logger.info(f"Loading YAML file: {file_path}")
                    data = yaml.safe_load(f)
                else:
                    self.logger.info(f"Loading JSON file: {file_path}")
                    data = json.load(f)
        except FileNotFoundError:
            self.logger.error(f"File not found: {file_path}")
            return False
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in {file_path}: {e}")
            return False
        except yaml.YAMLError as e:
            self.logger.error(f"Invalid YAML in {file_path}: {e}")
            return False

        # Handle both single organisation and list of organisations
        if isinstance(data, dict):
            organisations = [data]
        elif isinstance(data, list):
            organisations = data
        else:
            self.logger.error("File must contain either an organisation object or array of organisations")
            return False

        file_type = "YAML" if self.yaml_mode else "JSON"
        self.logger.info(f"Processing {len(organisations)} organisation(s) from {file_type} file: {file_path}")

        success_count = 0
        total_count = len(organisations)

        for i, org_data in enumerate(organisations, 1):
            self.logger.info(f"--- Organisation {i}/{total_count} ---")

            # Validate organisation
            submitter = self.validate_organisation(org_data)
            if not submitter:
                continue

            # Upload if requested
            if upload:
                if self.upsert_organisation(submitter, auth_token):
                    success_count += 1
            else:
                success_count += 1
                self.logger.info("Validation successful (upload skipped)")

        # Summary
        self.logger.info("=== Summary ===")
        self.logger.info(f"Total: {total_count}")
        self.logger.info(f"{'Uploaded' if upload else 'Validated'}: {success_count}")
        self.logger.info(f"Failed: {total_count - success_count}")

        return success_count == total_count


def create_example_organisation_file(yaml_format: bool = False):
    """Create an example organisation file in JSON or YAML format."""
    example_org = {
        "organisation_id": "demo-test-org",
        "access_level": "partner",
        "organisation_type": "cyber_partner",
        "sector": "cybersecurity_services",
        "region": "nl",
        "client_count": 100
    }

    logger = logging.getLogger("frank.org_uploader")
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.handlers = []
    logger.addHandler(handler)
    logger.propagate = False
    logger.setLevel(logging.INFO)

    if yaml_format:
        yaml.dump({'organisation': example_org}, sys.stdout, default_flow_style=False, indent=2)
    else:
        json.dump({'organisation': example_org}, sys.stdout, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Validate and upload organisations to FRANK API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate JSON file only
  python frank_org_uploader.py org.json
  
  # Validate YAML file only
  python frank_org_uploader.py org.yaml -y
  
  # Validate and upload JSON
  python frank_org_uploader.py org.json -u
  
  # Validate and upload YAML
  python frank_org_uploader.py org.yaml -y -u
  
  # Custom host and port with YAML
  python frank_org_uploader.py orgs.yaml -y -u --host 192.168.1.100 --port 9000
  
  # With authentication and verbose output
  python frank_org_uploader.py orgs.json -u -v --token partner_test_token
  
  # Create example JSON file
  python frank_org_uploader.py --create-example
  
  # Create example YAML file
  python frank_org_uploader.py --create-example -y
        """
    )
    
    parser.add_argument("file", nargs="?", help="JSON or YAML file containing organisation(s)")
    parser.add_argument("-u", "--upload", action="store_true", 
                       help="Upload to API after validation")
    parser.add_argument("-y", "--yaml", action="store_true",
                       help="Parse input file as YAML instead of JSON")
    parser.add_argument("--host", default="localhost", 
                       help="API host (default: localhost)")
    parser.add_argument("-p", "--port", type=int, default=8000, 
                       help="API port (default: 8000)")
    parser.add_argument("-t", "--token", type=str, default="core_test_token",
                       help="Authentication token (e.g., partner_test_token)")
    parser.add_argument("-v", "--verbose", action="store_true",
                       help="Verbose output")
    parser.add_argument("-e", "--create-example", action="store_true",
                       help="Create example organisation file (JSON by default, YAML if -y specified)")
    
    args = parser.parse_args()
    
    # Handle special case: create example
    if args.create_example:
        create_example_organisation_file(yaml_format=args.yaml)
        return

    # Accept stdin if file is '-' or omitted
    input_source = args.file if args.file else "-"

    uploader = FRANKOrgUploader(
        host=args.host,
        port=args.port,
        verbose=args.verbose,
        yaml_mode=args.yaml
    )

    if input_source == "-":
        # Read from stdin
        if args.yaml:
            uploader.logger.info("Reading YAML from stdin...")
            data = yaml.safe_load(sys.stdin)
        else:
            uploader.logger.info("Reading JSON from stdin...")
            data = json.load(sys.stdin)

        # Handle both single organisation and list of organisations
        if isinstance(data, dict):
            organisations = [data]
        elif isinstance(data, list):
            organisations = data
        else:
            uploader.logger.error("Input must be an organisation object or array of organisations")
            sys.exit(1)

        # Use process_file logic directly
        success_count = 0
        total_count = len(organisations)
        for i, org_data in enumerate(organisations, 1):
            uploader.logger.info(f"--- Organisation {i}/{total_count} ---")
            submitter = uploader.validate_organisation(org_data)
            if not submitter:
                continue
            if args.upload:
                if uploader.upsert_organisation(submitter, args.token):
                    success_count += 1
            else:
                success_count += 1
                uploader.logger.info("Validation successful (upload skipped)")
        uploader.logger.info("=== Summary ===")
        uploader.logger.info(f"Total: {total_count}")
        uploader.logger.info(f"{'Uploaded' if args.upload else 'Validated'}: {success_count}")
        uploader.logger.info(f"Failed: {total_count - success_count}")
        uploader.logger.info(f"Uploader: {args.token}")
        sys.exit(0 if success_count == total_count else 1)
    else:
        # Read from file
        file_path = Path(args.file)
        success = uploader.process_file(
            file_path=file_path,
            upload=args.upload,
            auth_token=args.token
        )
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()