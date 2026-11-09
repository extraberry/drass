# Demo accounts
**Demonstration only - change or delete these before real deployment.** Password for every account: `Drass2026`

| Username | Role | Notes |
|---|---|---|
| admin | ADMIN | users, roles, settings, reports, logs, indexing, backup and restore. Cannot search or read research |
| headlibrarian | LIBRARY_STAFF (Head Librarian) | verifies signatories and gives the final archival approval; also metadata and publication status |
| libstaff1 | LIBRARY_STAFF | metadata, publication status, companion files, sees the verification queue (cannot verify) |
| faculty1 | FACULTY | Prof. Adrian Cruz - choose as the adviser; searches and reads |
| dean1 | FACULTY | Dr. Elena Navarro - choose as the dean; searches and reads |
| student1 | STUDENT | clean - use for the demo scenario |
| student2 | STUDENT | |
| external1 | EXTERNAL_USER | searches and reads Public research only |

## Demo scenario
1. student1: *My Submissions -> New Submission*; pick course, adviser (Prof. Adrian Cruz) and dean (Dr. Elena Navarro), authors, keywords, abstract; upload a PDF (any PDF, standing in for manuscript + signed approval sheet); **Submit for Verification** -> *Pending Verification*.
2. headlibrarian: *Verification Queue -> Verify Selected* -> leave one item unticked, write remarks -> **Return to student**.
3. student1: open the submission (the remarks are shown), fix, add change notes, **Resubmit**.
4. headlibrarian: tick all five checklist items, choose a publication status -> **Approve and archive** -> *Archived*; the embedding is generated.
5. libstaff1: *Repository -> Open -> Publication Status...* change it to Restricted, then check that external1 can no longer find it.
6. student2 / faculty1 / external1 / a guest: *Search* -> "research projects that use technology to improve student learning"; open a result; **Read Research**; see *Related Research*.
7. admin: *Reports*, *Audit Logs*, *Indexing Monitor*, *Backup & Recovery -> Back up now*.

## Guest access and student sign-up (demo)
- The client opens as **Guest**: Repository + Search + reading Public research. Use **Sign in** for an account.
- **Create student account** works for roster IDs not yet registered: `2023-0101` Reyes, `2023-0102` Tan, `2023-0103` Lim, `2023-0104` Santos. `2022-0001` (Ramos) and `2022-0002` (Garcia) belong to student1/student2.
