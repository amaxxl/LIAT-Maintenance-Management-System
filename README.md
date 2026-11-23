# LIAT Maintenance — Stage 3 Django prototype

This is the **updated source project**, based on the user's original Stage 2 ZIP. It uses Django-rendered pages and SQLite by default. Vue, Django REST Framework and PostgreSQL are **not** implemented in this release. All accounts and faults in the seed dataset are fictional. Keep the application local; it has not undergone a deployment/security audit.

## Improvements in this update

- Four separate permission roles: **Requester** (student/employee account type), Technician, Maintenance Coordinator (maintenance workflow), Academy Administrator (user/equipment/master-data administration and read-only request oversight). Existing `employee` role entries remain accepted as requesters so older databases can migrate safely.
- Explicit shared **intake queue**: active coordinators see new unassigned Submitted and Under Review requests and may review or reject them. A coordinator may assign requests only to a group within their authorised scope. Once assigned, only a coordinator scoped to that group can manage the workflow. The academy administrator can view all requests and maintenance reports but **cannot** review, assign, reassign, return, reject or close maintenance requests.
- Assignment uses **validated group and technician dropdowns**. Candidate technicians must be active, have active group membership, and have active competency for the equipment category **and** problem type. Server-side validation is authoritative; filtering dropdown options is only a usability aid.
- **Reassignment** from Assigned, In Progress, or Completed resets the request to Assigned and logs the old/new technician and group with actor, time, and reason. The previous assignee loses access.
- **Return for correction** after Completed returns work to In Progress for the **same** technician; alternatively the coordinator selects *Reassign for correction*, which returns the work to Assigned for the new technician.
- Maintenance Coordinators can set, change, or clear optional due dates after review and before closure/rejection, with a mandatory reason and append-only deadline history. Existing deadlines are visible to requesters and technicians. Overdue means a due date is before now and the status is not Completed, Closed, or Rejected. Django Admin cannot edit due dates directly.
- Role-scoped dashboard with separate equipment, status, priority, maintenance group, submission-date-from/to, and overdue filters, plus text search. Filters can be combined. Equipment and group dropdown options are limited to data visible to the signed-in user. The submission date range uses the request creation date, while overdue is based on due_at. Coordinators/administrators also have a reports page showing status counts, completed/closed, overdue, and active work by group.
- Additional negative/boundary tests for direct-URL privacy, unauthorised actions, eligibility, cross-group coordinator scope, missing resolution notes, history, relocation snapshots, transitions, and reporting.
- A cleaner responsive interface. User and master-data management use Django Admin. Audit rows are read-only in Django Admin, not protected against raw database editing.

## How to run on Windows (new installation)

Open **PowerShell** in the extracted `LIAT_stage2_code` folder:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py makemigrations core
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe manage.py runserver
```

Open **http://127.0.0.1:8000/login/**. No internet access is needed after the Python dependencies have already been installed.

### If you already have Stage 2 request data and want to keep it

**Do not delete or overwrite your old project. Make a backup first.** The safest option is to extract this ZIP **into a new separate folder**, then:

1. From the **old** `LIAT_stage2_code`, copy `liat_dev.sqlite3` into the new extracted `LIAT_stage2_code` folder. This is the actual default database filename; it contains any existing demo requests and histories. **Do not share this file publicly.**
2. From the **old** `core/migrations/` folder, copy *all numbered migration files* (`0001_*.py`, `0002_*.py` etc.) into the new `core/migrations/` folder, retaining `__init__.py`. This is essential when reusing an existing database.
3. Run the commands above **in the new project**. `makemigrations core` should propose the new `Profile.account_type` and role-choice changes; `migrate` applies them while retaining existing records.
4. `seed_demo` will create any missing fictional student/technician accounts and update the demo roles. It **never changes the passwords of existing users**, so use your prior password for `employee1` if you changed it.
5. Run `python manage.py test` and only then start `runserver`. If migrations fail, **stop and share the complete error**; do not delete the database or migration files.

If you do not want to preserve previous local data, skip steps 1–2 and start with a fresh database. Previous Request #2 and its history will not appear in the new empty database unless copied.

## Demo accounts

`seed_demo` sets the password to `DemoPass123!` **only on newly created users**:

| Username | Role | Notes |
|---|---|---|
| `student1` | Requester | Student account type |
| `employee1` | Requester | Original employee demo account |
| `employee2` | Requester | Another reporter for privacy checks |
| `technician1` | Technician | IT Maintenance |
| `technician2` | Technician | IT Maintenance; reassignment demo |
| `coordinator1` | Coordinator | IT Maintenance scope |
| `coordinator2` | Coordinator | Facilities scope; not authorised for IT work |
| `admin1` | Administrator | Django Admin access |

**Local testing only:** Never deploy these accounts and passwords to the public internet. Set a unique `DJANGO_SECRET_KEY`, disable DEBUG, configure hosts/security settings, and perform a full deployment assessment before any real-world use.

## Main demonstration flow

1. Sign in as `student1` or `employee1`. Use **Report fault** and select `LIAT-PC-001`, Hardware fault. The new request starts as **Submitted** with its initial room/unit snapshot.
2. Sign in as `coordinator1`. Both `coordinator1` and `coordinator2` can initially see unassigned intake, but only a coordinator with IT Maintenance scope may assign it to that group. Open the request and select **Review request**, then **Assign technician** and choose **IT Maintenance** → **technician1** from dropdowns. Provide a reason.
3. Sign in as `technician1`, choose **Start work**, then **Complete work** with a resolution note. Blank completion notes are rejected.
4. Optionally, while the request is active, sign in as `coordinator1` and choose **Set or update due date**. Enter a future local date/time or leave it blank to clear a deadline, with a reason. Check **Due date history** to see the change.
5. Sign in as `coordinator1`. Choose **Return for correction** (same technician returns to In Progress) or **Reassign for correction** to `technician2` (request resets to Assigned; previous/new assignment is recorded), or **Approve and close** to finish.
6. View **Reports** as coordinator or administrator. Use filters and verify the request's **Status history**, **Assignment history**, and **Repair notes**.
7. Test privacy via `employee2`, `technician2`, and `coordinator2` on a request not assigned to them / their group. Those direct pages and actions should return HTTP 403 where unauthorised.
8. Change the equipment location in Django Admin and confirm the old request still displays the initial room/unit snapshot.

## Model and known limitations

- Model-level snapshot validation runs in `.save()`; raw SQL / bulk updates can bypass it. Audit history is transactionally saved by the service and read-only in Django Admin but is not tamper-evident at the DB level.
- A coordinator can triage any unassigned incoming request; after group assignment the scope becomes group-specific. This is a conscious policy choice for the prototype, not an academy-wide universal requirement.
- User creation, activation/deactivation, role assignment, and master data currently use **Django Admin**. A new user can be created via the User page and a Profile role can be attached via the user's edit page or Profiles admin. Don't grant `is_staff`/`is_superuser` to ordinary requesters.
- Due dates are optional and can be changed or cleared by a coordinator during Under Review, Assigned, In Progress and Completed states. Changes require an explanation and are logged in DueDateHistory; deadlines can no longer be edited directly in Django Admin. Backup/restore procedures still need further work.
- SQLite supports the local prototype. On SQLite, `select_for_update` does not provide the same row-level locking as PostgreSQL, so concurrency has not been stress-tested.
- Django's provided security features help, but full endpoint/penetration/performance tests, deployment, comprehensive account lifecycle integration, report exports, and frontend/API migration remain future work.
- This package contains **new tests**, but their execution must be verified in the user's local Django environment. A Python syntax check is not a substitute for the Django test suite.

## Thesis integrity

Document only features actually demonstrated or tested. Report the new test outcomes only after running `python manage.py test` successfully, and verify negative tests in the browser as appropriate. Describe unfinished work as planned. Disclose AI assistance according to the university's academic-integrity rules.
