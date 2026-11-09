import os
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog, QFormLayout, QGridLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QProgressDialog, QScrollArea, QSpinBox, QVBoxLayout, QWidget)
from ..widgets import button, confirm, h1, hbox, info, muted, show_error
from ..worker import run_async

FILE_SLOTS = (("MANUSCRIPT", "Final PDF (manuscript + signed approval sheet) *", "PDF files (*.pdf)"),
              ("SOURCE_CODE", "Source code archive", "Archives (*.zip *.7z *.rar)"),
              ("VIDEO", "Video demonstration", "Video (*.mp4 *.mov *.webm)"))


DEFAULT_LIMITS = [{"file_type": "MANUSCRIPT", "label": "Research document (PDF)", "max_mb": 100, "extensions": [".pdf"]},
                  {"file_type": "SOURCE_CODE", "label": "Source code (compressed archive)", "max_mb": 500, "extensions": [".7z", ".rar", ".zip"]},
                  {"file_type": "VIDEO", "label": "Video", "max_mb": 500, "extensions": [".mov", ".mp4", ".webm"]}]


class SubmissionForm(QDialog):
    """New submission, draft editing, and revision (when the work was returned)."""

    def __init__(self, api, work_id=None, parent=None):
        super().__init__(parent)
        self.api, self.work_id, self.work, self.lk = api, work_id, None, None
        self.setWindowTitle("Submission"); self.resize(760, 780)
        outer = QVBoxLayout(self)
        outer.addWidget(h1("Research Submission"))
        outer.addWidget(muted("Fields marked * are required. Your entries are kept if validation fails."))
        self.limits = {x["file_type"]: x for x in DEFAULT_LIMITS}
        self.limit_hint = muted(""); self.limit_hint.setWordWrap(True); outer.addWidget(self.limit_hint)
        self.limit_labels = {}
        scroll = QScrollArea(); scroll.setWidgetResizable(True); body = QWidget(); scroll.setWidget(body)
        self.form = QFormLayout(body); outer.addWidget(scroll, 1)
        self.err: dict[str, QLabel] = {}
        self.title = QLineEdit(); self.year = QSpinBox(); self.year.setRange(1990, 2100); self.year.setValue(QDate.currentDate().year())
        self.program, self.category, self.adviser, self.dean = QComboBox(), QComboBox(), QComboBox(), QComboBox()
        self.authors = QPlainTextEdit(); self.authors.setPlaceholderText("Sofia Ramos, 2022-0001\nMiguel Garcia, 2022-0002\nCarla Reyes, 2023-0101"); self.authors.setFixedHeight(90)
        self.keywords = QLineEdit(); self.keywords.setPlaceholderText("semantic search, digital archive, thesis repository, PDF viewer")
        self.abstract = QPlainTextEdit(); self.abstract.setMinimumHeight(150)
        self.notes = QPlainTextEdit(); self.notes.setFixedHeight(70); self.notes.setPlaceholderText("What changed in this revision?")
        self._row("Title *", self.title, "title"); self._row("Year *", self.year, "year")
        self._row("Course *", self.program, "program_id"); self._row("Research category", self.category, "category_id")
        self._row("Adviser *", self.adviser, "adviser_id"); self._row("Dean *", self.dean, "dean_id"); self._row("Author(s) *", self.authors, "authors", "One author per line: Full Name, Student Number (separated by a comma). Example:\nSofia Ramos, 2022-0001")
        self._row("Keywords *", self.keywords, "keywords", "Separate keywords with commas. Example: semantic search, digital archive, thesis repository"); self._row("Abstract *", self.abstract, "abstract")
        self.file_labels = {}
        for ftype, label, flt in FILE_SLOTS:
            lab = QLabel("No file uploaded"); self.file_labels[ftype] = lab
            self.form.addRow(label, self._file_row(lab, ftype, flt))
        self.err["manuscript"] = QLabel(); self.err["manuscript"].setObjectName("error"); self.form.addRow("", self.err["manuscript"])
        self.notes_row_added = False
        self._apply_limits()
        self.btns = hbox(button("Save Draft", slot=self.save_draft), button("Submit for Verification", "primary", self.submit), button("Close", slot=self.reject))
        outer.addLayout(self.btns)
        self.setEnabled(False)
        run_async(self._load, self._loaded, lambda e: (show_error(self, e), self.reject()))

    def _row(self, label, widget, key, hint=None):
        box = QVBoxLayout(); box.addWidget(widget)
        if hint:
            h = muted(hint); h.setWordWrap(True); box.addWidget(h)
        e = QLabel(); e.setObjectName("error"); e.setWordWrap(True); box.addWidget(e); self.err[key] = e
        w = QWidget(); w.setLayout(box); box.setContentsMargins(0, 0, 0, 0); self.form.addRow(label, w)

    def _file_row(self, lab, ftype, flt):
        w = QWidget(); l = QGridLayout(w); l.setContentsMargins(0, 0, 0, 0)
        l.addWidget(lab, 0, 0); l.addWidget(button("Choose & upload…", slot=lambda: self.pick(ftype, flt)), 0, 1)
        hint = muted(""); hint.setWordWrap(True); self.limit_labels[ftype] = hint
        l.addWidget(hint, 1, 0, 1, 2)
        return w

    def _limit_text(self, ftype) -> str:
        x = self.limits.get(ftype)
        return f"Maximum file size: {x['max_mb']} MB  ·  accepted formats: {', '.join(x['extensions'])}" if x else ""

    def _apply_limits(self):
        for ftype, lab in self.limit_labels.items():
            lab.setText(self._limit_text(ftype))
        parts = [f"{x['label']}: up to {x['max_mb']} MB" for x in self.limits.values()]
        self.limit_hint.setText("File size limits  —  " + "   ·   ".join(parts) + ".  Files larger than the limit are not accepted; "
                                "compress source code and video first, or ask the administrator.")

    def _load(self):
        lk = self.api.get("/lookups")
        work = self.api.get(f"/submissions/{self.work_id}") if self.work_id else None
        try:
            limits = self.api.get("/public/upload-limits")["limits"]
        except Exception:   # noqa: BLE001 - older server: keep the default limits shown on the form
            limits = None
        return lk, work, limits

    def _loaded(self, res):
        self.lk, self.work, limits = res
        if limits:
            self.limits = {x["file_type"]: x for x in limits}
            self._apply_limits()
        for p in self.lk["programs"]: self.program.addItem(p["name"], p)
        self.category.addItem("(none)", None)
        for c in self.lk["categories"]: self.category.addItem(c["name"], c["id"])
        for a in self.lk["faculty"]:
            self.adviser.addItem(a["name"], a["id"]); self.dean.addItem(a["name"], a["id"])
        self.setEnabled(True)
        if self.work:
            w = self.work
            self.title.setText(w["title"]); self.year.setValue(w["year"] or self.year.value())
            self.abstract.setPlainText(w["abstract"]); self.keywords.setText(", ".join(w["keywords"]))
            self.authors.setPlainText("\n".join(f"{a['name']}, {a['student_number'] or ''}".rstrip(", ") for a in w["authors"]))
            for combo, key in ((self.category, "category_id"), (self.adviser, "adviser_id"), (self.dean, "dean_id")):
                i = combo.findData(w[key]); combo.setCurrentIndex(max(i, 0))
            for i in range(self.program.count()):
                if self.program.itemData(i)["id"] == w["program_id"]: self.program.setCurrentIndex(i)
            self._file_status(w["files"])
            if w["status"] == "RETURNED":
                self.form.addRow("Change notes *", self.notes)
                self.err["change_notes"] = QLabel(); self.err["change_notes"].setObjectName("error"); self.form.addRow("", self.err["change_notes"])
                self.btns.itemAt(1).widget().setText("Resubmit")
                last = (w.get("verification_history") or [{}])[-1]
                if last.get("remarks"):
                    info(self, f"Remarks from the Head Librarian:\n\n{last['remarks']}")

    def _file_status(self, files):
        for ftype, lab in self.file_labels.items():
            f = [x for x in files if x["file_type"] == ftype]
            lab.setText(f"{f[-1]['filename']} ({f[-1]['size_bytes'] // 1024} KB)" if f else "No file uploaded")

    def payload(self) -> dict:
        authors = []
        for line in self.authors.toPlainText().splitlines():
            if line.strip():
                name, _, sn = line.partition(",")
                authors.append({"name": name.strip(), "student_number": sn.strip() or None})
        prog = self.program.currentData() or {}
        return {"title": self.title.text().strip(), "abstract": self.abstract.toPlainText().strip(), "year": self.year.value(),
                "program_id": prog.get("id"), "department_id": prog.get("department_id"),
                "category_id": self.category.currentData(), "adviser_id": self.adviser.currentData(), "dean_id": self.dean.currentData(),
                "authors": authors, "keywords": [k.strip() for k in self.keywords.text().split(",") if k.strip()]}

    def show_errors(self, fields: dict):
        for k, lab in self.err.items():
            lab.setText(fields.get(k, ""))

    def _fail(self, e):
        self.show_errors(getattr(e, "fields", {}) or {})
        show_error(self, e)

    def _save(self, then):
        body = self.payload()
        def call():
            if self.work_id is None:
                return self.api.post("/submissions", body)
            return self.api.patch(f"/submissions/{self.work_id}", body)
        def ok(w):
            self.work_id, self.work = w["work_id"], w
            self.show_errors({}); then()
        run_async(call, ok, self._fail)

    def save_draft(self):
        self._save(lambda: info(self, "Draft saved."))

    def pick(self, ftype, flt):
        path, _ = QFileDialog.getOpenFileName(self, "Choose file", "", flt)
        if not path:
            return
        x = self.limits.get(ftype)
        size_mb = os.path.getsize(path) / (1024 * 1024)
        if x and size_mb > x["max_mb"]:
            info(self, f"This file is {size_mb:.1f} MB, which is larger than the {x['max_mb']} MB limit for "
                       f"{x['label'].lower()}.\n\nChoose a smaller file (compress it first) or ask the administrator to raise the limit.")
            return
        self._save(lambda: self._upload(ftype, path))

    def _upload(self, ftype, path):
        dlg = QProgressDialog("Uploading…", None, 0, 100, self); dlg.setWindowTitle("Upload"); dlg.setMinimumDuration(0); dlg.setValue(0)
        def done(_):
            dlg.close()
            run_async(lambda: self.api.get(f"/submissions/{self.work_id}"), lambda w: self._file_status(w["files"]), None)
        def fail(e):
            dlg.close(); self._fail(e)
        run_async(lambda report: self.api.upload(self.work_id, ftype, path, report), done, fail, on_progress=dlg.setValue)

    def submit(self):
        resub = self.work and self.work["status"] == "RETURNED"
        if not confirm(self, "Resubmit for verification?" if resub else "Submit for verification by the Head Librarian? You can no longer edit it while it is pending."):
            return
        def final():
            if resub:
                run_async(lambda: self.api.post(f"/submissions/{self.work_id}/resubmit", {"change_notes": self.notes.toPlainText().strip()}),
                          self._done, self._fail)
            else:
                run_async(lambda: self.api.post(f"/submissions/{self.work_id}/submit"), self._done, self._fail)
        self._save(final)

    def _done(self, w):
        info(self, f"Submission received.\nReference number: {w['reference_no']}\nStatus: {w['status_label']}")
        self.accept()
