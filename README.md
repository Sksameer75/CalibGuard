# CalibGuard
### Industrial Calibration & Compliance Management Platform

CalibGuard is a full-stack industrial calibration and compliance management platform designed to help organizations monitor instrument calibration schedules, manage certificates, track work orders, identify compliance risks, and maintain operational traceability.

The platform combines a React frontend, Python Flask REST API, MySQL database, synthetic industrial datasets, and anomaly detection workflows.

## Features

- **Calibration Management:** Track instruments, calibration plans, events, and calibration status.
- **Certificate Management:** Maintain calibration certificate records.
- **Work Order Management:** Organize calibration-related work orders.
- **Overdue Calibration Monitoring:** Identify overdue instruments and potential compliance issues.
- **Anomaly Detection:** Generate and analyze synthetic industrial data containing injected anomalies.
- **Risk and Impact Assessment:** Evaluate operational impact and compliance risks.
- **Alerts and Audit Records:** Track alerts and important system activities.
- **Lifecycle History:** Maintain records for operational traceability.
- **Authorization Simulator:** Demonstrate authorization and decision workflows.
- **Interactive Dashboard:** View calibration and compliance information.

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | React, TypeScript, Vite |
| Backend | Python, Flask, REST API |
| Database | MySQL 8.4 |
| Database Connector | MySQL Connector/Python |
| Containerization | Docker, Docker Compose |
| Data Processing | Python, CSV, JSONL |

## Project Structure

```text
CalibGuard/
├── backend/
│   ├── api.py
│   ├── generator.py
│   ├── phase3.py
│   ├── phase3b.py
│   ├── production.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── database/
│   ├── schema.sql
│   └── 002_integrity_and_history.sql
│
├── data/
│   ├── phase3/
│   └── phase3b/
│       └── dataset.sql
│
├── frontend/
│   ├── src/
│   ├── package.json
│   └── Dockerfile
│
├── tests/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── .dockerignore
└── README.md
```

## Prerequisites

Install:

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Git](https://git-scm.com/)

Make sure Docker Desktop is running.

You do not need to install MySQL, Python, or Node.js separately for the Docker-based setup.

## Installation and Execution

### Step 1: Clone the Repository

Open VS Code terminal or PowerShell:

```powershell
git clone https://github.com/Sksameer75/CalibGuard.git
```

Navigate into the project:

```powershell
cd CalibGuard
```

### Step 2: Configure Environment Variables

Create your environment file:

```powershell
Copy-Item .env.example .env
```

Open `.env` and configure your own passwords:

```env
MYSQL_ROOT_PASSWORD=your_secure_root_password
MYSQL_PASSWORD=your_secure_app_password
DB_PASSWORD=your_secure_app_password
```

Important:
- `MYSQL_PASSWORD` and `DB_PASSWORD` must match.
- Replace all example passwords with your own.
- Never upload `.env` to GitHub.

### Step 3: Start CalibGuard

Run:

```powershell
docker compose up --build -d
```

Docker Compose automatically:

1. Builds the backend image.
2. Builds the frontend image.
3. Starts the MySQL database.
4. Creates the `calibguard` database and application user.
5. Executes the database schema.
6. Applies database integrity constraints and lifecycle migration.
7. Imports the demonstration dataset.
8. Starts the Flask backend.
9. Starts the React frontend.

Wait until the containers are running.

### Step 4: Display the Frontend URL in the Terminal

Run:

```powershell
docker compose logs -f frontend
```

The Vite development server should display output similar to:

```text
VITE ready

Local:   http://localhost:5173/
Network: http://172.x.x.x:5173/
```

The exact network address may differ.

**Open the Local URL shown in your terminal in your browser.**

For example:

```text
http://localhost:5173/
```

To stop displaying logs, press:

```text
Ctrl + C
```

This only stops log monitoring. It does not stop the application.

### Step 5: Verify the Backend

Open another VS Code terminal and run:

```powershell
Invoke-RestMethod http://localhost:5000/api/health
```

A successful response should show:

```text
database   mysql_version status
--------   ------------- ------
calibguard 8.4.13        ok
```

### Step 6: Verify Docker Containers

```powershell
docker compose ps
```

Expected services:

| Service | Port | Purpose |
|---|---|---|
| Frontend | 5173 | React web application |
| Backend | 5000 | Flask REST API |
| MySQL | 3308 | Database |

## Application Access

After successful startup:

| Component | Local Address |
|---|---|
| Web Dashboard | http://localhost:5173 |
| Backend API Health | http://localhost:5000/api/health |
| MySQL Database | localhost:3308 |

**Note:** These are local development addresses. They are accessible on the computer running CalibGuard, not public internet URLs.

## Database Initialization

CalibGuard uses MySQL 8.4.

The database is initialized automatically when the MySQL data volume is created for the first time.

Initialization sequence:

| Order | File | Purpose |
|---|---|---|
| 1 | `database/schema.sql` | Creates database and base tables |
| 2 | `database/002_integrity_and_history.sql` | Adds integrity constraints, lifecycle history, triggers, and indexes |
| 3 | `data/phase3b/dataset.sql` | Imports demonstration data |

Database files are stored in a persistent Docker volume.

Initialization scripts do not run again when an existing database volume is reused.

## Managing the Application

**Start the application:**

```powershell
docker compose up -d
```

**Display frontend URL and logs:**

```powershell
docker compose logs -f frontend
```

**Display backend logs:**

```powershell
docker compose logs -f backend
```

**Display all service logs:**

```powershell
docker compose logs -f
```

**Check container status:**

```powershell
docker compose ps
```

**Stop the application:**

```powershell
docker compose down
```

**Rebuild after source-code changes:**

```powershell
docker compose up --build -d
```

### Reset the Database

If you intentionally want a completely fresh database:

```powershell
docker compose down -v
docker compose up --build -d
```

**Warning:** This deletes the Compose-managed database volume and all its stored data. Do not run this unless you intend to reset your database.

## Data and Reproducibility

CalibGuard uses synthetic industrial data for demonstration, testing, and validation.

Data workflows include:

- Synthetic data generation.
- Anomaly injection.
- Anomaly detection and validation.
- Dataset exports and manifests.
- Demonstration dataset import into MySQL.

The demonstration SQL dataset is included in `data/phase3b/dataset.sql`.

## Testing

The repository includes Python test modules covering:

- Calibration records.
- Data generation.
- Operational workflows.
- Phase 3 data processing.
- Phase 3B data processing.
- Production workflows.

Install the necessary Python and test dependencies before running:

```powershell
python -m pytest tests/
```

## Troubleshooting

**Frontend is not opening**

```powershell
docker compose logs --tail 60 frontend
```

**Backend database connection issue**

```powershell
docker compose logs --tail 60 backend
```

Verify the database is healthy:

```powershell
docker compose ps
```

**Check backend connectivity:**

```powershell
Invoke-RestMethod http://localhost:5000/api/health
```

**Rebuild the containers:**

```powershell
docker compose up --build -d
```

## Project Purpose

CalibGuard demonstrates how industrial calibration records, compliance workflows, anomaly detection, database integrity, and operational traceability can be combined into a full-stack software platform.

It is a development and demonstration project, not a certified industrial compliance system. It should not be used as the sole basis for real-world safety or regulatory decisions.

## License

No license has been specified. All rights are reserved by default unless a license is added to this repository.

---

**CalibGuard — Industrial Calibration & Compliance Management Platform**