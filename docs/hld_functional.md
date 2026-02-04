# FRANK - High Level Design (Functional)

**For**: Schuberg Philis
**Date**: 10-08-2025
**Version**: 1.0
**Authors**: Frank Breedijk, Jenda Brands, Bernard Jenniskens, Ilja Heitlager
**Status**: Confidential

## Executive Summary

The Netherlands faces a critical cybersecurity challenge: private organizations possess vital threat intelligence but remain reluctant to share it with government-led initiatives like Cyclotron and Melissa due to concerns about regulatory scrutiny, competitive exposure, and potential disclosure requirements. This leaves an untapped value of distributed threat intelligence that could enable organizations to benefit from. These collective defensive experiences can multiply individual security investments, while improving threat detection across the entire business ecosystem.

FRANK addresses this fundamental barrier through an innovative five-tier access model that transforms cybersecurity collaboration from a compliance burden into a shared advantage. Organizations contribute threat intelligence at their analytical capability level - from basic observable reporting to advanced behavioral analysis - and receive intelligence value proportional to their contributions. This graduated approach eliminates the traditional requirement for uniform expertise across all participants.

The platform's leveled architecture enables natural capability progression. Small organizations can start by sharing simple IP addresses or domain observations, gaining access to regional threat summaries and basic protective intelligence. As they develop analytical sophistication and contribute higher-quality submissions, including campaign attribution, SIGMA rule development, or novel attack pattern identification, they unlock access to real-time threat feeds, complete technical artifacts, and attribution intelligence that gives much broader dynamic contextual information.

Partner status determines not just data access levels but participation privileges. Public users receive statistical summaries only, while Observer status provides masked indicators and trend analysis. Contributors access partial observables with campaign context, Partners receive comprehensive threat intelligence including financial impact assessments, and Core Members gain platform governance rights plus cross-organizational coordination capabilities during active threat response.

The system scales intelligence value through analytical diversity: a financial institution's basic observable becomes strategically valuable when correlated with a cybersecurity firm's campaign attribution and a managed service provider's SIGMA rule effectiveness data. The value of FRANK is that individual organizational limitations transform into collective strengths through this structured collaboration.

The reciprocity model fundamentally alters cybersecurity economics. Organizations traditionally purchasing expensive threat intelligence feeds instead invest their operational experience in a shared knowledge base that grows more valuable with each contribution. This creates sustainable participation incentives while addressing the private sector's core concern: receiving value commensurate with their sharing risks. This project believes that trust-based intelligence exchange is more effective than regulatory mandates in building the comprehensive threat visibility essential for national cyber resilience.

---

## 1. Introduction

FRANK (Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling) addresses a critical missing in the Netherlands' cybersecurity defense: being able to take dynamic contextual data in their threat-defense engineering. While programs like Cyclotron and Melissa exist to facilitate threat information sharing with professional cyber security companies, many private companies only live in the so called second ring. They might also avoid participation due to concerns about anonymity, regulatory scrutiny, and potential disclosure under freedom of information laws.

The platform creates a neutral "information economy" where organizations share cyber threat sightings and receive intelligence value proportional to their contributions. Unlike traditional threat intelligence platforms that rely on payment models, FRANK operates on reciprocity: the more high-quality threat data an organization contributes, the more detailed intelligence they receive in return.

This trust-based approach features five access tiers, from public summaries to real-time attribution data for core contributors. At its technical core, FRANK transforms security event logs into standardized threat indicators and contextual metadata. Participants can share threat intelligence anywhere in the lifecycle, from suspicion to compromise to after attribution, enabling automated distribution of threat observations while preserving anonymity through sophisticated pseudonymization.

But primarily, the platform focuses on sighting statistics and threat context rather than raw indicators, providing the dynamic intelligence that modern security operations centers require for risk-based defense decisions.

FRANK's innovation lies not in creating another threat intelligence database, but in solving the collaboration problem that limits Netherlands' cybersecurity visibility. By removing the privacy barriers that prevent private sector participation in national security initiatives, FRANK aims to create a comprehensive view of the Dutch threat landscape while maintaining the anonymity essential for commercial participation. The platform bridges the gap between private sector cybersecurity needs and public sector threat intelligence requirements, potentially serving as a model for European cybersecurity cooperation that respects both commercial sensitivity and collective defense needs.

---

## 2. Vision Statement

### Executive Vision

**Mission Statement**: To create a trusted, anonymous cybersecurity intelligence sharing platform that transforms isolated security observations into collective defensive strength for the Netherlands' digital infrastructure.

**Vision 2030**: FRANK will be the cornerstone of Dutch cybersecurity resilience, enabling seamless, trust-based threat intelligence sharing that makes every participating organization stronger while preserving confidentiality and operational autonomy.

### Core Principles

**Trust Through Reciprocity**
- Value exchange based on contribution quality and volume
- Progressive access tiers that reward active participation
- Community-driven validation and reputation systems

**Privacy by Design**
- Anonymization that preserves analytical value
- Granular disclosure controls respecting organizational sensitivity
- No government oversight barriers to private sector participation

**Operational Excellence**
- Real-time threat intelligence distribution
- SIEM-agnostic integration capabilities
- Scalable architecture supporting national cybersecurity needs

### Strategic Objectives

**Short-term (Year 1-2)**
- Establish core platform with 10+ participating MSPs
- Integrate with existing SBP MDR infrastructure
- Demonstrate measurable improvement in threat detection speed

**Medium-term (Year 3-5)**
- Bridge private sector with Cyclotron/Melissa initiatives
- Expand to 100+ participating organizations across sectors
- Develop AI-enhanced threat pattern recognition

**Long-term (Year 5+)**
- Become European model for private-public cybersecurity cooperation
- Achieve national-scale threat visibility and response coordination
- Enable predictive threat intelligence capabilities

### Success Metrics

**Quantitative Indicators**
- Participation Rate: Number of active contributing organizations
- Intelligence Quality: Threat detection accuracy improvement
- Response Time: Incident-to-mitigation duration reduction for partners
- Coverage: Percentage of Dutch critical infrastructure protected

**Qualitative Outcomes**
- Trust Building: Increased private sector willingness to share sensitive data
- Knowledge Transfer: Enhanced cybersecurity capabilities across participants
- Innovation Catalyst: New security practices emerging from collaborative insights

### Value Proposition

**For Private Organizations**
- Enhanced threat visibility without exposing competitive information
- Reduced cybersecurity investment through shared intelligence
- Faster incident response through community knowledge

**For Dutch Cybersecurity Ecosystem**
- Comprehensive national threat landscape visibility
- Reduced barriers between private and public security initiatives
- Strengthened collective defense against sophisticated threats

**For International Community**
- Replicable model for national cybersecurity collaboration
- Contribution to global threat intelligence capabilities
- Leadership in privacy-preserving security cooperation

### Implementation Philosophy

- **Evolutionary Approach**: Start with willing participants, prove value, expand organically
- **Technology Neutrality**: Support diverse technical environments without vendor lock-in
- **Community Governance**: Participant-driven decision making and platform evolution
- **Transparent Operations**: Clear policies, open-source components where possible

---

## 3. High-level Functionality

FRANK operates on a tiered submission model that recognizes varying levels of analytical sophistication among participating organizations. Rather than requiring uniform expertise across all contributors, the platform accepts threat intelligence submission anywhere in the threat analysis lifecycle at five distinct levels of analytical depth. Partners can voluntarily share suspicions, actual compromises or fully analyzed threats. Higher-level intelligence contribution receives greater contributions back.

This structure enables inclusive participation while incentivizing analytical sophistication through enhanced platform privileges. Organizations developing analytical capabilities and contributing advanced intelligence gain access to more detailed threat data, real-time feeds, and platform governance participation, creating a natural progression pathway that strengthens the overall collaborative defense ecosystem.

### 3.1 Access Levels

FRANK's access control system operates on a trust-based model where data detail depends on that trust-level. The level of each partner grows proportionally with the contribution of that partner based on quality and volume. The five-tier structure ensures that organizations sharing high-quality threat intelligence receive correspondingly more valuable intelligence in return.

| Access Level | Auth | Rate Limit | Sighting Detail Access | Observable Data | Threat Context | Contribution Requirement |
|--------------|------|------------|------------------------|-----------------|----------------|--------------------------|
| **Public** | Yes | 10/day | Aggregated statistics only | Hash values only | General threat categories | None |
| **Observer** | Yes | 500/day | Weekly summaries + sector trends | Obfuscated IPs/domains | Malware family names | Legitimate security interest |
| **Contributor** | Yes | Unlimited | Daily sightings + partial context | Partial observables + network patterns | Campaign attribution + MITRE techniques | Min 10 quality sightings/month |
| **Partner** | Yes | Unlimited | Real-time sightings + full impact data | Complete observables + relationships | Full threat actor attribution + TTPs | Min 50 sightings/month + high quality |
| **Core Member** | Yes | Unlimited | All data + mitigation effectiveness | Infrastructure details + evasion techniques | Campaign coordination + predictive analysis | Significant contribution + platform governance |

#### Public
Basic access tier providing aggregated threat statistics and general indicators. Users receive limited daily queries with hash values and broad threat categories, requiring no contribution commitment.

#### Observer
Entry-level intelligence access offering weekly threat summaries and sector-specific trends. Provides obfuscated network indicators and malware family classifications for organizations with legitimate security interests.

#### Contributor
Active participant tier with unlimited access to daily threat sightings and partial context data. Includes network patterns and campaign attribution with MITRE techniques, requiring consistent monthly intelligence submissions.

#### Partner
Advanced collaboration level providing real-time threat intelligence with comprehensive observable data. Full threat actor attribution and TTPs included, demanding substantial monthly contributions and high-quality submissions.

#### Core Member
Elite tier with complete platform access including mitigation effectiveness data and infrastructure details. Provides campaign coordination capabilities and predictive analysis, reserved for significant contributors participating in platform governance.

### 3.2 Submission Levels

The submission levels range from basic technical observations to advanced behavioral analysis, each providing different types of value to the collaborative intelligence ecosystem. The framework recognizes that meaningful threat intelligence exists across all levels, even basic observables provide community value when properly aggregated and contextualized.

| Level | Submission Type | Analytical Requirement | Example Content | Community Value | Validation Requirement |
|-------|-----------------|----------------------|-----------------|-----------------|----------------------|
| **L1** | Raw Observable | Minimal | "IP 185.220.102.45 contacted our server port 443" | Basic IoC distribution | Technical format validation |
| **L2** | Contextualized Observable | Operational | "IP caused 15 connections over 2 hours, blocked after containment in 45 minutes, 3 systems affected" | Operational intelligence | Impact assessment verification |
| **L3** | Threat Attribution | Expert analysis | "IP attributed to TrickBot banking campaign targeting financial sector, confidence 87%" | Strategic threat intelligence | Peer review and source validation |
| **L4** | SIGMA Detection | Rule development expertise | "SIGMA rule 'banking_c2_communication' triggered 23 times, false positive rate 3%" | Automated detection capability | Community testing and effectiveness validation |
| **L5** | Behavioral Analysis | Advanced research capability | "Novel persistence mechanism using undocumented registry keys in HKLM\Software\Classes" | Innovation and discovery | Expert validation and reproducibility testing |

#### Level 1: Raw Observable Sighting
The foundation level requires only basic technical observation capabilities. Organizations submit specific indicators they have observed in their environments without analytical interpretation. These submissions provide network addresses, file hashes, domain names, or other technical artifacts that can be correlated across the community. While requiring minimal cybersecurity expertise, these observations become valuable when aggregated across multiple sources to identify widespread threats. Most automated security tools can generate Level 1 submissions through basic log analysis.

#### Level 2: Contextualized Observable
This level adds operational context to technical observations by including environmental details such as timing, frequency, affected systems, and response actions taken. Organizations describe not just what they observed, but when, how often, what impact occurred, and what mitigation measures proved effective. This operational intelligence helps other organizations understand threat behavior patterns and response effectiveness without requiring deep analytical expertise. Many IT operations teams can contribute at this level through incident documentation practices.

#### Level 3: Threat Attribution
Level 3 represents analytical intelligence where organizations link their observations to known threat actors, malware families, or campaign activity. This requires access to threat intelligence sources and analytical expertise to make attribution assessments with appropriate confidence levels. Submissions include campaign context, target sector analysis, and threat actor behavioral patterns. These contributions provide strategic intelligence that enables proactive defense planning and resource allocation across the community.

#### Level 4: SIGMA Detection
This level involves submissions triggered by community-validated SIGMA detection rules, representing systematic and reproducible threat identification. Organizations contribute not only the detection event but also rule effectiveness metrics, false positive rates, and environmental adaptation requirements. These submissions enable automated threat detection deployment across the community while providing feedback on rule quality and operational performance. Level 4 submissions require SIGMA rule development or deployment capabilities.

#### Level 5: Behavioral Pattern Analysis
The highest submission level involves identification of novel attack patterns, previously unknown tactics, techniques, and procedures (TTPs), or innovative defensive insights that advance community knowledge. These submissions often identify threats before they become widespread or develop new detection methodologies that can be codified into SIGMA rules. Level 5 contributions require advanced analytical capabilities and often represent original research that benefits the entire cybersecurity community.

### 3.3 Confidence Assessment

At the core confidence is quite binary: you have either seen the observable or you don't. For deeper analysed threats FRANK employs a numerical confidence system, similar to STIX scores, that combines the granularity of numerical scoring (0-100) with the clarity of categorical levels for operational decision-making.

FRANK is based on the value of sharing sightings on a pure voluntary basis, but these sightings can be attributed with analysis metadata, ultimately becoming a platform of high-level threat intelligence.

This approach enables precise analytical assessment while providing clear guidance for contribution scoring and intelligence distribution. This is aligned with NATO STANAG 2511 source reliability standards and US Intelligence Community confidence identification. Submitters assign numerical confidence scores themselves based on their analytical evidence quality, source reliability, and validation methods.

| Level | Score Range | NATO STANAG Equivalent | US IC Equivalent | Platform Treatment | Example Use Case |
|-------|-------------|----------------------|------------------|-------------------|------------------|
| **Very High** | 85-100 | A1-A2 (Completely Reliable) | High Confidence | Immediate distribution | Known malware SHA256 hash detected by multiple AV engines with confirmed C2 communication |
| **High** | 70-84 | B2-B3 (Usually Reliable) | High Confidence | Standard distribution | SIGMA rule triggered across 3 organizations, analyst verified TTP correlation with known APT group |
| **Medium** | 50-69 | C3-C4 (Fairly Reliable) | Moderate Confidence | Community validation, standard scoring | Suspicious domain registered 2 days ago, targeting banking sector based on content analysis |
| **Low** | 25-49 | D4-E5 (Not Usually/Unreliable) | Low Confidence | Peer review required, reduced scoring | Single IP address showing unusual traffic patterns, possible C2 but no behavioral confirmation |
| **Very Low** | 0-24 | F6 (Cannot be Judged) | Low Confidence | Research flagged, minimal scoring | Hypothesis about new attack technique based on anomalous log entries requiring investigation |

The numerical scores enable precise analytical expression while categorical levels provide operational clarity. Submitters can provide extra details on their confidence methodology in submission metadata. This allows participants to make their own additional assessments.

### 3.4 Disclosure (TLP)

Disclosure represents the third operational dimension, governing how intelligence can be used, shared, and acted upon once accessed. This is determined by the submitter and respected by the system. While access controls determine who can view information, disclosure rules define what the system can do with that information towards other recipients. Disclosure levels operate independently of both submission rights and access permissions, creating granular control over intelligence utilization.

| TLP Level | Disclosure Restrictions | Link to Access Level |
|-----------|------------------------|---------------------|
| **TLP:RED** | No disclosure permitted beyond named recipients | Restricted to explicit approval list |
| **TLP:AMBER+** | Limited disclosure within organizational networks | Organization and pre-approved clients only |
| **TLP:AMBER** | Community sharing with attribution restrictions | Platform participating organizations |
| **TLP:GREEN** | Broader sharing permitted with source acknowledgment | Extended cybersecurity community |
| **TLP:CLEAR** | Unrestricted disclosure and redistribution | Public access with no limitations |

#### TLP:RED - No External Disclosure
Information marked TLP:RED cannot be shared, discussed, or referenced outside the explicitly named recipient list without prior authorization from the originating source. Recipients must treat this intelligence as compartmentalized information, using it only for internal analysis and defensive preparations without revealing specific details to additional parties. Any defensive actions taken must be implemented without disclosing the underlying intelligence source or specific threat details that could compromise ongoing operations or investigative activities.

#### TLP:AMBER+ - Organizational Network Disclosure
TLP:AMBER+ intelligence may be shared within the recipient's organizational structure and with pre-approved client organizations, but cannot be redistributed to external parties or published in any format. Recipients can brief leadership, implement defensive measures, and coordinate responses with authorized partners while maintaining source attribution and context. The information can be used to inform broader security strategies and resource allocation decisions within the defined organizational boundaries.

#### TLP:AMBER - Community Attribution Disclosure
Information designated TLP:AMBER can be shared among participating organizations within the cybersecurity community, but must maintain proper source attribution and cannot be published publicly or shared with non-participating entities. Recipients may reference this intelligence in community forums, coordinate collective defensive actions, and incorporate findings into organizational threat models while preserving the analytical context and originating source identification. Automated sharing systems and threat intelligence platforms can distribute this information within established community boundaries.

#### TLP:GREEN - Acknowledged Community Sharing
TLP:GREEN intelligence supports broader sharing across the extended cybersecurity community, including public-private partnerships, industry associations, and educational institutions, provided appropriate source acknowledgment is maintained. Recipients can reference this information in presentations, research publications, and public advisories while crediting the originating analysis and maintaining analytical integrity. This level enables community-wide threat awareness campaigns and collaborative defensive initiatives without compromising sensitive operational details.

#### TLP:CLEAR - Unrestricted Public Disclosure
TLP:CLEAR information can be freely shared, republished, and redistributed without restrictions, supporting public awareness campaigns, educational initiatives, and open-source intelligence development. Recipients may incorporate this intelligence into commercial products, academic research, and public policy recommendations without attribution requirements or disclosure limitations. This classification enables maximum community benefit through unrestricted knowledge sharing while maintaining the analytical quality and factual accuracy of the original submission.

### 3.5 Data Filtering and Access Control

FRANK's filtering system addresses a fundamental tension in collaborative threat intelligence: organizations need comprehensive threat data to defend effectively, yet sharing detailed intelligence creates competitive and operational risks. The platform resolves this through dynamic access control that provides different levels of detail based on user contribution history and trust relationships.

The filtering architecture operates on complete submission storage with retrieval-time access control. Raw submissions containing full organizational context, technical artifacts, and operational details are stored in DynamoDB without modification. When users query the platform, filtering rules dynamically remove, mask, or aggregate sensitive information based on their access tier. This approach maintains data integrity while enabling flexible security policies that evolve with platform maturity and regulatory requirements.

Five distinct filtering levels create graduated intelligence access. Public users receive only statistical summaries with completely anonymized observables, preventing organizational identification while enabling threat landscape awareness. Observer access adds regional threat patterns with partially masked indicators, supporting basic defensive planning without exposing sensitive operational details. Contributors gain access to contextualized threat data including campaign attribution and MITRE technique mapping, enabling strategic threat analysis while protecting organizational identities through persistent anonymization.

---

## 4. Specifications

### 4.1 Key Design Principles

**Trust-Based Progression**: Access levels increase based on actual contributions and verified identity, not just payment or membership status. This aligns with the project's goal of creating an "information economy" based on reciprocity.

**Graduated Anonymization**: Higher trust levels receive more detailed information while maintaining appropriate anonymization. Core members get attribution data because they've proven trustworthy through sustained high-quality contributions.

**Quality Incentives**: The scoring system rewards accurate, timely intelligence with more detail, encouraging contributors to maintain high standards.

**Fair Use Protection**: Rate limiting and abuse detection prevent any single party from extracting value without contributing, protecting the collaborative nature of the platform.

**Platform Agnostic Architecture**: All design decisions prioritize portability and vendor independence.

### 4.2 Critical Implementation Considerations

**Identity Verification**: Higher tiers require robust identity verification to prevent malicious actors from gaining access to sensitive attribution data.

**Governance Structure**: Core members participate in platform governance, making decisions about access policies, acceptable use, and response coordination.

**Data Sovereignty**: Contributors maintain control over their data through deletion rights and granular sharing preferences with the ability to deploy an installation themselves.

**Interoperability**: The API structure allows integration with existing tools (SIEM systems, threat intelligence platforms) while maintaining the platform's trust model.

### 4.3 Platform - High-Level Architecture

#### Authentication and Access Control Layer
The platform implements dual authentication mechanisms to handle both user access and programmatic API calls. Human users authenticate through Supertokens with multi-factor authentication, receiving JWT tokens that encode access tier and organizational affiliation. API submissions use mutual TLS with client certificates for cyber partners, ensuring cryptographic verification of submitting organizations.

#### REST Interface
The API Gateway exposes distinct endpoint patterns for different operations. Submission endpoints (POST /v1/submissions) handle threat intelligence ingestion with schema validation and immediate routing to processing pipelines. Query endpoints (GET /v1/threats, GET /v1/statistics) provide filtered access to threat data with parameters for sector, timeframe, and threat type. Administrative endpoints (PUT /v1/users/{id}/tier) enable contribution score updates and access level modifications. The gateway implements usage plans that automatically throttle requests based on user access tier and enforce quota limits that prevent platform abuse.

#### Storage Architecture
NoSQL (ScyllaDB, DynamoDB) serves as primary storage for complete, unfiltered submissions using a partition key of submission_id and clustering key of timestamp. Global Secondary Indexes (materialized views) enable efficient querying by sector (hit_target_sector-timestamp-index), submitter tier (submitter_tier-confidence-index), and observable type (observable_type-timestamp-index). The table stores full JSON documents, preserving all sensitive information for authorized access while maintaining query performance through strategic index design.

#### Data Processing and Filtering Pipeline
Containerized microservices process incoming submissions, performing validation, anonymization hash generation, and multi-tier document transformation. The pipeline creates access-level-specific versions during ingestion rather than runtime filtering, ensuring consistent query performance.

#### OpenSearch Query System
OpenSearch implements the secondary retrieval layer with separate indices per access tier (frank-submissions-public, frank-submissions-partner, etc.). Each index contains pre-filtered documents appropriate for that access level, with field-level security policies enforcing additional protection boundaries. Role-based access control maps user JWT claims to OpenSearch roles, automatically routing queries to appropriate indices. Index aliases enable seamless index rotation during reprocessing operations without service disruption.

#### Security and Compliance
The architecture implements defense-in-depth security with network isolation (Kubernetes Network Policies or equivalent), encryption at rest using standard encryption libraries, and comprehensive audit logging for all data access operations. Web Application Firewall (ModSecurity or cloud-native equivalent) protects API endpoints while network segmentation restricts access between components. The system maintains comprehensive audit trails linking user actions to specific data access patterns, supporting both operational security and regulatory compliance requirements.

#### Deployment Flexibility
The containerized architecture supports deployment across multiple environments: Kubernetes clusters on public clouds (AWS EKS, Azure AKS, GCP GKE), private cloud platforms (VMware vSphere, OpenStack), or on-premises infrastructure. Helm charts and Terraform/Pulumi modules enable consistent deployment patterns across different target environments. Container orchestration handles service discovery, load balancing, and automatic scaling regardless of the underlying infrastructure.

This cloud-agnostic approach eliminates vendor lock-in while maintaining the scalability and flexibility required for FRANK's collaborative intelligence sharing model. Organizations can deploy FRANK in their preferred environment while maintaining interoperability with the broader threat intelligence community.

### 4.4 TAXII Integration Approach

Rather than building FRANK as a pure TAXII implementation, a hybrid architecture would leverage TAXII's standardization benefits while preserving FRANK's unique collaborative features. This approach recognizes that TAXII serves as a mature transport protocol but lacks the sophisticated trust and reciprocity mechanisms essential to FRANK's value proposition.

**Core Platform Architecture**: The primary FRANK platform would operate as a custom application implementing contribution scoring, multi-tier access control, and dynamic anonymization capabilities. This layer handles the platform's innovative features: tracking submission quality metrics, enforcing reciprocal sharing requirements, and filtering data based on contributor trust levels.

**TAXII Gateway Layer**: A standards-compliant TAXII 2.1 server would provide an optional interface for organizations requiring protocol standardization. This gateway would translate between FRANK's internal data models and STIX objects, enabling integration with existing threat intelligence platforms while maintaining the platform's core functionality.

**Native API Endpoints**: Simplified REST and WebSocket APIs would serve the majority of users who prioritize ease of use over standards compliance. These interfaces would support FRANK's real-time capabilities and statistical aggregation features that extend beyond TAXII's scope.

This architectural separation allows FRANK to capture TAXII's interoperability advantages without constraining its innovative trust-based sharing model to fit within existing protocol limitations. The approach acknowledges that FRANK's core innovation lies in solving collaboration barriers through anonymization and reciprocity mechanisms that no existing threat intelligence protocol adequately addresses.

### 4.5 Format Strategy Consideration

FRANK will initially implement a custom YAML/JSON format optimized for simplicity and adoption by Dutch MSPs and private organizations. This approach prioritizes accessibility over standardization, using concise schemas that reduce barriers for smaller organizations lacking dedicated threat intelligence expertise. The custom format directly supports FRANK's unique features like contribution scoring, multi-tier anonymization, and reciprocity tracking without the verbose overhead of STIX objects.

STIX export capabilities will be added in subsequent phases to enable integration with existing enterprise threat intelligence platforms. This dual-format strategy allows FRANK to maintain operational simplicity while providing standards compliance for organizations requiring interoperability. The conversion layer will map FRANK's internal data structures to appropriate STIX Domain Objects, Relationship Objects, and Cyber Observable Objects, ensuring no analytical value is lost during translation while preserving the platform's core usability advantages.

---

## 5. Functional Requirements

The FRANK platform requirements implement a three-phase maturity model that progressively builds trust and capability within the cybersecurity intelligence sharing community. Starting with basic observation (submissions) to establish platform viability, the system evolves to support customer/partner relationships that drive commercial adoption and finally implements sophisticated leveled access controls that enable high-value intelligence sharing. Each requirement addresses the fundamental challenge of balancing openness with security, ensuring that increased sharing capabilities are matched by appropriate trust mechanisms and operational controls.

### Phase 1: Basic Submissions Foundation

**FR-001: Threat Observable Submission**
Organizations must submit cyber observable objects (IP addresses, domains, file hashes, network patterns) with temporal context, confidence levels, and detection metadata through standardized APIs. Submissions require minimum viable metadata including submitter, submission timestamp, and numerical confidence. The platform validates submission format and completeness while preserving submitter towards others.

**FR-002: Anonymous Organization Registration**
Cyber Partners must register participating organizations (their clients) with anonymized identities while maintaining sufficient metadata for sector classification, geographic attribution, and contribution tracking without exposing organizational details. The system uses persistent pseudonymous identifiers that enable tracking while preventing correlation with real-world entities. Registration metadata supports threat landscape analysis and platform governance without compromising organizational privacy or competitive positioning.

**FR-003: Statistical Threat Aggregation**
System must generate real-time statistical views of threat landscape including sighting frequencies, geographic distribution, sector impact, and trend analysis while preserving contributor (submitter) anonymity. Statistical outputs provide community value for basic tier users while incentivizing higher-tier participation through enhanced detail and analytical depth.

**FR-004: Quality Assurance Automation**
System must automatically assess submitted intelligence quality through completeness scoring. Automated validation includes format compliance checking, duplicate detection. Quality metrics feed into contributor reputation scoring and access tier determination while providing feedback for submission improvement.

### Phase 2: Customer/Partner Integration

**FR-005: Multi-Level Data Anonymization**
System must apply graduated anonymization to threat intelligence based on requestor access level, ranging from statistical summaries for public users to detailed attribution data for trusted contributors. Anonymization techniques scale from aggregate statistics through pseudonymized indicators to full contextual intelligence based on established trust relationships. Implementation ensures that intelligence detail increases proportionally with demonstrated community contribution and platform engagement.

**FR-006: Advanced TLP-Based Disclosure Control**
Platform must implement granular disclosure restrictions aligned with FIRST TLP classifications, controlling not only who can access intelligence but also how recipients can utilize and redistribute information. Disclosure controls operate independently of access permissions, enabling fine-grained operational security while supporting collaborative defense initiatives. Implementation includes automated TLP propagation to downstream systems and audit trails for compliance verification.

**FR-007: Threat Intelligence Validation**
Platform must implement community-driven validation mechanisms for submitted intelligence including duplicate detection, cross-reference correlation with established threat intelligence sources, cross-reference verification, and false positive identification with reputation scoring. Validation workflows enable peer review of submissions through anonymized community feedback while maintaining submitter privacy and encouraging quality improvement. Validation outcomes directly influence contributor reputation scores and platform-wide intelligence confidence ratings.

**FR-008: Reciprocity Enforcement**
Platform must track contribution-to-consumption ratios per organization and enforce sharing requirements, preventing data extraction without proportional intelligence contribution. Reciprocity algorithms monitor consumption patterns and implement progressive access restrictions for organizations that exceed sustainable consumption-to-contribution ratios. Enforcement mechanisms include reduced intelligence detail, delayed access to real-time feeds, and tier demotion for persistent free-riding behavior.

### Phase 3: Advanced Leveled Access

**FR-009: Contribution-Based Access Control**
The platform must evaluate user contributions in real-time using weighted metrics (volume, quality, timeliness, false positive rates) to dynamically assign access tiers and filter data responses accordingly. Contribution scoring combines quantitative submission metrics with qualitative community validation feedback to create fair and transparent tier advancement pathways. Access tier determination directly impacts disclosure permissions, submission capabilities, and intelligence detail levels available to each organization.

**FR-010: Real-Time Threat Distribution**
System must provide live threat intelligence feeds to Partner and Core Member tiers through persistent connections with priority queuing and bandwidth management based on access level. Distribution architecture supports TLP-compliant sharing with automatic disclosure controls and recipient verification for sensitive intelligence categories. Feed prioritization ensures that high-confidence, time-sensitive intelligence reaches appropriate recipients with minimal latency while maintaining platform stability under load.

**FR-011: Cross-Platform Intelligence Integration**
System must interface with existing Dutch cybersecurity initiatives (Cyclotron, Melissa) for bidirectional intelligence sharing while maintaining platform anonymity requirements and preventing data duplication. Integration protocols preserve FRANK's anonymization model while enabling value exchange with established platforms through standardized threat intelligence formats. Bidirectional sharing enhances platform value proposition while respecting existing ecosystem relationships and avoiding competitive conflicts.

**FR-012: Threat Context Attribution**
Platform must enable linking of observable artifacts to malware families, threat actors, and attack campaigns with community validation and confidence scoring mechanisms. Attribution capabilities support high-tier intelligence development while maintaining appropriate confidence assessment and source protection through graduated disclosure controls. Community validation processes ensure attribution accuracy while enabling collaborative campaign tracking and threat actor profiling.

**FR-013: Enterprise Compliance and Audit**
System must enforce configurable retention policies per data type and user tier while providing automated data purging, audit trails, and GDPR compliance including right-to-erasure functionality. Compliance mechanisms support enterprise security requirements and regulatory obligations while maintaining platform operational integrity. Audit capabilities enable organizational risk management and regulatory reporting without compromising platform anonymity or operational security.

**FR-014: Advanced Quality Analytics**
Platform must provide sophisticated quality assessment including confidence calibration analysis, accuracy verification against known databases, contributor accuracy tracking, and false positive trend identification to maintain high-value intelligence standards. Advanced analytics support tier-based quality requirements and enable platform-wide intelligence reliability improvement through targeted feedback and contributor development. Quality analytics inform platform governance decisions and support continuous improvement of community-driven validation processes.

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Access Level** | Trust-based tier system (Public, Observer, Contributor, Partner, Core Member) that determines the detail and scope of threat intelligence available to platform users based on their contribution history and verification status. |
| **Attribution** | The analytical process of linking observed cyber threat indicators to specific threat actors, malware families, or attack campaigns through technical analysis and behavioral pattern correlation. |
| **Behavioral Analysis** | Advanced analytical capability involving identification of novel attack patterns, previously unknown tactics, techniques, and procedures (TTPs), or innovative defensive insights that advance community knowledge. |
| **Confidence Assessment** | Numerical scoring system (0-100) aligned with NATO STANAG and US Intelligence Community standards that indicates the analytical certainty and evidence quality of submitted threat intelligence. |
| **Contribution Scoring** | Weighted metrics system that evaluates user submissions based on volume, quality, timeliness, and false positive rates to determine access tier progression and platform privileges. |
| **Core Member** | Highest access tier with complete platform access including mitigation effectiveness data, infrastructure details, campaign coordination capabilities, and platform governance participation rights. |
| **Cyber Partner** | Verified organization that facilitates threat intelligence submission on behalf of their clients while maintaining client anonymity through the platform's pseudonymization mechanisms. |
| **Disclosure** | Operational controls governing how recipients can utilize, share, and redistribute accessed threat intelligence, operating independently of access permissions and based on FIRST TLP classifications. |
| **FIRST TLP** | Forum of Incident Response and Security Teams Traffic Light Protocol classification system (RED, AMBER+, AMBER, GREEN, CLEAR) that controls information sharing and disclosure permissions. |
| **FRANK** | Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling - the threat intelligence sharing platform designed to address private sector reluctance to participate in government-led cybersecurity initiatives. |
| **Hit-Target** | The organization or entity that was the intended target or actual victim of a cyber threat incident described in a submission. |
| **Intelligence Validation** | Community-driven mechanisms for verifying submitted threat intelligence through duplicate detection, cross-reference verification, false positive identification, and peer review processes. |
| **Observable** | Technical cyber threat indicators such as IP addresses, domain names, file hashes, network patterns, or other artifacts that can be detected and shared across the security community. |
| **Pseudonymization** | Technical process of replacing identifying information with artificial identifiers while maintaining the ability to track contributions and reputation without revealing organizational identity. |
| **Reciprocity** | Platform enforcement mechanism that tracks contribution-to-consumption ratios and prevents organizations from extracting intelligence value without providing proportional contributions to the community. |
| **SIGMA Rule** | Community-developed detection rules written in the SIGMA format that enable automated threat detection deployment across multiple security platforms and environments. |
| **Sighting** | Instance of observing a specific cyber threat indicator or behavior within an organization's environment, representing the basic unit of threat intelligence contribution. |
| **STIX** | Structured Threat Information eXpression standard format for representing cyber threat intelligence that FRANK supports for interoperability with existing enterprise platforms. |
| **Submission** | Complete threat intelligence contribution to the FRANK platform, ranging from basic observables to advanced behavioral analysis, with associated metadata including confidence levels and temporal context. |
| **Submission Level** | Five-tier classification system (L1-L5) that categorizes threat intelligence contributions based on analytical sophistication and community value, from raw observables to behavioral pattern analysis. |
| **Submitter** | The Cyber Partner organization that contributes threat intelligence to the FRANK platform on behalf of their clients or their own organizational observations. |
| **TAXII** | Trusted Automated eXchange of Intelligence Information protocol that FRANK may support through a gateway layer for standards-compliant integration with existing threat intelligence platforms. |
| **Threat Context Attribution** | Advanced capability enabling linkage of observable artifacts to malware families, threat actors, and attack campaigns with community validation and confidence scoring mechanisms. |
| **TLP** | Traffic Light Protocol - FIRST classification system that controls information sharing permissions and disclosure restrictions for threat intelligence. |
| **Trust-Based Progression** | Core FRANK principle where access levels increase based on verified contributions and identity rather than payment or membership status alone. |

---

## Appendix B: Critical Information Sensitivity Assessment

The FRANK platform handles highly sensitive information that could compromise organizational security, reveal business relationships, or enable targeted attacks if inadequately protected. This analysis examines information sensitivity levels and appropriate access controls aligned with the platform's five-tier access model.

### B.1 Organizational Identity Data

**Risk Level: CRITICAL**
- `hit_target.organization_id`: Could enable reverse-engineering of actual customer identity through correlation attacks
- `customer_relationship.msp_provider`: Reveals business relationships between cyber partners and customers
- `client_count`: Provides competitive intelligence about cyber partner market position
- `organization_size`: Combined with sector and region, significantly narrows identification possibilities

**Anonymization Requirements:**
- Deterministic hashing with platform-specific salts to prevent rainbow table attacks
- Regular hash salt rotation to prevent long-term correlation
- Geographic generalization beyond city level
- Sector categorization rather than specific industry classification

### B.2 Operational Capability Intelligence

**Risk Level: HIGH**
- `detection_tool`: Reveals security stack composition and potential blind spots
- `mitigation_actions`: Exposes defensive capabilities and response procedures
- `containment_time`: Indicates organizational security maturity and response effectiveness
- `financial_impact_eur`: Provides competitive intelligence and potential extortion targets

**Access Control Requirements:**
- Limited to Partner tier and above for specific tool information
- Aggregated metrics only for Contributor tier and below
- No operational details for Observer/Public tiers

### B.3 Infrastructure and Technical Details

**Risk Level: HIGH**
- Internal IP addresses: Must be completely anonymized or generalized
- `network_behavior.beacon_interval`: Could enable attack timing optimization
- `technical_details.evasion_techniques`: Reveals detection gaps and blind spots
- `affected_systems`: Indicates network topology and critical asset distribution

**Mitigation Strategy:**
- Replace specific internal IPs with anonymized network ranges
- Generalize timing information to prevent attack optimization
- Aggregate technical details to prevent capability mapping

### B.4 Information Sensitivity by Access Tier

#### Public Access (Risk Tolerance: MINIMAL)

**Permitted Information:**
- Statistical aggregates only (total counts, percentages)
- Geographic data at country level
- Broad threat categories without attribution
- General timeline information (weekly/monthly trends)

**Prohibited Information:**
- Any specific observables or technical details
- Organizational identifiers or relationships
- Operational procedures or response capabilities
- Precise timing or frequency data

#### Observer Access (Risk Tolerance: LOW)

**Additional Permitted Information:**
- Obfuscated IP ranges (first two octets only)
- Domain patterns with wildcards
- Regional-level geographic data
- Weekly aggregated operational metrics

**Critical Restrictions:**
- No customer relationship data
- No specific tool or capability information
- No precise impact measurements
- No attribution beyond malware family names

#### Contributor Access (Risk Tolerance: MODERATE)

**Additional Permitted Information:**
- Partial observable data with anonymization
- Basic impact metrics (affected systems count, general damage assessment)
- MITRE ATT&CK technique mapping
- Campaign attribution with confidence levels

**Enhanced Protections:**
- Customer relationships remain anonymized
- Specific tool capabilities generalized
- Financial impact data categorized rather than precise
- Geographic data limited to regional level

#### Partner Access (Risk Tolerance: HIGH)

**Additional Permitted Information:**
- Complete observable data with full context
- Detailed impact assessments including financial data
- Infrastructure details and hosting information
- Full threat actor attribution and campaign analysis

**Residual Restrictions:**
- Customer identity protection through persistent anonymization
- Sensitive operational procedures may be summarized
- Internal network topology generalized

#### Core Member Access (Risk Tolerance: CONTROLLED HIGH)

**Additional Permitted Information:**
- Cross-organizational correlation data
- Platform analytics and contributor metrics
- Coordination capabilities for active threats
- Complete technical and operational context

**Enhanced Responsibilities:**
- Governance participation requirements
- Significant contribution obligations
- Community validation responsibilities
- Platform integrity protection duties

---

*Document converted from FRANK High Level Design (1).docx*
*Original date: 10-08-2025*
