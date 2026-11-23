# LIAT Maintenance Management System — development notes

These notes summarize implemented areas of the Stage 3 local Django prototype.
Actual Git commits provide the authoritative development chronology; no
backdated or artificial history has been created.

## Implementation areas

- Requester accounts (student or employee), technician, Maintenance Coordinator
  and Academy Administrator roles; legacy employee records remain recognized.
- Central unassigned intake followed by group-scoped coordinator actions.
- Group/technician dropdown validation with server-side eligibility checks.
- Audited assignment, reassignment, returns, resolution notes and closure.
- Administrator role separated from the maintenance workflow.
- Coordinator-controlled optional deadlines and a deadline-change history.
- Role-scoped dashboard filters for status, equipment, group, priority,
  submission date and overdue work; scoped reports.
- Restriction of submitted request identity edits and read-only request
  records in Django Admin; equipment master-data editing remains available.
- Included migrations and a growing automated regression test suite.

## Local verification and remaining work

The developer reported 33 passing Django tests and no system-check issues
on Windows on 23 November 2026. Clean-clone installation, current browser
walkthrough, and consistency checks between the final diagrams, thesis text,
and running project still require final verification.

This prototype has not implemented Vue, Django REST Framework or a production
deployment. See README.txt for installation, accounts, functionality and limits.
