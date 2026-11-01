# CalibGuard
### Industrial Calibration & Compliance Management Platform

CalibGuard is a full-stack industrial calibration and compliance management platform designed to help organizations monitor instrument calibration schedules, manage certificates, track work orders, identify compliance risks, and maintain operational traceability.

The project combines a Python Flask backend, React frontend, MySQL database, synthetic industrial datasets, and deterministic anomaly detection workflows.

## Key Features

- **Calibration Management** — Track instruments, calibration plans, calibration events, and calibration status.
- **Certificate Management** — Maintain calibration certificate records and associated information.
- **Work Order Management** — Organize and track calibration-related work orders.
- **Overdue Calibration Monitoring** — Identify overdue instruments and potential compliance issues.
- **Anomaly Detection** — Generate and analyze synthetic industrial data containing injected anomalies.
- **Risk and Impact Assessment** — Evaluate the operational impact of calibration and compliance issues.
- **Alerts and Audit Records** — Maintain alerts and records of important system activities.
- **Lifecycle History** — Preserve important lifecycle events for traceability.
- **Authorization Simulator** — Demonstrate authorization and decision workflows.
- **Dashboard** — Present calibration and compliance information through a web interface.

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | React, TypeScript, Vite |
| Backend | Python, Flask, REST API |
| Database | MySQL 8.4 |
| Database Connector | MySQL Connector/Python |
| Containerization | Docker, Docker Compose |
| Data Processing | Python, CSV, JSONL |
| Testing | Python test suite |

## Project Architecture

```text
CalibGuard/
│
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
│   ├── generated/
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

## Getting Started

### Prerequisites

Install the following before running the project:

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Git](https://git-scm.com/)

Docker Desktop must be running before you execute the commands below.

You do not need to install MySQL, Python, or Node.js separately to run the Docker-based setup.

### 1. Clone the Repository

```bash
git clone https://github.com/Sksameer75/CalibGuard.git
cd CalibGuard
```

### 2. Configure Environment Variables

Create your local environment file:

**Windows PowerShell:**

```powershell
Copy-Item .env.example .env
```

Open `.env` and replace the example passwords with your own strong passwords.

```env
MYSQL_ROOT_PASSWORD=your_secure_root_password
MYSQL_PASSWORD=your_secure_app_password
DB_PASSWORD=your_secure_app_password
```

Important:
- `MYSQL_PASSWORD` and `DB_PASSWORD` must match.
- Use your own passwords.
- Never commit `.env` to GitHub.
- `.env.example` contains placeholders only.

### 3. Build and Start the Application

Run:

```bash
docker compose up --build -d
```

Docker Compose will:

1. Build the Flask backend image.
2. Build the React frontend image.
3. Start the MySQL 8.4 database.
4. Create the `calibguard` database and application user.
5. Execute the database schema.
6. Apply the integrity and lifecycle migration.
7. Import the demonstration dataset.
8. Start the backend after MySQL becomes healthy.
9. Start the frontend.

**The database initialization scripts execute automatically when the MySQL data volume is first created.**

### 4. Access the Application

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API health | http://localhost:5000/api/health |
| MySQL | localhost:3308 |

### 5. Verify the Backend

Run:

```bash
curl http://localhost:5000/api/health
```

A successful response should report the database status as `ok` and show the MySQL version.

### 6. View Container Status

```bash
docker compose ps
```

View logs:

```bash
docker compose logs -f
```

View individual service logs:

```bash
docker compose logs backend
docker compose logs frontend
docker compose logs mysql
```

## Database Initialization

CalibGuard uses MySQL 8.4 and automatically initializes its database through Docker Compose.

The initialization sequence is:

| Order | File | Purpose |
|---|---|---|
| 1 | `database/schema.sql` | Creates the database and base tables |
| 2 | `database/002_integrity_and_history.sql` | Adds integrity constraints, lifecycle history, triggers, and indexes |
| 3 | `data/phase3b/dataset.sql` | Imports the demonstration dataset |

The database is stored in a persistent Docker volume named `calibguard_public_mysql_data` (managed by Docker Compose).

**Important:** Initialization scripts run automatically only when the MySQL data directory is empty. Restarting the application does not re-import the dataset or recreate the database.

## Stopping and Restarting

Stop the application:

```bash
docker compose down
```

Start it again:

```bash
docker compose up -d
```

The database volume remains intact when you run `docker compose down`.

To intentionally delete the database and start from a completely fresh installation:

```bash
docker compose down -v
docker compose up --build -d
```

**Warning:** The `-v` option permanently deletes the Compose-managed database volume and its stored data.

## Testing

The repository includes Python test modules covering data generation, calibration records, operations, anomaly detection, and production-related workflows.

Run the test suite from the project root after installing the required Python dependencies and any additional test dependencies:

```bash
python -m pytest tests/
```

## Data and Reproducibility

CalibGuard uses synthetic industrial data for demonstration and testing.

The data workflows include:
- Synthetic data generation.
- Anomaly injection.
- Anomaly detection and validation.
- Dataset exports and manifests.
- Demonstration data import into MySQL.

The demonstration dataset is included in `data/phase3b/dataset.sql`.

The project is intended for development, demonstration, and evaluation. It is not a certified industrial compliance system and should not be used as the sole basis for real-world safety or regulatory decisions.

## Troubleshooting

**MySQL is not ready**

```bash
docker compose logs mysql
docker compose ps
```

Wait until MySQL reports a healthy status.

**Backend cannot connect to MySQL**

Check that:
- MySQL is healthy.
- `MYSQL_PASSWORD` and `DB_PASSWORD` match in `.env`.
- The backend is configured to use the Compose service hostname `mysql`.
- The database name is `calibguard`.

**Frontend cannot communicate with the backend**

Check:

```bash
docker compose logs backend
docker compose logs frontend
```

Verify that the backend is available at:

```text
http://localhost:5000/api/health
```

**Rebuild after changing source code**

```bash
docker compose up --build -d
```

## License

No license has been specified yet. All rights and permissions are reserved by default unless a license is added to this repository.

---

**CalibGuard — Industrial Calibration & Compliance Management Platform**