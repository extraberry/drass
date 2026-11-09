import os, tempfile, unittest
from datetime import datetime, timedelta
import numpy as np
from server.app.domain import workflow as wf, rbac, duplicates, file_validation as fv, auth_rules as ar, search_core as sc
from server.app.domain.enums import *
from server.app.domain.errors import *


ALL_TICKED = dict(adviser_signed=True, panelists_signed=True, dean_signed=True, researchers_signed=True, sheet_complete=True)


def pending_work():
    return wf.Work(1, Status.PENDING_VERIFICATION)


class WorkflowTests(unittest.TestCase):
    """Manuscript FR4-FR8: submit one final PDF -> Head Librarian verifies signatories -> return with remarks or archive."""

    def test_submit_goes_to_pending_verification(self):
        w = wf.Work(1, Status.DRAFT)
        self.assertEqual(wf.submit(w), Status.PENDING_VERIFICATION)
        self.assertEqual(w.version, 1)

    def test_cannot_submit_twice_or_archive_a_draft(self):
        w = pending_work()
        with self.assertRaises(InvalidTransition): wf.submit(w)
        with self.assertRaises(InvalidTransition): wf.verify(wf.Work(1, Status.DRAFT), Decision.APPROVE, ALL_TICKED)

    def test_tc_final_approval_archives_with_publication_status(self):
        w = pending_work()
        out = wf.verify(w, Decision.APPROVE, ALL_TICKED, "", "RESTRICTED")
        self.assertEqual(w.status, Status.ARCHIVED)
        self.assertEqual(out.new_status, Status.ARCHIVED)
        self.assertEqual(out.publication_status, PublicationStatus.RESTRICTED)

    def test_publication_status_defaults_to_public_and_must_be_valid(self):
        w = pending_work()
        self.assertEqual(wf.verify(w, Decision.APPROVE, ALL_TICKED).publication_status, PublicationStatus.PUBLIC)
        w2 = pending_work()
        with self.assertRaises(ValidationFailed): wf.verify(w2, Decision.APPROVE, ALL_TICKED, "", "SECRET")
        self.assertEqual(w2.status, Status.PENDING_VERIFICATION)

    def test_approval_needs_every_checklist_item(self):
        for key in wf.CHECKLIST_ITEMS:
            w = pending_work()
            ticks = {**ALL_TICKED, key: False}
            with self.assertRaises(ValidationFailed) as cm: wf.verify(w, Decision.APPROVE, ticks)
            self.assertIn(wf.CHECKLIST_ITEMS[key], cm.exception.message)
            self.assertEqual(w.status, Status.PENDING_VERIFICATION)           # nothing changed
        with self.assertRaises(ValidationFailed): wf.verify(pending_work(), Decision.APPROVE, {})

    def test_return_needs_remarks_and_then_resubmit(self):
        w = pending_work()
        with self.assertRaises(ValidationFailed): wf.verify(w, Decision.RETURN, {}, "  ")
        out = wf.verify(w, Decision.RETURN, {"adviser_signed": True}, "Dean signature is missing")
        self.assertEqual((w.status, out.reason), (Status.RETURNED, "Dean signature is missing"))
        self.assertEqual(wf.resubmit(w), Status.PENDING_VERIFICATION)

    def test_only_returned_work_can_be_resubmitted(self):
        for st in (Status.DRAFT, Status.PENDING_VERIFICATION, Status.ARCHIVED):
            with self.assertRaises(InvalidTransition): wf.resubmit(wf.Work(1, st))

    def test_archived_is_final(self):
        w = wf.Work(1, Status.ARCHIVED)
        with self.assertRaises(InvalidTransition): wf.verify(w, Decision.RETURN, {}, "x")
        self.assertEqual(wf.TRANSITIONS[Status.ARCHIVED], set())

    def test_stale_version_is_refused(self):
        w = pending_work(); w.version = 3
        with self.assertRaises(StaleState): wf.verify(w, Decision.APPROVE, ALL_TICKED, expected_version=2)
        self.assertEqual(wf.verify(w, Decision.APPROVE, ALL_TICKED, expected_version=3).new_status, Status.ARCHIVED)

    def test_only_the_manuscript_statuses_exist(self):
        self.assertEqual({s.value for s in Status}, {"DRAFT", "PENDING_VERIFICATION", "RETURNED", "ARCHIVED"})
        self.assertEqual({d.value for d in Decision}, {"APPROVE", "RETURN"})
        self.assertEqual(wf.EDITABLE, {Status.DRAFT, Status.RETURNED})


class RolesTests(unittest.TestCase):
    def test_five_manuscript_roles(self):
        self.assertEqual({r.value for r in Role}, {"STUDENT", "FACULTY", "LIBRARY_STAFF", "ADMIN", "EXTERNAL_USER"})


class RbacTests(unittest.TestCase):
    def test_library_staff_manage_records_but_not_accounts(self):
        for p in ("verification.view", "verification.act", "metadata.maintain", "publication.manage", "repository.browse", "reader.read"):
            rbac.require(Role.LIBRARY_STAFF, p)
        for p in ("users.manage", "backup.manage", "reports.any", "submission.create"):
            with self.assertRaises(Forbidden): rbac.require(Role.LIBRARY_STAFF, p)

    def test_administrator_manages_system_but_does_not_read_research(self):
        for p in ("users.manage", "settings.manage", "backup.manage", "audit.read", "activity.read", "reports.any", "indexing.manage"):
            rbac.require(Role.ADMIN, p)
        for p in ("search.semantic", "reader.read", "repository.browse", "metadata.maintain", "verification.act", "submission.create"):
            self.assertFalse(rbac.can(Role.ADMIN, p), p)

    def test_students_and_faculty(self):
        self.assertTrue(rbac.can(Role.STUDENT, "submission.create"))
        self.assertFalse(rbac.can(Role.FACULTY, "submission.create"))
        for r in (Role.STUDENT, Role.FACULTY):
            for p in ("search.semantic", "reader.read", "repository.browse"): self.assertTrue(rbac.can(r, p))
            for p in ("verification.act", "metadata.maintain", "users.manage", "reports.any"): self.assertFalse(rbac.can(r, p))

    def test_external_user_reads_only(self):
        for p in ("search.semantic", "reader.read", "repository.browse"): self.assertTrue(rbac.can(Role.EXTERNAL_USER, p))
        for p in ("verification.view", "submission.create", "metadata.maintain", "companions.access"): self.assertFalse(rbac.can(Role.EXTERNAL_USER, p))

    def test_publication_status_visibility(self):
        v, A = rbac.can_view_work, Status.ARCHIVED
        # PUBLIC: everybody who may read research
        for r in (Role.STUDENT, Role.FACULTY, Role.LIBRARY_STAFF, Role.EXTERNAL_USER): self.assertTrue(v(r, 1, A, 5, "PUBLIC"), r)
        # RESTRICTED: signed-in internal roles only
        for r in (Role.STUDENT, Role.FACULTY, Role.LIBRARY_STAFF): self.assertTrue(v(r, 1, A, 5, "RESTRICTED"), r)
        self.assertFalse(v(Role.EXTERNAL_USER, 1, A, 5, "RESTRICTED"))
        self.assertFalse(v(Role.EXTERNAL_USER, None, A, 5, "RESTRICTED"))        # guest
        # UNPUBLISHED: Library Staff, and the student who submitted it
        self.assertTrue(v(Role.LIBRARY_STAFF, 1, A, 5, "UNPUBLISHED"))
        self.assertTrue(v(Role.STUDENT, 5, A, 5, "UNPUBLISHED"))
        for r, uid in ((Role.STUDENT, 1), (Role.FACULTY, 1), (Role.EXTERNAL_USER, 1)): self.assertFalse(v(r, uid, A, 5, "UNPUBLISHED"), r)
        # the administrator reads nothing; an archived record without a status is hidden
        for ps in ("PUBLIC", "RESTRICTED", "UNPUBLISHED"): self.assertFalse(v(Role.ADMIN, 1, A, 5, ps))
        self.assertFalse(v(Role.STUDENT, 5, A, 5, None))

    def test_unarchived_visibility(self):
        v = rbac.can_view_work
        for s in (Status.DRAFT, Status.PENDING_VERIFICATION, Status.RETURNED):
            self.assertFalse(v(Role.EXTERNAL_USER, 1, s, 5))
            self.assertFalse(v(Role.FACULTY, 1, s, 5))
            self.assertFalse(v(Role.ADMIN, 1, s, 5))
            self.assertFalse(v(Role.STUDENT, 1, s, 5))
            self.assertTrue(v(Role.STUDENT, 5, s, 5))                            # the owner
        self.assertFalse(v(Role.LIBRARY_STAFF, 1, Status.DRAFT, 5))
        self.assertTrue(v(Role.LIBRARY_STAFF, 1, Status.PENDING_VERIFICATION, 5))   # opens the PDF to verify it
        self.assertTrue(v(Role.LIBRARY_STAFF, 1, Status.RETURNED, 5))

    def test_companion_file_access_is_role_controlled(self):
        a = rbac.can_access_companions
        self.assertTrue(a(Role.LIBRARY_STAFF, 1, 5)); self.assertTrue(a(Role.STUDENT, 5, 5))
        for r, uid in ((Role.STUDENT, 1), (Role.FACULTY, 1), (Role.EXTERNAL_USER, 1), (Role.ADMIN, 1), (Role.EXTERNAL_USER, None)):
            self.assertFalse(a(r, uid, 5), r)


class DuplicateTests(unittest.TestCase):
    def test_tc02(self):
        a = duplicates.duplicate_key("Mobile  Quiz App!", ["Ana Cruz", "Ben Lee"], 2025)
        b = duplicates.duplicate_key("mobile quiz app", ["ben lee", "ANA CRUZ"], 2025)
        self.assertTrue(duplicates.is_strong_duplicate(a, b))
        self.assertFalse(duplicates.is_strong_duplicate(a, duplicates.duplicate_key("mobile quiz app", ["Ana Cruz", "Ben Lee"], 2024)))


class FileTests(unittest.TestCase):
    def test_validation(self):
        pdf = b"%PDF-1.7\n..."
        self.assertEqual(fv.validate_upload(FileType.MANUSCRIPT, "t.PDF", pdf, 1000), ".pdf")
        with self.assertRaises(ValidationFailed): fv.validate_upload(FileType.MANUSCRIPT, "t.pdf", b"MZ\x90", 1000)
        with self.assertRaises(ValidationFailed): fv.validate_upload(FileType.MANUSCRIPT, "t.exe", pdf, 1000)
        with self.assertRaises(ValidationFailed): fv.validate_upload(FileType.MANUSCRIPT, "t.pdf", pdf, 101 * fv.MB)
        with self.assertRaises(ValidationFailed): fv.validate_upload(FileType.MANUSCRIPT, "t.pdf", pdf, 0)
        self.assertEqual(fv.validate_upload(FileType.SOURCE_CODE, "a.zip", b"PK\x03\x04x", 10), ".zip")
    def test_limits_configurable(self):
        with self.assertRaises(ValidationFailed):
            fv.validate_upload(FileType.MANUSCRIPT, "t.pdf", b"%PDF-1", 3 * fv.MB, {FileType.MANUSCRIPT: 2})
    def test_sanitize_and_traversal(self):
        self.assertEqual(fv.sanitize_filename("../../etc/passwd"), "passwd")
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValidationFailed): fv.safe_join(d, "../x.pdf")
            with self.assertRaises(ValidationFailed): fv.safe_join(d, "/etc/passwd")
            self.assertTrue(fv.safe_join(d, "ok.pdf").startswith(os.path.realpath(d)))
    def test_checksum(self):
        with tempfile.NamedTemporaryFile(delete=False) as f: f.write(b"abc")
        try: self.assertEqual(fv.sha256_file(f.name), fv.sha256_bytes(b"abc"))
        finally: os.unlink(f.name)


class AuthRuleTests(unittest.TestCase):
    def test_lockout_and_session(self):
        p = ar.AuthPolicy(); now = datetime(2026, 1, 1, 8); c = 0
        for _ in range(4):
            c, lock = ar.register_failure(c, now, p); self.assertIsNone(lock)
        c, lock = ar.register_failure(c, now, p)
        self.assertEqual(lock, now + timedelta(minutes=15)); self.assertTrue(ar.is_locked(lock, now))
        self.assertFalse(ar.is_locked(lock, now + timedelta(minutes=16)))
        self.assertTrue(ar.session_valid(now, None, now + timedelta(minutes=19), p))
        self.assertFalse(ar.session_valid(now, None, now + timedelta(minutes=21), p))
        self.assertFalse(ar.session_valid(now, now, now, p))
    def test_password_policy(self):
        self.assertTrue(ar.password_problems("short", ar.AuthPolicy()))
        self.assertFalse(ar.password_problems("longenough", ar.AuthPolicy()))


class SearchCoreTests(unittest.TestCase):
    def cand(self, i, v, **kw): return sc.Candidate(i, np.array(v, dtype=np.float32), **kw)
    def test_text_and_blob(self):
        t = sc.build_index_text(" T ", " A ", ["x", "y"])
        self.assertEqual(t, "Title: T\n\nAbstract: A\n\nKeywords: x, y")
        v = np.random.rand(384).astype(np.float32)
        self.assertTrue(np.array_equal(sc.from_blob(sc.to_blob(v)), v))
    def test_rank_threshold_order(self):
        cs = [self.cand(1, [1, 0]), self.cand(2, [0.9, 0.436]), self.cand(3, [0, 1])]
        r = sc.rank([1, 0], cs, 0.35)
        self.assertEqual([w for w, _ in r], [1, 2])         # tc07: unrelated excluded
        self.assertEqual(sc.rank([0.0, 1.0], [self.cand(1, [1, 0])], 0.35), [])
    def test_recommend_excludes_self_and_weak(self):
        t = self.cand(1, [1, 0], year=2025)
        cs = [t, self.cand(2, [0.95, 0.3], year=2025), self.cand(3, [0, 1])]
        self.assertEqual([w for w, _ in sc.recommend(t, cs)], [2])
    def test_recommend_limit(self):
        t = self.cand(0, [1, 0]); cs = [self.cand(i, [1, 0.01 * i]) for i in range(1, 12)]
        self.assertEqual(len(sc.recommend(t, cs, count=5)), 5)
    def test_multi_vector_candidate_uses_best_piece(self):
        c = self.cand(1, [[0, 1], [1, 0]])                  # two embedded pieces; the 2nd matches the query
        r = sc.rank([1, 0], [c], 0.35)
        self.assertEqual([w for w, _ in r], [1]); self.assertAlmostEqual(r[0][1], 1.0, places=5)

    def test_blob_roundtrip_many_vectors_and_old_single_vector(self):
        m = np.random.rand(3, 8).astype(np.float32)
        self.assertTrue(np.array_equal(sc.matrix_from_blob(sc.to_blob(m), 8), m))
        v = np.random.rand(8).astype(np.float32)
        self.assertEqual(sc.matrix_from_blob(sc.to_blob(v), 8).shape, (1, 8))      # vectors saved before this change still load

    def test_index_pieces_cover_title_keywords_and_abstract_windows(self):
        ab = "First sentence here. Second one follows. Third is last."
        p = sc.build_index_pieces("My Title", ab, ["alpha", "beta"])
        self.assertEqual(p[0], sc.build_index_text("My Title", ab, ["alpha", "beta"]))
        self.assertEqual(p[1], "My Title. alpha, beta")
        self.assertIn("First sentence here. Second one follows.", p)
        self.assertLessEqual(len(p), sc.MAX_PIECES)
        self.assertEqual(sc.build_index_pieces("T", "", []), ["Title: T\n\nAbstract: \n\nKeywords: ", "T"])

    def test_query_normalization(self):
        self.assertEqual(sc.normalize_query("  a \n  b "), "a b")

class UploadLimitTextTests(unittest.TestCase):
    def test_describe_limits_lists_every_kind_with_size_and_formats(self):
        rows = {r["file_type"]: r for r in fv.describe_limits()}
        self.assertEqual(set(rows), {"MANUSCRIPT", "SOURCE_CODE", "VIDEO", "OTHER_COMPANION"})
        self.assertEqual(rows["MANUSCRIPT"]["max_mb"], 100)
        self.assertEqual(rows["VIDEO"]["extensions"], [".mov", ".mp4", ".webm"])
        self.assertIn(".zip", rows["SOURCE_CODE"]["extensions"])

    def test_configured_limits_are_reflected(self):
        rows = {r["file_type"]: r for r in fv.describe_limits({FileType.VIDEO: 250})}
        self.assertEqual(rows["VIDEO"]["max_mb"], 250)

    def test_too_big_message_names_the_limit(self):
        with self.assertRaises(ValidationFailed) as cm:
            fv.validate_upload(FileType.VIDEO, "demo.mp4", b"\x00\x00\x00\x18ftypmp42", 600 * fv.MB)
        self.assertIn("500 MB", cm.exception.message)


class LexicalSearchTests(unittest.TestCase):
    T = "Gamified Learning Management System to Increase Student Motivation in Online Classes"
    A = "The researchers designed a learning management system with badges, points and progress tracking to motivate students in online classes."
    K = ["gamification", "learning management system", "motivation", "online learning"]

    def lex(self, q): return sc.lexical_score(q, self.T, self.A, self.K)

    def test_exact_word_and_plural_forms(self):
        self.assertGreaterEqual(self.lex("gamification"), 0.99)
        self.assertGreaterEqual(self.lex("students"), 0.99)          # plural of a title word
        self.assertGreaterEqual(self.lex("badge"), 0.6)              # only in the abstract

    def test_acronym_matches_title_or_keyword_phrase(self):
        self.assertGreaterEqual(self.lex("LMS"), 0.9)

    def test_small_typo_still_matches(self):
        self.assertGreater(self.lex("gamifcation"), 0.5)
        self.assertGreater(self.lex("motivaton"), 0.5)

    def test_unrelated_words_score_zero(self):
        self.assertEqual(self.lex("hospital queue"), 0.0)
        self.assertEqual(sc.lexical_score("", self.T, self.A, self.K), 0.0)

    def test_short_query_is_not_dropped(self):
        self.assertGreater(sc.lexical_score("AI", "An AI Tutoring Chatbot", "x", []), 0.9)

    def test_rank_keeps_word_match_even_when_meaning_score_is_low(self):
        weak = sc.Candidate(1, np.array([0.0, 1.0], dtype=np.float32), title=self.T, abstract=self.A, keywords=frozenset(self.K))
        other = sc.Candidate(2, np.array([0.0, 1.0], dtype=np.float32), title="Dengue mapping", abstract="x")
        self.assertEqual(sc.rank([1, 0], [weak, other], 0.25), [])                              # meaning alone finds nothing
        r = sc.rank([1, 0], [weak, other], 0.25, query_text="gamification")
        self.assertEqual([w for w, _ in r], [1])

    def test_rank_combines_both_scores(self):
        a = sc.Candidate(1, np.array([0.6, 0.8], dtype=np.float32), title="Dengue map", abstract="")
        b = sc.Candidate(2, np.array([0.6, 0.8], dtype=np.float32), title="Other", abstract="")
        r = sc.rank([1, 0], [b, a], 0.25, query_text="dengue")
        self.assertEqual([w for w, _ in r], [1, 2])                                             # word match ranks first


if __name__ == "__main__":
    unittest.main()
