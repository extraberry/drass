from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QFormLayout, QLineEdit, QVBoxLayout, QLabel
from ..widgets import button, hbox, show_error
from ..worker import run_async


class UserDialog(QDialog):
    def __init__(self, api, user=None, parent=None):
        super().__init__(parent)
        self.api, self.user = api, user
        self.setWindowTitle("Edit user" if user else "New user"); self.resize(480, 420)
        form = QFormLayout()
        self.username, self.password = QLineEdit(), QLineEdit(); self.password.setEchoMode(QLineEdit.Password)
        self.full_name, self.email, self.sn = QLineEdit(), QLineEdit(), QLineEdit()
        self.role, self.dept = QComboBox(), QComboBox()
        self.head = QCheckBox("Head Librarian (verifies signatories and gives final approval)")
        form.addRow("Username *", self.username)
        if not user: form.addRow("Temporary password *", self.password)
        form.addRow("Full name *", self.full_name); form.addRow("Email *", self.email)
        form.addRow("Role *", self.role); form.addRow("", self.head); form.addRow("Student number", self.sn); form.addRow("Department", self.dept)
        self.error = QLabel(); self.error.setObjectName("error"); self.error.setWordWrap(True)
        lay = QVBoxLayout(self); lay.addLayout(form); lay.addWidget(self.error)
        lay.addLayout(hbox(button("Save", "primary", self.save), button("Cancel", slot=self.reject)))
        self.role.currentTextChanged.connect(self._role_changed)
        run_async(lambda: self.api.get("/lookups"), self._loaded, lambda e: show_error(self, e))

    def _role_changed(self, role):
        self.head.setVisible(role == "LIBRARY_STAFF")
        if role != "LIBRARY_STAFF": self.head.setChecked(False)

    def _loaded(self, lk):
        self.role.addItems(lk["roles"]); self.dept.addItem("(none)", None)
        for d in lk["departments"]: self.dept.addItem(d["name"], d["id"])
        if self.user:
            u = self.user
            self.username.setText(u["username"]); self.full_name.setText(u["full_name"])
            self.email.setText(u["email"]); self.sn.setText(u["student_number"] or "")
            self.role.setCurrentText(u["role"]); self.head.setChecked(bool(u.get("is_head_librarian"))); self.dept.setCurrentIndex(max(self.dept.findData(u["department_id"]), 0))

    def save(self):
        body = {"username": self.username.text().strip(), "full_name": self.full_name.text().strip(), "email": self.email.text().strip(), "role": self.role.currentText(),
                "student_number": self.sn.text().strip() or None, "department_id": self.dept.currentData(),
                "is_head_librarian": self.head.isChecked() and self.role.currentText() == "LIBRARY_STAFF"}
        def call():
            if self.user:
                if body["username"] == self.user["username"]: body.pop("username")
                return self.api.patch(f"/users/{self.user['user_id']}", body)
            return self.api.post("/users", {**body, "username": self.username.text().strip(), "password": self.password.text()})
        def fail(e):
            self.error.setText("; ".join(f"{k}: {v}" for k, v in (getattr(e, "fields", None) or {}).items()) or e.message)
        run_async(call, lambda _: self.accept(), fail)
