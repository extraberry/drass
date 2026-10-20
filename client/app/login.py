from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import QApplication, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget
from . import style
from .brand import APP_NAME, INSTITUTION, TAGLINE, res
from .widgets import button, h1, muted
from .worker import run_async


class LoginWindow(QWidget):
    logged_in = Signal()
    guest_requested = Signal()

    def __init__(self, api, message: str = ""):
        super().__init__()
        self.api = api
        self.setObjectName("login"); self.setWindowTitle(f"{APP_NAME} — Sign in"); self.setFixedSize(460, 640)
        lay = QVBoxLayout(self); lay.setContentsMargins(40, 30, 40, 30)
        top = QHBoxLayout(); logo = QLabel(); pm = QPixmap(res("seal.png"))
        if not pm.isNull():
            logo.setPixmap(pm.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)); top.addWidget(logo)
        title = QLabel(APP_NAME); title.setObjectName("wordmark")        # bold + condensed (tight letter spacing)
        f = title.font(); f.setLetterSpacing(QFont.PercentageSpacing, 88); title.setFont(f)
        top.addWidget(title); top.addStretch(1)
        self.theme_btn = button(style.theme_button_text(), slot=self.toggle_theme); top.addWidget(self.theme_btn)
        lay.addLayout(top)
        lay.addWidget(muted(TAGLINE)); lay.addWidget(muted(INSTITUTION))
        lay.addSpacing(18)
        form = QFormLayout()
        self.user, self.pw, self.server = QLineEdit(), QLineEdit(), QLineEdit(api.base)
        self.pw.setEchoMode(QLineEdit.Password)
        self.user.setPlaceholderText("Username"); self.pw.setPlaceholderText("Password")
        form.addRow("Username", self.user); form.addRow("Password", self.pw); form.addRow("Server", self.server)
        lay.addLayout(form)
        self.msg = QLabel(message); self.msg.setObjectName("error"); self.msg.setWordWrap(True); lay.addWidget(self.msg)
        self.btn = button("Sign in", "primary", self.submit); lay.addWidget(self.btn)
        lay.addWidget(button("Continue as guest (search and browse)", slot=self.guest_requested.emit))
        lay.addWidget(button("Create student account", slot=self.register))
        lay.addStretch(1)
        lay.addWidget(muted("Access is logged. Contact the system administrator if you cannot sign in."))
        self.pw.returnPressed.connect(self.submit); self.user.returnPressed.connect(self.pw.setFocus)

    def toggle_theme(self):
        style.toggle_theme(QApplication.instance()); self.theme_btn.setText(style.theme_button_text())

    def register(self):
        from .dialogs.register_dialog import RegisterDialog
        self.api.base = self.server.text().strip().rstrip("/")
        RegisterDialog(self.api, self).exec()

    def submit(self):
        if not self.user.text().strip() or not self.pw.text():
            self.msg.setText("Enter your username and password."); return
        self.api.base = self.server.text().strip().rstrip("/")
        self.btn.setEnabled(False); self.msg.setText("Signing in…")
        u, p = self.user.text().strip(), self.pw.text()
        run_async(lambda: self.api.login(u, p), lambda _: (self.pw.clear(), self.logged_in.emit()), self._fail)

    def _fail(self, e):
        self.btn.setEnabled(True); self.pw.clear(); self.msg.setText(getattr(e, "message", str(e)))
