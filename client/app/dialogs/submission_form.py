from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog, QFormLayout, QGridLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QProgressDialog, QScrollArea, QSpinBox, QVBoxLayout, QWidget)
from ..widgets import button, confirm, h1, hbox, info, muted, show_error
from ..worker import run_async

FILE_SLOTS = (("MANUSCRIPT", "Manuscript PDF *", "PDF files (*.pdf)"),
              ("SOURCE_CODE", "Source code archive", "Archives (*.zip *.7z *.rar)"),
              ("VIDEO", "Video demonstration", "Video (*.mp4 *.mov *.webm)"))


class SubmissionForm(QDialog):
    """New submission, draft editing, and revision (when the work was returned)."""

    def __init__(self, api, work_id=None, parent=None):
        super().__init__(parent)
        self.api, self.work_id, self.work, self.lk = api, work_id, None, None
        self.setWindowTitle("Submission"); self.resize(760, 780)
        outer = QVBoxLayout(self)
        outer.addWidget(h1("Research Submission"))
        outer.addWidget(muted("Fields marked * are required. Your entries are kept if validation fails."))
        scroll = QScrollArea(); scroll.setWidgetResizable(True); body = QWidget(); scroll.setWidget(body)
        self.form = QFormLayout(body); outer.addWidget(scroll, 1)
        self.err: dict[str, QLabel] = {}
        self.title = QLineEdit(); self.year = QSpinBox(); self.year.setRange(1990, 2100); self.year.setValue(QDate.currentDate().year())
        self.program, self.category, self.adviser = QComboBox(), QComboBox(), QComboBox()
        self.authors = QPlainTextEdit(); self.authors.setPlaceholderText("One author per line:  Full Name, Student Number"); self.authors.setFixedHeight(80)
        self.keywords = QLineEdit(); self.keywords.setPlaceholderText("comma, separated, keywords")
        self.abstract = QPlainTextEdit(); self.abstract.setMinimumHeight(150)
        self.notes = QPlainTextEdit(); self.notes.setFixedHeight(70); self.notes.setPlaceholderText("What changed in this revision?")
        self._row("Title *", self.title, "title"); self._row("Year *", self.year, "year")
        self._row("Program *", self.program, "program_id"); self._row("Research category *", self.category, "category_id")
        self._row("Adviser *", self.adviser, "adviser_id"); self._row("Author(s) *", self.authors, "authors")
        self._row("Keywords *", self.keywords, "keywords"); self._row("Abstract *", self.abstract, "abstract")
        self.file_labels = {}
        for ftype, label, flt in FILE_SLOTS:
            lab = QLabel("No file uploaded"); self.file_labels[ftype] = lab
            self.form.addRow(label, self._file_row(lab, ftype, flt))
        self.err["manuscript"] = QLabel(); self.err["manuscript"].setObjectName("error"); self.form.addRow("", self.err["manuscript"])
        self.notes_row_added = False
        self.btns = hbox(button("Save Draft", slot=self.save_draft), button("Submit for Review", "primary", self.submit), button("Close", slot=self.reject))
        outer.addLayout(self.btns)
        self.setEnabled(False)
        run_async(self._load, self._loaded, lambda e: (show_error(self, e), self.reject()))

    def _row(self, label, widget, key):
        box = QVBoxLayout(); box.addWidget(widget)
        e = QLabel(); e.setObjectName("error"); e.setWordWrap(True); box.addWidget(e); self.err[key] = e
        w = QWidget(); w.setLayout(box); box.setContentsMargins(0, 0, 0, 0); self.form.addRow(label, w)

    def _file_row(self, lab, ftype, flt):
        w = QWidget(); l = QGridLayout(w); l.setContentsMargins(0, 0, 0, 0)
        l.addWidget(lab, 0, 0); l.addWidget(button("Choose & upload…", slot=lambda: self.pick(ftype, flt)), 0, 1)
        return w

    def _load(self):
        lk = self.api.get("/lookups")
        work = self.api.get(f"/submissions/{self.work_id}") if self.work_id else None
        return lk, work

    def _loaded(self, res):
        self.lk, self.work = res
        for p in self.lk["programs"]: self.program.addItem(p["name"], p)
        for c in self.lk["categories"]: self.category.addItem(c["name"], c["id"])
        for a in self.lk["advisers"]: self.adviser.addItem(a["name"], a["id"])
        self.setEnabled(True)
        if self.work:
            w = self.work
            self.title.setText(w["title"]); self.year.setValue(w["year"] or self.year.value())
            self.abstract.setPlainText(w["abstract"]); self.keywords.setText(", ".join(w["keywords"]))
            self.authors.setPlainText("\n".join(f"{a['name']}, {a['student_number'] or ''}".rstrip(", ") for a in w["authors"]))
            for combo, key in ((self.category, "category_id"), (self.adviser, "adviser_id")):
                i = combo.findData(w[key]); combo.setCurrentIndex(max(i, 0))
            for i in range(self.program.count()):
                if self.program.itemData(i)["id"] == w["program_id"]: self.program.setCurrentIndex(i)
            self._file_status(w["files"])
            if w["status"] == "RETURNED_FOR_REVISION":
                self.form.addRow("Change notes *", self.notes)
                self.err["change_notes"] = QLabel(); self.err["change_notes"].setObjectName("error"); self.form.addRow("", self.err["change_notes"])
                self.btns.itemAt(1).widget().setText("Resubmit")
                last = (w.get("review_history") or [{}])[-1]
                if last.get("comments"):
                    info(self, f"Reviewer comments ({last.get('stage')}):\n\n{last['comments']}")

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
                "category_id": self.category.currentData(), "adviser_id": self.adviser.currentData(),
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
        if path:
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
        resub = self.work and self.work["status"] == "RETURNED_FOR_REVISION"
        if not confirm(self, "Resubmit for adviser review?" if resub else "Submit for review? You can no longer edit it while it is under review."):
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
