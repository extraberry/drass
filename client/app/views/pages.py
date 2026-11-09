from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QComboBox, QDateEdit, QFileDialog, QFormLayout, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QPlainTextEdit, QRadioButton, QVBoxLayout, QWidget)
from ..style import card_shadow_rgba
from PySide6.QtCore import QDate, Qt
from ..dialogs.research_detail import ResearchDetailDialog
from ..dialogs.verification_dialog import VerificationDialog
from ..dialogs.submission_form import SubmissionForm
from ..dialogs.user_dialog import UserDialog
from ..widgets import (PUBLICATION_LABELS, StatCard, DataTable, Page, button, card, confirm, h1, h2, hbox, info, muted, show_error, status_text)
from ..worker import run_async
from .common import FilterBar


def _stat(title, value):
    c = card(); l = QVBoxLayout(c); v = QLabel(str(value)); v.setObjectName("h1"); l.addWidget(v); l.addWidget(muted(title)); return c


class DashboardPage(Page):
    title = "Dashboard"

    def refresh(self):
        run_async(lambda: self.api.get("/dashboard"), self._render, lambda e: show_error(self, e))

    def _render(self, d):
        while self.root.count():
            it = self.root.takeAt(0)
            if it.widget(): it.widget().deleteLater()
            elif it.layout():
                while it.layout().count():
                    x = it.layout().takeAt(0)
                    if x.widget(): x.widget().deleteLater()
        u = self.api.user
        self.root.addWidget(h1(f"Welcome, {u['full_name']}"))
        self.root.addWidget(muted("Digital Research Archiving System with Semantic Search — Mary the Queen College of Quezon City, Inc."))
        labels = {"pending_verification": "Pending verification", "verified_total": "Verifications completed", "returned": "Returned to students",
                  "archived": "Archived research", "total_works": "Total research works",
                  "indexing_failures": "Indexing failures", "unread_notifications": "Unread notifications",
                  "active_users": "Active users", "inactive_users": "Deactivated users", "failed_logins": "Failed login events"}
        def target(key):
            if key == "archived" and self.api.role != "ADMIN": return (["Repository"], {})
            if key == "active_users": return (["Users"], {"status": "ACTIVE"})
            if key == "inactive_users": return (["Users"], {"status": "INACTIVE"})
            if key == "failed_logins": return (["Audit Logs"], {"action": "LOGIN_FAILED"})
            if key == "indexing_failures": return (["Indexing Monitor"], {})
            if key == "unread_notifications": return (["Notifications"], {})
            if key == "pending_verification" and self.api.role == "LIBRARY_STAFF": return (["Verification Queue"], {})
            if key == "verified_total": return (["Verification History"], {})
            return None
        admin = self.api.role == "ADMIN"
        g = QGridLayout(); g.setHorizontalSpacing(20); g.setVerticalSpacing(20); g.setContentsMargins(40, 14, 40, 26); g.setAlignment(Qt.AlignTop)
        i = 0
        for k, lbl in labels.items():
            if k not in d: continue
            tg = target(k)
            sc = StatCard(lbl, d[k], clickable=tg is not None)   # (not named `card`: that would shadow the card() helper below)
            if tg and self.main:
                sc.clicked.connect(lambda labels_=tg[0], preset=tg[1]: self.main.navigate_first(labels_, preset))
            g.addWidget(sc, i // 4, i % 4); i += 1
        for c in range(4): g.setColumnStretch(c, 1)
        w = QWidget(); w.setLayout(g); self.root.addWidget(w)
        if admin:
            # Panel below the grid (matches the UI design): same colour as the cards in light and dark, 190px tall,
            # at most 980px wide, sitting 26px under the grid so the card shadows stay visible.
            panel = card(); panel.setFixedHeight(190); panel.setMaximumWidth(980)
            sh = QGraphicsDropShadowEffect(panel); sh.setBlurRadius(14); sh.setOffset(0, 3); sh.setColor(QColor(*card_shadow_rgba()))
            panel.setGraphicsEffect(sh)
            row = QHBoxLayout(); row.setContentsMargins(40, 0, 40, 14); row.addWidget(panel); row.addStretch(1)
            self.root.addLayout(row)
        if "submissions" in d:
            self.root.addWidget(h2("My submissions"))
            t = DataTable(); t.set_data(["Title", "Status"], [[s["title"], status_text(s["status"])] for s in d["submissions"]])
            if not d["submissions"]: self.root.addWidget(muted("You have not started a submission yet. Open “My Submissions” to create one."))
            else: self.root.addWidget(t)
        self.root.addStretch(1)


class SubmissionsPage(Page):
    title = "My Submissions"

    def __init__(self, api, main=None):
        super().__init__(api, main)
        self.root.addWidget(h1("My Submissions"))
        self.root.addLayout(hbox(button("New Submission", "primary", self.new), button("Open / Edit / Revise", slot=self.open), button("Refresh", slot=self.refresh)))
        self.table = DataTable(); self.table.doubleClicked.connect(lambda *_: self.open()); self.root.addWidget(self.table)
        self.detail = QPlainTextEdit(); self.detail.setReadOnly(True); self.detail.setMaximumHeight(210); self.root.addWidget(self.detail)
        self.table.itemSelectionChanged.connect(self.show_detail)

    def refresh(self):
        run_async(lambda: self.api.get("/submissions")["items"], self._fill, lambda e: show_error(self, e))

    def _fill(self, items):
        self.table.set_data(["Reference", "Title", "Year", "Status", "Submitted"],
                            [[i["reference_no"], i["title"] or "(untitled)", i["year"], status_text(i["status"]), (i["submitted_at"] or "")[:10]] for i in items],
                            [i["work_id"] for i in items])

    def new(self):
        SubmissionForm(self.api, None, self).exec(); self.refresh()

    def open(self):
        wid = self.table.selected_id()
        if wid is None: return info(self, "Select a submission first.")
        SubmissionForm(self.api, wid, self).exec(); self.refresh()

    def show_detail(self):
        wid = self.table.selected_id()
        if wid is None: return
        def render(w):
            lines = [f"{w['title']}  [{w['status_label']}]", ""]
            for h in w.get("verification_history", []):
                lines.append(f"• Verification (rev {h['revision_number']}) — {h['verified_by']}: {'Approved' if h['result'] == 'APPROVE' else 'Returned'} — {h['remarks']}")
            for r in w.get("revisions", []):
                lines.append(f"Revision {r['revision_number']}: {r['change_notes']}")
            self.detail.setPlainText("\n".join(lines))
        run_async(lambda: self.api.get(f"/submissions/{wid}"), render, None)


class VerificationQueuePage(Page):
    """Submissions waiting for signatory verification. The Head Librarian verifies; other Library Staff can open and read them."""
    title = "Verification Queue"

    def __init__(self, api, main=None):
        super().__init__(api, main)
        self.can_verify = bool(api.user.get("is_head_librarian"))
        self.root.addWidget(h1("Verification Queue"))
        if not self.can_verify:
            self.root.addWidget(muted("Only the Head Librarian can verify the signatories and approve a submission. You can open the records to read them."))
        self.root.addLayout(hbox(button("Open" if not self.can_verify else "Verify Selected", "primary", self.open), button("Refresh", slot=self.refresh)))
        self.table = DataTable(); self.table.doubleClicked.connect(lambda *_: self.open()); self.root.addWidget(self.table)
        self.empty = muted(""); self.root.addWidget(self.empty)

    def refresh(self):
        def load():
            r = self.api.get("/verifications/queue")
            return r["items"], r.get("can_verify", False)
        run_async(load, self._fill, lambda e: show_error(self, e))

    def _fill(self, res):
        items, self.can_verify = res
        self.table.set_data(["Reference", "Title", "Course", "Adviser", "Dean", "Submitted"],
                            [[i["reference_no"], i["title"], i["program"], i["adviser"], i["dean"], (i["submitted_at"] or "")[:16]] for i in items],
                            [i["work_id"] for i in items])
        self.empty.setText("" if items else "No submissions are waiting for verification.")

    def open(self):
        wid = self.table.selected_id()
        if wid is None: return info(self, "Select a submission first.")
        VerificationDialog(self.api, wid, self.can_verify, self).exec(); self.refresh()


class VerificationHistoryPage(Page):
    title = "Verification History"

    def __init__(self, api, main=None):
        super().__init__(api, main)
        self.root.addWidget(h1("Verification History")); self.table = DataTable(); self.root.addWidget(self.table)

    def refresh(self):
        run_async(lambda: self.api.get("/verifications/history")["items"],
                  lambda items: self.table.set_data(["Title", "My decision", "Remarks", "Current status", "When"],
                                                    [[i["title"], "Approved" if i["result"] == "APPROVE" else "Returned", i["remarks"], status_text(i["status"]), i["verified_at"][:16]] for i in items]),
                  lambda e: show_error(self, e))


class RepositoryPage(Page):
    def __init__(self, api, main=None, title="Repository"):
        super().__init__(api, main)
        self.title, self.page_no, self.page_size = title, 1, 20
        self.root.addWidget(h1(title))
        self.filters = FilterBar(api); self.root.addWidget(self.filters)
        self.sort = QComboBox(); [self.sort.addItem(l, v) for l, v in (("Newest archived", "archived_at"), ("Title", "title"), ("Year", "year"))]
        self.order = QComboBox(); self.order.addItem("Descending", "desc"); self.order.addItem("Ascending", "asc")
        self.pub = QComboBox(); self.pub.addItem("Any publication status", None)
        for k, v in PUBLICATION_LABELS.items(): self.pub.addItem(v, k)
        row = [muted("Sort:"), self.sort, self.order]
        if api.role == "LIBRARY_STAFF": row.append(self.pub)           # only Library Staff filter by publication status
        self.root.addLayout(hbox(*row, button("Apply filters", "primary", self.apply), button("Clear", slot=self.clear), button("Open", slot=self.open)))
        self.table = DataTable(); self.table.doubleClicked.connect(lambda *_: self.open()); self.root.addWidget(self.table)
        self.info = muted(""); self.prev, self.next = button("< Previous", slot=lambda: self.goto(self.page_no - 1)), button("Next >", slot=lambda: self.goto(self.page_no + 1))
        self.root.addLayout(hbox(self.prev, self.next, self.info))

    def apply(self): self.goto(1)
    def clear(self): self.filters.clear(); self.pub.setCurrentIndex(0); self.goto(1)
    def refresh(self): self.goto(self.page_no)

    def goto(self, n):
        if n < 1: return
        self.page_no = n
        params = {**self.filters.values(), "publication_status": self.pub.currentData() if self.api.role == "LIBRARY_STAFF" else None, "sort": self.sort.currentData(), "order": self.order.currentData(), "page": n, "page_size": self.page_size}
        run_async(lambda: self.api.get("/repository", **params), self._fill, lambda e: show_error(self, e))

    def _fill(self, r):
        self.table.set_data(["Title", "Authors", "Year", "Course", "Adviser", "Dean", "Publication"],
                            [[i["title"], "; ".join(a["name"] for a in i["authors"]), i["year"], i["program"], i["adviser"], i["dean"], i["publication_label"]] for i in r["items"]],
                            [i["work_id"] for i in r["items"]])
        pages = max(1, -(-r["total"] // r["page_size"]))
        self.info.setText(f"{r['total']} record(s) — page {r['page']} of {pages}" if r["total"] else "No research matches these filters.")
        self.prev.setEnabled(r["page"] > 1); self.next.setEnabled(r["page"] < pages)

    def open(self):
        wid = self.table.selected_id()
        if wid is None: return info(self, "Select a research record first.")
        ResearchDetailDialog(self.api, wid, self).exec()


class SearchPage(Page):
    title = "Search"

    def __init__(self, api, main=None):
        super().__init__(api, main)
        self.root.addWidget(h1("Semantic Search"))
        self.box = QLineEdit(); self.box.setPlaceholderText("Search research by topic, idea, or research question...")
        self.box.setMinimumHeight(38); self.box.returnPressed.connect(self.search)
        self.root.addLayout(hbox(self.box, button("Search", "primary", self.search), stretch_end=False))
        self.root.addWidget(muted("Examples: “research projects that use technology to improve student learning” · “systems that help hospitals reduce waiting time”"))
        self.filters = FilterBar(api); self.root.addWidget(self.filters)
        self.status = muted(""); self.root.addWidget(self.status)
        self.table = DataTable(); self.table.doubleClicked.connect(lambda *_: self.open()); self.root.addWidget(self.table)
        self.snippet = QPlainTextEdit(); self.snippet.setReadOnly(True); self.snippet.setMaximumHeight(110); self.root.addWidget(self.snippet)
        self.root.addWidget(muted("Relevance combines meaning and matching words. It is an estimate, not a guarantee of factual relevance."))
        self.items = []; self.table.itemSelectionChanged.connect(self._sel)

    def search(self):
        q = self.box.text().strip()
        if len(q) < 2: self.status.setText("Please type at least 2 characters."); return
        self.status.setText("Searching… (the first search after the server starts can take a little longer)"); self.table.setEnabled(False)
        body = {"query": q, "filters": {k: v for k, v in self.filters.values().items() if v is not None}, "limit": 25}
        run_async(lambda: self.api.post("/search/semantic", body, timeout=120), self._results, lambda e: (self.table.setEnabled(True), self.status.setText(""), show_error(self, e)))

    def _results(self, r):
        self.table.setEnabled(True); self.items = r["results"]
        self.table.set_data(["Title", "Authors", "Year", "Course", "Adviser", "Category", "Relevance"],
                            [[i["title"], "; ".join(a["name"] for a in i["authors"]), i["year"], i["program"], i["adviser"], i["category"], i["score_label"].replace("Semantic relevance: ", "")] for i in self.items],
                            [i["work_id"] for i in self.items])
        self.snippet.clear()
        self.status.setText(f"{r['count']} result(s). Relevance = semantic similarity." if r["count"] else f"{r['message']}  {r['hint']}")

    def _sel(self):
        wid = self.table.selected_id()
        it = next((i for i in self.items if i["work_id"] == wid), None)
        if it: self.snippet.setPlainText(it["abstract_snippet"] + "…")

    def open(self):
        wid = self.table.selected_id()
        if wid is not None: ResearchDetailDialog(self.api, wid, self).exec()


class NotificationsPage(Page):
    title = "Notifications"

    def __init__(self, api, main=None):
        super().__init__(api, main)
        self.root.addWidget(h1("Notifications"))
        self.root.addLayout(hbox(button("Mark selected read", slot=self.mark), button("Mark all read", slot=self.mark_all), button("Refresh", slot=self.refresh)))
        self.table = DataTable(); self.root.addWidget(self.table)

    def refresh(self):
        run_async(lambda: self.api.get("/notifications"), self._fill, lambda e: show_error(self, e))

    def _fill(self, r):
        self.table.set_data(["", "Title", "Message", "When"], [["●" if not n["is_read"] else "", n["title"], n["message"], n["created_at"][:16]] for n in r["items"]],
                            [n["notification_id"] for n in r["items"]])
        if self.main: self.main.set_unread(r["unread"])

    def mark(self):
        nid = self.table.selected_id()
        if nid is not None: run_async(lambda: self.api.post(f"/notifications/{nid}/read"), lambda _: self.refresh(), None)

    def mark_all(self):
        run_async(lambda: self.api.post("/notifications/read-all"), lambda _: self.refresh(), None)


class ProfilePage(Page):
    title = "Profile"

    def __init__(self, api, main=None):
        super().__init__(api, main)
        self.root.addWidget(h1("My Profile"))
        form = QFormLayout()
        self.name, self.email = QLineEdit(), QLineEdit()
        self.old, self.new = QLineEdit(), QLineEdit()
        for e in (self.old, self.new): e.setEchoMode(QLineEdit.Password)
        form.addRow("Full name", self.name); form.addRow("Email", self.email)
        self.root.addLayout(form); self.root.addLayout(hbox(button("Save profile", "primary", self.save)))
        self.root.addWidget(h2("Change password"))
        f2 = QFormLayout(); f2.addRow("Current password", self.old); f2.addRow("New password", self.new)
        self.root.addLayout(f2); self.root.addLayout(hbox(button("Change password", slot=self.change)))
        self.root.addStretch(1)

    def refresh(self):
        u = self.api.user; self.name.setText(u["full_name"]); self.email.setText(u["email"])

    def save(self):
        run_async(lambda: self.api.patch("/auth/me", {"full_name": self.name.text().strip(), "email": self.email.text().strip()}),
                  lambda u: (self.api.user.update(u), info(self, "Profile saved.")), lambda e: show_error(self, e))

    def change(self):
        run_async(lambda: self.api.post("/auth/change-password", {"old_password": self.old.text(), "new_password": self.new.text()}),
                  lambda _: (self.old.clear(), self.new.clear(), info(self, "Password changed.")), lambda e: show_error(self, e))


# ---------------- administration ----------------
class UsersPage(Page):
    title = "Users"

    def __init__(self, api, main=None):
        super().__init__(api, main)
        self.root.addWidget(h1("User Management"))
        self.q = QLineEdit(); self.q.setPlaceholderText("Search username, name or email"); self.q.returnPressed.connect(self.refresh)
        self.role, self.status = QComboBox(), QComboBox()
        self.role.addItem("All roles", None); self.status.addItem("Any status", None); self.status.addItem("Active", "ACTIVE"); self.status.addItem("Deactivated", "INACTIVE")
        self.root.addLayout(hbox(self.q, self.role, self.status, button("Search", slot=self.refresh)))
        self.root.addLayout(hbox(button("New user", "primary", self.new), button("Edit", slot=self.edit), button("Activate", slot=lambda: self.toggle(True)),
                                 button("Deactivate", "danger", lambda: self.toggle(False)), button("Reset password", slot=self.reset)))
        self.table = DataTable(); self.root.addWidget(self.table); self.users = {}
        run_async(lambda: self.api.get("/lookups")["roles"], lambda rs: [self.role.addItem(r, r) for r in rs], None)

    def apply_preset(self, preset):
        st = (preset or {}).get("status")
        if st:
            self._preset_on = True; i = self.status.findData(st); self.status.setCurrentIndex(max(i, 0))
        elif getattr(self, "_preset_on", False):
            self._preset_on = False; self.status.setCurrentIndex(0)
        self.refresh()

    def refresh(self):
        run_async(lambda: self.api.get("/users", q=self.q.text().strip(), role=self.role.currentData(), status=self.status.currentData(), page_size=200), self._fill, lambda e: show_error(self, e))

    def _fill(self, r):
        self.users = {u["user_id"]: u for u in r["items"]}
        self.table.set_data(["Username", "Name", "Role", "Email", "Status", "Last login"],
                            [[u["username"], u["full_name"], u["role"] + (" (Head Librarian)" if u.get("is_head_librarian") else ""), u["email"], "Active" if u["status"] == "ACTIVE" else "Deactivated", (u["last_login_at"] or "")[:16]] for u in r["items"]],
                            [u["user_id"] for u in r["items"]])

    def new(self):
        if UserDialog(self.api, None, self).exec(): self.refresh()

    def _sel(self):
        uid = self.table.selected_id()
        if uid is None: info(self, "Select a user first.")
        return uid

    def edit(self):
        uid = self._sel()
        if uid and UserDialog(self.api, self.users[uid], self).exec(): self.refresh()

    def toggle(self, active):
        uid = self._sel()
        if uid and confirm(self, f"{'Activate' if active else 'Deactivate'} {self.users[uid]['username']}?"):
            run_async(lambda: self.api.post(f"/users/{uid}/{'activate' if active else 'deactivate'}"), lambda _: self.refresh(), lambda e: show_error(self, e))

    def reset(self):
        uid = self._sel()
        if not uid: return
        pw, ok = QInputDialog.getText(self, "Reset password", "New temporary password:", QLineEdit.Password)
        if ok and pw:
            run_async(lambda: self.api.post(f"/users/{uid}/reset-password", {"new_password": pw}), lambda _: info(self, "Password reset. Existing sessions were signed out."), lambda e: show_error(self, e))


class RolesPage(Page):
    title = "Roles"

    def __init__(self, api, main=None):
        super().__init__(api, main)
        self.root.addWidget(h1("Roles")); self.root.addWidget(muted("The five system roles (Student, Faculty, Library Staff, Administrator, External User) are required by the system and cannot be deleted. The Head Librarian is a Library Staff account designated in User Management."))
        self.table = DataTable(); self.root.addWidget(self.table)

    def refresh(self):
        run_async(lambda: self.api.get("/admin/roles")["items"], lambda it: self.table.set_data(["Role", "Description", "System-required"], [[r["role_name"], r["description"], "Yes"] for r in it]), lambda e: show_error(self, e))


class LookupsPage(Page):
    title = "Departments / Courses / Categories"

    def __init__(self, api, main=None):
        super().__init__(api, main)
        self.root.addWidget(h1("Departments, Courses and Categories"))
        self.kind = QComboBox(); [self.kind.addItem(l, v) for l, v in (("Departments", "departments"), ("Courses", "programs"), ("Research categories", "categories"))]
        self.kind.currentIndexChanged.connect(self.refresh)
        self.root.addLayout(hbox(self.kind, button("Add", "primary", self.add), button("Rename", slot=self.rename), button("Activate / Deactivate", slot=self.toggle)))
        self.table = DataTable(); self.root.addWidget(self.table); self.items = {}

    def refresh(self):
        k = self.kind.currentData()
        run_async(lambda: self.api.get(f"/admin/lookups/{k}")["items"], self._fill, lambda e: show_error(self, e))

    def _fill(self, items):
        self.items = {i["id"]: i for i in items}
        self.table.set_data(["ID", "Name", "Status"], [[i["id"], i["name"], i["status"]] for i in items], [i["id"] for i in items])

    def add(self):
        name, ok = QInputDialog.getText(self, "Add", "Name:")
        if not (ok and name.strip()): return
        body = {"name": name.strip()}
        if self.kind.currentData() == "programs":
            run_async(lambda: self.api.get("/lookups")["departments"], lambda ds: self._add_prog(ds, body), None); return
        self._post(body)

    def _add_prog(self, depts, body):
        d, ok = QInputDialog.getItem(self, "Department", "Department:", [x["name"] for x in depts], 0, False)
        if ok: body["department_id"] = next(x["id"] for x in depts if x["name"] == d); self._post(body)

    def _post(self, body):
        k = self.kind.currentData()
        run_async(lambda: self.api.post(f"/admin/lookups/{k}", body), lambda _: self.refresh(), lambda e: show_error(self, e))

    def rename(self):
        i = self.table.selected_id()
        if i is None: return
        name, ok = QInputDialog.getText(self, "Rename", "New name:", text=self.items[i]["name"])
        if ok and name.strip():
            k = self.kind.currentData()
            run_async(lambda: self.api.patch(f"/admin/lookups/{k}/{i}", {"name": name.strip()}), lambda _: self.refresh(), lambda e: show_error(self, e))

    def toggle(self):
        i = self.table.selected_id()
        if i is None: return
        it, k = self.items[i], self.kind.currentData()
        new = "INACTIVE" if it["status"] == "ACTIVE" else "ACTIVE"
        if confirm(self, f"Set “{it['name']}” to {new}?"):
            run_async(lambda: self.api.patch(f"/admin/lookups/{k}/{i}", {"name": it["name"], "status": new}), lambda _: self.refresh(), lambda e: show_error(self, e))


SETTING_LABELS = {"min_password_length": "Minimum password length", "failed_login_limit": "Failed-login limit", "lockout_minutes": "Lockout duration (minutes)",
                  "idle_timeout_minutes": "Session idle timeout (minutes)", "max_manuscript_mb": "Max research document (PDF) size (MB)", "max_source_code_mb": "Max source code archive size (MB)",
                  "max_video_mb": "Max video size (MB)", "max_companion_mb": "Max other supporting file size (MB)",
                  "semantic_threshold": "Semantic threshold (0–1)", "recommendation_count": "Recommendations shown", "log_search_queries": "Log search queries (true/false)",
                  "guest_reading_enabled": "Let visitors without an account read archived research (true/false)"}


class SettingsPage(Page):
    title = "System Settings"

    def __init__(self, api, main=None):
        super().__init__(api, main)
        self.root.addWidget(h1("System Settings")); self.root.addWidget(muted("Every change is written to the audit log. The semantic threshold is a tunable starting point."))
        self.form = QFormLayout(); self.edits = {}
        for k, lbl in SETTING_LABELS.items():
            e = QLineEdit(); self.edits[k] = e; self.form.addRow(lbl, e)
        w = QWidget(); w.setLayout(self.form); self.root.addWidget(w)
        self.root.addLayout(hbox(button("Save settings", "primary", self.save)))
        self.root.addStretch(1)

    def refresh(self):
        run_async(lambda: self.api.get("/admin/settings"), lambda s: [self.edits[k].setText(str(v)) for k, v in s.items() if k in self.edits], lambda e: show_error(self, e))

    def save(self):
        vals = {k: e.text().strip() for k, e in self.edits.items()}
        run_async(lambda: self.api.put("/admin/settings", {"values": vals}), lambda _: info(self, "Settings saved."), lambda e: show_error(self, e))


class IndexingPage(Page):
    title = "Indexing Monitor"

    def __init__(self, api, main=None):
        super().__init__(api, main)
        self.root.addWidget(h1("Indexing Monitor"))
        self.summary = muted(""); self.root.addWidget(self.summary)
        self.admin = api.role == "ADMIN"
        if self.admin:
            self.root.addLayout(hbox(button("Reindex Failed", slot=lambda: self.rebuild("failed")), button("Reindex All", "danger", lambda: self.rebuild("all")), button("Refresh", slot=self.refresh)))
        self.root.addWidget(h2("Failed / stale embeddings")); self.table = DataTable(); self.root.addWidget(self.table)
        self.timer = QTimer(self); self.timer.setInterval(2000); self.timer.timeout.connect(self.refresh)

    def refresh(self):
        run_async(lambda: self.api.get("/admin/indexing"), self._fill, lambda e: show_error(self, e))

    def _fill(self, s):
        p = s["progress"]
        run = f"   |   Rebuild running: {p['done']}/{p['total']} (failed {p['failed']})" if p["running"] else ""
        self.summary.setText(f"Archived: {s['total_archived']}  ·  Indexed: {s['indexed']}  ·  Failed: {s['failed']}  ·  Stale: {s['stale']}  ·  Pending: {s['pending']}\n"
                             f"Model: {s['model'] or 'n/a'}  ·  Threshold: {s['threshold']}  ·  Last indexing: {(s['last_indexed_at'] or 'never')[:19]}{run}")
        self.table.set_data(["Work", "Title", "Status", "Error"], [[f["work_id"], f["title"], f["status"], f["error"]] for f in s["failures"]])
        self.timer.start() if p["running"] else self.timer.stop()

    def rebuild(self, mode):
        if mode == "all" and not confirm(self, "Rebuild ALL embeddings? Searches keep working while it runs."): return
        run_async(lambda: self.api.post("/admin/indexing/rebuild", {"mode": mode}), lambda _: (self.timer.start(), self.refresh()), lambda e: show_error(self, e))


class LogsPage(Page):
    title = "Logs"

    def __init__(self, api, main=None, kind="audit-logs", title="Audit Logs"):
        super().__init__(api, main)
        self.kind, self.title, self.n = kind, title, 1
        self.root.addWidget(h1(title)); self.root.addWidget(muted("Read-only. Log entries cannot be edited or deleted from the application."))
        self.table = DataTable(); self.root.addWidget(self.table)
        self.prev, self.next = button("< Newer", slot=lambda: self.go(self.n - 1)), button("Older >", slot=lambda: self.go(self.n + 1))
        self.lbl = muted(""); self.root.addLayout(hbox(self.prev, self.next, self.lbl))
        self.filter_val = None
        self.filter_lbl = muted(""); self.clear_btn = button("Show all", slot=lambda: self.apply_preset({}, force=True))
        self.root.insertLayout(2, hbox(self.filter_lbl, self.clear_btn)); self.clear_btn.hide()

    def apply_preset(self, preset, force=False):
        """Dashboard shortcut, e.g. {"action": "LOGIN_FAILED"} (audit) ; empty preset shows everything."""
        v = (preset or {}).get("action")
        self.filter_val = v if (v and self.kind == "audit-logs") else None
        self.filter_lbl.setText(f"Filtered: {self.filter_val}" if self.filter_val else ""); self.clear_btn.setVisible(bool(self.filter_val))
        self.go(1)

    def refresh(self): self.go(self.n)

    def go(self, n):
        if n < 1: return
        self.n = n
        extra = {"action": self.filter_val} if self.filter_val else {}
        run_async(lambda: self.api.get(f"/{self.kind}", page=n, page_size=50, **extra), self._fill, lambda e: show_error(self, e))

    def _fill(self, r):
        audit = self.kind == "audit-logs"
        cols = ["Time", "User", "Action", "Target", "Result", "Details"] if audit else ["Time", "User", "Event", "Target", "Details"]
        rows = [[i["timestamp"][:19], i["user"], i["action"], i["target"], i["result"], i["details"]] if audit else [i["timestamp"][:19], i["user"], i["event_type"], i["target"], i["details"]] for i in r["items"]]
        self.table.set_data(cols, rows); self.lbl.setText(f"Page {r['page']}"); self.next.setEnabled(len(rows) == 50); self.prev.setEnabled(r["page"] > 1)


REPORT_NAMES = {"submissions": "Submissions Report", "approvals": "Approvals Report", "returns": "Returned Submissions Report",
                "pending-verification": "Pending Verification Report", "archived": "Archived Research Report",
                "user-activity": "User Activity Report", "system-activity": "System Activity Report"}


class ReportsPage(Page):
    title = "Reports"

    def __init__(self, api, main=None):
        super().__init__(api, main)
        self.root.addWidget(h1("Reports")); self.root.addWidget(muted("Administrator reports. Each can be exported as CSV."))
        self.kind = QComboBox()
        for k, v in REPORT_NAMES.items(): self.kind.addItem(v, k)
        self.d1, self.d2 = QDateEdit(QDate.currentDate().addMonths(-12)), QDateEdit(QDate.currentDate())
        for d in (self.d1, self.d2): d.setCalendarPopup(True); d.setDisplayFormat("yyyy-MM-dd")
        self.use_dates = QComboBox(); self.use_dates.addItems(["Any date", "Use date range"])
        self.status = QComboBox(); self.status.addItem("Any status", None)
        self.root.addLayout(hbox(self.kind, self.use_dates, self.d1, self.d2, self.status))
        self.root.addLayout(hbox(button("Run report", "primary", self.run), button("Export CSV…", slot=self.export)))
        self.info = muted(""); self.root.addWidget(self.info); self.table = DataTable(); self.root.addWidget(self.table)
        run_async(lambda: self.api.get("/lookups")["statuses"], lambda ss: [self.status.addItem(x["name"], x["id"]) for x in ss], None)

    def params(self):
        p = {"status": self.status.currentData()}
        if self.use_dates.currentIndex() == 1:
            p["date_from"], p["date_to"] = self.d1.date().toString("yyyy-MM-dd"), self.d2.date().toString("yyyy-MM-dd")
        return {k: v for k, v in p.items() if v}

    def run(self):
        k, p = self.kind.currentData(), self.params(); self.info.setText("Generating…")
        run_async(lambda: self.api.get(f"/reports/{k}", **p), lambda r: (self.table.set_data(r["columns"], r["rows"]), self.info.setText(f"{r['count']} row(s)")),
                  lambda e: (self.info.setText(""), show_error(self, e)))

    def export(self):
        k, p = self.kind.currentData(), self.params()
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", f"{k}.csv", "CSV (*.csv)")
        if path:
            run_async(lambda: self.api.report_csv(k, p), lambda data: (open(path, "wb").write(data), info(self, "Report exported.")), lambda e: show_error(self, e))


class RosterPage(Page):
    title = "Student Roster"

    def __init__(self, api, main=None):
        super().__init__(api, main)
        self.root.addWidget(h1("Student Roster"))
        self.root.addWidget(muted("Only students on this list can create an account. Import the registrar's CSV (columns: student_number, last_name, first_name, department optional)."))
        self.q = QLineEdit(); self.q.setPlaceholderText("Search ID or name"); self.q.returnPressed.connect(self.refresh)
        self.root.addLayout(hbox(self.q, button("Search", slot=self.refresh), button("Add student", "primary", self.add), button("Import CSV…", slot=self.import_csv)))
        self.table = DataTable(); self.root.addWidget(self.table)
        self.info = muted(""); self.root.addWidget(self.info)

    def refresh(self):
        q = self.q.text().strip()
        run_async(lambda: self.api.get("/admin/roster", q=q, page_size=200), self._fill, lambda e: show_error(self, e))

    def _fill(self, r):
        self.table.set_data(["Student ID", "Last name", "First name", "Account"], [[i["student_number"], i["last_name"], i["first_name"], i["account"]] for i in r["items"]])
        self.info.setText(f"{r['total']} student(s) on the roster")

    def add(self):
        sn, ok = QInputDialog.getText(self, "Add student", "Student ID:")
        if not (ok and sn.strip()): return
        last, ok = QInputDialog.getText(self, "Add student", "Last name:")
        if not (ok and last.strip()): return
        first, ok = QInputDialog.getText(self, "Add student", "First name:")
        if not (ok and first.strip()): return
        run_async(lambda: self.api.post("/admin/roster", {"student_number": sn.strip(), "last_name": last.strip(), "first_name": first.strip()}),
                  lambda _: self.refresh(), lambda e: show_error(self, e))

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import roster CSV", "", "CSV (*.csv)")
        if not path: return
        with open(path, "r", encoding="utf-8-sig") as f: text = f.read()
        run_async(lambda: self.api.post("/admin/roster/import", {"csv": text}),
                  lambda r: (info(self, f"Added {r['added']}, skipped {r['skipped']} existing." + (f"\nProblems: {'; '.join(r['errors'][:5])}" if r["errors"] else "")), self.refresh()),
                  lambda e: show_error(self, e))


class ApiKeysPage(Page):
    title = "Integrations (API keys)"

    def __init__(self, api, main=None):
        super().__init__(api, main)
        self.root.addWidget(h1("Integrations — API keys"))
        self.root.addWidget(muted("API keys let another system (e.g. the registrar or library catalog) call the DRASS integration API (/api/v1). "
                                  "Keys are shown once, stored only as a hash, limited to the scopes you choose, and can be revoked."))
        self.root.addLayout(hbox(button("Create API key", "primary", self.create), button("Revoke selected", "danger", self.revoke), button("Refresh", slot=self.refresh)))
        self.table = DataTable(); self.root.addWidget(self.table)

    def refresh(self):
        run_async(lambda: self.api.get("/admin/api-keys"), self._fill, lambda e: show_error(self, e))

    def _fill(self, r):
        self.scopes = r["scopes"]
        items = r["items"]
        self.table.set_data(["Name", "Key starts with", "Scopes", "Status", "Expires", "Last used"],
                            [[k["name"], k["key_prefix"] + "…", k["scopes"], k["status"], (k["expires_at"] or "never")[:10], (k["last_used_at"] or "never")[:16]] for k in items],
                            [k["key_id"] for k in items])

    def create(self):
        from PySide6.QtWidgets import QCheckBox, QDialog, QSpinBox
        d = QDialog(self); d.setWindowTitle("Create API key"); lay = QVBoxLayout(d)
        name = QLineEdit(); name.setPlaceholderText("e.g. Registrar roster sync")
        lay.addWidget(muted("Name of the system that will use this key *")); lay.addWidget(name)
        boxes = {}
        for sc, desc in (getattr(self, "scopes", {"roster:write": "Sync the student roster", "catalog:read": "Read archived research metadata"})).items():
            cb = QCheckBox(f"{sc} — {desc}"); boxes[sc] = cb; lay.addWidget(cb)
        days = QSpinBox(); days.setRange(0, 3650); days.setValue(365); days.setSpecialValueText("Never expires")
        lay.addWidget(muted("Expires after (days)")); lay.addWidget(days)
        def go():
            chosen = [s for s, c in boxes.items() if c.isChecked()]
            if not name.text().strip() or not chosen:
                return info(d, "Enter a name and choose at least one scope.")
            body = {"name": name.text().strip(), "scopes": chosen, "expires_days": days.value() or None}
            def ok(r):
                d.accept()
                box = QLineEdit(r["api_key"]); box.setReadOnly(True); box.setMinimumWidth(480)
                k = QDialog(self); k.setWindowTitle("Your new API key"); kl = QVBoxLayout(k)
                kl.addWidget(h2("Copy this key now")); kl.addWidget(muted("It cannot be shown again. Anyone with this key can use its scopes."))
                kl.addWidget(box); kl.addLayout(hbox(button("Close", "primary", k.accept))); box.selectAll(); k.exec(); self.refresh()
            run_async(lambda: self.api.post("/admin/api-keys", body), ok, lambda e: show_error(d, e))
        lay.addLayout(hbox(button("Create", "primary", go), button("Cancel", slot=d.reject)))
        d.exec()

    def revoke(self):
        kid = self.table.selected_id()
        if kid is None: return info(self, "Select a key first.")
        if confirm(self, "Revoke this key? The external system will stop working immediately."):
            run_async(lambda: self.api.post(f"/admin/api-keys/{kid}/revoke"), lambda _: self.refresh(), lambda e: show_error(self, e))


class BackupPage(Page):
    """Administrator: back up and restore the database and research files (manuscript FR17, NFR6)."""
    title = "Backup & Recovery"

    def __init__(self, api, main=None):
        super().__init__(api, main)
        self.root.addWidget(h1("Backup & Recovery"))
        self.root.addWidget(muted("A backup holds the database and every research file, with a checksum. Keep the backup folder on separate storage "
                                  "(external drive or NAS). Restoring replaces the current data; a safety backup of the current state is made first. "
                                  "Automatic daily backups run through Windows Task Scheduler (see docs/BACKUP_AND_SYNC.md)."))
        self.where = muted(""); self.root.addWidget(self.where)
        self.root.addLayout(hbox(button("Back up now", "primary", self.backup), button("Restore selected…", "danger", self.restore), button("Refresh", slot=self.refresh)))
        self.table = DataTable(); self.root.addWidget(self.table); self.items = {}

    def refresh(self):
        run_async(lambda: self.api.get("/admin/backups"), self._fill, lambda e: show_error(self, e))

    def _fill(self, r):
        self.where.setText(f"Backup folder: {r['backup_dir']}")
        self.items = {i["name"]: i for i in r["items"]}
        self.table.set_data(["Backup", "Type", "Created", "Research files", "Size (MB)"],
                            [[i["name"], i["label"], i["created_at"].replace("T", " "), i["file_count"], round(i["storage_bytes"] / 1048576, 1)] for i in r["items"]],
                            list(range(len(r["items"]))))
        self._names = [i["name"] for i in r["items"]]

    def backup(self):
        self.where.setText("Backing up… this can take a while for many files.")
        run_async(lambda: self.api.request("POST", "/admin/backups", json={}, timeout=3600).json(),
                  lambda m: (info(self, f"Backup created: {m['name']}"), self.refresh()), lambda e: (self.refresh(), show_error(self, e)))

    def restore(self):
        idx = self.table.selected_id()
        if idx is None: return info(self, "Select a backup first.")
        name = self._names[idx]
        typed, ok = QInputDialog.getText(self, "Restore backup", f"This REPLACES the database and research files with backup\n{name}\n\nType RESTORE to continue:")
        if not ok: return
        if typed.strip() != "RESTORE": return info(self, "Not confirmed. Nothing was changed.")
        run_async(lambda: self.api.request("POST", "/admin/backups/restore", json={"name": name, "confirm": "RESTORE"}, timeout=3600).json(),
                  lambda r: (info(self, f"Restored {r['restored']}. A safety backup of the previous state was saved as {r['safety_backup']}.\nSign in again if asked."), self.refresh()),
                  lambda e: show_error(self, e))
