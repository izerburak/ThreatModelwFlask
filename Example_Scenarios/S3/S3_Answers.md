# Threat Modeling Questionnaire Answers
System: Online Ride-Sharing & Mobility Platform

## Layer 1 – Scope & Context (Outer Boundary)

1. Primary business function  
   - Selected: Transportation-as-a-service, Location tracking, Communication/messaging, Financial transactions

2. System lifecycle stage  
   - Selected: Production (mature)

3. Expected system scale  
   - Selected: Large (100K–1M users/day)

4. Deployment location  
   - Selected: Public cloud (AWS/Azure/GCP)

5. Network accessibility  
   - Selected: Mixed (some components public, some internal)

6. Geographic constraints  
   - Selected: Multi-regional

7. Business impact if system is unavailable  
   - Selected: Critical (business shutdown)

8. Business impact if data is compromised  
   - Selected: High (financial/legal consequences)


## Layer 2 – Actors & External Entities

9. End user types  
   - Selected: Customers (passengers), Drivers, Employees (operations), Partners/vendors, System administrators, Auditors/compliance officers

10. User roles with administrative privileges  
    - Selected: System administrators, Database administrators, Application administrators, Security administrators, Business administrators

11. Automated actors  
    - Selected: Internal automation/scripts, Partner API integrations, Third-party service calls, Monitoring/health check systems

12. External services the system depends on  
    - Selected: Authentication providers (OAuth/OIDC), Payment processors, Email/SMS services, Cloud storage services, Map/navigation providers, Analytics services

13. External systems that consume data  
    - Selected: Reporting/BI systems, Partner systems, Backup/archival systems, Monitoring/SIEM systems

14. Relevant threat actors  
    - Selected: Script kiddies, Organized cybercriminals, Insider threats, Competitors, Hacktivists, Disgruntled customers/users


## Layer 3 – Data Assets & Classification

15. Types of personal data processed  
    - Selected: Names, contact information; Payment token info; Real-time and historical location data; Behavioral/usage data

16. Business-critical data stored  
    - Selected: Customer databases, Driver data, Payment and fare records, Audit logs, Configuration data

17. Overall data sensitivity classification  
    - Selected: Confidential (significant harm if disclosed)

18. Primary data storage locations  
    - Selected: Relational databases (PostgreSQL), NoSQL/caches (Redis), Object storage (documents, invoices), Geo-index/time-series stores

19. Data flow mechanisms  
    - Selected: REST APIs, Message queues, Real-time location streaming (WebSocket/gRPC)

20. Data retention policy  
    - Selected: Legal/regulatory requirements dictate retention


## Layer 4 – System Components & Architecture

21. Main application tiers  
    - Selected: Web frontend, Mobile apps, API gateway, Application services, Microservices, Background workers

22. Programming languages/frameworks used  
    - Selected: JavaScript/Node.js, Kotlin/Swift (mobile), Python (some services)

23. Deployment architecture  
    - Selected: Microservices on Kubernetes

24. Infrastructure components  
    - Selected: Load balancers, WAF, API gateways, Message brokers, Caching layers

25. Component interconnection  
    - Selected: Direct HTTPS calls, Message queues, Event-driven architecture, Database connections

26. Single points of failure  
    - Selected: Primary DB, Auth service, Payment processor, External map/navigation APIs, Load balancer (if not HA)


## Layer 5 – Security Controls & Compliance

27. User authentication methods  
    - Selected: Username/password, MFA, SSO (for fleet admins), OAuth tokens, API keys

28. Authorization model  
    - Selected: RBAC (passenger, driver, fleet manager, operations, admin)

29. Data protection in transit  
    - Selected: TLS/HTTPS everywhere

30. Data protection at rest  
    - Selected: DB encryption, Object storage encryption, KMS/HSM

31. Security monitoring  
    - Selected: Application logs, SIEM, IDS, WAF logs

32. Regulatory frameworks  
    - Selected: GDPR, KVKK, PCI DSS, ISO 27001


## Layer 6 – Operations & Maintenance

33. SDLC approach  
    - Selected: DevOps/CI/CD

34. Code deployment  
    - Selected: Automated CI/CD pipelines, Rolling updates

35. Patch management  
    - Selected: Regular maintenance windows

36. Backup strategy  
    - Selected: Automated backups, Cloud-based backups, Replicated DBs

37. Disaster recovery plan  
    - Selected: Documented procedures, Cloud DR

38. Security incident handling  
    - Selected: Formal IR plan, Incident response team


## Layer 7 – LLM Output Guidance & Threat Hypotheses

39. Data flows crossing the most trust boundaries  
    - Answer: Passenger/driver traffic from public clients through API gateway; payment processor integrations; map/navigation queries; SMS/e-mail notifications. These cross public internet, DMZ, internal networks, and third-party boundaries.

40. Components with the largest attack surface  
    - Answer: API gateway, mobile/web API endpoints, authentication endpoints, payment/webhook endpoints, real-time tracking service entry points.

41. Most probable threats  
    - Answer: Credential stuffing; API abuse; IDOR; Location data leakage; Payment fraud; Compromised driver/admin accounts; DDoS.

42. Insufficient existing controls  
    - Answer: RBAC inconsistencies, WAF not addressing business logic flaws, insufficient detection for slow data exfiltration, limited vendor risk controls (PSP/maps/SMS).

43. Highest-impact threats lacking detection  
    - Answer: Mass location data exfiltration; unauthorized access to driver or passenger data; manipulation of trip states or fare logic; compromise of CI/CD pipeline enabling malicious deployment.
