# System Summary – Online Ride‑Sharing & Mobility Platform

## System Overview
The **Online Ride‑Sharing & Mobility Platform** is a cloud‑based, multi‑tenant transportation service that connects passengers with drivers for on‑demand urban mobility. Passengers can request rides, view estimated fares, track drivers in real time, make online payments, and rate their experience. Drivers receive ride requests, navigate to passengers, complete trips, and monitor their earnings. The platform includes real‑time location tracking, dynamic pricing, fleet and corporate ride management, operational dashboards, and integrations with payment processors and mapping services.

## Key Architectural Components

### 1. Client Layer
**Passenger Mobile App (iOS/Android)**  
Provides ride request, location sharing, fare estimation, real‑time tracking, payment, trip history, and notifications.

**Driver Mobile App (iOS/Android)**  
Enables availability toggling, receiving/accepting ride requests, navigation, real‑time location sharing, and earnings overview.

**Passenger Web Application**  
Offers simplified capabilities such as requesting rides, managing payment information, viewing invoices, and accessing past trips.

**Fleet / Corporate Management Portal**  
Allows companies to manage employees, budgets, policies, invoices, and specialized tariffs.

**Operations & Support Dashboard**  
Used by support and ops teams for live trip tracking, user/driver management, intervention in problematic rides, and document verification.

---

### 2. API Layer
**API Gateway / Reverse Proxy**  
Central entry point for all client requests. Handles TLS, rate limiting, token validation, and routing.

**Authentication & Authorization Service**  
OAuth 2.0 / OIDC‑based identity provider with roles such as passenger, driver, fleet manager, support, and administrators. Includes MFA, password reset, and device binding.

---

### 3. Application Services
**User & Profile Service**  
Manages user accounts, personal details, communication preferences, and GDPR/KVKK consents.

**Driver Management Service**  
Handles onboarding, document verification, vehicle data, and driver status transitions.

**Ride Matching & Dispatch Service**  
Core component responsible for matching ride requests with available drivers using ETA, distance, ratings, and surge pricing inputs.

**Real‑Time Location & Tracking Service**  
Processes driver (and optionally passenger) location updates and streams live tracking via WebSocket/gRPC.

**Pricing & Fare Calculation Service**  
Implements dynamic pricing, calculates estimated and final fares, and applies promotions.

**Trip Management Service**  
Orchestrates the trip lifecycle from creation to completion/cancellation and manages event logs.

**Payment Service**  
Integrates with external PSPs for card tokenization, charging, refunds, payouts, and invoicing.

**Rating & Feedback Service**  
Records and aggregates passenger and driver ratings and comments.

**Notification Service**  
Manages SMS, email, and push notifications triggered by system events.

**Fraud Detection & Risk Scoring (Optional)**  
Detects suspicious behavior such as account abuse, stolen cards, excessive cancellations, or unsafe driving patterns.

**Reporting & Analytics Service**  
Provides dashboards and insights for business, operations, and performance monitoring.

---

### 4. Data Layer
**Relational Database Cluster (PostgreSQL)**  
Stores core tables such as users, drivers, vehicles, rides, ride events, pricing rules, payments, invoices, feedback, consents, and audit logs.

**NoSQL / In‑Memory Cache (Redis)**  
Used for driver availability, real‑time matching states, rate limiting counters, and ephemeral session data.

**Time‑Series / Geo‑Indexed Storage**  
Keeps historical location traces, route geometry, and demand/surge analytics.

**Object Storage**  
Stores driver documents, invoices, PDFs, reports, and media assets.

**Logging & SIEM Pipelines**  
Centralized application logs, security logs, anomaly detection, and monitoring integrations.

---

### 5. Infrastructure & Deployment
**Kubernetes / Container Orchestration**  
Hosts all microservices with autoscaling and rolling updates.

**Load Balancers + API Gateway**  
Provide secure external access and traffic routing.

**VPC with Private Subnets**  
Hosts internal services and databases isolated from the public internet.

**Monitoring, Metrics, and Alerting**  
Enables health monitoring, performance tracking, and early anomaly detection.

