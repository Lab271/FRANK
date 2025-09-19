# FRANK Submission Message - Technical Taxonomy

## Executive Summary

This technical taxonomy provides a comprehensive breakdown of the FRANK submission message structure, defining every field, data type, validation rule, and relationship within the submission schema. Based on the FRANKSubmission dataclass and example messages, this taxonomy serves as the definitive technical specification for submission message implementation.

## Core Message Architecture

### Level 1: Message Container
The root-level structure that encapsulates all submission data.

```yaml
submission:
  # All submission content contained within this root element
```

#### 1.1 Format Specification
- **Format**: YAML/JSON compatible structure
- **Schema Version**: 1.0 (as defined in maximum submission example)
- **Encoding**: UTF-8
- **Size Limits**: No explicit limits defined, governed by platform capacity
- **Validation**: Schema-based with "be forgiving" principle

### Level 2: Primary Message Sections
The main structural components of every submission message.

#### 2.1 Metadata Section (`submission.metadata`)
**Purpose**: Administrative and technical information about the submission itself
**Cardinality**: 0..1 (Optional)
**Data Type**: Object

```yaml
metadata:
  format_version: string        # Required: "1.0"
  submission_id: string         # Required: UUID format
  timestamp: string            # Required: ISO 8601 format
```

#### 2.2 Submitter Section (`submission.submitter`)
**Purpose**: Information about the organisation making the submission
**Cardinality**: 1 (Required)
**Data Type**: Object

```yaml
submitter:
  organisation_id: string       # Required: UUID format
  organisation_type: string     # Optional: "cyber_partner", "customer"
  access_level: string                 # Required: access access_level level
  sector: string               # Optional: industry classification
  region: string               # Optional: geographical identifier
  submission_method: string     # Optional: "automated_api", "manual"
  client_count: integer        # Optional: number of served clients
```

#### 2.3 Hit Target Section (`submission.hit_target`)
**Purpose**: Information about the organisation that experienced the threat
**Cardinality**: 0..1 (Optional)
**Data Type**: Object

```yaml
hit_target:
  organisation_id: string       # Required: anonymized UUID
  organisation_type: string     # Optional: "customer", "internal"
  sector: string               # Optional: target industry
  organisation_size: string     # Optional: "small", "medium", "large"
  region: string               # Optional: geographical location
  anonymization_level: string  # Optional: "low", "medium", "high"
  customer_relationship: object # Optional: MSP relationship data
```

#### 2.4 Sighting Section (`submission.sighting`)
**Purpose**: Core threat intelligence data and observations
**Cardinality**: 1 (Required)
**Data Type**: Object

#### 2.5 Sharing Section (`submission.sharing`)
**Purpose**: Distribution and disclosure preferences
**Cardinality**: 0..1 (Optional)
**Data Type**: Object

### Level 3: Sighting Structure Deep Dive
The most complex and critical section containing actual threat intelligence.

#### 3.1 Core Sighting Metadata
**Purpose**: Fundamental identification and timing information

```yaml
sighting:
  sighting_id: string          # Required: UUID format
  first_observed: string       # Optional: ISO 8601 timestamp
  last_observed: string        # Optional: ISO 8601 timestamp
  observation_count: integer   # Optional: number of observations
  confidence: integer          # Optional: 0-100 (default: 69)
  severity: string             # Optional: "low", "medium", "high", "critical"
  timestamp: string            # Required: ISO 8601 format
```

#### 3.2 SIGMA Detection Integration
**Purpose**: Community-validated detection rule information
**Cardinality**: 0..1 (Optional)

```yaml
sigma_detection:
  rule_id: string              # Optional: UUID of SIGMA rule
  rule_name: string            # Optional: human-readable rule name
  rule_version: string         # Optional: version identifier
  rule_status: string          # Optional: "stable", "experimental"
  sigma_yaml: string           # Optional: complete SIGMA rule YAML
  detection_engine: string     # Optional: engine that triggered
  trigger_timestamp: string    # Optional: ISO 8601 detection time
  rule_effectiveness: float    # Optional: 0.0-1.0 effectiveness rating
  false_positive_rate: float   # Optional: 0.0-1.0 FP rate
  analyst_verified: boolean    # Optional: human verification status
  verification_timestamp: string # Optional: verification time
```

#### 3.3 Observable Artifacts Structure
**Purpose**: Technical indicators and artifacts observed during the incident
**Cardinality**: 1 (Required)
**Data Type**: Object with typed arrays

```yaml
observables:
  network: array              # Optional: network-based indicators
  files: array                # Optional: file-based indicators  
  email: array                # Optional: email-based indicators
```

### Level 4: Observable Type Specifications
Detailed schemas for each type of observable artifact.

#### 4.1 Network Observables
**Purpose**: IP addresses, domains, and network-based indicators

```yaml
network:
  - id: string                 # Required: UUID identifier
    type: string               # Required: "ipv4", "ipv6", "domain", "url"
    value: string              # Required: the actual observable value
    role: string               # Optional: "c2_server", "phishing_domain", etc.
    port: integer              # Optional: network port number
    protocol: string           # Optional: "https", "tcp", "udp"
    first_seen: string         # Optional: ISO 8601 timestamp
    connection_count: integer  # Optional: number of connections observed
    geographic_location: string # Optional: general geographic area
    asn: string                # Optional: Autonomous System Number
    hosting_provider: string   # Optional: hosting service identifier
    resolution_ip: string      # Optional: resolved IP for domains
    first_registered: string   # Optional: domain registration date
    registrar: string          # Optional: domain registrar
    registrar_suspicious: boolean # Optional: registrar reputation flag
    domain_age_days: integer   # Optional: age of domain in days
    tld_reputation: string     # Optional: "low_risk", "medium_risk", "high_risk"
```

#### 4.2 File Observables  
**Purpose**: Malware samples and file-based indicators

```yaml
files:
  - id: string                 # Required: UUID identifier
    type: string               # Required: "executable", "document", "script"
    name: string               # Optional: original filename
    size_bytes: integer        # Optional: file size in bytes
    hash_md5: string           # Optional: MD5 hash
    hash_sha256: string        # Optional: SHA256 hash
    hash_sha1: string          # Optional: SHA1 hash
    first_seen: string         # Optional: ISO 8601 timestamp
    delivery_method: string    # Optional: "email_attachment", "download"
    file_type: string          # Optional: "pe32", "pdf", "doc"
    compilation_timestamp: string # Optional: compilation time
    digital_signature: string  # Optional: "valid", "invalid", "none"
    entropy: float             # Optional: file entropy value
    packer_detected: string    # Optional: packer/obfuscation tool
```

#### 4.3 Email Observables
**Purpose**: Email-based threats and phishing indicators

```yaml
email:
  - id: string                 # Required: UUID identifier
    sender: string             # Optional: sender email (may be spoofed)
    sender_ip: string          # Optional: originating IP address
    subject: string            # Optional: email subject line
    message_id: string         # Optional: email message identifier
    attachment_count: integer  # Optional: number of attachments
    suspicious_links: integer  # Optional: count of suspicious URLs
    phishing_indicators: array # Optional: array of indicator strings
    dmarc_result: string       # Optional: "pass", "fail", "none"
    spf_result: string         # Optional: SPF authentication result
    dkim_result: string        # Optional: DKIM authentication result
    received_timestamp: string # Optional: ISO 8601 receipt time
```

### Level 5: Advanced Context Structures
Higher-level analytical and contextual information.

#### 5.1 Threat Context Section
**Purpose**: Campaign attribution and threat actor analysis

```yaml
threat_context:
  campaign:
    id: string                 # Optional: campaign UUID
    name: string               # Optional: campaign identifier
    confidence: integer        # Optional: attribution confidence 0-100
    attribution: string        # Optional: threat actor attribution
    target_sectors: array      # Optional: targeted industry sectors
    attack_vector: string      # Optional: primary attack method
    payload_type: string       # Optional: malware family/type
    campaign_start: string     # Optional: ISO 8601 campaign start
    estimated_victims: integer # Optional: estimated victim count
  
  mitre_attack:
    techniques: array          # Optional: array of MITRE ATT&CK techniques
    tactics: array            # Optional: array of MITRE tactics
  
  malware_family:
    id: string                 # Optional: malware family UUID
    name: string               # Optional: malware family name
    variant: string            # Optional: specific variant identifier
    confidence: integer        # Optional: classification confidence
    capabilities: array        # Optional: malware capabilities
    first_seen_wild: string    # Optional: first observed in wild
    yara_rule_matches: array   # Optional: matching YARA rules
```

#### 5.2 Impact Assessment Section
**Purpose**: Quantitative and qualitative impact measurement

```yaml
impact:
  affected_systems: integer    # Optional: number of systems impacted
  compromised_accounts: integer # Optional: number of accounts compromised
  credentials_harvested: integer # Optional: stolen credentials count
  data_exfiltrated: boolean    # Optional: data theft occurred
  estimated_damage: string     # Optional: "low", "medium", "high"
  business_disruption: string  # Optional: operational impact level
  containment_time: string     # Optional: time to containment (duration)
  recovery_time: string        # Optional: time to full recovery
  financial_impact_eur: integer # Optional: financial loss in euros
  
  mitigation_actions:
    immediate: array           # Optional: immediate response actions
    tactical: array            # Optional: tactical countermeasures
```

#### 5.3 Technical Details Section
**Purpose**: Detailed technical analysis and behavior

```yaml
technical_details:
  network_behavior:
    beacon_interval: string    # Optional: C2 beacon timing
    beacon_jitter: string      # Optional: timing variation
    data_exfiltration_attempt: boolean # Optional: exfiltration flag
    c2_protocol: string        # Optional: command and control protocol
    persistence_mechanisms: array # Optional: persistence methods
    communication_encryption: string # Optional: encryption type
    obfuscation_methods: array # Optional: evasion techniques
  
  evasion_techniques: array    # Optional: techniques used to evade detection
  
  infrastructure:
    hosting_provider: string   # Optional: threat infrastructure host
    geographic_location: string # Optional: infrastructure location
    infrastructure_age: string # Optional: how long infrastructure existed
    shared_infrastructure: boolean # Optional: shared vs dedicated
    hosting_history: array     # Optional: previous hosting providers
    infrastructure_cost_estimate: string # Optional: estimated monthly cost
```

### Level 6: Validation and Quality Control
Technical validation rules and data quality specifications.

#### 6.1 Required Field Validation
**Core Required Fields** (enforced by FRANKValidator):
- `submission.submitter.organisation_id`
- `submission.submitter.access_level`
- `submission.sighting.sighting_id`
- `submission.sighting.timestamp`
- `submission.sighting.observables`

#### 6.2 Data Type Constraints
**String Fields**:
- UUID fields: Must match UUID format pattern
- Timestamp fields: Must be valid ISO 8601 format
- Enum fields: Must match predefined valid values

**Numeric Fields**:
- `confidence`: Integer 0-100 (default: 69)
- `observation_count`: Positive integer
- `affected_systems`: Non-negative integer
- Float fields: Must be valid floating point numbers

**Array Fields**:
- Must contain objects with required sub-fields
- Empty arrays are acceptable but null arrays are not

#### 6.3 Enumerated Value Lists
**Valid access_levels**: `public`, `observer`, `contributor`, `partner`, `core_member`
**Valid Severities**: `low`, `medium`, `high`, `critical`
**Valid Observable Types**: `ipv4`, `ipv6`, `domain`, `url`, `file_hash`, `email`, `registry_key`
**Valid TLP Levels**: `RED`, `AMBER+`, `AMBER`, `GREEN`, `CLEAR`

### Level 7: Message Processing Workflow
Technical processing pipeline for submission messages.

#### 7.1 Input Processing
1. **Format Detection**: YAML/JSON format identification
2. **Schema Validation**: Structure validation against taxonomy
3. **Required Field Check**: Verification of mandatory fields
4. **Type Validation**: Data type constraint enforcement
5. **Enum Validation**: Enumerated value verification

#### 7.2 Content Processing
1. **Observable Extraction**: Parse observable arrays by type
2. **Confidence Scoring**: Validate and default confidence values
3. **Timestamp Normalization**: Convert to standard UTC format
4. **UUID Validation**: Verify UUID format compliance
5. **Anonymization Application**: Apply privacy-preserving transforms

#### 7.3 Quality Assessment
1. **Completeness Scoring**: Calculate metadata completeness
2. **Consistency Checking**: Cross-field validation
3. **Duplication Detection**: Identify duplicate submissions
4. **Contribution Scoring**: Calculate community value metrics

## Implementation Specifications

### Message Size Constraints
- **Minimum Message**: Must contain required fields only (~200 bytes)
- **Maximum Message**: No hard limit, constrained by platform capacity
- **Optimal Range**: 1KB - 100KB for efficient processing
- **Large Submissions**: >1MB may require special handling

### Format Requirements
- **Primary Format**: YAML (human-readable, version control friendly)
- **Alternative Format**: JSON (API and automation friendly)
- **Character Encoding**: UTF-8 mandatory
- **Line Endings**: Platform-agnostic (LF/CRLF acceptable)

### Backward Compatibility
- **Version Strategy**: Semantic versioning for schema evolution
- **Field Addition**: New optional fields can be added without breaking changes
- **Field Deprecation**: Deprecated fields maintained for 2+ major versions
- **Migration Path**: Automated conversion tools for major version upgrades

### Error Handling
- **Validation Errors**: Detailed field-level error reporting
- **Format Errors**: Graceful handling with specific error messages
- **Recovery Strategy**: Attempt partial processing for malformed submissions
- **Error Codes**: Standardized error classification system

This technical taxonomy serves as the definitive specification for FRANK Submission message implementation, providing complete coverage of all fields, validation rules, and processing requirements while maintaining the platform's core principle of being "forgiving on what you receive and strong on what you return."