from PySide6.QtWidgets import (QDialog, QFormLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit,
                               QVBoxLayout)
from ..widgets import button, h1, h2, hbox, info, muted, show_error, status_text
from ..worker import run_async
from .reader import ReaderDialog

LIB_ROLES = {"LIBRARY_STAFF", "HEAD_LIBRARIAN", "ADMIN"}


class ResearchDetailDialog(QDialog):
    def __init__(self, api, work_id: int, parent=None):
        super().__init__(parent)
        self.api, self.work_id, self.work = api, work_id, None
        self.setWindowTitle("Research Detail"); self.resize(820, 720)
        self.lay = QVBoxLayout(self)
        self.lay.addWidget(muted("Loading…"))
        run_async(lambda: api.get(f"/repository/{work_id}"), self._render, lambda e: (show_error(self, e), self.reject()))

    def _clear(self):
        while self.lay.count():
            w = self.lay.takeAt(0)
            if w.widget(): w.widget().deleteLater()
            elif w.layout():
                while w.layout().count():
                    ww = w.layout().takeAt(0)
                    if ww.widget(): ww.widget().deleteLater()

    def _render(self, w):
        self.work = w; self._clear()
        self.lay.addWidget(h1(w["title"]))
        form = QFormLayout()
        for label, val in (("Authors", "; ".join(a["name"] for a in w["authors"])), ("Program", w["program"]),
                           ("Department", w["department"]), ("Year", w["year"]), ("Research Category", w["category"]),
                           ("Adviser", w["adviser"]), ("Keywords", ", ".join(w["keywords"])),
                           ("Status", status_text(w["status"])), ("Archived", (w["archived_at"] or "")[:10]),
                           ("Access", "Accessible — read in secure reader")):
            v = QLabel(str(val or "—")); v.setWordWrap(True); form.addRow(label + ":", v)
        self.lay.addLayout(form)
        self.lay.addWidget(h2("Abstract"))
        ab = QPlainTextEdit(w["abstract"]); ab.setReadOnly(True); ab.setMaximumHeight(160); self.lay.addWidget(ab)
        row = [button("Read Research" if self.api.token else "Sign in to read", "primary", self.read)]
        if self.api.role in LIB_ROLES and w["status"] == "ARCHIVED":
            row.append(button("Edit Metadata…", slot=self.edit_meta))
        self.lay.addLayout(hbox(*row))
        self.lay.addWidget(h2("Related Research"))
        self.rel = QListWidget(); self.rel.setMaximumHeight(150); self.lay.addWidget(self.rel)
        self.rel_msg = muted("Loading related research…"); self.lay.addWidget(self.rel_msg)
        self.rel.itemDoubleClicked.connect(lambda it: ResearchDetailDialog(self.api, it.data(256), self).exec())
        run_async(lambda: self.api.get(f"/recommendations/{self.work_id}"), self._recs, lambda e: self.rel_msg.setText("Related research is unavailable."))

    def _recs(self, r):
        self.rel.clear()
        for i, it in enumerate(r["items"], 1):
            li = QListWidgetItem(f"{i}. {it['title']} ({it['year']}) — {it['score_label']}"); li.setData(256, it["work_id"]); self.rel.addItem(li)
        self.rel_msg.setText(r["message"] or "Double-click a title to open it.")

    def read(self):
        if not self.api.token:
            return info(self, "Please sign in to read the manuscript. Guests can browse and search the repository only.")
        ReaderDialog(self.api, self.work_id, self.work["title"], self).exec()

    def edit_meta(self):
        d = MetadataDialog(self.api, self.work, self)
        if d.exec():
            run_async(lambda: self.api.get(f"/repository/{self.work_id}"), self._render, lambda e: show_error(self, e))


class MetadataDialog(QDialog):
    def __init__(self, api, work, parent=None):
        super().__init__(parent)
        self.api, self.work = api, work
        self.setWindowTitle("Edit Metadata"); self.resize(620, 480)
        lay = QVBoxLayout(self)
        self.title = QLineEdit(work["title"]); self.kw = QLineEdit(", ".join(work["keywords"])); self.ab = QPlainTextEdit(work["abstract"])
        for lbl, w in (("Title *", self.title), ("Keywords (comma separated) *", self.kw), ("Abstract *", self.ab)):
            lay.addWidget(muted(lbl)); lay.addWidget(w)
        lay.addWidget(muted("Changing these fields marks the semantic index stale and re-indexes the record."))
        lay.addLayout(hbox(button("Save", "primary", self.save), button("Cancel", slot=self.reject)))

    def save(self):
        body = {"title": self.title.text().strip(), "abstract": self.ab.toPlainText().strip(),
                "keywords": [k.strip() for k in self.kw.text().split(",") if k.strip()]}
        run_async(lambda: self.api.patch(f"/repository/{self.work['work_id']}", body),
                  lambda _: (info(self, "Metadata saved and re-indexed."), self.accept()), lambda e: show_error(self, e))
