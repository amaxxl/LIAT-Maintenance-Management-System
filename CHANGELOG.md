# Changes from uploaded Stage 2 project

- Added `requester` role and `Profile.account_type` (`student` or `employee`), while interpreting legacy `employee` roles as requesters.
- Expanded demo accounts; old accounts remain, and existing passwords are never reset.
- Shared central intake queue until the maintenance group is chosen, then group-scoped coordinator ownership.
- Validated group/technician dropdowns with matching group membership, equipment category and problem type.
- Explicit, audited reassignment from Assigned/In Progress/Completed to Assigned; approved closure and return to In Progress for the same technician.
- Search/status/priority/group/overdue request filters and scoped reporting by status, completion, overdue and group workload.
- Expanded test suite from 5 to 19 cases with direct-URL privacy, authorisation, eligibility, invalid completion, reassignment, return, snapshots and reports.
- Professionalised the Django interface and added user profile editing support in Django Admin.
- Read-only status, assignment and repair-audit rows in Django Admin.

## Verification status

Python files passed `compileall` in the packaging environment. Django was not installed there and could not be downloaded, so Django migrations, `manage.py check`, automated tests and browser integration tests **have not been run on the new ZIP**. Run the included Windows commands before declaring those results in the thesis.
