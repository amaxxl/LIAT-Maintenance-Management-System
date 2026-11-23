# LIAT Stage 3 — verification checklist (record outcomes honestly)

Do not claim these tests passed until they were run on a machine with the project's Django dependencies installed. The provided project defines **19 automated test cases**; they were checked for Python syntax in the preparation environment but the Django suite was **not executed there** because Django was not available and the environment could not download packages.

## Before a supervisor submission

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test -v 2
.\.venv\Scripts\python.exe manage.py runserver
```

Record the actual test count, outcome, date and environment **after running** these commands. A newly created migration may need to be applied before `--check --dry-run` passes.

## Browser scenarios to demonstrate

| ID | Test | What to check | Result |
|---|---|---|---|
| B01 | Student fault reporting | `student1` creates a new fault; submitted and snapshotted | Not yet run |
| B02 | Legacy employee migration | Existing `employee1` still sees only their requests | Not yet run |
| B03 | Intake queue | New unassigned request visible to coordinators 1 and 2 | Not yet run |
| B04 | Qualified assignment | Coordinator 1 uses group and technician dropdowns; reason logged | Not yet run |
| B05 | Scope enforcement | Coordinator 2 cannot read/modify a request assigned to IT Maintenance | Not yet run |
| B06 | Technician privacy | Technician 2 cannot modify Technician 1's current work | Not yet run |
| B07 | Completion guard | Completion without resolution note is rejected | Not yet run |
| B08 | Reassignment | Technician 1 → 2; new status Assigned and old/new history saved | Not yet run |
| B09 | Return for correction | Completed → In Progress for same technician | Not yet run |
| B10 | Reassign for correction | Completed → Assigned to a different technician | Not yet run |
| B11 | Closed workflow | Repaired request ends Closed; no further actions allowed | Not yet run |
| B12 | Equipment relocation | Earlier request retains original unit/room/tag | Not yet run |
| B13 | Reporting | Correct counts for status, completed/closed, overdue and group work | Not yet run |
| B14 | Request filtering | Search and separate equipment, status, group, priority, submitted-from/to, and overdue filters work together without exposing out-of-scope requests | Not yet run |
| B15 | Admin users | Create/update/deactivate user and assign profile role in Django Admin | Not yet run |

Use fictional data only and capture screenshots of the test results for the thesis. Note any failure and the corrections applied. Negative tests should show HTTP 403 or a validation error with no unauthorised state change.

## Scope and limitations

- No Vue/DRF implementation or PostgreSQL migration in this Stage 3 ZIP.
- Django Admin provides account/master-data editing but this has not been individually browser-tested in this ZIP.
- Backups, concurrent editing, load testing, secure deployment, and comprehensive UX assessment are unfinished.
- `liat_dev.sqlite3` is deliberately excluded from this ZIP; local request records remain in your existing database if you choose the documented migration-safe upgrade path.
