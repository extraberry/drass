from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QLineEdit, QVBoxLayout
from ..widgets import button, hbox, info, muted, h1
from ..worker import run_async


class RegisterDialog(QDialog):
    """Student-only sign-up. The student ID must be on the registrar roster; one account per student."""
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Create student account"); self.resize(480, 460)
        lay = QVBoxLayout(self)
        lay.addWidget(h1("Create student account"))
        lay.addWidget(muted("For enrolled students only. Your student ID and last name are checked against the registrar list. Each student can have one account."))
        form = QFormLayout()
        self.sn, self.last, self.user, self.email = QLineEdit(), QLineEdit(), QLineEdit(), QLineEdit()
        self.pw, self.pw2 = QLineEdit(), QLineEdit()
        for e in (self.pw, self.pw2): e.setEchoMode(QLineEdit.Password)
        self.sn.setPlaceholderText("e.g. 2023-0101")
        for lbl, w in (("Student ID *", self.sn), ("Last name *", self.last), ("Username *", self.user), ("Email *", self.email),
                       ("Password *", self.pw), ("Confirm password *", self.pw2)):
            form.addRow(lbl, w)
        lay.addLayout(form)
        self.msg = QLabel(""); self.msg.setObjectName("error"); self.msg.setWordWrap(True); lay.addWidget(self.msg)
        self.btn = button("Create account", "primary", self.submit)
        lay.addLayout(hbox(self.btn, button("Cancel", slot=self.reject)))

    def submit(self):
        if self.pw.text() != self.pw2.text():
            self.msg.setText("The two passwords do not match."); return
        body = {"student_number": self.sn.text().strip(), "last_name": self.last.text().strip(), "username": self.user.text().strip(),
                "email": self.email.text().strip(), "password": self.pw.text()}
        self.btn.setEnabled(False); self.msg.setText("Creating account…")
        def ok(r):
            info(self, "Account created. You can now sign in with your username and password."); self.accept()
        def fail(e):
            self.btn.setEnabled(True)
            f = getattr(e, "fields", None) or {}
            self.msg.setText(e.message if not f else e.message + "\n" + "; ".join(f"{k}: {v}" for k, v in f.items()))
        run_async(lambda: self.api.register_student(body), ok, fail)
