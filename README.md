# Email Intelligence Platform (Find. Verify. Enrich.)

> **"Find. Verify. Enrich."**  
> Complete end-to-end technical implementation conforming strictly to the platform documentation v0.2.0.

---

## 🌟 Overview

The **Email Intelligence Platform** is a trustworthy, evidence-based email discovery and verification platform designed with full transparency:
- **Email Finder Engine**: Discovers publicly listed business emails from company web pages and permitted public professional directories within bounded depth and page limits. Tracks exact source pages and methods (`mailto_link`, `page_text`, `company_pattern`).
- **Email Verification Engine**: Evaluates technical deliverability signals across **13 deterministic decision rules** (syntax, DNS resolution, MX records, multi-MX failover, 600+ disposable domain detection, role-based classification, and safe SMTP probing without sending message data).
- **Company & People Intelligence Engine**: Collects publicly evidenced business facts and professional profiles with per-attribute source references.
- **Bulk Verification**: Processes lists of up to 10,000 rows (`.csv` and `.xlsx`) with background chunking, deduplication, live 2.5s polling progress tracking, and spreadsheet formula-injection neutralization.
- **Modern Live Dashboard**: Real-time deliverability donut chart, 7-day activity timeline, timeframe filtering (All Time, 30 Days, 7 Days, Today), active job pulse indicator, and quota telemetry. Zero fake buttons or dummy statistics.
- **Public & Internal REST API (v1)**: Scoped API keys with SHA-256 storage, OpenAPI 3.0 schema generation, Swagger UI, and Redoc.
- **Security & Privacy by Design**: SSRF protection guarding every outbound fetch, Argon2 password hashing, owner-only data isolation, and audited administrative break-glass access.

---

## 📚 Technical Documentation

- 📘 **[Complete Technical Documentation](docs/PROJECT_DOCUMENTATION.md)**: Full architecture breakdown, 13-rule verification flowchart, multi-MX failover logic, RFC 3463 diagnostics, audit evidence schema, and security specifications.
- 💻 **[VS Code & Windows Setup Guide](docs/VSCODE_SETUP.md)**: Beginner-friendly Windows setup, virtual environment configuration, debugging with `F5`, and troubleshooting.

---

## 🚀 Quick Start (Local Setup)

### 1. Prerequisites
- Python 3.12+
- Visual Studio Code (or terminal of your choice)

### 2. Environment Setup
Configure your environment from the example file:
```powershell
# In PowerShell:
Copy-Item .env.example .env

# Or in Command Prompt:
copy .env.example .env
```

Install dependencies:
```powershell
pip install -r requirements.txt
```

### 3. Run Database Migrations & Static Assets
```powershell
python manage.py migrate
python manage.py collectstatic --noinput
```

### 4. Administrator Credentials
A pre-seeded administrator account is already provisioned in the local database:

| Field | Value |
| :--- | :--- |
| **Email** | `admin@emailintelligence.local` |
| **Password** | `AdminPassword123#Secure` |
| **Verification Balance** | 100,000 Credits |

To create an additional administrator:
```powershell
python manage.py createsuperuser
```

### 5. Launch the Server
```powershell
python manage.py runserver 127.0.0.1:8000 --noreload
```

Visit the application in your browser:
- 🌐 **Landing Page**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- 📊 **Professional Dashboard**: [http://127.0.0.1:8000/dashboard/](http://127.0.0.1:8000/dashboard/)
- 🔍 **Single Email Verifier**: [http://127.0.0.1:8000/verifier/single/](http://127.0.0.1:8000/verifier/single/)
- 📁 **Bulk List Verifier**: [http://127.0.0.1:8000/verifier/bulk/](http://127.0.0.1:8000/verifier/bulk/)
- 📖 **Interactive Swagger UI**: [http://127.0.0.1:8000/api/schema/swagger-ui/](http://127.0.0.1:8000/api/schema/swagger-ui/)

---

## 💻 Running with VS Code

The project includes ready-to-use VS Code configurations in `.vscode/`:
- **Press `F5`** to launch **"Django: Run Server"** with full debugging and breakpoints.
- **Select "Django: Run Tests"** in the Run and Debug tab to execute all automated tests.
- **Tasks Menu (`Ctrl+Shift+P` > `Tasks: Run Task`)** includes pre-built shortcuts for migrations, static files, and running workers.

For complete step-by-step instructions, see [`docs/VSCODE_SETUP.md`](docs/VSCODE_SETUP.md).

---

## 🐳 Running with Docker Compose

To run the full stack including PostgreSQL, Redis, Django Web, Celery Worker, and Celery Beat:
```bash
docker-compose up --build
```

---

## 🧪 Running the Test Suite

Run the full automated test suite covering all 13 verification rules, DNS lookups, multi-MX probing, SSRF guards, bulk deduplication, formula injection neutralization, owner isolation, and public APIs:
```powershell
python manage.py test --verbosity=2
```

**Status:** 33 tests executed in ~3.0s — **100% Passing (0 failures, 0 errors, 0 warnings)**.

---

## 📖 Key Routes & Architecture

### Public & Marketing Screens
- **`/`**: Landing Page (S-01)
- **`/register/`**: Registration with 12+ character password enforcement (S-02)
- **`/login/`**: Authentication with Argon2 password hashing (S-04)
- **`/terms/`**, **`/privacy/`**, **`/acceptable-use/`**: Legal Disclaimers (S-21)
- **`/opt-out/`**: Suppression & Do Not Disclose Request Form (S-22)

### Authenticated Application Screens
- **`/dashboard/`**: Metrics derivable from real stored data (S-06)
- **`/verifier/single/`**: Single Email Verifier with 13-rule evidence breakdown (S-09)
- **`/verifier/bulk/`**: Bulk List Processor for CSV/XLSX with live polling (S-10)
- **`/finder/company/`**: Company Website Email Finder (S-07)
- **`/finder/person/`**: Person Finder Both-Plus (Method A: Profile URL & Method B: Name + Company) (S-08)
- **`/finder/combined/`**: 4-Stage Combined Orchestration Pipeline (S-11)
- **`/intelligence/`**: Public Knowledge Graph Directory (S-12, S-13)
- **`/history/finder/`**: Search History (S-14)
- **`/history/verifications/`**: Verification History (S-15)
- **`/reports/`**: Reports & Neutralized Spreadsheet Downloads (S-16)
- **`/api-keys/`**: Scoped API Key Management (S-17)
- **`/api-docs/`**: Interactive Documentation & Swagger UI (S-18)
- **`/settings/`**: Preferences & Account Deletion with Cascade (S-19)
- **`/admin-portal/`**: Administrative Operations & Audited Break-Glass View (S-20)

### Public REST API (v1)
All endpoints require `Authorization: Api-Key <key>`:
- `POST /api/v1/email/verify` (Scope: `email:verify`)
- `POST /api/v1/email/verify/bulk` (Scope: `bulk:write`)
- `GET /api/v1/jobs/{id}` (Scope: `jobs:read`)
- `GET /api/v1/jobs/{id}/results` (Scope: `jobs:read`)
- `POST /api/v1/jobs/{id}/cancel` (Scope: `bulk:write` or `finder:run`)
- `POST /api/v1/finder/company` (Scope: `finder:run`)
- `POST /api/v1/finder/person` (Scope: `finder:run`)
- `GET /api/v1/usage` (Scope: `usage:read`)
- `GET /api/v1/account` (Scope: `account:read`)
- OpenAPI Spec: `/api/schema/`, `/api/schema/swagger-ui/`, `/api/schema/redoc/`

---

## ⚖️ Standing Disclaimer
*Results show technical deliverability signals and are not a delivery guarantee. Mail server firewalls, catch-all settings, and spam filters can alter final delivery.*
