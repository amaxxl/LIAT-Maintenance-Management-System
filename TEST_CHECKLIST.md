# LIAT Maintenance Management System — final verification checklist

**Existing development setup:** On 23 November 2026, the developer reported
`Ran 33 tests ... OK` with zero Django system-check issues. Those results do
**not** yet verify a completely clean clone or the latest documentation/script.
Record fresh results and browser observations honestly before submission.

## Fresh-install verification

Use a separate fresh clone or extracted source folder, NOT the folder that
contains your existing demo database. Follow `README.txt` and run:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe manage.py runserver
```

Check that `migrate` uses the included migration files without first running
`makemigrations`, and that no new model changes are proposed. Confirm
README.txt instructions, demo user logins, and URL match the actual project.

## Browser demonstration scenarios

| ID | Scenario | Expected result | Current final-verification status |
|---|---|---|---|
| B01 | Student fault reporting | New request Submitted; original unit/room recorded | To verify |
| B02 | Requester privacy | Another requester cannot see/open the request | To verify |
| B03 | Shared intake | Unassigned request initially visible to authorised coordinators | To verify |
| B04 | Qualified assignment | Valid group/technician choice with reason; invalid choice refused | To verify |
| B05 | Coordinator scope | Out-of-group coordinator cannot manage assigned work | To verify |
| B06 | Technician privacy | Only currently assigned technician can work on a request | To verify |
| B07 | Completion guard | Empty resolution note rejected | To verify |
| B08 | Reassignment | Assigned status and assignment history correctly recorded | To verify |
| B09 | Return for correction | Same technician: In Progress; different: Assigned | To verify |
| B10 | Workflow closure | Coordinator closes completed work; closed request cannot be changed | To verify |
| B11 | Equipment move | Request's original unit/room remains unchanged | To verify |
| B12 | Reports | Status, completed, overdue and group workload counts correct | To verify |
| B13 | Dashboard filters | Status/equipment/group/priority/date/overdue can be combined | To verify |
| B14 | Deadline management | Coordinator sets/updates/clears with reason; history saved | To verify |
| B15 | Administrator role | Admin cannot perform coordinator actions; master-data edits work | To verify |
| B16 | Request Django Admin | MaintenanceRequest is view-only, including superusers | To verify |

For negative tests, confirm HTTP 403 or a validation error and verify no
unauthorised database change. Capture screenshots if used in the thesis.

## Final submission checks

- [ ] Fresh-clone installation completed using tracked migrations.
- [ ] `README.txt` instructions and local demo accounts checked.
- [ ] `python manage.py test` completed and results recorded accurately.
- [ ] UI, Django Admin and request history reviewed in browser.
- [ ] Final thesis states only features truly present in this version.
- [ ] Process/state/sequence diagrams are distinct and match the code.
- [ ] No `.venv`, local `.sqlite3`, real credentials or `.env` files in Git.
- [ ] Private GitHub repository is shared with the supervisor if needed.
- [ ] Final commit and ZIP, if sent, contain source, migrations, tests,
      requirements and `README.txt`.

## Known limits

The current prototype is Django templates + SQLite; Vue/DRF and a verified
PostgreSQL installation are not implemented. Production deployment, advanced
backup/restore, penetration testing, performance/concurrency validation and
report export are outside the current tested scope.
