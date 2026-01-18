# Threat Modeling Question Set (v2.1)

---

## Layer 1 – System Scope & Context

1. What is the primary purpose of the system being modeled?
2. What business problem or user need does this system address?
3. Who are the intended users or user roles of the system?
4. Is the system publicly accessible or restricted to a private network?
5. What environments does the system operate in (e.g., production, staging, development)?
6. Are there any explicit assumptions made about the system’s operating environment?
7. What assets (data, services, capabilities) are considered most critical to protect?
8. What parts of the system are explicitly out of scope for this threat model?

---

## Layer 2 – External Dependencies & Integrations

9. Does the system rely on third-party services or external platforms?
10. Are cloud services (IaaS, PaaS, SaaS) used as part of the system?
11. Are external identity providers or authentication services used?
12. Does the system consume external APIs or data sources?
13. Are third-party SDKs, libraries, or plugins integrated into the system?
14. Are there trust assumptions made about any external dependency?
15. Could failure or compromise of an external dependency impact system security?

---

## Layer 3 – Data & Object Flow

16. What types of data are collected, processed, or stored by the system?
17. Does the system process personal, sensitive, or regulated data?
18. How does data enter the system (user input, APIs, files, sensors)?
19. How does data leave the system or get shared externally?
20. Are there internal data flows between system components or services?
21. Are data flows authenticated and authorized between internal components?
22. Are any data transformations performed within the system?
23. Are data flows documented or visualized (e.g., DFDs)?
24. Do API endpoints operate on user-owned objects identified by IDs (e.g., ticketId, orderId, documentId), and how is ownership enforced at the design level?
25. Are API responses designed to expose different object fields based on caller role or context (field-level authorization), or is a single generic object returned?

---

## Layer 4 – Trust Boundaries & Authorization Logic

26. Where are the trust boundaries within the system?
27. How are trust boundaries enforced between system components?
28. Do any components communicate across trust boundaries without authentication?
29. Are there multiple privilege levels within the system architecture?
30. How is user identity propagated across system components?
31. Are sensitive operations restricted to specific trust zones?
32. Are communications across trust boundaries encrypted?
33. Are there any implicit trust assumptions between internal services?
34. Are authorization decisions centralized (policy-based) or implemented individually within each service or endpoint?
35. What happens if an authorization or identity service becomes unavailable—does the system fail closed or fail open?

---

## Layer 5 – Application Logic & Abuse Scenarios

36. What core business logic does the application implement?
37. Are there workflows that change system state or user privileges?
38. Can users influence application logic through input or configuration?
39. Are there safeguards against repeated or automated actions?
40. Is sensitive data encrypted at rest?
41. Are backups created, and do they contain sensitive data?
42. Can users access or infer data belonging to other users?
43. Is user-generated content stored and reused within the system?
44. Are there sensitive business flows (e.g., ticket status changes, refunds, approvals) that could be abused through API automation or repeated calls?

---

## Layer 6 – Authentication, Authorization & Session Management

45. How are users authenticated to the system?
46. Are sessions stateful or stateless?
47. How are authentication tokens or credentials stored and protected?
48. What authentication mechanisms are used (e.g., passwords, OAuth, JWT)?
49. Are authorization checks enforced consistently across the application?
50. Is there separation between user-facing and administrative functionality?
51. Are security checks centralized or scattered across the codebase?
52. Does the system allow file uploads or user-supplied content?
53. Are privileged operations audited or logged?

---

## Layer 7 – API & LLM Integration Boundaries

54. Does the system expose public or internal APIs?
55. Are APIs versioned and documented?
56. How are API clients authenticated?
57. Are rate limits enforced on API usage?
58. Are deprecated or legacy API versions still accessible?
59. Are API requests and responses logged or monitored?
60. Are there admin-only or high-privilege API endpoints?
61. Are API schemas or contracts validated at runtime?

62. Does the system integrate with a Large Language Model (LLM)?
63. What user inputs are forwarded to the LLM?
64. Does the LLM receive system or internal context data?
65. Is chat history or prompt data stored persistently?
66. Can the LLM access internal APIs, tools, or databases?
67. Can the LLM trigger actions or workflows beyond simple text generation?
68. Are controls in place to prevent prompt injection attacks?
69. Is LLM output validated or filtered before being used or displayed?
70. Does the LLM output directly trigger actions or decisions without explicit human validation?
71. Can the LLM invoke tools, APIs, or workflows that have broader permissions than the original user request context?

---

## Layer 8 – Operational & Resource Controls

72. Is the LLM hosted internally or provided by a third-party service?
73. Are prompts, templates, or model configurations treated as sensitive assets?
74. Are there explicit limits on LLM usage (tokens, request rate, cost) to prevent denial-of-service or cost exhaustion attacks?
