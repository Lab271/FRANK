# FRANK Platform - Small Sighting Submission Schema

**Version:** 1.0  
**Copyright:** © 2025 Schuberg Philis B.V.  
**License:** Apache-2.0

## Overview

This document describes the JSON Schema for small sighting submissions to the FRANK Platform. The schema defines the structure and validation rules for submitting security sighting data, including network observables and organization metadata.

## Purpose

The Small Sighting Submission Schema is designed for:
- **Structured threat intelligence sharing** between organizations
- **Validation of submission data** before ingestion
- **Standardized format** for security observables
- **Access control** through organization-level permissions

## Key Components

### 1. Submission Metadata
Each submission requires:
- **submission_id**: Unique identifier following STIX pattern
- **submitter**: Organization details including identity and access level
- **sighting**: The actual threat intelligence data

### 2. Access Levels
Organizations are assigned one of four access levels:
- `partner` - Partner organizations with elevated access
- `member` - Member organizations
- `public` - Public access level
- `internal` - Internal organizational use

### 3. Network Observables
The schema supports various network-related observables:
- IPv4 addresses
- IPv6 addresses
- Domain names
- URLs
- Email addresses
- MAC addresses

## Schema Definition

```yaml
$schema: http://json-schema.org/draft-07/schema#
title: FRANK Platform Sighting Submission Schema
description: Schema for FRANK Platform small sighting submission format
type: object
required:
  - submission

properties:
  submission:
    type: object
    required:
      - submission_id
      - submitter
      - sighting
    properties:
      submission_id:
        type: string
        description: Unique identifier for the submission
        pattern: ^submission--[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$
        examples:
          - submission--550e8400-e29b-41d4-a716-446655440000
      
      submitter:
        type: object
        required:
          - organisation_id
          - access_level
        properties:
          organisation_id:
            type: string
            description: STIX identity identifier for the submitting organization
            pattern: ^identity--[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$
            examples:
              - identity--f431f809-377b-45e0-aa1c-6a4751cae5ff
          
          access_level:
            type: string
            description: Access level of the submitting organization
            enum:
              - partner
              - member
              - public
              - internal
            examples:
              - partner
        additionalProperties: false
      
      sighting:
        type: object
        required:
          - sighting_id
          - timestamp
          - observables
        properties:
          sighting_id:
            type: string
            description: STIX sighting identifier
            pattern: ^sighting--[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$
            examples:
              - sighting--ee20065d-2555-424f-ad9e-0f8428623c75
          
          timestamp:
            type: string
            description: ISO 8601 timestamp of when the sighting occurred
            format: date-time
            examples:
              - "2025-01-20T14:30:22Z"
          
          observables:
            type: object
            properties:
              network:
                type: array
                description: Array of network-related observables
                minItems: 1
                items:
                  type: object
                  required:
                    - id
                    - type
                    - value
                  properties:
                    id:
                      type: string
                      description: STIX cyber observable identifier
                      pattern: ^(ipv4-addr|ipv6-addr|domain-name|url|email-addr|mac-addr)--[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$
                      examples:
                        - ipv4-addr--c4e54321-1234-5678-9abc-def012345678
                        - domain-name--d5f65432-2345-6789-abcd-ef0123456789
                    
                    type:
                      type: string
                      description: Type of the network observable
                      enum:
                        - ipv4-addr
                        - ipv6-addr
                        - domain-name
                        - url
                        - email-addr
                        - mac-addr
                      examples:
                        - ipv4-addr
                        - domain-name
                    
                    value:
                      type: string
                      description: The actual observable value
                      examples:
                        - "185.220.102.45"
                        - secure-bank-verify.nl
                  additionalProperties: false
            additionalProperties: true
        additionalProperties: false
    additionalProperties: false

additionalProperties: false
```

## Example Usage

See `small.yaml` for a complete example of a valid submission conforming to this schema.

## Validation

All submissions must:
1. Include all required fields
2. Follow STIX identifier patterns (UUIDv4 format)
3. Use ISO 8601 timestamps
4. Specify valid access levels
5. Include at least one network observable

## Integration

This schema is used by the FRANK Platform API to validate incoming submissions before storage and processing. Invalid submissions will be rejected with detailed error messages indicating which validation rules were violated.
