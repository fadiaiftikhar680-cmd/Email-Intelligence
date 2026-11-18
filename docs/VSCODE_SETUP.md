# VS Code & Windows Developer Setup Guide

> **Email Intelligence Platform ("Find. Verify. Enrich.")**  
> Complete, beginner-friendly instructions for running, debugging, and testing the project on Windows 10/11 using Visual Studio Code.

---

## 📋 1. Prerequisites

Before starting, ensure you have the following installed on your Windows machine:
1. **Python 3.12+**: Download and install from [python.org](https://www.python.org/downloads/).  
   *(Make sure to check the box **"Add Python to PATH"** during installation!)*
2. **Visual Studio Code**: Download and install from [code.visualstudio.com](https://code.visualstudio.com/).
3. **Recommended VS Code Extensions**:
   - **Python** (`ms-python.python`)
   - **Pylance** (`ms-python.vscode-pylance`)
   - **Black Formatter** (`ms-python.black-formatter`)
   - **Django** (`batisteo.vscode-django`)

---

## 📁 2. Open Project in VS Code

1. Launch **Visual Studio Code**.
2. Click **File** > **Open Folder...** (or press `Ctrl+K Ctrl+O`).
3. Select the project folder:
   ```text
   C:\Users\ABDULLAH COMPUTERS\OneDrive\Desktop\Emil Intelligence
   ```
4. Trust the authors if prompted.

---

## 🛠️ 3. Create & Activate Virtual Environment

Open the VS Code Integrated Terminal by pressing ``Ctrl+` `` (backtick) or selecting **Terminal** > **New Terminal**.

### Option A: PowerShell (Recommended)

1. Check or enable execution policy if script running is restricted:
   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   ```
2. Create the virtual environment named `venv`:
   ```powershell
   python -m venv venv
   ```
3. Activate the virtual environment:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
   *(You should see `(venv)` appear at the beginning of your terminal prompt).*

### Option B: Command Prompt (cmd.exe)

1. Create the virtual environment:
   ```cmd
   python -m venv venv
   ```
2. Activate it:
   ```cmd
   venv\Scripts\activate.bat
   ```

---

## 📦 4. Install Dependencies

With your virtual environment activated, install all required packages:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Verify installed packages:
- `Django==5.0.6`
- `djangorestframework==3.15.1`
- `drf-spectacular==0.27.2`
- `dnspython==2.6.1`
- `argon2-cffi==23.1.0`
- `openpyxl==3.1.2`
- `whitenoise==6.6.0`
- `requests==2.32.3`
- `beautifulsoup4==4.12.3`

---

## ⚙️ 5. Configure Environment Variables

The project comes with a pre-configured `.env.example`. Create your local `.env`:

In PowerShell:
```powershell
Copy-Item .env.example .env
```
Or in CMD:
```cmd
copy .env.example .env
```

The default values are already pre-configured for local development with SQLite (`db.sqlite3`).

---

## 🗄️ 6. Run Migrations & Collect Static Assets

Initialize the database schema and gather UI static assets:

```powershell
# Apply database migrations (25 migrations across all modules)
python manage.py migrate

# Collect static assets into staticfiles
python manage.py collectstatic --noinput
```

---

## 👤 7. Pre-seeded Administrator Account

The database already includes a pre-seeded, active administrative user ready for immediate login:

| Field | Value |
| :--- | :--- |
| **Email / Username** | `admin@emailintelligence.local` |
| **Password** | `AdminPassword123#Secure` |
| **Role** | Superuser & Staff |
| **Verification Balance** | 100,000 Credits |

If you ever need to create an additional administrator, run:
```powershell
python manage.py createsuperuser
```

---

## 🚀 8. Running the Platform in VS Code

You have three easy ways to run the project in VS Code:

### Method 1: VS Code Run & Debug (`F5`)
1. Press `F5` (or click the **Run and Debug** tab on the left sidebar: `Ctrl+Shift+D`).
2. Select **"Django: Run Server"** from the drop-down menu at the top.
3. Click the green Play button.
4. The server starts in the integrated terminal with full debugging support and breakpoints enabled!

### Method 2: VS Code Tasks Menu
1. Press `Ctrl+Shift+P` (or `F1`).
2. Type `Tasks: Run Task` and press Enter.
3. Select **"Django: Run Server"**.

### Method 3: Direct Terminal Command
In your activated terminal:
```powershell
python manage.py runserver 127.0.0.1:8000 --noreload
```

> **Note on `--noreload`:** On Windows, the `--noreload` flag ensures that the server binds cleanly without port collisions or terminal output buffering issues.

Open your browser and navigate to:
👉 **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**  
👉 Dashboard: **[http://127.0.0.1:8000/dashboard/](http://127.0.0.1:8000/dashboard/)**  
👉 Interactive API Docs (Swagger): **[http://127.0.0.1:8000/api/schema/swagger-ui/](http://127.0.0.1:8000/api/schema/swagger-ui/)**

---

## 🧪 9. Running Automated Tests in VS Code

The platform includes a test suite covering the 13 verification rules, DNS lookups, multi-MX probing, SSRF defense, bulk deduplication, formula injection protection, and REST API authentication.

### In VS Code Run & Debug:
1. Open the **Run and Debug** view (`Ctrl+Shift+D`).
2. Select **"Django: Run Tests"** and press `F5`.

### In Terminal:
```powershell
python manage.py test --verbosity=2
```

**Expected Result:**
```text
Ran 33 tests in ~3.0s
OK
```

---

## 🔧 10. Troubleshooting Common Windows Issues

### Issue 1: `Activate.ps1 cannot be loaded because running scripts is disabled`
- **Cause:** Windows PowerShell default execution policy blocks unsigned scripts.
- **Solution:** Run this command once in PowerShell:
  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
  ```

### Issue 2: `Error: That port is already in use.`
- **Cause:** A previous Django server instance is still running in the background.
- **Solution:** Find and terminate the process holding port 8000:
  ```powershell
  Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
  ```

### Issue 3: Port 25 Outbound Blocking by Residential ISP
- **Cause:** Most consumer internet service providers (ISPs) block outbound connections to TCP port 25 to prevent spam bots.
- **Behavior:** The engine handles this cleanly according to RFC standards. If port 25 times out, the engine returns `status: unknown` and reason `PROBE_UNAVAILABLE` or `INSUFFICIENT_EVIDENCE`.
- **Note:** In production, run on cloud hosts (AWS/GCP/DigitalOcean) with port 25 unblocked or reverse DNS configured.

---

## 📂 11. VS Code Configuration Files Summary

The following configuration files are located in `.vscode/`:
- **`.vscode/launch.json`**: Debugging profiles for `Django: Run Server`, `Django: Run Tests`, `Celery: Worker (Windows Solo)`, and `Python: Current File`.
- **`.vscode/settings.json`**: Interpreter path, Black formatting on save, Django template formatting, and file exclusions.
- **`.vscode/tasks.json`**: Pre-configured build and maintenance tasks (Run Server, Run Tests, Make Migrations, Migrate, Collect Static, Generate OpenAPI Schema).

