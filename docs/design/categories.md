# FRANK Platform Categories Documentation

## Submission Levels

```yaml
submission_levels:
  level_1: "raw_observable"
  level_2: "contextualized_observable"  
  level_3: "threat_attribution"
  level_4: "sigma_detection"
  level_5: "behavioral_analysis"
```

FRANK's submission system accommodates organizations with varying analytical capabilities through five distinct contribution levels. Each level represents increasing analytical sophistication and community value, from basic technical observations to advanced behavioral research. This tiered approach enables inclusive participation while incentivizing analytical development through enhanced platform privileges.

| Level | Type | Analytical Requirement | Community Value |
|-------|------|----------------------|-----------------|
| 1 | Raw Observable | Minimal | Basic IoC distribution |
| 2 | Contextualized Observable | Operational | Operational intelligence |
| 3 | Threat Attribution | Expert analysis | Strategic intelligence |
| 4 | SIGMA Detection | Rule development | Automated detection |
| 5 | Behavioral Analysis | Research capability | Innovation discovery |

### Level 1: Raw Observable Sighting
Basic technical observations requiring minimal cybersecurity expertise. Organizations submit specific indicators (IP addresses, file hashes, domain names) without analytical interpretation. These become valuable when aggregated across multiple sources.

**Example**: `"IP 185.220.102.45 contacted our server port 443"`

### Level 2: Contextualized Observable
Operational intelligence adding environmental context to technical observations. Includes timing, frequency, affected systems, and response effectiveness. Accessible to most IT operations teams through incident documentation.

**Example**: `"IP caused 15 connections over 2 hours, blocked after containment in 45 minutes, 3 systems affected"`

### Level 3: Threat Attribution
Analytical intelligence linking observations to known threat actors or campaigns. Requires access to threat intelligence sources and expertise for attribution assessments. Provides strategic context for proactive defense planning.

**Example**: `"IP attributed to TrickBot banking campaign targeting financial sector, confidence 87%"`

### Level 4: SIGMA Detection
Systematic threat identification using community-validated detection rules. Organizations contribute detection events plus rule effectiveness metrics and false positive rates. Enables automated detection deployment across the community.

**Example**: `"SIGMA rule 'banking_c2_communication' triggered 23 times, false positive rate 3%"`

### Level 5: Behavioral Analysis
Advanced research identifying novel attack patterns or innovative defensive insights. Often represents original research identifying threats before widespread recognition. Requires advanced analytical capabilities and research methodology.

**Example**: `"Novel persistence mechanism using undocumented registry keys in HKLM\\Software\\Classes"`

---

## Access Levels

```yaml
access_levels:
  public: "basic_statistics"
  observer: "regional_trends"
  contributor: "threat_context"
  partner: "full_intelligence"
  core_member: "governance_access"
```

FRANK's access control operates on trust-based progression where intelligence detail increases with contribution history. The five-tier structure ensures organizations sharing high-quality threat intelligence receive correspondingly valuable intelligence in return. This reciprocity model addresses private sector reluctance to participate in government-led cybersecurity initiatives.

| Level | Rate Limit | Data Access | Contribution Requirement |
|-------|------------|-------------|-------------------------|
| Public | 10/day | Statistics only | None |
| Observer | 500/day | Weekly summaries | Verified interest |
| Contributor | Unlimited | Daily sightings | 10 sightings/month |
| Partner | Unlimited | Real-time intelligence | 50 sightings/month |
| Core Member | Unlimited | Full platform access | Governance participation |

### Public Access
Basic threat landscape awareness through aggregated statistics and general indicators. Provides hash values and broad threat categories with minimal contribution barriers. Supports community education and basic threat awareness initiatives.

**Example Access**: `"Banking sector experienced 47% increase in credential harvesting attempts this week. Top malware families: TrickBot (23%), Emotet (18%), Zeus (12%)"`

### Observer Access
Entry-level intelligence access for organizations with legitimate security interests. Weekly threat summaries with obfuscated indicators and sector-specific trends. Enables basic defensive planning without requiring active contribution.

**Example Access**: `"Financial institutions in North Holland region targeted by IP range 185.220.102.x with banking trojan variant. Domain pattern: *-bank-verify.nl registered in past 7 days"`

### Contributor Access
Active participant tier with comprehensive daily threat intelligence access. Includes partial observables, network patterns, and campaign attribution with MITRE techniques. Requires consistent monthly intelligence submissions demonstrating platform value.

**Example Access**: `"IP 185.220.102.45 linked to TrickBot campaign #2025-01-20-BANK targeting Dutch financial sector. MITRE T1566.001 (Spearphishing), T1071.001 (Web Protocols). 15 confirmed infections across 8 organizations"`

### Partner Access
Advanced collaboration level providing real-time threat intelligence with complete technical context. Full threat actor attribution and TTPs with comprehensive impact assessments. Demands substantial monthly contributions and high-quality analytical submissions.

**Example Access**: `"REAL-TIME: 185.220.102.45:443 serving banking_update.exe (SHA256: e3b0c44298fc...), C2 communication every 30min ±15% jitter. Financial impact: €15,000 average per incident. Bulletproof hosting provider AS12345, active 3 days"`

### Core Member Access
Elite platform tier with complete access including governance participation rights. Provides mitigation effectiveness data, infrastructure details, and campaign coordination capabilities. Reserved for significant contributors participating in platform strategic direction.

**Example Access**: `"Infrastructure cluster: 185.220.102.45-48 (€500/month hosting cost), 15 organizations affected, average containment time 45min. Mitigation effectiveness: IP blocking 95%, SIGMA rule detection 87%. Coordinate response with Partners X,Y,Z"`

---

## Confidence Assessment

```yaml
confidence_levels:
  very_high: 85-100
  high: 70-84
  medium: 50-69
  low: 25-49
  very_low: 0-24
```

FRANK employs numerical confidence scoring (0-100) aligned with NATO STANAG 2511 and US Intelligence Community standards. This system combines analytical precision with operational clarity for contribution scoring and intelligence distribution. Submitters assign scores based on evidence quality, source reliability, and validation methods.

| Confidence | Score Range | NATO Equivalent | Platform Treatment |
|------------|-------------|-----------------|-------------------|
| Very High | 85-100 | A1-A2 (Reliable) | Immediate distribution |
| High | 70-84 | B2-B3 (Usually Reliable) | Standard distribution |
| Medium | 50-69 | C3-C4 (Fairly Reliable) | Community validation |
| Low | 25-49 | D4-E5 (Unreliable) | Peer review required |
| Very Low | 0-24 | F6 (Cannot Judge) | Research flagged |

### Very High Confidence (85-100)
Multiple validated technical artifacts with independent verification. Confirmed malware hashes with behavioral analysis, verified C2 infrastructure with network evidence. Receives immediate platform distribution and maximum contribution scoring impact.

### High Confidence (70-84)
Strong analytical evidence from credible sources with validation. SIGMA rule detections with analyst verification, infrastructure correlation analysis. Standard distribution workflow with enhanced contribution scoring.

### Medium Confidence (50-69)
Limited but credible sources requiring community validation. Single-source attribution claims, behavioral analysis without technical correlation. Community review process with standard contribution scoring.

### Low Confidence (25-49)
Preliminary assessments requiring peer review before acceptance. Speculative attribution claims, partial technical analysis. Mandatory peer review by higher-tier contributors.

### Very Low Confidence (0-24)
Experimental submissions flagged for research rather than operational use. Valuable for platform innovation but minimal contribution scoring. Specialized distribution to research-focused community members.

---

## Disclosure Control (TLP-Based)

```yaml
disclosure_levels:
  tlp_red: "no_external_disclosure"
  tlp_amber_plus: "organizational_networks"
  tlp_amber: "community_attribution"
  tlp_green: "acknowledged_sharing"
  tlp_clear: "unrestricted_public"
access_level_mapping:
  core_member: ["tlp_red", "tlp_amber_plus", "tlp_amber", "tlp_green", "tlp_clear"]
  partner: ["tlp_amber_plus", "tlp_amber", "tlp_green", "tlp_clear"]
  contributor: ["tlp_amber", "tlp_green", "tlp_clear"]
  observer: ["tlp_green", "tlp_clear"]
  public: ["tlp_clear"]
```

FRANK implements Traffic Light Protocol classifications controlling information utilization beyond access permissions. Disclosure rules operate independently of access tiers, enabling granular operational security while supporting collaborative defense. TLP levels determine not only viewing rights but also redistribution and action capabilities, with higher access levels enabling access to more restrictive TLP classifications.

| TLP Level | Disclosure Scope | Usage Permissions | Access Level Required |
|-----------|------------------|-------------------|----------------------|
| TLP:RED | Named recipients only | Internal analysis only | Core Member |
| TLP:AMBER+ | Organizational networks | Authorized partners | Partner+ |
| TLP:AMBER | Community sharing | Platform participants | Contributor+ |
| TLP:GREEN | Extended community | Public advisories | Observer+ |
| TLP:CLEAR | Unrestricted public | Commercial use | Public+ |

### TLP:RED - No External Disclosure (Core Member Only)
Information restricted to explicitly named recipients without prior authorization, accessible only to Core Members with governance responsibilities. Recipients must compartmentalize intelligence for internal analysis only. Any defensive actions must avoid revealing underlying intelligence sources or specific threat details.

### TLP:AMBER+ - Organizational Network Disclosure (Partner+ Access)
Intelligence shareable within recipient's organizational structure and pre-approved clients, available to Partner and Core Member access levels. Enables leadership briefings and authorized partner coordination. Cannot be redistributed to external parties or published in any format.

### TLP:AMBER - Community Attribution Disclosure (Contributor+ Access)
Information shareable among platform participants while maintaining source attribution, accessible to Contributors, Partners, and Core Members. Recipients may coordinate collective defensive actions and reference findings in community forums. Automated sharing systems can distribute within established community boundaries.

### TLP:GREEN - Acknowledged Community Sharing (Observer+ Access)
Intelligence supporting broader cybersecurity community sharing with source acknowledgment, available to Observer level and above. Recipients can reference information in presentations, advisories, and collaborative initiatives. Enables community-wide threat awareness while preserving analytical integrity.

### TLP:CLEAR - Unrestricted Public Disclosure (All Access Levels)
Information freely shareable and redistributable without restrictions, accessible to all access levels including Public users. Recipients may incorporate into commercial products, academic research, and public policy recommendations. Maximum community benefit through unrestricted knowledge sharing.

---

## Observable Types

```yaml
observable_types:
  network:
    - ipv4_address
    - ipv6_address
    - domain_name
    - url
    - network_pattern
  file:
    - hash_md5
    - hash_sha1
    - hash_sha256
    - file_name
    - file_path
  email:
    - sender_address
    - sender_ip
    - subject_line
    - message_id
    - attachment_hash
  system:
    - registry_key
    - process_name
    - service_name
    - scheduled_task
```

FRANK supports comprehensive cyber threat observables across network, file, email, and system categories. Each observable type provides specific technical artifacts that security teams can correlate and act upon. The platform maintains relationships between observables to enable comprehensive threat analysis and attribution.

| Category | Observable Types | Usage Context | Correlation Value |
|----------|------------------|---------------|-------------------|
| Network | IPs, domains, URLs | Traffic analysis | Infrastructure mapping |
| File | Hashes, names, paths | Malware analysis | Campaign tracking |
| Email | Addresses, subjects | Phishing detection | Actor attribution |
| System | Registry, processes | Host analysis | TTP identification |

### Network Observables
IP addresses, domain names, and URLs representing network-based threat indicators. Include port/protocol combinations and ASN information for infrastructure analysis. Enable network security teams to implement blocking rules and traffic analysis.

**Examples**:
- `ipv4_address: "185.220.102.45"`
- `domain_name: "secure-bank-verify.nl"`
- `url: "https://secure-bank-verify.nl/login/update.php"`
- `network_pattern: "185.220.102.0/24 hosting malicious banking sites"`

### File Observables
File hashes, names, and metadata supporting malware identification and analysis. Include compilation timestamps, digital signatures, and packer information. Critical for endpoint security and forensic analysis capabilities.

**Examples**:
- `hash_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"`
- `file_name: "banking_update.exe"`
- `file_path: "C:\\Users\\victim\\Downloads\\banking_update.exe"`
- `compilation_timestamp: "2025-01-17T09:30:00Z"`

### Email Observables
Email-based threat indicators including sender information and message characteristics. Include DMARC/SPF/DKIM validation results and phishing indicators. Essential for email security gateway configuration and user awareness.

**Examples**:
- `sender_address: "security@trusted-bank.nl" (spoofed)`
- `sender_ip: "185.220.102.45"`
- `subject_line: "Urgent: Account Security Verification Required"`
- `message_id: "<malicious123@fake-domain.com>"`

### System Observables
Host-based artifacts including registry keys, processes, and services. Include persistence mechanisms and system configuration changes. Support endpoint detection and response (EDR) rule development.

**Examples**:
- `registry_key: "HKLM\\Software\\Classes\\CLSID\\{malicious-guid}"`
- `process_name: "banking_update.exe"`
- `service_name: "TrustedBankingService"`
- `scheduled_task: "\\Microsoft\\Windows\\BankingUpdate"`

---

## Impact Assessment

```yaml
impact_levels:
  severity:
    critical: "significant_disruption"
    high: "notable_impact"
    medium: "limited_impact"
    low: "minimal_impact"
  financial_ranges:
    minimal: "0-1000_eur"
    low: "1000-10000_eur"
    medium: "10000-100000_eur"
    high: "100000-1000000_eur"
    critical: "1000000plus_eur"
  recovery_time:
    immediate: "less_than_1_hour"
    short: "1_to_8_hours"
    medium: "8_to_24_hours"
    extended: "1_to_7_days"
    longterm: "more_than_7_days"
```

FRANK categorizes security incident impacts across severity, financial, and temporal dimensions to support risk-based decision making. Impact assessments help organizations prioritize responses and allocate resources effectively based on potential consequences. These categories enable comparative analysis across different organizational contexts and threat scenarios.

| Dimension | Categories | Purpose | Decision Support |
|-----------|------------|---------|------------------|
| Severity | Critical to Low | Risk prioritization | Response urgency |
| Financial | €0 to €1M+ | Resource allocation | Cost-benefit analysis |
| Recovery | <1hr to >7 days | Business continuity | SLA planning |
| Systems | Endpoint to Cloud | Asset protection | Defense strategy |

### Severity Assessment
Critical incidents involve significant business disruption, data breaches, or complete system compromise requiring immediate response. High severity indicates notable impact with contained damage but substantial operational effects. Medium and low severity represent progressively limited impacts with faster resolution capabilities.

### Financial Impact Ranges
Financial categories span from minimal (€0-€1,000) through critical (€1M+) enabling cost-benefit analysis for security investments. Organizations can correlate threat intelligence value with potential financial exposure. Supports business case development for enhanced security measures.

### Recovery Time Categories  
Temporal impact ranges from immediate (<1 hour) to long-term (>7 days) supporting business continuity planning. Recovery timeframes help organizations establish appropriate response procedures and resource requirements. Critical for service level agreement (SLA) development and customer communications.

### Affected Systems Categories
System impact categories span endpoints, network infrastructure, applications, databases, cloud services, and mobile devices. Each category requires different response procedures and recovery approaches. Enables targeted security control implementation and incident response planning.