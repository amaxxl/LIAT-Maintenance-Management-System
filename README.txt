LIAT MAINTENANCE MANAGEMENT SYSTEM
Stage 3 Django Prototype | Documentation revision: 23 November 2026
===============================================================

1. PURPOSE AND SCOPE
--------------------
LIAT is a web-based maintenance-request prototype for one fictional educational
institution. Students and employees report equipment/facility problems;
maintenance coordinators review and assign work; technicians record repairs;
coordinators approve closure. The application retains status, assignment,
repair, deadline and original-location history.

The application is for LOCAL DEMONSTRATION only. It is not a production service.

2. SOFTWARE REQUIREMENTS
------------------------
- Windows 11 with PowerShell; VS Code is optional.
- Python 3.14.5 is the version used in the developer's tested Windows setup.
  Use Python 3.14.x for the closest match. Other versions have not been
  verified for this submission.
- pip, supplied with Python.
- Dependencies in requirements.txt: Django >=5.2,<6.0 and
  psycopg[binary] >=3.2,<4.0. The developer previously tested Django 5.2.19.
- Local database: SQLite (automatically created by Django migrations).
- No external database server or frontend build tool is needed for SQLite.

3. INSTALLATION FROM A FRESH COPY (WINDOWS POWERSHELL)
-----------------------------------------------------
Download the repository as a ZIP or clone it using Git. Open a PowerShell
terminal INSIDE the folder containing manage.py (not inside core/).

  py -3.14 -m venv .venv
  .\.venv\Scripts\python.exe -m pip install -r requirements.txt
  .\.venv\Scripts\python.exe manage.py migrate
  .\.venv\Scripts\python.exe manage.py seed_demo
  .\.venv\Scripts\python.exe manage.py check
  .\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
  .\.venv\Scripts\python.exe manage.py test
  .\.venv\Scripts\python.exe manage.py runserver

If the Python launcher does not recognize -3.14, verify the installed version
with 'py --version' and use 'py -m venv .venv' when it is Python 3.14.x.
Use the exact commands above on separate lines. Stop the server with Ctrl+C.

IMPORTANT: Run 'migrate' using the INCLUDED migration files. Do not generate
fresh migrations as part of normal installation. The repository contains
core/migrations/0001_initial.py and 0002_duedatehistory.py.

4. START THE APPLICATION
-----------------------
Open http://127.0.0.1:8000/login/ after starting the server.
Dashboard: http://127.0.0.1:8000/
Django Admin (administrator only): http://127.0.0.1:8000/admin/

For later runs, open a terminal in the same folder and use:

  .\.venv\Scripts\python.exe manage.py runserver

An optional start_windows.ps1 script installs dependencies, migrates, seeds
fictional users, runs the tests, then starts the local development server.
Do not run this script on any production or real-data environment.

5. LOCAL DEMONSTRATION CREDENTIALS ONLY
--------------------------------------
The seed_demo command creates the following FICTIONAL accounts.
For NEWLY CREATED accounts, the local demo password is: DemoPass123!
Existing account passwords are not changed by seed_demo.

  student1       Requester (student)
  employee1      Requester (employee)
  employee2      Requester (employee; privacy checks)
  technician1    Technician (IT Maintenance)
  technician2    Technician (IT Maintenance)
  coordinator1   Maintenance Coordinator (IT Maintenance scope)
  coordinator2   Maintenance Coordinator (Facilities scope)
  admin1         Academy Administrator (Django Admin access)

NEVER reuse these credentials for real accounts or deploy the application
with seeded demo users. Do not publish any real passwords or local database.

6. MAIN IMPLEMENTED FUNCTIONALITY
---------------------------------
- Authenticated, role-scoped request submission and viewing.
- Separate Academy Administrator and Maintenance Coordinator roles:
  administrators manage accounts/equipment/master data and view requests;
  they do NOT perform maintenance workflow actions.
- Central intake for initially unassigned requests, followed by
  maintenance-group-scoped coordinator permissions.
- Equipment, problem type, priority and original room/unit snapshots.
- Validated group/technician selection with server-side eligibility checks
  for active membership, equipment category and problem type.
- Workflow: Submitted -> Under Review -> Assigned -> In Progress ->
  Completed -> Closed; permitted rejection, reassignment and return paths.
- Reassignment and return-for-correction paths with recorded history.
- Resolution note required for completion; coordinator approves closure.
- Optional coordinator-set deadlines with a reason and DueDateHistory;
  overdue means the deadline has passed and the request is not Completed,
  Closed or Rejected.
- Request dashboard search and separate status, equipment, group,
  priority, submission-date-from/to and overdue filters, within role scope.
- Reports covering status, completed/closed work, overdue work and group load.
- Transactional history for workflow updates. In Django Admin, submitted
  MaintenanceRequest entries are view-only. Normal model saves protect
  submitted reporter, equipment, problem type and location snapshot.
- Automated Django tests for permissions, workflow, history, filters,
  deadlines, reporting and validation.

7. DEMONSTRATION FLOW
---------------------
Sign in as student1; submit a problem for LIAT-PC-001. Then sign in as
coordinator1 to review and assign the request to technician1. As the
technician, start work and complete it with a resolution note. As the
coordinator, set/change a deadline if appropriate, verify audit history,
then close the request or return it for correction. Compare the historical
request location with the equipment's current location after an admin
updates the asset's room. Check role restrictions with employee2 and
coordinator2, and inspect reports and dashboard filters.

8. AUTOMATED TESTS AND CURRENT VERIFICATION
-------------------------------------------
Command: .\.venv\Scripts\python.exe manage.py test

On 23 November 2026, the developer reported the following result from the
existing Windows development environment:
  Found 33 test(s).
  System check identified no issues (0 silenced).
  Ran 33 tests in 217.864s
  OK

These results establish that the suite passed on that existing setup.
They DO NOT establish that this revised documentation/startup script has
been checked from a fresh clone. A clean-install test and an end-to-end
browser walkthrough still need to be verified before the final submission.

9. DATABASE, VERSION HISTORY AND BACKUP
---------------------------------------
The default SQLite file is liat_dev.sqlite3 in the project root. It is
created automatically by 'migrate' and must NOT be committed to GitHub.
The .gitignore excludes it, .venv, caches and .env files.

Back up the SQLite file before changing an existing installation. Do not
copy older migration files over the repository's current numbered migrations;
those files correspond to the submitted model history. If you have an old
Stage 2 database, do not swap it into this prototype without a verified
migration plan. Fresh installation is recommended for reviewers.

Git repository:
https://github.com/amaxxl/LIAT-Maintenance-Management-System
Access is private unless the owner changes the setting; reviewers need a
GitHub invitation. Commit history records separate development corrections.

10. LIMITATIONS AND SECURITY
----------------------------
- Current UI uses Django templates, HTML and CSS, NOT Vue.
- The prototype does NOT implement Django REST Framework or a REST API.
- Current verified database is SQLite. PostgreSQL is not configured/tested
  as the submitted working deployment; an optional environment-based setting
  exists but does not make PostgreSQL an implemented, verified deployment.
- Not production deployed. DEBUG defaults to on, and the source contains a
  DEVELOPMENT-ONLY fallback secret key. A safe production configuration,
  security review and deployment are OUTSIDE this prototype.
- Audit history is not cryptographically tamper-proof; bulk updates or raw
  SQL could bypass model-level save validation.
- Automated tests are not a substitute for full usability, performance,
  penetration or concurrency tests. Backup/restore procedures are not fully
  implemented as application features.

11. PROJECT FILES
-----------------
manage.py                      Django management entry point
liat_settings.py               Django settings (development-oriented)
liat_urls.py                   Application URL routing
core/models.py                 Database models and record constraints
core/forms.py                  Forms and validation
core/views.py                  Request handlers, dashboard and reports
core/services.py               Workflow permissions and business rules
core/admin.py                  Django Admin configuration
core/tests.py                  Automated regression tests
core/migrations/               Included database migrations
core/templates/core/           Django-rendered HTML templates
core/management/commands/      seed_demo management command
requirements.txt               Required dependencies
start_windows.ps1              Optional local setup/start script
TEST_CHECKLIST.md              Manual browser-verification checklist

This documentation describes the prototype and must be checked against the
actual final GitHub commit before it is sent to the supervisor.
