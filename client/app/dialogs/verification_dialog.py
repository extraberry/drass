"""Head Librarian: verify the signatories on the approval sheet and give the final archival approval (manuscript FR5-FR7).
Other Library Staff can open the same view read-only."""
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QPlainTextEdit, QVBoxLayout
from ..widgets import DataTable, PUBLICATION_LABELS, button, confirm, h1, h2, hbox, info, muted, show_error, status_text
from ..worker import run_async
from .reader import ReaderDialog


class VerificationDialog(QDialog):
    def __init__(self, api, work_id: int, can_verify: bool, parent=None):
        super().__init__(parent)
        self.api, self.work_id, self.can_verify, self.data = api, work_id, can_verify, None
        self.setWindowTitle("Signatory Verification"); self.resize(880, 820)
        self.lay = QVBoxLayout(self); self.lay.addWidget(muted("Loading…"))
        run_async(lambda: api.get(f"/verifications/{work_id}"), self._render, lambda e: (show_error(self, e), self.reject()))

    def _render(self, d):
        self.data = d; w = d["work"]
        while self.lay.count():
            it = self.lay.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        self.lay.addWidget(h1(w["title"]))
        self.lay.addWidget(muted(f"{w['reference_no']}  ·  {status_text(w['status'])}  ·  Authors: " + "; ".join(a["name"] for a in w["authors"])))
        self.lay.addWidget(muted(f"Course: {w['program']}  ·  Department: {w['department']}  ·  Year: {w['year']}  ·  "
                                 f"Adviser: {w['adviser'] or '—'}  ·  Dean: {w['dean'] or '—'}"))
        self.lay.addWidget(muted("Keywords: " + ", ".join(w["keywords"])))
        ab = QPlainTextEdit(w["abstract"]); ab.setReadOnly(True); ab.setMaximumHeight(110); self.lay.addWidget(ab)
        self.lay.addLayout(hbox(button("Open final PDF", slot=lambda: ReaderDialog(self.api, w["work_id"], w["title"], self).exec())))
        self.lay.addWidget(h2("Previous verifications"))
        t = DataTable(); t.setMaximumHeight(120)
        t.set_data(["Rev", "By", "Result", "Remarks", "When"],
                   [[h["revision_number"], h["verified_by"], "Approved" if h["result"] == "APPROVE" else "Returned", h["remarks"], h["verified_at"][:16]] for h in d["history"]])
        self.lay.addWidget(t)
        pending = w["status"] == "PENDING_VERIFICATION"
        self.boxes = {}
        if not pending:
            self.lay.addWidget(muted("This record is no longer pending verification."))
        elif not self.can_verify:
            self.lay.addWidget(muted("Only the Head Librarian can verify signatories and approve for archiving. You can read the record here."))
        else:
            self.lay.addWidget(h2("Approval sheet checklist"))
            self.lay.addWidget(muted("Tick each item that is confirmed on the signed approval sheet inside the final PDF. All items must be ticked to approve."))
            for it in d["checklist_items"]:
                cb = QCheckBox(it["label"]); self.boxes[it["key"]] = cb; self.lay.addWidget(cb)
            self.pub = QComboBox()
            for k, v in PUBLICATION_LABELS.items(): self.pub.addItem(v, k)
            self.lay.addWidget(muted("Publication status when archived:")); self.lay.addWidget(self.pub)
            self.remarks = QPlainTextEdit(); self.remarks.setFixedHeight(80)
            self.remarks.setPlaceholderText("Remarks (required when returning to the student: say what is missing or incomplete)")
            self.lay.addWidget(self.remarks)
            self.lay.addLayout(hbox(button("Approve and archive", "primary", lambda: self.decide("APPROVE")),
                                    button("Return to student", "danger", lambda: self.decide("RETURN")), button("Close", slot=self.reject)))
            return
        self.lay.addLayout(hbox(button("Close", slot=self.reject)))

    def decide(self, decision: str):
        checklist = {k: cb.isChecked() for k, cb in self.boxes.items()}
        remarks = self.remarks.toPlainText().strip()
        if decision == "APPROVE" and not all(checklist.values()):
            return info(self, "Every item on the checklist must be confirmed before the research can be approved. Return it to the student otherwise.")
        if decision == "RETURN" and len(remarks) < 3:
            return info(self, "Enter remarks so the student knows what to fix.")
        msg = ("Approve and ARCHIVE this research? It becomes searchable according to its publication status." if decision == "APPROVE"
               else "Return this submission to the student with your remarks?")
        if not confirm(self, msg): return
        body = {"decision": decision, **checklist, "remarks": remarks, "expected_version": self.data["work"]["version"]}
        if decision == "APPROVE": body["publication_status"] = self.pub.currentData()
        run_async(lambda: self.api.post(f"/verifications/{self.work_id}", body),
                  lambda r: (info(self, f"Recorded. New status: {status_text(r['status'])}"), self.accept()), lambda e: show_error(self, e))
