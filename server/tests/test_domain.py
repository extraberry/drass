import os, tempfile, unittest
from datetime import datetime, timedelta
import numpy as np
from server.app.domain import workflow as wf, rbac, duplicates, file_validation as fv, auth_rules as ar, search_core as sc
from server.app.domain.enums import *
from server.app.domain.errors import *


def make_work(panel=(20, 21)):
    w = wf.Work(1, Status.DRAFT)
    w.assignments = [wf.Assignment(10, Stage.ADVISER)] + [wf.Assignment(p, Stage.PANEL) for p in panel] + \
        [wf.Assignment(30, Stage.DEAN), wf.Assignment(40, Stage.HEAD_LIBRARIAN)]
    return w


class WorkflowTests(unittest.TestCase):
    def test_tc03_full_approval_chain(self):
        w = make_work(); wf.submit(w)
        self.assertEqual(w.status, Status.UNDER_ADVISER_REVIEW)
        wf.review(w, 10, Stage.ADVISER, Decision.APPROVE)
        self.assertEqual(w.status, Status.UNDER_PANEL_REVIEW)
        o = wf.review(w, 20, Stage.PANEL, Decision.APPROVE)
        self.assertFalse(o.stage_complete); self.assertEqual(w.status, Status.UNDER_PANEL_REVIEW)
        wf.review(w, 21, Stage.PANEL, Decision.APPROVE)
        self.assertEqual(w.status, Status.UNDER_DEAN_REVIEW)
        wf.review(w, 30, Stage.DEAN, Decision.APPROVE)
        self.assertEqual(w.status, Status.UNDER_HEAD_LIBRARIAN_REVIEW)
        wf.review(w, 40, Stage.HEAD_LIBRARIAN, Decision.APPROVE)
        self.assertEqual(w.status, Status.ARCHIVED)

    def test_tc04_return_and_resubmit(self):
        w = make_work(); wf.submit(w)
        with self.assertRaises(ValidationFailed):
            wf.review(w, 10, Stage.ADVISER, Decision.RETURN, "  ")
        wf.review(w, 10, Stage.ADVISER, Decision.RETURN, "Fix chapter 3")
        self.assertEqual(w.status, Status.RETURNED_FOR_REVISION)
        wf.resubmit(w)
        self.assertEqual(w.status, Status.UNDER_ADVISER_REVIEW)

    def test_tc05_reject_needs_reason_and_is_terminal(self):
        w = make_work(); wf.submit(w)
        with self.assertRaises(ValidationFailed):
            wf.review(w, 10, Stage.ADVISER, Decision.REJECT, "")
        wf.review(w, 10, Stage.ADVISER, Decision.REJECT, "Out of scope")
        self.assertEqual(w.status, Status.REJECTED)
        with self.assertRaises(InvalidTransition):
            wf.assert_transition(Status.REJECTED, Status.UNDER_ADVISER_REVIEW)

    def test_panel_return_is_immediate(self):
        w = make_work(); wf.submit(w); wf.review(w, 10, Stage.ADVISER, Decision.APPROVE)
        wf.review(w, 20, Stage.PANEL, Decision.RETURN, "Needs work")
        self.assertEqual(w.status, Status.RETURNED_FOR_REVISION)

    def test_guards(self):
        w = make_work(); wf.submit(w)
        with self.assertRaises(Forbidden): wf.review(w, 99, Stage.ADVISER, Decision.APPROVE)
        with self.assertRaises(InvalidTransition): wf.review(w, 20, Stage.PANEL, Decision.APPROVE)
        with self.assertRaises(StaleState): wf.review(w, 10, Stage.ADVISER, Decision.APPROVE, expected_version=-5)
        wf.review(w, 10, Stage.ADVISER, Decision.APPROVE)
        with self.assertRaises(InvalidTransition): wf.assert_transition(Status.ARCHIVED, Status.DRAFT)
        with self.assertRaises(InvalidTransition): wf.resubmit(w)

    def test_duplicate_approval_blocked(self):
        w = make_work(); wf.submit(w); wf.review(w, 10, Stage.ADVISER, Decision.APPROVE)
        wf.review(w, 20, Stage.PANEL, Decision.APPROVE)
        with self.assertRaises(StaleState): wf.review(w, 20, Stage.PANEL, Decision.APPROVE)


class RbacTests(unittest.TestCase):
    def test_external_denied_review(self):
        with self.assertRaises(Forbidden): rbac.require(Role.EXTERNAL_USER, "review.act")
    def test_student_cannot_approve_or_manage(self):
        self.assertFalse(rbac.can(Role.STUDENT, "review.act")); self.assertFalse(rbac.can(Role.STUDENT, "users.manage"))
    def test_visibility(self):
        v = rbac.can_view_work
        self.assertTrue(v(Role.EXTERNAL_USER, 1, Status.ARCHIVED, 5, set()))
        for s in (Status.DRAFT, Status.REJECTED, Status.UNDER_PANEL_REVIEW):
            self.assertFalse(v(Role.EXTERNAL_USER, 1, s, 5, set()))
        self.assertFalse(v(Role.STUDENT, 1, Status.DRAFT, 5, set()))
        self.assertTrue(v(Role.STUDENT, 5, Status.DRAFT, 5, set()))
        self.assertFalse(v(Role.LIBRARY_STAFF, 1, Status.UNDER_DEAN_REVIEW, 5, {1}))


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
    def test_query_normalization(self):
        self.assertEqual(sc.normalize_query("  a \n  b "), "a b")

if __name__ == "__main__":
    unittest.main()
