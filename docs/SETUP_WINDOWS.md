# Smart Attendance & Security System — Windows Setup Guide

> **Phase 2 document** — generated from the real steps executed during Phase 2.  
> OS tested: Windows 10/11 · Python 3.11.9 · PowerShell 5 / 7

---

## Prerequisites

| Tool | Version | Download |
|------|---------|----------|
| Python | **3.11.x** (3.11.9 verified) | https://python.org/downloads/release/python-3119/ |
| Git | ≥ 2.40 | https://git-scm.com |
| Microsoft C++ Build Tools | ≥ 14.0 (needed by InsightFace Cython) | https://visualstudio.microsoft.com/visual-cpp-build-tools/ → select **"Desktop development with C++"** |
| Docker Desktop | ≥ 4.x | https://docs.docker.com/desktop/install/windows/ |

> **Why C++ Build Tools?**  
> InsightFace ships Cython extensions that must compile from source on Windows.  
> Without the build tools you will get:  
> `error: Microsoft Visual C++ 14.0 or greater is required`

---

## 1. Clone the Repository

```powershell
git clone https://github.com/<org>/smart-attendance-security-system.git
cd smart-attendance-security-system
```

---

## 2. Create the Python 3.11 Virtual Environment

```powershell
# Verify Python 3.11 is on PATH (or use the full installer path)
py -3.11 --version          # expected: Python 3.11.x

# Create venv (do NOT use py -3.12 or py -3.10)
py -3.11 -m venv .venv
```

---

## 3. Activate the Virtual Environment

```powershell
# If script execution is disabled, run this once:
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# Activate
.\.venv\Scripts\Activate.ps1
```

You should see `(.venv)` in your prompt.

---

## 4. Upgrade pip and Install CPU Dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
```

> **Notes:**
> - `requirements.txt` installs CPU-only runtime (no GPU/CUDA).
> - `requirements-gpu.txt` is **not** installed here — GPU setup is a separate optional step.
> - If insightface compilation fails, ensure Visual C++ Build Tools 14.0+ are installed (see Prerequisites).
> - `numpy<2` is pinned intentionally — onnxruntime and insightface require NumPy 1.x.

---

## 5. Verify the Environment

```powershell
pip check                        # must report "No broken requirements"
python scripts\check_env.py      # full check table
python scripts\check_env.py --no-camera   # skip webcam (e.g., on a server)
```

Expected output (all mandatory checks PASS):

```
Smart Attendance & Security System — Environment Check
Python: 3.11.9 (...)
Platform: Windows-...
------------------------------------------------------------
  [PASS] Python version — 3.11.9
  [PASS] import cv2
  [PASS] import numpy
  [PASS] import onnxruntime
  [PASS] import insightface
  [PASS] import fastapi
  [PASS] import sqlalchemy
  [PASS] import psycopg
  [PASS] import pgvector
  [PASS] import streamlit
  ...
  [PASS] onnxruntime CPUExecutionProvider — ['CPUExecutionProvider']
  [WARN] Docker daemon — docker not found (if Docker not installed)
  [PASS] Webcam — 1280×720 frame captured
------------------------------------------------------------
Summary: N/T PASS | W WARN | 0 FAIL
```

> If Docker shows `WARN`, install Docker Desktop and start it before Phase 3.

---

## 6. Copy and Edit Environment Variables

```powershell
Copy-Item .env.example .env
# Open .env and fill in real values — especially SECRET_KEY and database credentials
notepad .env
```

Key variables to set for local development:

| Variable | Default | Notes |
|----------|---------|-------|
| `SECRET_KEY` | `change_this_...` | Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Update after Phase 3 brings up PostgreSQL |
| `INSIGHTFACE_HOME` | `C:\Users\<You>\.insightface` | Model cache — must be outside the repo |
| `APP_TIMEZONE` | `Asia/Kolkata` | e.g. `UTC`, `America/New_York` |
| `DEVICE` | `cpu` | Keep `cpu` until GPU phase |

---

## 7. Verify .gitignore Protections

```powershell
# These must all show they are ignored — never committed
git check-ignore -v .env
git check-ignore -v data\x.jpg
git check-ignore -v model.onnx
git check-ignore -v .venv\pyvenv.cfg
```

---

## 8. Start Docker (for Phase 3+)

```powershell
# Verify Docker is running
docker info

# Bring up PostgreSQL with pgvector (Phase 3)
docker compose up -d db
docker compose ps
```

> Docker is **not required** for Phase 2 — the `check_env.py` script records it as WARN if absent, not FAIL.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `error: Microsoft Visual C++ 14.0 or greater is required` | insightface compilation fails | Install Build Tools → "Desktop development with C++" workload |
| `numpy 2.x incompatibility` | numpy version too new | Pin `numpy<2` in requirements.txt (already done) and reinstall |
| `Webcam not opening` | Camera in use by another app | Close Zoom/Teams/browser; try `cv2.VideoCapture(1)`; check Windows Settings → Privacy → Camera |
| `Script execution disabled` | PowerShell execution policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `getaddrinfo failed` during pip | DNS/proxy issue | Check VPN; set `HTTP_PROXY` / `HTTPS_PROXY`; or use `pip install --proxy <proxy>` |
| `pip check` shows conflicts | Version pinning mismatch | Update the conflicting package version range in requirements.txt and reinstall |

---

## Known Findings (Phase 2)

| Finding | Status |
|---------|--------|
| Python 3.11.9 confirmed working | ✅ |
| Docker Desktop not installed on dev machine | ⚠️ Documented — required for Phase 3 |
| InsightFace Cython compilation requires C++ Build Tools | ℹ️ Documented above |
| GPU dependencies intentionally excluded | ✅ CPU-first per ADR-05 |

---

## Next Step

Phase 3 — Docker Infrastructure: brings up PostgreSQL 16 + pgvector and Redis.
