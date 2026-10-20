# Workflows
**Submission**: DRAFT → (validate fields + manuscript + duplicate check) → revision 1 → SUBMITTED → UNDER_ADVISER_REVIEW.
**Approval**: Adviser → Panel (ALL_ASSIGNED) → Dean → Head Librarian → ARCHIVED. Approve advances; Return (comments required) → RETURNED_FOR_REVISION; Reject (reason required) → REJECTED (terminal). Each decision creates a `reviews` row, status_history row, notifications and audit entry in one transaction; the work row is locked (`SELECT … FOR UPDATE`) and version-checked.
**Revision**: student edits metadata/files, enters change notes → new `revisions` row (previous preserved) → back to UNDER_ADVISER_REVIEW with fresh assignments; old reviews stay in history.
**Archive**: before final approval the manuscript's existence and SHA-256 are verified; then commit; then indexing runs (failure never undoes the archive).
**Search**: query → normalize → local model embedding → candidates = ARCHIVED + filters + COMPLETE embeddings → NumPy cosine → threshold → sorted. **Recommendations**: cosine vs other archived works, threshold, small metadata boost, top N, never itself.
**Reader**: client requests page N → session + record access check → PyMuPDF renders PNG → returned with no-store headers; each view logged as PDF_PAGE_VIEWED.

**Panel approved offline (shortcut)**: Adviser approves with *panel already approved* + reference → UNDER_HEAD_LIBRARIAN_REVIEW (or UNDER_DEAN_REVIEW if `offline_panel_skips_dean=false`). Panel stage is skipped and never created.
**Administrator override**: ADMIN, any UNDER_* status → next stage or ARCHIVED, reason required; see DECISIONS.md.
