from PySide6.QtWidgets import (QDialog, QLabel, QListWidget, QListWidgetItem, QPlainTextEdit, QVBoxLayout)
from PySide6.QtCore import Qt
from ..widgets import DataTable, button, confirm, h1, h2, hbox, info, muted, show_error, status_text
from ..worker import run_async
from .reader import ReaderDialog


class ReviewDialog(QDialog):
    def __init__(self, api, assignment_id: int, parent=None):
        super().__init__(parent)
        self.api, self.aid, self.data = api, assignment_id, None
        self.setWindowTitle("Review"); self.resize(860, 780)
        self.lay = QVBoxLayout(self); self.lay.addWidget(muted("Loading…"))
        run_async(lambda: api.get(f"/reviews/{assignment_id}"), self._render, lambda e: (show_error(self, e), self.reject()))

    def _render(self, d):
        self.data = d; w = d["work"]
        while self.lay.count():
            it = self.lay.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        self.lay.addWidget(h1(w["title"]))
        self.lay.addWidget(muted(f"{w['reference_no']}  ·  Stage: {d['stage'].replace('_', ' ').title()}  ·  {status_text(w['status'])}  ·  Revision history below"))
        self.lay.addWidget(muted("Authors: " + "; ".join(a["name"] for a in w["authors"]) + f"   |   {w['program']}  ·  {w['year']}  ·  {w['category']}"))
        self.lay.addWidget(muted("Keywords: " + ", ".join(w["keywords"])))
        ab = QPlainTextEdit(w["abstract"]); ab.setReadOnly(True); ab.setMaximumHeight(130); self.lay.addWidget(ab)
        top = [button("Read Manuscript", slot=lambda: ReaderDialog(self.api, w["work_id"], w["title"], self).exec())]
        if d["stage"] == "ADVISER" and self.api.role in ("ADVISER", "ADMIN"):
            top.append(button("Assign Panel…", slot=self.assign_panel))
        self.lay.addLayout(hbox(*top))
        self.lay.addWidget(h2("Review history"))
        t = DataTable(); t.setMaximumHeight(150)
        t.set_data(["Stage", "Rev", "Reviewer", "Decision", "Comments", "When"],
                   [[h["stage"], h["revision_number"], h["reviewer"], h["decision"], h["comments"], h["decided_at"][:16]] for h in d["history"]])
        self.lay.addWidget(t)
        self.lay.addWidget(h2("Your decision"))
        self.comments = QPlainTextEdit(); self.comments.setPlaceholderText("Comments (required to return; reason required to reject)"); self.comments.setFixedHeight(90)
        self.lay.addWidget(self.comments)
        pending = d["assignment_status"] == "PENDING"
        row = [button("Approve", "primary", lambda: self.decide("approve")), button("Return for Revision", slot=lambda: self.decide("return")),
               button("Reject", "danger", lambda: self.decide("reject")), button("Close", slot=self.reject)]
        for b in row[:3]: b.setEnabled(pending)
        self.lay.addLayout(hbox(*row))

    def decide(self, action: str):
        label = {"approve": "approve", "return": "return for revision", "reject": "REJECT (this cannot be undone)"}[action]
        if not confirm(self, f"Are you sure you want to {label} this research?"):
            return
        body = {"comments": self.comments.toPlainText().strip(), "expected_version": self.data["work"]["version"]}
        run_async(lambda: self.api.post(f"/reviews/{self.aid}/{action}", body),
                  lambda r: (info(self, f"Recorded. New status: {r['status'].replace('_', ' ').title()}"), self.accept()),
                  lambda e: show_error(self, e))

    def assign_panel(self):
        d = QDialog(self); d.setWindowTitle("Assign panel"); lay = QVBoxLayout(d)
        lst = QListWidget()
        run_async(lambda: self.api.get("/lookups")["panelists"], lambda ps: [self._add(lst, p) for p in ps], lambda e: show_error(self, e))
        lay.addWidget(muted("Select panelists. ALL assigned panelists must approve.")); lay.addWidget(lst)
        def save():
            ids = [lst.item(i).data(256) for i in range(lst.count()) if lst.item(i).checkState() == Qt.Checked]
            run_async(lambda: self.api.post(f"/submissions/{self.data['work']['work_id']}/panel", {"panelist_ids": ids}),
                      lambda _: (info(self, "Panel saved."), d.accept()), lambda e: show_error(self, e))
        lay.addLayout(hbox(button("Save", "primary", save), button("Cancel", slot=d.reject)))
        d.exec()

    @staticmethod
    def _add(lst, p):
        it = QListWidgetItem(p["name"]); it.setData(256, p["id"]); it.setFlags(it.flags() | Qt.ItemIsUserCheckable); it.setCheckState(Qt.Unchecked); lst.addItem(it)
