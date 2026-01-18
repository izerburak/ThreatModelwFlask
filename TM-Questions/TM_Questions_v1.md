# Threat Modeling Questions

## Layer 1 – Scope & Context (Outer Boundary)
*LLM Purpose: Define system boundaries and determine high-level DFD structure*

### Core System Definition
1. **What is the primary business function of this system?** 
   - [ ] Financial transactions
   - [ ] Data analytics/reporting
   - [ ] Communication/messaging
   - [ ] Content management
   - [ ] Identity/authentication
   - [ ] E-commerce
   - [ ] Healthcare management
   - [ ] Other: ___

   *LLM Reason: Defines business context, attacker motivations, and the overall attack surface*

2. **What is the system's lifecycle stage?**
   - [ ] Development/prototype
   - [ ] Testing/staging
   - [ ] Production (new)
   - [ ] Production (mature)
   - [ ] Legacy/maintenance

   *LLM Reason: Influences threat prioritization and maturity of security controls*

3. **What is the expected system scale?**
   - [ ] Small (<1,000 users/day)
   - [ ] Medium (1K-100K users/day)
   - [ ] Large (100K-1M users/day)
   - [ ] Enterprise (>1M users/day)

   *LLM Reason: Identifies scale-based threats such as DDoS and resource exhaustion*

### Deployment Context
4. **Where is the system primarily deployed?**
   - [ ] On-premises (private datacenter)
   - [ ] Public cloud (AWS/Azure/GCP)
   - [ ] Private cloud
   - [ ] Hybrid (on-prem + cloud)
   - [ ] Edge/distributed

   *LLM Reason: Defines infrastructure-level threats and trust boundaries*

5. **What is the network accessibility?**
   - [ ] Internet-facing (public)
   - [ ] VPN-only access
   - [ ] Internal network only
   - [ ] Partner network access
   - [ ] Mixed (some components public, some internal)

   *LLM Reason: Identifies external attack surfaces and network-based threats*

6. **What are the key geographic constraints?**
   - [ ] Single country/region
   - [ ] Multi-regional
   - [ ] Global
   - [ ] Specific regulatory jurisdictions only

   *LLM Reason: Highlights regulatory compliance needs and potential nation-state actors*

### Business Criticality
7. **What is the business impact if this system is unavailable?**
   - [ ] Minimal (nice to have)
   - [ ] Moderate (workflow disruption)
   - [ ] High (revenue loss)
   - [ ] Critical (business shutdown)

   *LLM Reason: Helps prioritize threats to availability*

8. **What is the business impact if data is compromised?**
   - [ ] Minimal
   - [ ] Moderate (reputation damage)
   - [ ] High (financial/legal consequences)
   - [ ] Critical (business existence threat)

   *LLM Reason: Evaluates confidentiality versus availability priorities*

---

## Layer 2 – Actors & External Entities
*LLM Purpose: Identify external entities, trust relationships, and attack vectors in DFD*

### Human Actors
9. **What types of end users interact with the system?**
   - [ ] Employees (internal staff)
   - [ ] Customers (external users)
   - [ ] Partners/vendors
   - [ ] System administrators
   - [ ] Auditors/compliance officers
   - [ ] Anonymous/guest users
   - [ ] Other: ___

   *LLM Reason: Identifies DFD external entities and insider threat scenarios*

10. **Which user roles have administrative privileges?**
    - [ ] System administrators
    - [ ] Database administrators
    - [ ] Application administrators
    - [ ] Security administrators
    - [ ] Business administrators
    - [ ] None (no admin roles)

    *LLM Reason: Reveals privilege escalation paths and insider threat risks*

11. **Are there automated actors (bots, scripts, APIs)?**
    - [ ] Internal automation/scripts
    - [ ] Partner API integrations
    - [ ] Third-party service calls
    - [ ] Public API consumers
    - [ ] Monitoring/health check systems
    - [ ] None

    *LLM Reason: Identifies automated non-human attack vectors*

### External Systems & Dependencies
12. **Which external services does the system depend on?**
    - [ ] Authentication providers (LDAP, OAuth, SAML)
    - [ ] Payment processors
    - [ ] Email/SMS services
    - [ ] Cloud storage services
    - [ ] CDN/hosting services
    - [ ] Analytics/tracking services
    - [ ] Government/regulatory APIs
    - [ ] Other: ___

    *LLM Reason: Identifies supply chain and dependency-related risks*

13. **Which external systems consume data from this system?**
    - [ ] Reporting/BI systems
    - [ ] Partner systems
    - [ ] Regulatory reporting systems
    - [ ] Backup/archival systems
    - [ ] Monitoring/SIEM systems
    - [ ] None

    *LLM Reason: Highlights data exfiltration paths and downstream impact areas*

### Threat Actors
14. **Which threat actors are most relevant to your business domain?**
    - [ ] Script kiddies (opportunistic)
    - [ ] Organized cybercriminals
    - [ ] Nation-state actors
    - [ ] Insider threats (malicious employees)
    - [ ] Competitors
    - [ ] Hacktivists
    - [ ] Disgruntled customers/users

    *LLM Reason: Defines attacker motivations, resources, and capabilities*

---

## Layer 3 – Data Assets & Classification
*LLM Purpose: Identify data stores, flows, and data-centric threats*

### Data Types & Sensitivity
15. **What types of personal data are processed?**
    - [ ] Names, contact information
    - [ ] Financial information (credit cards, bank accounts)
    - [ ] Health/medical records
    - [ ] Biometric data
    - [ ] Location data
    - [ ] Behavioral/usage data
    - [ ] None
    - [ ] Other: ___

    *LLM Reason: Identifies privacy regulations and data-specific attack surfaces*

16. **What business-critical data is stored?**
    - [ ] Customer databases
    - [ ] Financial records
    - [ ] Intellectual property
    - [ ] Trade secrets
    - [ ] Strategic business information
    - [ ] Audit logs
    - [ ] Configuration data
    - [ ] Other: ___

    *LLM Reason: Assesses data value and potential for targeted attacks*

17. **How would you classify the overall data sensitivity?**
    - [ ] Public (no harm if disclosed)
    - [ ] Internal (minor harm if disclosed)
    - [ ] Confidential (significant harm if disclosed)
    - [ ] Secret (severe harm if disclosed)

    *LLM Reason: Defines control requirements based on threat impact*

### Data Storage & Flow
18. **Where is data primarily stored?**
    - [ ] Relational databases (MySQL, PostgreSQL, etc.)
    - [ ] NoSQL databases (MongoDB, Redis, etc.)
    - [ ] File systems (local, network shares)
    - [ ] Cloud storage (S3, Azure Blob, etc.)
    - [ ] Data warehouses
    - [ ] In-memory caches
    - [ ] Other: ___

    *LLM Reason: Maps DFD data stores and identifies storage vulnerabilities*

19. **How does data flow between components?**
    - [ ] REST APIs
    - [ ] GraphQL APIs
    - [ ] Message queues (RabbitMQ, Kafka, etc.)
    - [ ] Direct database connections
    - [ ] File transfers (FTP, SFTP, etc.)
    - [ ] Real-time streams
    - [ ] Batch processing
    - [ ] Other: ___

    *LLM Reason: Identifies DFD data flows and transmission vulnerabilities*

20. **What is the data retention policy?**
    - [ ] No specific retention (kept indefinitely)
    - [ ] Short-term (days to weeks)
    - [ ] Medium-term (months)
    - [ ] Long-term (years)
    - [ ] Legal/regulatory requirements dictate retention

    *LLM Reason: Highlights data lifecycle threats and compliance implications*

---

## Layer 4 – System Components & Architecture
*LLM Purpose: Identify system processes, architectural vulnerabilities, and attack vectors*

### Application Components
21. **What are the main application tiers?**
    - [ ] Web frontend (HTML/JS/React/Angular)
    - [ ] Mobile applications (iOS/Android)
    - [ ] Desktop applications
    - [ ] API gateway/reverse proxy
    - [ ] Application servers
    - [ ] Background job processors
    - [ ] Microservices
    - [ ] Other: ___

    *LLM Reason: Identifies DFD processes and tier-specific vulnerabilities*

22. **Which programming languages/frameworks are used?**
    - [ ] JavaScript/Node.js
    - [ ] Python (Django/Flask)
    - [ ] Java (Spring/JSF)
    - [ ] C# (.NET)
    - [ ] PHP
    - [ ] Go
    - [ ] Ruby
    - [ ] Other: ___

    *LLM Reason: Highlights language and framework-specific vulnerabilities*

23. **What is the deployment architecture?**
    - [ ] Monolithic application
    - [ ] Microservices architecture
    - [ ] Serverless functions
    - [ ] Container-based (Docker/Kubernetes)
    - [ ] Virtual machines
    - [ ] Hybrid approach

    *LLM Reason: Identifies architecture-specific attack patterns*

### Infrastructure Components
24. **Which infrastructure components are used?**
    - [ ] Load balancers
    - [ ] Web application firewalls (WAF)
    - [ ] Content delivery networks (CDN)
    - [ ] API gateways
    - [ ] Service mesh
    - [ ] Message brokers
    - [ ] Caching layers
    - [ ] Other: ___

    *LLM Reason: Maps infrastructure attack surfaces and DFD nodes*

25. **How are components interconnected?**
    - [ ] Direct HTTP/HTTPS calls
    - [ ] Service mesh (Istio, Linkerd)
    - [ ] Message queues
    - [ ] Event-driven architecture
    - [ ] Database connections
    - [ ] Shared file systems
    - [ ] Other: ___

    *LLM Reason: Reveals inter-component attack paths and segmentation risks*

### Critical Dependencies
26. **Which systems are single points of failure?**
    - [ ] Primary database
    - [ ] Authentication service
    - [ ] Payment processor
    - [ ] External API dependencies
    - [ ] Load balancer
    - [ ] None identified
    - [ ] Other: ___

    *LLM Reason: Identifies availability threats and cascading failures*

---

## Layer 5 – Security Controls & Compliance
*LLM Purpose: Assess existing security controls and identify control gaps*

### Authentication & Authorization
27. **How do users authenticate?**
    - [ ] Username/password only
    - [ ] Multi-factor authentication (MFA)
    - [ ] Single sign-on (SSO)
    - [ ] Certificate-based authentication
    - [ ] Biometric authentication
    - [ ] OAuth/social login
    - [ ] API keys/tokens
    - [ ] Other: ___

    *LLM Reason: Identifies authentication bypass vulnerabilities*

28. **How is authorization managed?**
    - [ ] Role-based access control (RBAC)
    - [ ] Attribute-based access control (ABAC)
    - [ ] Access control lists (ACL)
    - [ ] Hardcoded permissions
    - [ ] No formal authorization model
    - [ ] Other: ___

    *LLM Reason: Detects privilege escalation and authorization flaws*

### Data Protection
29. **How is data protected in transit?**
    - [ ] TLS/HTTPS for all communications
    - [ ] TLS for external communications only
    - [ ] VPN for internal communications
    - [ ] No encryption in transit
    - [ ] End-to-end encryption
    - [ ] Other: ___

    *LLM Reason: Identifies man-in-the-middle and eavesdropping risks*

30. **How is data protected at rest?**
    - [ ] Database-level encryption
    - [ ] File system encryption
    - [ ] Application-level encryption
    - [ ] Key management service (HSM/KMS)
    - [ ] No encryption at rest
    - [ ] Other: ___

    *LLM Reason: Evaluates data breach risks and storage security controls*

### Monitoring & Detection
31. **What security monitoring is in place?**
    - [ ] Application logging
    - [ ] Security information and event management (SIEM)
    - [ ] Intrusion detection system (IDS)
    - [ ] Intrusion prevention system (IPS)
    - [ ] Web application firewall (WAF) logs
    - [ ] User behavior analytics
    - [ ] None
    - [ ] Other: ___

    *LLM Reason: Assesses detection capabilities and coverage gaps*

### Compliance Requirements
32. **Which regulatory frameworks apply?**
    - [ ] GDPR
    - [ ] HIPAA
    - [ ] PCI DSS
    - [ ] SOX
    - [ ] KVKK (Turkish Data Protection)
    - [ ] ISO 27001
    - [ ] None
    - [ ] Other: ___

    *LLM Reason: Identifies compliance-driven security obligations*

---

## Layer 6 – Operations & Maintenance
*LLM Purpose: Identify operational threats and lifecycle security aspects*

### Development & Deployment
33. **What is the software development lifecycle (SDLC) approach?**
    - [ ] Waterfall
    - [ ] Agile/Scrum
    - [ ] DevOps/CI/CD
    - [ ] DevSecOps
    - [ ] Ad-hoc development
    - [ ] Other: ___

    *LLM Reason: Detects development-stage vulnerabilities*

34. **How are code changes deployed?**
    - [ ] Manual deployment
    - [ ] Automated CI/CD pipelines
    - [ ] Blue/green deployments
    - [ ] Canary deployments
    - [ ] Rolling updates
    - [ ] Other: ___

    *LLM Reason: Identifies risks in deployment processes*

35. **What is the patch management process?**
    - [ ] Automated patching
    - [ ] Regular maintenance windows
    - [ ] Ad-hoc patching when issues arise
    - [ ] No formal patch management
    - [ ] Third-party managed patching
    - [ ] Other: ___

    *LLM Reason: Evaluates vulnerability exposure and zero-day management*

### Backup & Recovery
36. **What is the backup strategy?**
    - [ ] Regular automated backups
    - [ ] Manual backups
    - [ ] Cloud-based backups
    - [ ] Replicated databases
    - [ ] No backup strategy
    - [ ] Other: ___

    *LLM Reason: Assesses resilience against data loss and ransomware*

37. **What is the disaster recovery plan?**
    - [ ] Documented recovery procedures
    - [ ] Hot standby systems
    - [ ] Cold backup systems
    - [ ] Cloud-based disaster recovery
    - [ ] No recovery plan
    - [ ] Other: ___

    *LLM Reason: Evaluates business continuity readiness*

### Incident Response
38. **How are security incidents handled?**
    - [ ] Formal incident response plan
    - [ ] Incident response team
    - [ ] Third-party response service
    - [ ] Ad-hoc incident handling
    - [ ] No incident response
    - [ ] Other: ___

    *LLM Reason: Determines incident containment and forensic capabilities*

---

## Layer 7 –  LLM Output Guidance & Threat Hypotheses  
*This layer guides the LLM on how to utilize information collected from previous layers*

### LLM Prompt Template Structure:
```
Based on the collected information from Layers 1–6, generate:

1. **System Architecture (DFD Elements):**
   - External Entities: [From Layer 2 actors]
   - Processes: [From Layer 4 components]
   - Data Stores: [From Layer 3 storage locations]
   - Data Flows: [From Layer 3 flow patterns]
   - Trust Boundaries: [From Layer 1 deployment + Layer 5 controls]

2. **STRIDE Threat Analysis:**
   For each DFD element, identify threats in categories:
   - Spoofing: Authentication-related threats
   - Tampering: Data/code integrity threats
   - Repudiation: Logging/audit threats
   - Information Disclosure: Confidentiality threats
   - Denial of Service: Availability threats
   - Elevation of Privilege: Authorization threats

3. **Risk Prioritization:**
   - Critical: High business impact + easy to exploit
   - High: High impact OR easy to exploit
   - Medium: Moderate impact + moderate difficulty
   - Low: Low impact + hard to exploit

4. **Recommended Controls:**
   Based on identified Layer 5 gaps, suggest mitigations.
```

### Key LLM Guidance Questions:
39. **Which data flows cross the most trust boundaries?**
40. **Which components have the largest attack surface due to external connectivity?**
41. **Which threats are most probable given the known threat actors and capabilities?**
42. **Which existing controls are insufficient for current threats?**
43. **What are the highest-impact threats lacking detection or prevention controls?**
