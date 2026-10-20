# Demo accounts
**Demonstration only — change or delete these before real deployment.** Password for every account: `Drass2026`

| Username | Role | Notes |
|---|---|---|
| admin | ADMIN | |
| headlibrarian | HEAD_LIBRARIAN | final archive approval |
| librarian | LIBRARY_STAFF | |
| dean | DEAN | College of Information Technology |
| adviser1 | ADVISER | |
| panelist1, panelist2 | PANELIST | both must approve (ALL_ASSIGNED) |
| student1 | STUDENT | clean — use for the demo scenario |
| student2 | STUDENT | owns the 12 seeded demo records |
| external1 | EXTERNAL_USER | read-only |

## Demo scenario
1. student1: *My Submissions → New Submission*; pick program/category/adviser (Prof. Adrian Cruz), authors, keywords, abstract; upload a PDF (any PDF) and optionally a .zip; **Submit for Review**.
2. adviser1: *Review Queue → Open* → comments → **Return for Revision**.
3. student1: open the submission (comments are shown), edit, add change notes, **Resubmit**.
4. adviser1 approves → (optional *Assign Panel…*, otherwise both panelists auto-assigned) → panelist1 and panelist2 approve → dean approves → headlibrarian approves → **Archived**; embedding is generated.
5. student2 / external1: *Search* → “research projects that use technology to improve student learning”; open a result; **Read Research**; see *Related Research*.
6. admin: *Audit Logs*, *Reports*, *Indexing Monitor*.

## Guest access and student sign-up (demo)
- Launch the client: it opens as **Guest** (Repository + Search only). Use **Sign in** for an account; guests cannot read manuscripts.
- **Create student account** works for roster IDs not yet registered: `2023-0101` Reyes, `2023-0102` Tan, `2023-0103` Lim, `2023-0104` Santos. `2022-0001` (Ramos) and `2022-0002` (Garcia) are already taken by student1/student2.
