# FRANK – AWS MVP Implementatiehandleiding

Dit document beschrijft per AWS-onderdeel wat je moet inrichten om het FRANK‑MVP (sightings delen, (anonieme) statistieken) werkend te krijgen. Het is geschreven voor een overwegend serverless architectuur.

Assumpties
- Doel: ingest van sightings, pseudonimisering, opslag, aggregatie en query/rapportage.
- Security-by-default: alles versleuteld met KMS, geen publieke S3‑toegang, least privilege IAM.
- Gefaseerde aanpak

Inhoud
- MVP core services
- Security & compliance
- Observability & operations
- Data governance & lifecycle
- Integraties & respons (optioneel)
- Schaalbaarheid (optioneel of latere fase)
- DevOps & IaC
- Kostenbewaking

------------------------------------------------------------

## MVP core services

### Amazon API Gateway (REST)
Doel: Ingest van sightings, query van statistieken, distributie van SIGMA‑artefacten.
- Endpoints
  - POST /v1/submissions (push door deelnemers van sightings)
  - GET /v1/stats (geaggregeerde statistieken, filterbaar)
- Configuratie
  - Authorizer: Cognito JWT authorizer (User Pool).
  - Request/response models en schema‑validatie (JSON Schema).
  - Throttling per method + Usage Plans/ API Keys voor partners indien nodig.
  - Stages: dev, test, prod; stage variables (bijv. target Lambda alias).
  - Access logs + execution logs naar CloudWatch.
  - Koppeling met AWS WAF (zie Security).
  - CORS alleen op lees‑API’s en strikt (origine, methoden, headers).

### Amazon Cognito
Doel: Authenticatie/authorisatie van klanten en service‑clients.
- User Pool + App Client (no secret, JWT).
- Custom attributes: submitter_id, sector.
- Groepen/rollen per submitter of rol (publisher, reader).
- Resource Server + scopes (bijv. stats.read, sightings.write).
- Policies: API Gateway method mapping op scopes/claims.
- Beveiliging: MFA aan, password policy, risicodetectie.
- JWKS endpoint gebruiken in API Gateway authorizer.

### AWS Lambda
Doel: Serverless verwerking.
- Functies (minimaal)
  - ingest_submissions (van sightings): validatie, normalisatie (schema), deduplicatie (idempotency), pseudonimisering.
  - write_persistence: schrijf naar S3 (raw) + update DynamoDB aggregaten + indexeer in OpenSearch.
  - query_stats: lees aggregaten (DynamoDB/OpenSearch) en geef geanonimiseerde statistieken terug.
- Techniek
  - Runtime: Python (met AWS Powertools voor logging/metrics/tracing).
  - Timeouts bewust (ingest < 10s), memory tunen, provisioned/RC indien nodig.
  - DLQ (SQS) en retry policy.
  - IAM‑rol per functie (least privilege).
  - Omgevingsvariabelen voor bucket‑namen, tabel‑namen, KMS‑key‑ARN’s.
  - Idempotency: DynamoDB tabel of Powertools layer.

### AWS Key Management Service (KMS)
Doel: Sleutelbeheer voor data‑encryptie en HMAC‑pseudonimisering.
- Customer managed keys (CMK’s)
  - frank-s3-key: S3 SSE‑KMS voor buckets.
  - frank-ddb-key: DynamoDB encryptie.
  - frank-os-key: OpenSearch at‑rest encryptie (indien ondersteund in regio).
  - frank-app-key: afscherming van HMAC‑seeds/secret; optioneel data‑keys via KMS GenerateDataKey.
- Policies en grants
  - Toegang beperken tot specifieke IAM‑rollen (Lambda/ECS).
  - Key rotation aan (jaarlijks).
  - CloudTrail integratie voor KMS events.

### Amazon S3
Doel: Data lake en artefactopslag.
- Buckets (voorbeeldnamen)
  - s3://frank-raw-<env> (raw submissions; partitionering: submitter_id=…/date=YYYY/MM/DD/)
  - s3://frank-exports-<env> (rapporten/exports)
- Config
  - Block Public Access: aan.
  - Versioning: aan.
  - Default SSE‑KMS met frank-s3-key.
  - Bucket policies: alleen via specifieke rollen/VPC endpoints.
  - Lifecycle policies: hot→standard‑IA→Glacier, retentie per dataset.
  - Event notifications (S3→EventBridge of S3→Lambda) bij artefact updates.

### Amazon DynamoDB
Doel: Hot aggregaten, submitter, idempotency.
- Tabellen
  - frank-aggregates: PK = ioc#type (of composite), SK = timebucket#sector#submitter (naar behoefte). GSIs voor andere query‑paden.
  - frank-submitters: PK = submitter_id; metadata (sector, status, retentie, beleid).
  - frank-idempotency: request_key TTL.
- Config
  - On‑Demand (start) of autoscaling; WCU/RCU alarms.
  - TTL op vluchtige items (idempotency, temp aggregates).
  - PITR aan.
  - SSE‑KMS met frank-ddb-key.

### Amazon OpenSearch Service
Doel: Interactieve zoek/visualisatie van sightings en context.
- Domein
  - VPC‑gebaseerd (private subnets), SG’s beperken tot Lambda/ECS/Jump.
  - Data nodes kleinschalig starten (bijv. t3.small.search) en groeien op gebruik.
  - Encryptie at rest (KMS) + node‑to‑node encryption.
- Security
  - Fine‑grained access control (FGAC) aan.
  - Master user via IAM of internal user db; IAM‑policies per rol.
  - Audit/slow logs aan naar CloudWatch.
- Indices en lifecycle
  - Index per env en eventueel per submitter (frank-sightings-<submitter>-YYYY.MM).
  - ISM/ILM policies (rollover op grootte/tijd, retentie).
  - Index templates en mappings (IoC velden, sector, tijd).
- Dashboards
  - OpenSearch Dashboards met read‑only rollen voor analisten.

### AWS Step Functions
Doel: Orkestratie van jobs en beheerflows.
- State machines
  - SubmitterOffboard: revoke creds → purge S3 prefixes → delete OS‑indices → invalideren aggregaten → audit log.
  - ReportGenerate: Athena query → S3 export → sign URL return.
- Instellen
  - Logging (level: all) en X‑Ray tracing.
  - Retry/backoff en fallback paden.
  - IAM‑rol met beperken tot benodigde acties.

### Amazon ECS (Fargate)
Doel: Containerized taken (sigma‑tools e.d.).
- Task definition
  - Image uit Amazon ECR (sigma‑cli + tooling).
  - CPU/memory passend (bijv. 0.5 vCPU/1GB voor kleine jobs).
  - Env vars: S3 paden, output bucket, KMS key ARN.
  - IAM task role: S3 read/write, KMS decrypt, CloudWatch logs.
- Service/RunTask
  - Geen long‑running service nodig: on‑demand RunTask via Step Functions.
  - Logging naar CloudWatch Logs.

------------------------------------------------------------

## Security & compliance

### AWS WAF + AWS Shield
- WAF web ACL koppelen aan API Gateway stage.
- Regels: AWS Managed rule groups, rate‑limiting per IP, size constraints, geo controls indien nodig.
- Logging naar CloudWatch of S3 (Kinesis Firehose).
- Shield Standard is standaard actief; evalueer Shield Advanced bij hoog risicoprofiel.

### AWS Secrets Manager
- Opslaan en roteren van externe API‑keys (MISP/TAXII) en partner secrets.
- Resource policies beperken per account/rol.
- Rotatie met Lambda rotator waar mogelijk.

### IAM
- Least privilege: aparte rollen per Lambda/ECS.
- Condition keys gebruiken (bijv. aws:ResourceTag/submitter_id).
- Service‑linked roles voor OS, WAF, etc.
- Access Analyzer en IAM Access Advisor periodiek nalopen.

### AWS CloudTrail, AWS Config, Security Hub, GuardDuty
- CloudTrail org‑breed, alle regio’s, S3 + CloudWatch Logs.
- AWS Config regels (encrypted volumes, public S3 = verboden, IAM best practices).
- Security Hub aan + standaard frameworks (CIS, Foundational).
- GuardDuty aan, findings naar SecOps.

### Amazon Macie
- Classificaties op S3 buckets (raw/artefacts) om PII/gevoelige data te detecteren.
- Findings naar Security Hub.

### Netwerk/VPC
- VPC endpoints (Gateway/Interface) voor S3, DynamoDB, OpenSearch, Secrets Manager.
- Security Groups: least privilege outbound/inbound.
- Private subnets voor ECS/Lambda (indien VPC‑enabled) met NAT of VPC endpoints.

------------------------------------------------------------

## Observability & operations

### Amazon CloudWatch
- Log groups per Lambda/ECS, retention ingesteld (bijv. 30–90 dagen).
- Metrics en metric filters (error rates, throttles, 4xx/5xx van API Gateway).
- Alarms naar SNS/Slack (via Chatbot) voor SLO/SLA events.
- Dashboards: ingest throughput, latency, DynamoDB RCUs/WCUs, OS cluster health.

### AWS X‑Ray
- Tracing aan op API Gateway, Lambda, Step Functions voor end‑to‑end latency inzicht.

### AWS Systems Manager
- Parameter Store voor niet‑geheime configuratie.
- Runbooks voor incident/operational tasks.
- OpsCenter integratie met alarms.

### AWS Backup
- DynamoDB back‑up plannen (dagelijks, retentie).
- OpenSearch: gebruik managed snapshots naar S3 (plan en test restore).
- S3: versiebeheer + lifecycle (AWS Backup is beperkt voor S3; gebruik object lock indien vereist).

------------------------------------------------------------

## Data governance & lifecycle

### AWS Glue + Amazon Athena
- Glue Data Catalog: tabellen op s3://frank-raw-*/ (partitions: submitter_id, datum).
- Crawlers of handmatige schema’s (voorkomen van schema drift).
- Athena workgroup met query resultaten in s3://frank-exports-*/athena/.
- Toegang via Lake Formation (row/column‑level policies indien nodig).

### Lake Formation (optioneel, maar aanbevolen)
- Centraal rechtenbeheer voor S3 data lake.
- Toegang per submitter/rol naar tabellen/kolommen.

### Retentie en verwijdering
- S3 lifecycle per dataset, conform beleid per submitter.
- DynamoDB TTL voor tijdelijke items; periodieke jobs voor “hard delete” waar vereist.
- OpenSearch ILM: cold/warm/force delete na afgesproken termijn.

------------------------------------------------------------

## Integraties & respons (optioneel/fase 2)

### Amazon EventBridge
- Event bus voor interne events (submitter.revoked, sighting.ingested).
- Scheduler rules voor periodieke MISP/TAXII pulls.

### MISP/TAXII ingest (Lambda)
- Pullers die IoC’s ophalen, dedupliceren en plaatsen in S3 (artefacts).
- Secrets in Secrets Manager; backoff/retry; observability.

### Distributie
- Amazon SNS topics voor notificaties (nieuwe IoC/SIGMA), of EventBridge partner events.
- Signed S3 URLs voor rule‑packs.

### CACAO (respons)
- Opslag van playbooks in S3; orkestratie met Step Functions of Systems Manager Automation.
- In deze fase “pull/handmatig” verwacht; documenteer beperkingen.

------------------------------------------------------------

## Schaalbaarheid (optioneel of latere fase)

### Amazon Kinesis Data Streams + Kinesis Data Analytics
- Data Streams voor hoge ingest (shard‑based scaling).
- Flink jobs voor sliding‑window aggregaties (counts per IoC/sector/tijd).

### Caching
- API Gateway caching op lees‑API’s met zorg (multi‑submitter isolatie).
- CloudFront voor statische dashboards/artefact downloads (indien publiek gedeeld, anders liever niet).

### Datastores
- DynamoDB On‑Demand → autoscaling met alarmen.
- OpenSearch: nodes/schijven schaalbaar; UltraWarm/Cold voor kostenreductie.

------------------------------------------------------------

## DevOps & IaC

### CI/CD
- CodeCommit/CodeBuild/CodePipeline of GitHub Actions + OIDC.
- Quality gates: linting, tests, security scans (cfn‑nag/checkov, trivy).
- Deploy per environment met approvals.

### Infrastructure as Code
- CloudFormation (SAM/CDK) of Terraform (met staat in S3 + DynamoDB lock).
- Service Catalog voor herbruikbare stacks (bijv. “frank-submitter-onboard”).

### Container registry
- Amazon ECR voor ECS images; immutability en scan on push.

------------------------------------------------------------

## submitter governance & offboarding

### Pseudonimisering/anonymisering
- Deterministische HMAC‑SHA256 over bronidentifiers met submitter‑specifieke salt/secret (beschermd door KMS).
- Alleen geaggregeerde/anonieme data beschikbaar via publieke query‑API.

### Offboarding flow (Step Functions)
- Revoke credentials (Cognito/Keys) → Purge S3 prefixes → Delete OS indices → Markeer/regenereer aggregaten → Auditlog.
- Verwijder alle submitter‑gebonden metadata in DynamoDB (behoud referentie‑audit waar wettelijk geoorloofd).

------------------------------------------------------------

## Kostenbewaking

### Budgetten en tagging
- AWS Budgets met e‑mail/Slack alerts.
- Cost Allocation Tags (project=frank, env, submitter).
- Cost Explorer dashboards per service.

### Optimalisaties
- DynamoDB On‑Demand in MVP, later vast/auto‑scale tunen.
- OpenSearch sizing conservatief starten; verplaats historisch naar UltraWarm/Cold of S3+Athena.
- S3 lifecycle agressief instellen op raw/log data.

------------------------------------------------------------

## Snelle checklist (MVP volgorde)

1) Cognito (User Pool, app client, groepen, claims).  
2) KMS keys (S3, DDB, OS, app/HMAC).  
3) S3 buckets (raw, artefacts, exports) met SSE‑KMS, versioning, lifecycle.  
4) DynamoDB (aggregates, submitters, idempotency) met TTL, PITR.  
5) OpenSearch domain (VPC, FGAC, ILM, dashboards).  
6) Lambda functies (ingest, write, query, sigma_update) + roles + logs.  
7) API Gateway (routes, models, authorizer, throttling, logs) + WAF.  
8) Step Functions + ECS Fargate taak voor sigma‑tooling.  
9) Security services (CloudTrail, Config, Security Hub, GuardDuty, Macie).  
10) Observability (CloudWatch alarms/dashboards, X‑Ray).  

Vervolg (fase 2): EventBridge + MISP/TAXII pullers, SNS/EventBridge distributie, CACAO orkestratie.
