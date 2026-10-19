from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QStackedWidget,
                               QVBoxLayout, QWidget, QFormLayout)
from .views import pages as P
from .widgets import button, h1, muted, show_error
from .worker import bus, run_async

INSTITUTION = "Mary the Queen College of Quezon City, Inc."


def _nav(role, api):
    S = lambda cls, *a, **k: (lambda: cls(api, None, *a, **k))
    dash, notif, prof, search = ("Dashboard", S(P.DashboardPage)), ("Notifications", S(P.NotificationsPage)), ("Profile", S(P.ProfilePage)), ("Search", S(P.SearchPage))
    repo, reports = ("Repository", S(P.RepositoryPage)), ("Reports", S(P.ReportsPage))
    hist = ("Review History", S(P.ReviewHistoryPage))
    return {
        "STUDENT": [dash, ("My Submissions", S(P.SubmissionsPage)), search, repo, notif, prof],
        "ADVISER": [dash, ("Review Queue", S(P.ReviewQueuePage, "Review Queue")), hist, search, repo, reports, notif, prof],
        "PANELIST": [dash, ("Assigned Reviews", S(P.ReviewQueuePage, "Assigned Reviews")), hist, search, repo, reports, notif, prof],
        "DEAN": [dash, ("Pending Approvals", S(P.ReviewQueuePage, "Pending Approvals")), hist, ("Department Research", S(P.RepositoryPage, "Department Research")), search, reports, notif, prof],
        "LIBRARY_STAFF": [dash, repo, search, ("Indexing Monitor", S(P.IndexingPage)), reports, notif, prof],
        "HEAD_LIBRARIAN": [dash, ("Archive Approval Queue", S(P.ReviewQueuePage, "Archive Approval Queue")), hist, repo, search, ("Indexing Monitor", S(P.IndexingPage)), reports, notif, prof],
        "ADMIN": [dash, ("Users", S(P.UsersPage)), ("Roles", S(P.RolesPage)), ("Departments / Programs / Categories", S(P.LookupsPage)), ("System Settings", S(P.SettingsPage)), ("Student Roster", S(P.RosterPage)),
                  ("Audit Logs", S(P.LogsPage, "audit-logs", "Audit Logs")), ("Activity Logs", S(P.LogsPage, "activity-logs", "Activity Logs")),
                  ("Repository Management", S(P.RepositoryPage, "Repository Management", True)), ("Indexing Monitor", S(P.IndexingPage)), search, reports, notif, prof],
        "EXTERNAL_USER": [dash, repo, search, prof],
        "GUEST": [repo, search],
    }[role]


class MainWindow(QMainWindow):
    logged_out = Signal(str)
    sign_in_requested = Signal()

    def __init__(self, api):
        super().__init__()
        self.api = api
        self.setWindowTitle(f"DRASS — {INSTITUTION}"); self.resize(1280, 820)
        root = QWidget(); self.setCentralWidget(root); outer = QVBoxLayout(root); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        header = QFrame(); header.setObjectName("header"); hl = QHBoxLayout(header)
        t = QLabel("<b>DRASS</b> — Digital Research Archiving System with Semantic Search"); sub = QLabel(INSTITUTION)
        left = QVBoxLayout(); left.addWidget(t); left.addWidget(sub)
        hl.addLayout(left); hl.addStretch(1)
        u = api.user
        self.guest = u["role"] == "GUEST"
        hl.addWidget(QLabel("Guest visitor — browse and search only" if self.guest else f"{u['full_name']}  ·  {u['role'].replace('_', ' ').title()}"))
        self.bell = button("🔔 0", slot=self.open_notifications); hl.addWidget(self.bell)
        if self.guest:
            self.bell.hide()
            hl.addWidget(button("Create student account", slot=self.register))
            hl.addWidget(button("Sign in", slot=self.sign_in_requested.emit))
        else:
            hl.addWidget(button("Log out", slot=lambda: self.logout()))
        outer.addWidget(header)
        body = QHBoxLayout(); body.setSpacing(0); outer.addLayout(body, 1)
        side = QFrame(); side.setObjectName("sidebar"); side.setFixedWidth(250); sl = QVBoxLayout(side); sl.setContentsMargins(0, 8, 0, 8)
        self.nav = QListWidget(); self.nav.setObjectName("nav"); sl.addWidget(self.nav); body.addWidget(side)
        right = QVBoxLayout(); body.addLayout(right, 1)
        self.crumb = muted(""); self.crumb.setContentsMargins(20, 8, 20, 0); right.addWidget(self.crumb)
        self.stack = QStackedWidget(); right.addWidget(self.stack, 1)
        self.items = _nav(u["role"], api); self.pages = {}
        for label, _ in self.items: self.nav.addItem(QListWidgetItem(label))
        self.nav.currentRowChanged.connect(self.show_page)
        self.nav.setCurrentRow(0)
        self.timer = QTimer(self); self.timer.setInterval(60_000); self.timer.timeout.connect(self.poll); self.timer.start(); self.poll()

    def show_page(self, row):
        if row < 0: return
        label, factory = self.items[row]
        if row not in self.pages:
            page = factory(); page.main = self; self.pages[row] = page; self.stack.addWidget(page)
        page = self.pages[row]
        self.stack.setCurrentWidget(page); self.crumb.setText(f"Home  ›  {label}"); page.refresh()

    def open_notifications(self):
        for i, (label, _) in enumerate(self.items):
            if label == "Notifications": self.nav.setCurrentRow(i)

    def set_unread(self, n): self.bell.setText(f"🔔 {n}")

    def register(self):
        from .dialogs.register_dialog import RegisterDialog
        RegisterDialog(self.api, self).exec()

    def poll(self):
        if self.api.role in ("EXTERNAL_USER", "GUEST"): self.bell.hide(); return
        run_async(lambda: self.api.get("/notifications", unread_only=True, limit=1)["unread"], self.set_unread, None)

    def logout(self, message=""):
        self.timer.stop()
        run_async(self.api.logout, lambda _: self.logged_out.emit(message), lambda _: self.logged_out.emit(message))
