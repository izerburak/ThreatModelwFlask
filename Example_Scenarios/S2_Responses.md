# Threat Modeling Questionnaire Answers
System: Online Healthcare Appointment Platform

## Layer 1 – Scope & Context (Outer Boundary)

1. Primary business function
   - Selected: Healthcare management, Communication/messaging, Financial transactions

2. System lifecycle stage
   - Selected: Production (mature)

3. Expected system scale
   - Selected: Medium (1K–100K users/day)

4. Deployment location
   - Selected: Public cloud (AWS/Azure/GCP)

5. Network accessibility
   - Selected: Mixed (some components public, some internal)

6. Geographic constraints
   - Selected: Multi-regional, with specific healthcare/data protection regulatory jurisdictions

7. Business impact if system is unavailable
   - Selected: High (revenue loss)

8. Business impact if data is compromised
   - Selected: Critical (business existence threat)


## Layer 2 – Actors & External Entities

9. End user types
   - Selected: Employees (internal staff), Customers (external users), Partners/vendors, System administrators, Auditors/compliance officers

10. User roles with administrative privileges
    - Selected: System administrators, Database administrators, Application administrators, Security administrators, Business administrators

11. Automated actors
    - Selected: Internal automation/scripts, Partner API integrations, Third-party service calls, Monitoring/health check systems

12. External services the system depends on
    - Selected: Authentication providers (LDAP, OAuth, SAML), Payment processors, Email/SMS services, Cloud storage services, CDN/hosting services, Analytics/tracking services, Government/regulatory APIs (where applicable)

13. External systems that consume data from this system
    - Selected: Reporting/BI systems, Partner systems, Regulatory reporting systems, Backup/archival systems, Monitoring/SIEM systems

14. Relevant threat actors
    - Selected: Script kiddies (opportunistic), Organized cybercriminals, Insider threats (malicious employees), Competitors, Disgruntled customers/users, (in some regions) Nation-state actors


## Layer 3 – Data Assets & Classification

15. Types of personal data processed
    - Selected: Names, contact information; Financial information (via payment provider tokens/identifiers); Health/medical records; Location data (clinic, approximate region, IP/geolocation); Behavioral/usage data

16. Business-critical data stored
    - Selected: Customer databases, Financial records, Audit logs, Configuration data, Strategic business information related to clinic performance

17. Overall data sensitivity classification
    - Selected: Secret (severe harm if disclosed)

18. Primary data storage locations
    - Selected: Relational databases (PostgreSQL or similar), NoSQL/datastore for caching/session (Redis, etc.), File systems/object storage for documents (S3-like), In-memory caches

19. Data flow mechanisms
    - Selected: REST APIs, Message queues, Direct database connections (from application layer), Batch processing (imports/exports, lab sync, reporting)

20. Data retention policy
    - Selected: Legal/regulatory requirements dictate retention (e.g., health record retention periods, financial record retention)


## Layer 4 – System Components & Architecture

21. Main application tiers
    - Selected: Web frontend (HTML/JS/React), Mobile applications (iOS/Android), API gateway/reverse proxy, Application servers, Background job processors, Microservices

22. Programming languages/frameworks used
    - Selected: JavaScript/Node.js (API and services), Python (Flask/Django-based services), Other: React for frontend clients

23. Deployment architecture
    - Selected: Microservices architecture, Container-based (Docker/Kubernetes)

24. Infrastructure components
    - Selected: Load balancers, Web application firewalls (WAF), Content delivery networks (CDN), API gateways, Message brokers, Caching layers

25. Component interconnection
    - Selected: Direct HTTP/HTTPS calls, Message queues, Event-driven architecture, Database connections

26. Single points of failure
    - Selected: Primary database, Authentication service, Payment processor, External API dependencies (lab systems, SMS/e-mail), Load balancer (if not highly available)


## Layer 5 – Security Controls & Compliance

27. User authentication methods
    - Selected: Username/password, Multi-factor authentication (MFA) for higher-risk roles and optional for patients, Single sign-on (SSO) for clinical staff, API keys/tokens for service-to-service and integrations

28. Authorization model
    - Selected: Role-based access control (RBAC) with roles such as patient, doctor, clinic staff, clinic admin, platform admin, auditor

29. Data protection in transit
    - Selected: TLS/HTTPS for all communications (external and internal where possible), VPN for certain internal/partner connections

30. Data protection at rest
    - Selected: Database-level encryption, File system/Object storage encryption, Key management service (KMS/HSM)

31. Security monitoring in place
    - Selected: Application logging, SIEM integration, IDS/IPS (network or host-based), WAF logs, User behavior analytics (for privileged users and anomalous access)

32. Applicable regulatory frameworks
    - Selected: GDPR (where applicable), HIPAA, PCI DSS (for payment aspects), KVKK (for Turkey), ISO 27001 (as target ISMS framework)


## Layer 6 – Operations & Maintenance

33. SDLC approach
    - Selected: Agile/Scrum with DevOps/CI/CD practices, progressively moving towards DevSecOps

34. Code deployment
    - Selected: Automated CI/CD pipelines, Rolling updates, Blue/green or canary deployments for critical services

35. Patch management process
    - Selected: Regular maintenance windows with scheduled patching, some automated patching for infrastructure, ad-hoc emergency patching for critical vulnerabilities

36. Backup strategy
    - Selected: Regular automated backups, Cloud-based backups, Replicated databases

37. Disaster recovery plan
    - Selected: Documented recovery procedures, Hot or warm standby systems in secondary region, Cloud-based disaster recovery capabilities

38. Security incident handling
    - Selected: Formal incident response plan, Incident response team, Some use of third-party response/forensics services for major incidents


## Layer 7 – LLM Output Guidance & Threat Hypotheses

39. Data flows crossing the most trust boundaries
    - Answer: Patient and doctor traffic from internet-facing web/mobile clients through the API gateway to internal microservices; data flows to/from external payment processors; data exchange with external lab systems over dedicated or internet links; notifications via third-party SMS/e-mail providers. These flows traverse boundaries between public internet, cloud DMZ, internal service networks, and third-party networks.

40. Components with the largest attack surface due to external connectivity
    - Answer: API gateway and internet-facing application services (web and mobile APIs); authentication endpoints; public endpoints for payment callbacks and lab result ingestion; notification webhooks and any exposed admin or SSO endpoints.

41. Most probable threats given known threat actors and capabilities
    - Answer: Credential stuffing and phishing against patient and doctor accounts; exploitation of web/API vulnerabilities (e.g., IDOR, injection, broken access control) for PHI access; misuse or abuse of public APIs (rate-limit/bot attacks); ransomware or data exfiltration via compromised admin accounts; misconfiguration of cloud storage leading to PHI exposure; DDoS against public endpoints impacting availability.

42. Existing controls that are likely insufficient for current threats
    - Answer: Basic RBAC and MFA may be inconsistently enforced across all roles; WAF and IDS/IPS coverage may not fully address business logic and access control flaws; monitoring and SIEM rules may miss low-and-slow data exfiltration or insider abuse; dependency on third-party services (labs, payment, notifications) may not be fully covered by vendor risk management and security SLAs.

43. Highest-impact threats lacking detection or prevention controls
    - Answer: Unauthorized access to large volumes of PHI via compromised privileged accounts or broken access control that is not adequately logged or alerted; subtle tampering with test results or prescriptions that affects patient safety but is difficult to detect; large-scale data exfiltration via misconfigured storage or outbound integrations; compromise of CI/CD or configuration management pipelines leading to malicious code deployment into production.
