# Layer 1 – System Scope & Product Boundary (High-Level Context)

1. What is the primary purpose of the web application?
2. Is the application intended for internal users, external users, or both?
3. What type of users interact with the system? (e.g., anonymous users, registered users, admins, moderators)
4. Is the system publicly accessible over the internet?
5. Are there different environments (development, staging, production)?
6. Is the application deployed in a single region or multiple geographic regions?
7. Are there regulatory or compliance requirements relevant to the system? (e.g., GDPR, HIPAA, PCI-DSS)
8. What parts of the system are considered **out of scope** for this threat model?

------

# Layer 2 – Actors & External Dependencies

1. Who are the primary human actors interacting with the system?
2. Are there automated actors (bots, scripts, integrations) interacting with the system?
3. Does the system rely on third-party services? (e.g., auth providers, payment services, email services)
4. Are any external APIs consumed by the application?
5. Are third-party JavaScript libraries or SDKs loaded in the frontend?
6. Is there a centralized identity provider (IdP) used for authentication?
7. Are any external services trusted with sensitive data?

------

# Layer 3 – Asset Inventory (Infrastructure & Components)

1. How many major infrastructure assets does the system consist of? (e.g., web server, API server, worker, database)
2. What types of compute assets are used? (VMs, containers, serverless functions)
3. Is there a separate API backend or is the API integrated into the web app?
4. Are background workers or job queues used?
5. Are there dedicated services for authentication or authorization?
6. Is a load balancer, reverse proxy, or API gateway used?
7. Are assets logically separated by network boundaries (VPCs, subnets, firewalls)?
8. Are any assets shared with other applications or teams?

------

# Layer 4 – Data Flow & Trust Boundaries

1. How does user traffic enter the system? (direct web access, CDN, API gateway)
2. What are the main data flows between frontend, backend, and databases?
3. Are there clear trust boundaries between users, application servers, and data stores?
4. Does data flow across network or security boundaries (e.g., public → private)?
5. Are there asynchronous data flows (queues, events, webhooks)?
6. Is sensitive data transmitted between components?
7. Are data flows encrypted in transit?
8. Are any components allowed to communicate without authentication?

------

# Layer 5 – Data Storage & Data Classification

1. What types of data are stored by the system? (PII, credentials, logs, business data)
2. Which databases are used? (PostgreSQL, MySQL, MongoDB, NoSQL, etc.)
3. Are multiple databases used for different purposes?
4. Is any data stored in object storage (e.g., file uploads, documents)?
5. Are encryption-at-rest mechanisms enabled for data stores?
6. Are backups created for stored data?
7. Who has access to production data?
8. Is any user-generated content stored and later re-used?

------

# Layer 6 – Application Code & Frameworks

1. Which backend framework is used? (e.g., Django, Flask, FastAPI, Node.js)
2. Which frontend framework or library is used?
3. Are framework default security features enabled or customized?
4. How is authentication implemented? (sessions, JWTs, OAuth, custom)
5. How is authorization enforced across endpoints?
6. Are security-critical checks centralized or scattered across the codebase?
7. Is user input consistently validated and sanitized?
8. Are file uploads supported, and if so, how are they handled?
9. Are secrets stored securely (e.g., environment variables, secret managers)?

------

# Layer 7 – API Surface & API Security

1. What type of APIs are exposed? (REST, GraphQL, WebSocket)
2. Are APIs publicly accessible or restricted to authenticated users?
3. How are API clients authenticated?
4. Is rate limiting or throttling applied to APIs?
5. Are APIs versioned?
6. Are there admin-only or privileged API endpoints?
7. Are API requests logged and monitored?
8. Are input schemas or contracts enforced for API requests?

------

# Layer 8 – Embedded LLM / Chatbot Security

1. How is the LLM integrated into the application? (chatbot, assistant, background analysis)
2. Who can interact with the LLM feature?
3. What types of input does the LLM receive? (free text, structured data, retrieved content)
4. Does the LLM have access to internal data or user-specific data?
5. Are chat histories or prompts stored?
6. Can the LLM trigger actions or tools within the system?
7. Are safeguards in place against prompt injection?
8. Is LLM output validated or filtered before being shown to users?
9. Is the LLM hosted internally or accessed via an external provider?
10. Are LLM prompts, system instructions, or templates treated as sensitive assets?