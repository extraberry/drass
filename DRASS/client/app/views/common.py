from PySide6.QtWidgets import QComboBox, QGridLayout, QLabel, QLineEdit, QWidget
from ..worker import run_async


class FilterBar(QWidget):
    """Program / department / year / category / adviser / author / keyword filters shared by repository + search."""
    def __init__(self, api, on_change=None, with_status=False):
        super().__init__()
        self.api, self.on_change = api, on_change
        g = QGridLayout(self); g.setContentsMargins(0, 0, 0, 0)
        self.program, self.department, self.category, self.adviser = QComboBox(), QComboBox(), QComboBox(), QComboBox()
        self.year, self.author, self.keyword = QLineEdit(), QLineEdit(), QLineEdit()
        self.year.setPlaceholderText("Year"); self.author.setPlaceholderText("Author"); self.keyword.setPlaceholderText("Keyword")
        self.status = QComboBox() if with_status else None
        self._want_status = None
        widgets = [("Program", self.program), ("Department", self.department), ("Category", self.category), ("Adviser", self.adviser),
                   ("Year", self.year), ("Author", self.author), ("Keyword", self.keyword)]
        if self.status is not None:
            widgets.append(("Status", self.status))
        for i, (lbl, w) in enumerate(widgets):
            g.addWidget(QLabel(lbl), 0, i); g.addWidget(w, 1, i)
        for c in (self.program, self.department, self.category, self.adviser):
            c.addItem("All", None)
        if self.status is not None:
            self.status.addItem("Archived (default)", None)
        run_async(lambda: api.get("/lookups"), self._fill, None)

    def _fill(self, lk):
        for combo, key in ((self.program, "programs"), (self.department, "departments"), (self.category, "categories"), (self.adviser, "advisers")):
            for it in lk[key]:
                combo.addItem(it["name"], it["id"])
        if self.status is not None:
            for s in lk["statuses"]:
                self.status.addItem(s["name"], s["id"])
            if self._want_status:
                self.set_status(self._want_status)

    def values(self) -> dict:
        v = {"program_id": self.program.currentData(), "department_id": self.department.currentData(),
             "category_id": self.category.currentData(), "adviser_id": self.adviser.currentData(),
             "author": self.author.text().strip() or None, "keyword": self.keyword.text().strip() or None}
        y = self.year.text().strip()
        v["year"] = int(y) if y.isdigit() else None
        if self.status is not None:
            v["status"] = self.status.currentData()
        return v

    def set_status(self, value):
        """Select a status (used by dashboard shortcuts). Remembered if the lookup list has not loaded yet."""
        if self.status is None: return
        self._want_status = value
        i = self.status.findData(value) if value else 0
        if i >= 0:
            self.status.setCurrentIndex(i)
            if value: self._want_status = None

    def clear(self):
        self._want_status = None
        if self.status is not None: self.status.setCurrentIndex(0)
        for c in (self.program, self.department, self.category, self.adviser):
            c.setCurrentIndex(0)
        for e in (self.year, self.author, self.keyword):
            e.clear()
