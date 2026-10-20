from PySide6.QtCore import QDateTime, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QPushButton
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow, QStackedWidget,
                               QVBoxLayout, QWidget)
from . import style
from .brand import APP_NAME, INSTITUTION, TAGLINE, res
from .views import pages as P
from .widgets import button, muted
from .worker import run_async



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
        "ADMIN": [dash, ("Users", S(P.UsersPage)), ("Roles", S(P.RolesPage)), ("Department/ Programs", S(P.LookupsPage)),
                  ("System Settings", S(P.SettingsPage)), ("Student Roster", S(P.RosterPage)), ("Integrations (API keys)", S(P.ApiKeysPage)),
                  ("Audit Logs", S(P.LogsPage, "audit-logs", "Audit Logs")), ("Activity Logs", S(P.LogsPage, "activity-logs", "Activity Logs")),
                  ("Repository Management", S(P.RepositoryPage, "Repository Management", True)), ("Indexing Monitor", S(P.IndexingPage)),
                  search, reports, notif, prof],
        "EXTERNAL_USER": [dash, repo, search, prof],
        "GUEST": [repo, search],
    }[role]


class MainWindow(QMainWindow):
    logged_out = Signal(str)
    sign_in_requested = Signal()

    def __init__(self, api):
        super().__init__()
        self.api = api
        self.setWindowTitle(f"{APP_NAME} — {INSTITUTION}"); self.resize(1280, 820)
        root = QWidget(); self.setCentralWidget(root); outer = QVBoxLayout(root); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        header = QFrame(); header.setObjectName("header"); header.setFixedHeight(86)
        hl = QHBoxLayout(header); hl.setContentsMargins(128, 0, 31, 0); hl.setSpacing(3)
        t = QLabel(f"<b>{APP_NAME} - {TAGLINE}</b>"); t.setStyleSheet("font-size: 12.5pt;")
        sub = QLabel(f"<b>{INSTITUTION}</b>")
        left = QVBoxLayout(); left.setSpacing(2); left.addWidget(t); left.addWidget(sub)
        hl.addLayout(left); hl.addStretch(1)
        u = api.user
        self.guest = u["role"] == "GUEST"
        who = "Guest visitor - browse and search only" if self.guest else f"{u['full_name']} - {u['role'].replace('_', ' ').title()}"
        who_lbl = QLabel(who); who_lbl.setContentsMargins(0, 0, 8, 0); hl.addWidget(who_lbl)
        self.bell = button("0", slot=self.open_notifications); self.bell.setToolTip("Notifications")
        self.bell.setIcon(QIcon(res("bell.svg"))); self.bell.setIconSize(QSize(18, 18)); self.bell.setFixedHeight(32); hl.addWidget(self.bell)
        self.theme_btn = button("", slot=self.toggle_theme); self.theme_btn.setToolTip("Switch light / dark mode"); self.theme_btn.setIconSize(QSize(18, 18))
        self.theme_btn.setFixedSize(32, 32); self._theme_icon(); hl.addWidget(self.theme_btn)
        if self.guest:
            self.bell.hide()
            hl.addWidget(button("Create student account", slot=self.register))
            hl.addWidget(button("Sign in", slot=self.sign_in_requested.emit))
        else:
            lo = button("Log out", slot=lambda: self.logout()); lo.setFixedHeight(32); hl.addWidget(lo)
        for i in range(hl.count()):
            w_ = hl.itemAt(i).widget()
            if isinstance(w_, QPushButton): w_.setFixedHeight(32)
        hl.addSpacing(24)
        self.seal = QLabel(); spm = QPixmap(res("seal.png"))
        if not spm.isNull():
            self.seal.setPixmap(spm.scaled(69, 69, Qt.KeepAspectRatio, Qt.SmoothTransformation)); hl.addWidget(self.seal)
        outer.addWidget(header)
        body = QHBoxLayout(); body.setSpacing(0); outer.addLayout(body, 1)
        side = QFrame(); side.setObjectName("sidebar"); side.setFixedWidth(255); sl = QVBoxLayout(side); sl.setContentsMargins(0, 42, 0, 8)
        self.nav = QListWidget(); self.nav.setObjectName("nav"); sl.addWidget(self.nav); body.addWidget(side)
        content = QWidget(); content.setObjectName("content"); right = QVBoxLayout(content); right.setContentsMargins(0, 0, 0, 0); body.addWidget(content, 1)
        self.crumb = muted(""); self.crumb.setContentsMargins(32, 14, 20, 0); right.addWidget(self.crumb)
        self.stack = QStackedWidget(); right.addWidget(self.stack, 1)
        self.clock = QLabel(""); self.clock.setObjectName("clock"); self.clock.setAlignment(Qt.AlignRight); self.clock.setContentsMargins(0, 0, 20, 8); right.addWidget(self.clock)
        self.items = _nav(u["role"], api); self.pages = {}
        for label, _ in self.items: self.nav.addItem(QListWidgetItem(label))
        self.nav.currentRowChanged.connect(self.show_page)
        # cream ribbon with the archive icon, overlapping the header (as in the approved design)
        self.ribbon = QLabel(root); pm = QPixmap(res("ribbon.png"))
        if pm.isNull():
            self.ribbon.hide()
        else:
            self.ribbon.setPixmap(pm.scaled(66, 85, Qt.KeepAspectRatio, Qt.SmoothTransformation)); self.ribbon.adjustSize(); self.ribbon.move(33, 0); self.ribbon.raise_()
            sh = QGraphicsDropShadowEffect(self.ribbon); sh.setBlurRadius(10); sh.setOffset(0, 2); sh.setColor(QColor(0, 0, 0, 110)); self.ribbon.setGraphicsEffect(sh)
        self.nav.setCurrentRow(0)
        self.timer = QTimer(self); self.timer.setInterval(60_000); self.timer.timeout.connect(self.poll); self.timer.start(); self.poll()
        self.tick = QTimer(self); self.tick.setInterval(1000); self.tick.timeout.connect(self._clock); self.tick.start(); self._clock()

    def _clock(self):
        self.clock.setText(QDateTime.currentDateTime().toString("MMMM d, yyyy  h:mm:ss AP"))

    def show_page(self, row, preset=None):
        if row < 0: return
        label, factory = self.items[row]
        if row not in self.pages:
            page = factory(); page.main = self; self.pages[row] = page; self.stack.addWidget(page)
        page = self.pages[row]
        self.stack.setCurrentWidget(page); self.crumb.setText(f"Home > {label}")
        if hasattr(page, "apply_preset"):
            page.apply_preset(preset or {})              # {} clears any earlier shortcut filter
        else:
            page.refresh()

    def navigate(self, label: str, preset=None) -> bool:
        """Open a page by its sidebar label (used by clickable dashboard boxes). Returns False if the role has no such page."""
        for i, (lbl, _) in enumerate(self.items):
            if lbl == label:
                if self.nav.currentRow() == i:
                    self.show_page(i, preset)
                else:
                    self._preset = preset
                    self.nav.blockSignals(True); self.nav.setCurrentRow(i); self.nav.blockSignals(False)
                    self.show_page(i, preset)
                return True
        return False

    def navigate_first(self, labels, preset=None) -> bool:
        have = [l for l, _ in self.items]
        for lbl in labels:
            if lbl in have: return self.navigate(lbl, preset)
        return False

    def open_notifications(self):
        self.navigate("Notifications")

    def set_unread(self, n): self.bell.setText(str(n))

    def toggle_theme(self):
        style.toggle_theme(QApplication.instance()); self._theme_icon()

    def _theme_icon(self):
        self.theme_btn.setIcon(QIcon(res("sun.svg" if style.current_theme() == "dark" else "moon.svg")))

    def register(self):
        from .dialogs.register_dialog import RegisterDialog
        RegisterDialog(self.api, self).exec()

    def poll(self):
        if self.api.role in ("EXTERNAL_USER", "GUEST"): self.bell.hide(); return
        run_async(lambda: self.api.get("/notifications", unread_only=True, limit=1)["unread"], self.set_unread, None)

    def logout(self, message=""):
        self.timer.stop(); self.tick.stop()
        run_async(self.api.logout, lambda _: self.logged_out.emit(message), lambda _: self.logged_out.emit(message))
