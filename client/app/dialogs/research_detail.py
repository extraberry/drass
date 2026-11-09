from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog, QFormLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit,
                               QVBoxLayout)
from ..widgets import PUBLICATION_LABELS, button, confirm, h1, h2, hbox, info, muted, show_error, status_text
from ..worker import run_async
from .reader import ReaderDialog

LIB_ROLE = "LIBRARY_STAFF"


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
        for label, val in (("Authors", "; ".join(a["name"] for a in w["authors"])), ("Course", w["program"]),
                           ("Department", w["department"]), ("Year", w["year"]), ("Research Category", w["category"]),
                           ("Adviser", w["adviser"]), ("Dean", w.get("dean")), ("Keywords", ", ".join(w["keywords"])),
                           ("Status", status_text(w["status"])), ("Publication status", w.get("publication_label")),
                           ("Archived", ((w["archived_at"] or "")[:10] + (f" by {w['archived_by']}" if w.get("archived_by") else "")).strip()),
                           ("Access", "Accessible — read in secure reader")):
            v = QLabel(str(val or "—")); v.setWordWrap(True); form.addRow(label + ":", v)
        self.lay.addLayout(form)
        self.lay.addWidget(h2("Abstract"))
        ab = QPlainTextEdit(w["abstract"]); ab.setReadOnly(True); ab.setMaximumHeight(160); self.lay.addWidget(ab)
        can_read = w.get("can_read", True)
        read_btn = button("Read Research", "primary", self.read)
        read_btn.setEnabled(bool(can_read))
        if not can_read:
            read_btn.setToolTip("Reading without an account is turned off, or this record has no manuscript. Please sign in.")
        row = [read_btn]
        if self.api.role == LIB_ROLE and w["status"] == "ARCHIVED":
            row.append(button("Edit Metadata…", slot=self.edit_meta))
            row.append(button("Publication Status…", slot=self.edit_publication))
        self.lay.addLayout(hbox(*row))
        companions = [f for f in w.get("files", []) if f["file_type"] != "MANUSCRIPT"]
        if companions:                                     # only sent by the server to Library Staff and the owning student (FR15)
            self.lay.addWidget(h2("Companion files"))
            for f in companions:
                kind = "Source code" if f["file_type"] == "SOURCE_CODE" else "Video demonstration"
                self.lay.addLayout(hbox(muted(f"{kind}: {f['filename']} ({f['size_bytes'] // 1024} KB)"),
                                        button("Save a copy…", slot=lambda _=None, f=f: self.save_companion(f))))
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
        ReaderDialog(self.api, self.work_id, self.work["title"], self).exec()

    def save_companion(self, f):
        path, _ = QFileDialog.getSaveFileName(self, "Save companion file", f["filename"])
        if path:
            run_async(lambda: self.api.download(f"/repository/{self.work_id}/companions/{f['file_id']}"),
                      lambda data: (open(path, "wb").write(data), info(self, "File saved.")), lambda e: show_error(self, e))

    def edit_publication(self):
        d = PublicationDialog(self.api, self.work, self)
        if d.exec():
            run_async(lambda: self.api.get(f"/repository/{self.work_id}"), self._render, lambda e: show_error(self, e))

    def edit_meta(self):
        d = MetadataDialog(self.api, self.work, self)
        if d.exec():
            run_async(lambda: self.api.get(f"/repository/{self.work_id}"), self._render, lambda e: show_error(self, e))


class PublicationDialog(QDialog):
    """Library Staff set Public / Restricted / Unpublished for archived research (FR10)."""
    def __init__(self, api, work, parent=None):
        super().__init__(parent)
        self.api, self.work = api, work
        self.setWindowTitle("Publication Status"); self.resize(480, 260)
        lay = QVBoxLayout(self); lay.addWidget(h2(work["title"]))
        lay.addWidget(muted("Public: everyone who may read research.  Restricted: signed-in students, faculty and library staff.  "
                            "Unpublished: library staff and the owning student only."))
        self.combo = QComboBox()
        for k, v in PUBLICATION_LABELS.items(): self.combo.addItem(v, k)
        self.combo.setCurrentIndex(max(self.combo.findData(work.get("publication_status")), 0))
        lay.addWidget(self.combo)
        lay.addLayout(hbox(button("Save", "primary", self.go), button("Cancel", slot=self.reject)))

    def go(self):
        v = self.combo.currentData()
        run_async(lambda: self.api.put(f"/repository/{self.work['work_id']}/publication", {"publication_status": v}),
                  lambda _: (info(self, "Publication status updated."), self.accept()), lambda e: show_error(self, e))


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
