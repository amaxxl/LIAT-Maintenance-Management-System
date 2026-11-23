# LIAT Maintenance Management System — Stage 3 Django Prototype

A local demonstration application for managing maintenance requests in one fictional educational institution. Requesters report equipment problems, maintenance coordinators review and assign eligible technicians, technicians record repairs, and coordinators close completed work. The application preserves request histories and original equipment-location snapshots.

**The authoritative setup and demonstration guide is [README.txt](README.txt).** It includes the precise Windows setup steps, Python version, migration instructions, local demonstration users, test command, implemented functionality and limitations requested for supervisor review.

## Quick start (Windows PowerShell)

Open a terminal in the project root (the directory containing `manage.py`):

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe manage.py runserver
```

Open <http://127.0.0.1:8000/login/>. Python 3.14.5 and Django 5.2.19 were used in the developer's Windows environment. `requirements.txt` expresses the supported dependency ranges; exact cross-version compatibility has not been independently verified.

**Do not run `makemigrations` during normal setup.** The tracked files `core/migrations/0001_initial.py` and `core/migrations/0002_duedatehistory.py` are included; `migrate` applies them.

## Features

- Separate requester, technician, coordinator and administrator permissions.
- Shared unassigned intake, group-scoped assignment, technician eligibility checks, status transitions and reassignment.
- Completion notes, coordinator approval, immutable original-location snapshots and historical audit records.
- Optional coordinator-maintained due dates with reason/history and overdue reporting.
- Role-scoped dashboard with search plus status, equipment, group, priority, submitted-date-range and overdue filters.
- Reports, Django Admin master-data management and regression tests.

## Verification

On 23 November 2026 the developer ran **33 Django tests**, all passing, with zero system-check issues in the existing Windows setup. A full fresh-clone verification and final browser walkthrough remain to be completed. See `TEST_CHECKLIST.md`.

## Scope and safety

**Local prototype only.** The running UI uses Django templates and SQLite; Vue, Django REST Framework, a verified PostgreSQL deployment and production hosting are **not implemented** in this release. The source contains fictional demo credentials and development-only defaults; do not deploy this project on the public internet or commit a local SQLite database or real secrets. See `README.txt` for the complete explanation.

Development history is preserved through the Git commit log. Thesis descriptions should reflect only verified features and clearly disclose AI assistance as required by university policy.
