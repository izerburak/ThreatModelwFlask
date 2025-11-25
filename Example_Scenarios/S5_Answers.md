# Threat Modeling Questionnaire Answers
System: University Learning Management System (LMS)

## Layer 1 – Scope & Context (Outer Boundary)

1. Primary business function  
   - Selected: Online teaching and assessment, Content management (courses, materials), Communication/messaging (announcements, forums), Identity/authentication for students and staff

2. System lifecycle stage  
   - Selected: Production (mature)

3. Expected system scale  
   - Selected: Medium (1K–100K users/day)

4. Deployment location  
   - Selected: Hybrid (on-prem + cloud), typically on-prem/University datacenter integrated with cloud services

5. Network accessibility  
   - Selected: Mixed (some components public, some internal)

6. Geographic constraints  
   - Selected: Single country/region (primary campus and affiliated institutions)

7. Business impact if system is unavailable  
   - Selected: High (teaching and exam disruption, operational impact)

8. Business impact if data is compromised  
   - Selected: High (financial/legal consequences, privacy and academic integrity impact)


## Layer 2 – Actors & External Entities

9. End user types  
   - Selected: Students, Instructors/lecturers, Teaching assistants, Department/Registrar/administrative staff, System administrators, Auditors/compliance officers

10. User roles with administrative privileges  
    - Selected: System administrators, Database administrators, Application administrators, Security administrators, Business/academic administrators (program/department admins)

11. Automated actors  
    - Selected: Internal automation/scripts (course creation, enrollment sync, grade calculations), Partner API integrations (plagiarism detection, video platforms), Third-party service calls (email/push, SMS, proctoring tools), Monitoring/health check systems

12. External services the system depends on  
    - Selected: Authentication providers (LDAP/Active Directory, SAML/OIDC SSO), Email/SMS services, Cloud storage services, CDN/hosting services, Video streaming/lecture capture platforms, Analytics/reporting services

13. External systems that consume data  
    - Selected: Reporting/BI systems, Student Information System (SIS) / ERP, Backup/archival systems, Monitoring/SIEM systems

14. Relevant threat actors  
    - Selected: Script kiddies, Students attempting to bypass controls or manipulate grades, Organized cybercriminals (for credential theft and data exfiltration), Insider threats (staff with elevated access), Disgruntled users, Hacktivists (targeting universities)


## Layer 3 – Data Assets & Classification

15. Types of personal data processed  
    - Selected: Names, contact information; Student and staff identifiers; Location/IP metadata; Behavioral/usage data (logins, activity, submissions); Other: Educational records such as grades and course participation

16. Business-critical data stored  
    - Selected: Student and staff databases (identities, enrollments), Course content and exam banks, Gradebooks and assessment results, Audit logs (access and changes), Configuration data (roles, permissions, course settings), Institutional reports

17. Overall data sensitivity classification  
    - Selected: Confidential (significant harm if disclosed)

18. Primary data storage locations  
    - Selected: Relational databases, Object storage (files, submissions, lecture materials), File systems (temporary storage, logs), In-memory caches

19. Data flow mechanisms  
    - Selected: REST/HTTPS APIs, Direct database connections (internal services), File uploads/downloads (browser-based), Message queues (for background jobs and notifications)

20. Data retention policy  
    - Selected: Legal/regulatory requirements and university policy dictate retention for academic records; shorter-term retention for logs and some content (e.g., course archives)


## Layer 4 – System Components & Architecture

21. Main application tiers  
    - Selected: Web frontend (student and instructor portals), Mobile applications (optional but common), API gateway/reverse proxy, Application servers, Background job processors (reporting, notifications, batch updates)

22. Programming languages/frameworks used  
    - Selected: PHP or Java (traditional LMS platforms), plus JavaScript/Node.js for frontend/API components and Python for reporting/ETL tasks

23. Deployment architecture  
    - Selected: Monolithic application with supporting services, often container-based (Docker/Kubernetes) or virtual machine-based

24. Infrastructure components  
    - Selected: Load balancers, Web application firewalls (WAF), API gateways, Caching layers, Message brokers (for async processing)

25. Component interconnection  
    - Selected: Direct HTTP/HTTPS calls, Database connections, Message queues, Event-driven processing for notifications and background tasks

26. Single points of failure  
    - Selected: Primary database, Central authentication (LDAP/AD/SSO), File storage subsystem (for submissions and materials), Load balancer or reverse proxy if not deployed in HA mode


## Layer 5 – Security Controls & Compliance

27. User authentication methods  
    - Selected: Username/password (students and staff), Single sign-on (SSO) via LDAP/Active Directory or SAML/OIDC, Multi-factor authentication (for admins and high-privilege roles), API keys/tokens (for integrations)

28. Authorization model  
    - Selected: Role-based access control (RBAC) (student, instructor, TA, department admin, system admin), Access control lists (ACL) for course and resource-level permissions

29. Data protection in transit  
    - Selected: TLS/HTTPS for all web access, VPN or restricted internal network for administrative and database access

30. Data protection at rest  
    - Selected: Database-level encryption, File system/object storage encryption (for submissions and materials), Application-level encryption for particularly sensitive attributes (e.g., some identifiers), Key management service (KMS/HSM)

31. Security monitoring  
    - Selected: Application logging (access, changes, important actions), Security information and event management (SIEM), Web application firewall (WAF) logs, Authentication/authorization logs, Optional IDS/IPS at network perimeter

32. Regulatory frameworks  
    - Selected: GDPR (for EU data subjects where applicable), KVKK (Turkish Personal Data Protection Law), ISO 27001; Other: Education privacy and record-keeping regulations (e.g., FERPA-like requirements depending on jurisdiction)


## Layer 6 – Operations & Maintenance

33. SDLC approach  
    - Selected: Agile/Scrum, DevOps/CI/CD, with incremental feature releases during academic off-peak times

34. Code deployment  
    - Selected: Automated CI/CD pipelines where possible, Rolling updates or controlled maintenance windows, Blue/green or canary deployments for major upgrades

35. Patch management  
    - Selected: Regular scheduled maintenance windows for OS, middleware, and LMS platform; Out-of-band emergency patching for critical vulnerabilities

36. Backup strategy  
    - Selected: Regular automated backups of databases and file/object storage, Cloud-based or offsite backups, Replicated databases where supported

37. Disaster recovery plan  
    - Selected: Documented disaster recovery procedures, Secondary environment or region for DR, Tested restore and failover processes

38. Security incident handling  
    - Selected: Formal incident response plan, Incident response team involving IT and information security, Coordination with university legal/compliance and communications for major incidents
