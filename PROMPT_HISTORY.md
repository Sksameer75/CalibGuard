# CalibGuard — AI Prompt History

## 1. Project Context

**Project:** CalibGuard — Industrial Calibration & Compliance Management Platform

**Challenge:** YottaFlex.ai — Associate AI Forward Deployed Engineer, 72-Hour Challenge

**Purpose:** Build a working industrial calibration and compliance management platform using AI-assisted development.

**Development approach:** Iterative development using AI for requirements analysis, architecture, synthetic data generation, backend development, frontend implementation, validation, debugging, and documentation.

---

## 2. Master Project Development Prompt

The following is a consolidated reconstruction of the project brief used to guide development.

### Master Prompt

Act as a Senior Software Architect, Industrial Compliance Domain Expert, Python Backend Engineer, Database Architect, Data Engineer, and Frontend Developer.

I want to develop a complete, functional, professional-grade industrial calibration and compliance management platform called **CalibGuard**.

This project is being developed for a 72-hour technical challenge for an Associate AI Forward Deployed Engineer position at YottaFlex.ai.

Do not build a static dashboard or a simple CRUD application. Build a working end-to-end platform that demonstrates industrial business logic, data integrity, calibration compliance, anomaly detection, traceability, and operational workflows.

### A. Business Problem

Manufacturing organizations depend on instruments such as pressure gauges, temperature sensors, flow meters, and weighing systems.

These instruments require periodic calibration to maintain measurement accuracy and compliance.

The platform must help organizations:

- Maintain instrument master records.
- Manage calibration schedules.
- Track calibration results.
- Manage calibration certificates.
- Identify expired and invalid calibration conditions.
- Prevent unauthorized production usage where policy requires blocking.
- Manage maintenance work orders.
- Handle calibration failures and impact assessments.
- Maintain audit trails and traceability.

### B. User Roles

Design workflows around these users:

1. Plant Operator
2. Maintenance / Quality Engineer
3. Production Planner
4. OT / IT Administrator

### C. Core Database Entities

Design a relational MySQL database covering:

- Assets
- Instrument Types
- Calibration Plans
- Calibration Events
- Certificates
- Work Orders
- Production Uses
- Suppliers
- Alerts
- Audit Records

Include additional entities where required for:

- Emergency Extensions
- Impact Assessments
- Work Order Asset Relationships
- Asset Lifecycle Events

Use proper primary keys, foreign keys, constraints, and relationships.

### D. Synthetic Data Generation

Create a deterministic industrial synthetic dataset using Python.

Target dataset:

- 2,000 instruments
- 5,000 calibration events
- 100,000 production-use records
- One year of synthetic operating history
- Fixed random seed: 20261022

Generate related records using valid parent IDs and consistent relationships.

Do not generate arbitrary disconnected records.

Calibration results, certificate validity, production-use decisions, and compliance outcomes must follow documented business rules.

### E. Industrial Business Logic

Implement the following workflows:

1. Create instrument master records.
2. Assign calibration plans.
3. Generate calibration events.
4. Determine calibration pass/fail results.
5. Generate certificates for applicable calibration events.
6. Generate maintenance work orders.
7. Generate production-use records.
8. Evaluate whether instruments are eligible for production use.
9. Identify expired calibration conditions.
10. Identify invalid certificates.
11. Handle approved emergency extensions.
12. Generate corrective actions and impact assessments for failed calibration events.

Maintain historical traceability instead of overwriting important business events.

### F. Authorization Engine

Implement rule-based instrument-use authorization.

Evaluate:

- Asset lifecycle state.
- Latest calibration result.
- Calibration plan validity.
- Calibration due date.
- Certificate validity.
- Certificate-to-asset relationship.
- Active maintenance work orders.
- Approved emergency extensions.
- Instrument-specific blocking policies.

Return clear decisions:

- ALLOW
- CONDITIONAL_ALLOW
- BLOCK

Include explanations for authorization decisions.

An emergency extension must not override failed calibration or invalid certificate conditions.

### G. Anomaly Injection and Detection

Create a separate anomaly injection and detection module.

Plant exactly 12 anomalies across four categories, with three anomalies per category.

The four categories are:

1. Due-date inconsistency.
2. Expired instrument used without an approved exception.
3. Certificate linked to the wrong asset.
4. Failed calibration without an impact assessment.

Maintain separate ground-truth labels.

Implement detection rules and compare detected anomalies against ground truth.

Do not confuse planted-anomaly detection results with general machine-learning accuracy.

### H. Data Validation and Reproducibility

Implement comprehensive data validation.

Check:

- Primary-key uniqueness.
- Foreign-key integrity.
- Required fields.
- Data types.
- Enum values.
- Timestamp consistency.
- Calibration calculations.
- Certificate relationships.
- Work-order consistency.
- Production-use conditions.
- Emergency-extension relationships.
- Lifecycle-event relationships.
- Audit-record structure.

Implement deterministic reproducibility testing.

Generate the dataset twice using the same seed and compare output hashes.

Generate:

- CSV exports.
- JSONL exports.
- SQL exports.
- Data dictionary.
- Validation report.
- Export manifest.
- Ground-truth anomaly files.

### I. Backend Development

Use:

- Python
- Flask
- MySQL 8.4
- REST APIs

Develop endpoints for:

- Health checks.
- Database verification.
- Dashboard metrics.
- Assets.
- Individual asset details.
- Calibration records.
- Alerts.
- Production usage.
- Authorization evaluation.
- Scheduling.
- Work-order management.
- Corrective actions.
- Impact assessments.

Use structured JSON responses, appropriate HTTP status codes, validation, error handling, and database connection management.

### J. Frontend Development

Use:

- React
- TypeScript
- Vite
- HTML
- CSS

Build a professional industrial dashboard with a consistent design system.

Include:

1. Overview Dashboard
2. Asset Explorer
3. Calibration Explorer
4. Alerts
5. Production Usage
6. Authorization Simulator
7. Scheduling Workspace
8. Corrective Actions Workspace

The dashboard must retrieve information from the Flask backend.

Do not use hardcoded sample metrics to simulate a working application.

Use a consistent light industrial interface with readable typography, organized cards, tables, filters, and clear status indicators.

### K. Project Quality Requirements

The project must be:

- Functional end to end.
- Database-driven.
- Reproducible.
- Validated.
- Documented.
- Organized for GitHub.
- Suitable for technical demonstration.

Provide complete files when implementing or correcting modules.

Avoid unnecessary modifications to working files.

Do not claim that features are complete unless they have been implemented and tested.

Explain architectural decisions and identify limitations honestly.

---

## 3. Iterative Development Prompts

The following sections reconstruct the major prompt categories used during implementation. They are organized by development phase, not presented as a verbatim transcript.

### Phase 1 — Requirements and Architecture

**Prompt objective:** Understand the industrial problem and translate the challenge requirements into a technical architecture.

- Analyze the industrial calibration and compliance problem.
- Identify entities and relationships.
- Define the database-first architecture.
- Separate master data from dependent transactional records.
- Define the business workflows.
- Establish measurable acceptance criteria.

### Phase 2 — MySQL Database Design

**Prompt objective:** Build a relational database that supports the complete application.

- Design the MySQL schema.
- Define primary and foreign keys.
- Establish relationships between assets, plans, calibration events, certificates, work orders, and production usage.
- Add emergency-extension, impact-assessment, and lifecycle-event support.
- Validate relationships and constraints.
- Keep the active demonstration database separate from schema-only databases.

### Phase 3 — Synthetic Data Generator

**Prompt objective:** Generate realistic and reproducible industrial records.

- Implement Python master-data generation.
- Generate calibration plans and events.
- Generate certificates and work orders.
- Generate production-use records.
- Use fixed seed 20261022.
- Preserve valid relationships between generated records.
- Implement business rules for calibration and production authorization.

### Phase 4 — Anomaly Injection and Detection

**Prompt objective:** Introduce controlled anomalies and verify detection.

- Implement four anomaly categories.
- Inject three anomalies per category.
- Maintain separate ground-truth records.
- Implement detection logic.
- Compare detected results against expected results.
- Generate anomaly reports.

### Phase 5 — Data Validation and Export

**Prompt objective:** Validate dataset quality and reproducibility.

- Implement structural validation.
- Validate business rules.
- Check relationships and timestamp consistency.
- Generate the dataset twice.
- Compare output hashes.
- Export CSV, JSONL, and SQL.
- Generate data dictionaries, reports, and manifests.

### Phase 6 — Flask Backend

**Prompt objective:** Build the REST API layer.

- Configure Flask and MySQL connectivity.
- Implement database connection management.
- Build health and verification endpoints.
- Implement dashboard metrics.
- Implement asset, calibration, alert, and production-use endpoints.
- Add authorization evaluation.
- Implement scheduling and work-order endpoints.
- Implement corrective-action and impact-assessment endpoints.
- Add error handling and JSON serialization.

### Phase 7 — React Frontend

**Prompt objective:** Build the industrial dashboard.

- Configure React, TypeScript, and Vite.
- Establish consistent styling.
- Connect the frontend to Flask APIs.
- Build the overview dashboard.
- Build asset and calibration explorers.
- Build alerts and production-use views.
- Implement the Authorization Simulator.
- Implement the Scheduling Workspace.
- Implement the Corrective Actions Workspace.
- Resolve TypeScript and production-build errors.

### Phase 8 — Integration and Debugging

**Prompt objective:** Make the application work as one integrated system.

- Verify backend connectivity.
- Verify MySQL connectivity.
- Resolve API response mismatches.
- Resolve frontend build errors.
- Test scheduling and work-order workflows.
- Test authorization decisions.
- Test corrective-action workflows.
- Align CSS across application modules.
- Avoid modifying unrelated working components.

### Phase 9 — Docker and GitHub Preparation

**Prompt objective:** Prepare the project for reviewers.

- Review the repository structure.
- Protect environment credentials.
- Prepare `.env.example`.
- Configure `.gitignore`.
- Consolidate project documentation into one root README.
- Prepare Docker Compose and service configurations.
- Preserve database persistence.
- Test the project from a fresh clone.
- Prepare GitHub screenshots and documentation.

---

## 4. AI-Assisted Development Principles

The AI-assisted development process followed these principles:

1. Build incrementally rather than generating the entire application in one step.
2. Prioritize database integrity and business rules.
3. Validate generated data before integrating it into the application.
4. Use actual backend responses in frontend components.
5. Test features after implementation.
6. Preserve working code when making changes.
7. Document known limitations rather than exaggerating functionality.
8. Use deterministic data generation for repeatable demonstrations.

---

## 5. Important Implementation Limitations

The following distinctions must be preserved in the final technical submission:

- Authorization evaluation is currently a simulator and does not itself persist production-use transactions.
- Production-grade authentication and role-based access control are not yet implemented.
- Synthetic records are used instead of live industrial data.
- Corrective-action workflows can be extended with mandatory root-cause analysis, verification evidence, and effectiveness checks.
- Real equipment, ERP, CMMS, and OT integrations are not included.

---

## 6. Final Development Outcome

The resulting CalibGuard implementation includes:

- MySQL industrial database.
- Python synthetic data generator.
- 2,000 generated instruments.
- 5,000 calibration events.
- 100,000 production-use records.
- Four anomaly categories with 12 planted anomalies.
- Anomaly detection and ground-truth comparison.
- Data integrity and reproducibility validation.
- CSV, JSONL, and SQL export functionality.
- Flask REST API.
- React and TypeScript dashboard.
- Authorization Simulator.
- Scheduling and Work Order Management.
- Corrective Actions and Impact Assessment workflows.

**Note:** This document is a reconstructed summary of the major development prompts and instructions. It is not an exact export of the original ChatGPT conversation history.