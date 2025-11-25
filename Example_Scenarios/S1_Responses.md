# Threat Modeling Questionnaire Answers
System: Smart Home IoT Management System

## Layer 1 – Scope & Context (Outer Boundary)

1. Primary business function  
   - Selected: Home automation / IoT device management, Data analytics/usage insights, Communication/messaging (alerts and notifications)

2. System lifecycle stage  
   - Selected: Production (mature)

3. Expected system scale  
   - Selected: Medium (1K–100K users/day)

4. Deployment location  
   - Selected: Public cloud (AWS/Azure/GCP)

5. Network accessibility  
   - Selected: Mixed (some components public, some internal)

6. Geographic constraints  
   - Selected: Multi-regional

7. Business impact if system is unavailable  
   - Selected: High (revenue loss)

8. Business impact if data is compromised  
   - Selected: Critical (business existence threat, privacy/safety impact)


## Layer 2 – Actors & External Entities

9. End user types  
   - Selected: Customers (home users), Employees (support/operations), Partners/vendors (device OEMs/integrators), System administrators, Auditors/compliance officers

10. User roles with administrative privileges  
    - Selected: System administrators, Application administrators, Security administrators, Business/tenant administrators

11. Automated actors  
    - Selected: Internal automation/scripts (schedules, rules, scenes), Partner API integrations (voice assistants, platforms), Third-party service calls (cloud messaging/storage), Monitoring/health check systems

12. External services the system depends on  
    - Selected: Authentication providers (OAuth/OIDC), Email/SMS/push notification services, Cloud storage services, CDN/hosting services, Analytics/tracking services, IoT/device management platforms (optional)

13. External systems that consume data  
    - Selected: Reporting/BI systems, Partner OEM portals, Backup/archival systems, Monitoring/SIEM systems

14. Relevant threat actors  
    - Selected: Script kiddies (IoT botnet operators), Organized cybercriminals, Nation-state actors, Insider threats, Competitors, Hacktivists


## Layer 3 – Data Assets & Classification

15. Types of personal data processed  
    - Selected: Names, contact information; Location data (home address, IP geolocation); Behavioral/usage data (device usage patterns, presence indicators); Other: Live and recorded video/audio streams from cameras

16. Business-critical data stored  
    - Selected: Customer databases, Device inventories and configurations, Automation rules/policies, Audit logs, Configuration data, Intellectual property (device models, analytics algorithms)

17. Overall data sensitivity classification  
    - Selected: Secret (severe harm if disclosed)

18. Primary data storage locations  
    - Selected: Relational databases, NoSQL databases, Cloud object storage, File systems (for logs/temp), In-memory caches

19. Data flow mechanisms  
    - Selected: REST APIs, MQTT-based messaging, Message queues, Real-time streams (video, telemetry), Direct database connections (internal services)

20. Data retention policy  
    - Selected: Medium-term (months) for telemetry and logs, Shorter-term configurable retention for video; Legal/regulatory requirements and user privacy preferences dictate retention for some data types


## Layer 4 – System Components & Architecture

21. Main application tiers  
    - Selected: Mobile applications (iOS/Android), Web frontend (for admins/ops), API gateway/reverse proxy, Application servers, Background job processors, Microservices

22. Programming languages/frameworks used  
    - Selected: JavaScript/Node.js, Python (for IoT/fleet and analytics services)

23. Deployment architecture  
    - Selected: Microservices architecture, Container-based (Docker/Kubernetes)

24. Infrastructure components  
    - Selected: Load balancers, Web application firewalls (WAF), API gateways, Service mesh, Message brokers, Caching layers

25. Component interconnection  
    - Selected: Direct HTTP/HTTPS calls, Service mesh, Message queues, Event-driven architecture, Database connections

26. Single points of failure  
    - Selected: Primary database, Central IoT/MQTT broker or device gateway, Authentication service, External push notification services, Edge load balancer/API ingress


## Layer 5 – Security Controls & Compliance

27. User authentication methods  
    - Selected: Username/password, Multi-factor authentication (for admins and sensitive actions), OAuth/social login (for end users), API keys/tokens (for integrations), Certificate-based authentication (for devices and gateways)

28. Authorization model  
    - Selected: Role-based access control (RBAC), Attribute-based access control (ABAC) for device/home scoping

29. Data protection in transit  
    - Selected: TLS/HTTPS for all REST communications, TLS-secured MQTT where supported, VPN for internal administrative access

30. Data protection at rest  
    - Selected: Database-level encryption, File system/disk encryption, Application-level encryption for credentials and sensitive keys, Key management service (HSM/KMS)

31. Security monitoring  
    - Selected: Application logging, Security information and event management (SIEM), Intrusion detection/prevention systems (IDS/IPS), Web application firewall (WAF) logs, User and device behavior analytics

32. Regulatory frameworks  
    - Selected: GDPR (for applicable regions), KVKK (Turkish Personal Data Protection Law), ISO 27001; Other: Local consumer protection and telecom/IoT regulations where applicable


## Layer 6 – Operations & Maintenance

33. SDLC approach  
    - Selected: Agile/Scrum, DevOps/CI/CD, DevSecOps

34. Code deployment  
    - Selected: Automated CI/CD pipelines, Rolling updates, Canary deployments (for critical services)

35. Patch management  
    - Selected: Regular scheduled maintenance windows, Over-the-air (OTA) firmware updates for edge devices, Ad-hoc emergency patching for critical vulnerabilities

36. Backup strategy  
    - Selected: Regular automated backups, Cloud-based backup services, Replicated databases

37. Disaster recovery plan  
    - Selected: Documented disaster recovery procedures, Hot standby systems, Cloud-based disaster recovery with secondary region

38. Security incident handling  
    - Selected: Formal incident response plan, Incident response team, Third-party incident response support for major breaches
