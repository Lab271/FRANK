# FRANK Evolving Design Approach

## Philosophy: Structured Evolution Over Big-Bang Development

FRANK (Feedback Infrastructure for Cyber Risk Analysis and Network Knowledge sharing) demonstrates a **structured evolutionary approach** to software development that separates infrastructure complexity from functional complexity while maintaining working systems at every stage.

Rather than attempting to build the complete system in one go, FRANK evolves through deliberate stages where each stage maintains a fully working system, introduces one major complexity dimension at a time, provides fallback options to previous stages, and enables confident experimentation through comprehensive testing.

A fundamental aspect of this evolutionary strategy is maintaining one single code library (`src/frank/`) that contains all business logic, data models, and core functionality. This unified library serves as the stable foundation that persists across all infrastructure stages. The library structure encompasses models for data structures, validation for business rules, processing for core threat intelligence logic, repositories for database abstraction interfaces, and serialization for YAML/JSON conversion utilities. This approach ensures the same `frank` library code runs unchanged from SQLite in Stage 1 to ScyllaDB in Stage 4. Infrastructure changes require only new repository implementations while business logic remains completely isolated from deployment concerns.

The benefits of this single library approach include consistency where the same behavior is guaranteed across all stages, testability where core logic is tested once and works everywhere, maintainability where bug fixes and features are applied universally, confidence where infrastructure changes cannot break business logic, and velocity where the team focuses on business value rather than infrastructure porting.

## Four-Stage Infrastructure Evolution

FRANK evolves through four distinct stages, each building upon the previous while introducing controlled complexity. Stage 1 uses SQLite database with FastAPI compute on a local laptop, serving as the foundation and proof of concept while focusing on core business logic and data models. Stage 2 transitions to MySQL or DynamoDB with FastAPI running on LocalStack and Docker, emphasizing AWS service patterns with learning focused on database abstraction and containerization.

Stage 3 moves to DynamoDB with ECS compute in AWS Cloud for cloud-native deployment, concentrating on containerized patterns and real AWS services. Stage 4 adopts ScyllaDB or MongoDB with FastAPI or Go on Kubernetes for a cloud-agnostic stack, prioritizing vendor independence and scalability.

The evolution prioritizes infrastructure learning before functional complexity. Stages 1 and 2 maintain a simple submission model while focusing on infrastructure learning. Stage 3 introduces complex submission models with stable cloud infrastructure. Stage 4 delivers the full feature set with production optimization. Working fallbacks are maintained at every stage where Stage 1 remains the development baseline, each stage can fall back to the previous working configuration, and there is no "point of no return" during evolution.

## Test-Driven Evolution Strategy

FRANK employs a comprehensive testing strategy with three distinct layers that create a safety net enabling confident evolution. Unit tests provide fast, isolated component testing of individual functions, classes, and modules with execution times under 100ms per test. These tests offer high coverage of business logic and enable fearless refactoring.

Integration tests deliver system confidence by testing component interactions and data flow, validating database operations, API endpoints, and external services while ensuring cross-boundary behavior and system coherence during evolution. Spike tests provide exploration confidence by validating new technologies and patterns before adoption. These proof-of-concept implementations reduce risk for architectural decisions while capturing knowledge for future reference.

Database abstraction allows the same business logic to work across different storage technologies, with comprehensive tests ensuring all implementations behave identically. This approach enables safe technology transitions while maintaining system reliability. New requirements trigger spike implementations for validation before integration. If a spike fails, the team tries a different approach. If a spike succeeds, they build the production implementation. This pattern provides risk reduction through early validation, knowledge acquisition before commitment, and clear go/no-go decision points.

## Functional MVP Evolution

Each functional evolution is captured as a Git version tag, enabling precise tracking of capability growth. Version 0.1.0 establishes minimal viable threat intelligence with basic submission models, simple confidence scoring, and organization identity management. Version 0.2.0 introduces enhanced observables with complex observable types covering network, file, and behavioral data, observable relationships and context, plus improved validation and error handling. Version 0.3.0 adds threat context including campaign attribution, threat actor profiling, and attack context with TTPs.

Version 0.4.0 implements sharing intelligence with multi-organization sharing levels, privacy controls and anonymization, and collaborative threat hunting features. Version 1.0.0 delivers the production intelligence platform with full STIX/TAXII compatibility, real-time threat feeds, and advanced analytics and reporting.

Each MVP represents a complete, deployable system with no "work in progress" states in version tags, ensuring immediate value delivery to users. Each version adds meaningful capability while maintaining backward compatibility where possible and providing clear migration paths between versions. The system employs abstract interfaces that enable evolution, where database abstractions define methods for saving submissions and querying data, with concrete implementations for SQLite, DynamoDB, and ScyllaDB. This approach enables technology switching without business logic changes, A/B testing of different implementations, and gradual migration capabilities.

## Key Success Factors

Success in evolutionary development requires maintaining working systems by never breaking the current working stage while building the next, always having a deployment-ready version available, and using feature flags for gradual rollouts. The approach demands keeping infrastructure complexity separate from functional complexity, database technology separate from business logic, and deployment environment separate from application code.

Comprehensive testing includes unit tests for component reliability, integration tests for system reliability, spike tests for technology validation, and performance tests for scalability validation. The strategy requires Git tags for functional milestones, Docker tags for deployment artifacts, database schema versions for data migration, and configuration versions for environment management.

Documentation is integral to evolutionary development, not an afterthought. FRANK employs a multi-layered documentation strategy that captures knowledge at different levels of abstraction and serves different audiences. Code-level documentation through comprehensive docstrings captures API contracts, provides concrete examples for developer onboarding, documents explicit error conditions to prevent debugging sessions, and makes breaking changes immediately obvious during evolution.

Spike documentation accompanies every spike test with detailed markdown files capturing the hypothesis, implementation approach, results including both successes and failures, and final decisions. This preserves decision rationale for future developers, prevents re-learning the same lessons, documents risk assessments, and provides blueprints for production implementation.

High-level design documentation in the docs folder organizes content into architecture, design, infrastructure, and decisions sections. These living documents are updated with each architectural evolution, maintain audience-specific technical depth, capture decision records for major choices, and provide cross-references between related concepts and implementations.

Architecture principles, while planned for future implementation, will document numbered principles that ensure consistency in team decisions, provide trade-off guidance with clear criteria for evaluating design alternatives, support onboarding by helping new team members understand system philosophy, and guide evolution while preventing architectural drift.

## Benefits of Evolutionary Approach

The evolutionary approach provides incremental learning that reduces big failure risks, working fallbacks that provide safety nets, and early validation that prevents costly mistakes. This strategy enables always deployable systems, incremental value delivery, and faster feedback cycles. Teams learn new technologies gradually, see architectural patterns emerge organically, and address technical debt continuously. The approach provides demonstrable progress at every stage, clear milestone achievements, and predictable delivery timelines.

## Conclusion

The FRANK evolutionary approach demonstrates that complex systems can be built incrementally without sacrificing quality or velocity. By separating infrastructure evolution from functional evolution, maintaining comprehensive test coverage, and ensuring working systems at every stage, teams can confidently navigate technological complexity while delivering continuous value.

This approach is particularly powerful when combined with AI-assisted development, where the safety net of tests and abstractions enables aggressive experimentation and rapid iteration while maintaining system reliability.