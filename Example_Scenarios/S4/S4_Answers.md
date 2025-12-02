# Threat Modeling Questionnaire Answers
System: FinTech Payment Gateway

## Layer 1 – Scope & Context (Outer Boundary)

1. What is the primary business function of this system?
   - Selected: Financial transactions, E-commerce

2. What is the system's lifecycle stage?
   - Selected: Production (mature)

3. What is the expected system scale?
   - Selected: Large (100K–1M users/day)

4. Where is the system primarily deployed?
   - Selected: Public cloud (AWS/Azure/GCP)

5. What is the network accessibility?
   - Selected: Mixed (some components public, some internal)

6. What are the key geographic constraints?
   - Selected: Multi-regional

7. What is the business impact if this system is unavailable?
   - Selected: High (revenue loss), Critical (business shutdown)

8. What is the business impact if data is compromised?
   - Selected: Critical (business existence threat)

## Layer 2 – Actors & External Entities

9. What types of end users interact with the system?
   - Selected: Employees (internal staff – ops, risk, support), Customers (external users – cardholders on hosted payment pages), Partners/vendors (merchant operators, PSP partners), System administrators, Auditors/compliance officers

10. Which user roles have administrative privileges?
   - Selected: System administrators, Database administrators, Application administrators, Security administrators, Business administrators (merchant onboarding, limits, pricing)

11. Are there automated actors (bots, scripts, APIs)?
   - Selected: Internal automation/scripts (reconciliation, settlement, batch jobs), Partner API integrations (merchant backends calling payment APIs), Third-party service calls (acquirer/bank APIs, card schemes, 3DS), Monitoring/health check systems

12. Which external services does the system depend on?
   - Selected: Authentication providers (LDAP, OAuth, SAML), Payment processors (acquirers, card schemes, alternative payment methods), Email/SMS services (OTP, alerts, notifications), Cloud storage services (log archiving, backups), CDN/hosting services (for payment pages, static assets), Analytics/tracking services (fraud analytics, business reporting)

13. Which external systems consume data from this system?
   - Selected: Reporting/BI systems, Partner systems (merchant reporting portals, ERP), Regulatory reporting systems (for financial regulators/card schemes), Backup/archival systems, Monitoring/SIEM systems

14. Which threat actors are most relevant to your business domain?
   - Selected: Script kiddies (opportunistic scanning of APIs/endpoints), Organized cybercriminals, Nation-state actors, Insider threats (malicious employees or contractors), Competitors, Hacktivists

## Layer 3 – Data Assets & Classification

15. What types of personal data are processed?
   - Selected: Names, contact information (billing details, email, phone), Financial information (credit cards, bank accounts, tokens), Location data (billing/shipping country, IP geolocation), Behavioral/usage data (transaction history, fraud signals)

16. What business-critical data is stored?
   - Selected: Customer databases (cardholders, merchants), Financial records (authorizations, captures, settlements, chargebacks), Intellectual property (fraud scoring models, risk rules), Trade secrets (pricing models, routing strategies), Strategic business information (merchant performance, volumes), Audit logs (admin actions, security events, transaction logs), Configuration data (routing rules, risk thresholds, API keys metadata)

17. How would you classify the overall data sensitivity?
   - Selected: Secret (severe harm if disclosed)

18. Where is data primarily stored?
   - Selected: Relational databases (MySQL, PostgreSQL, etc.) – core transactional data, NoSQL databases (Redis, etc.) – sessions, caching, rate limits, File systems (local, network shares) – logs, temp files, Cloud storage (S3, Azure Blob, etc.) – long-term log/archive storage, In-memory caches

19. How does data flow between components?
   - Selected: REST APIs (merchant integrations, internal microservices), Message queues (RabbitMQ/Kafka for async processing, eventing), Direct database connections (internal services to DB), Real-time streams (fraud events, monitoring feeds)

20. What is the data retention policy?
   - Selected: Long-term (years), Legal/regulatory requirements dictate retention (card scheme & financial regs)

## Layer 4 – System Components & Architecture

21. What are the main application tiers?
   - Selected: Web frontend (HTML/JS – merchant portal, hosted payment pages), API gateway/reverse proxy (public payment APIs), Application servers (transaction processor, merchant portal backend), Background job processors (settlement, reconciliation, reporting), Microservices (fraud detection, tokenization, routing)

22. Which programming languages/frameworks are used?
   - Selected: JavaScript/Node.js (API gateway, some microservices), Java (Spring) (core transaction processing, integration services)

23. What is the deployment architecture?
   - Selected: Microservices architecture, Container-based (Docker/Kubernetes)

24. Which infrastructure components are used?
   - Selected: Load balancers, Web application firewalls (WAF), Content delivery networks (CDN), API gateways, Service mesh (for east–west traffic control/observability), Message brokers, Caching layers

25. How are components interconnected?
   - Selected: Direct HTTP/HTTPS calls, Service mesh (mTLS between services), Message queues, Event-driven architecture (payment/fraud events), Database connections

26. Which systems are single points of failure?
   - Selected: Primary database, Authentication service (SSO/IdP), Payment processor (acquirer/card network connectivity), External API dependencies (3DS, bank APIs), Load balancer / edge ingress layer

## Layer 5 – Security Controls & Compliance

27. How do users authenticate?
   - Selected: Username/password only (for some internal accounts, to be minimized), Multi-factor authentication (MFA) (required for admin/merchant console), Single sign-on (SSO) (for internal staff via IdP), API keys/tokens (for merchant API clients, service-to-service)

28. How is authorization managed?
   - Selected: Role-based access control (RBAC) (merchants, ops, risk, admin roles), Access control lists (ACL) (fine-grained rights on merchants/resources)

29. How is data protected in transit?
   - Selected: TLS/HTTPS for all communications (internet-facing APIs, portals), TLS for external communications only (legacy external bank links if any), VPN for internal communications (back-office/admin access)

30. How is data protected at rest?
   - Selected: Database-level encryption (cardholder data, PII), File system encryption (log and backup volumes), Application-level encryption (tokenization, field-level crypto for PAN), Key management service (HSM/KMS) (PCI-compliant key management)

31. What security monitoring is in place?
   - Selected: Application logging, Security information and event management (SIEM), Intrusion detection system (IDS), Intrusion prevention system (IPS) (network/edge), Web application firewall (WAF) logs, User behavior analytics (fraud & anomaly detection on transactions/logins)

32. Which regulatory frameworks apply?
   - Selected: PCI DSS (Payment Card Industry Data Security Standard), KVKK (Turkish Personal Data Protection Law), ISO 27001, Other: Local financial regulator requirements (e.g., banking/payment regs)

## Layer 6 – Operations & Maintenance

33. What is the software development lifecycle (SDLC) approach?
   - Selected: DevOps/CI/CD, DevSecOps (security integrated into pipelines)

34. How are code changes deployed?
   - Selected: Automated CI/CD pipelines, Blue/green deployments (for critical components like transaction processor), Canary deployments (for selected microservices)

35. What is the patch management process?
   - Selected: Automated patching (for base OS images, containers where possible), Regular scheduled maintenance windows (for DBs and core infra)

36. What is the backup strategy?
   - Selected: Regular automated backups (databases, configs), Cloud-based backup services, Replicated databases (multi-AZ/region where supported)

37. What is the disaster recovery plan?
   - Selected: Documented disaster recovery procedures, Hot standby systems (HA within primary region), Cold backup systems or secondary region (for regional outages)

38. How are security incidents handled?
   - Selected: Formal incident response plan, Incident response team (internal security/CSIRT), Third-party incident response service (on retainer for major breaches)
