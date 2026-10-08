# Traceability
| Capstone objective | PRD area | Feature / service | API | DB | UI | Test |
|---|---|---|---|---|---|---|
| Digital submission | Submission | submission_service | /submissions | research_works, revisions, files | SubmissionForm | TC-01, TC-02 |
| Review & approval chain | Workflow | domain/workflow, review_service | /reviews/* | review_assignments, reviews, status_history | ReviewDialog | TC-03, TC-04, TC-05 |
| Archiving | Archive | review_service + files_service | approve (HEAD_LIBRARIAN) | research_works.archived_at | Archive Approval Queue | e2e chain, archive-blocked test |
| Semantic search | Search | search_service, index_service, embedder | /search/semantic | embeddings | SearchPage | TC-06, TC-07, test_real_model |
| Recommendations | Recommendations | search_service.recommendations | /recommendations/{id} | embeddings | ResearchDetailDialog | recommendations test |
| Secure PDF reading | Reader | reader_service | /reader/* | files | ReaderDialog | TC-08 |
| Role/access management | RBAC | domain/rbac, deps | all | roles, users | role-based navigation | TC-09, TC-10 |
| Audit trails & reports | Logging/Reports | common.audit, reports_service | /audit-logs, /reports/* | audit_logs, activity_logs | LogsPage, ReportsPage | TC-11 |
| Embedding failure handling | Indexing | index_service | /admin/indexing | embeddings.status | IndexingPage | TC-12 |
