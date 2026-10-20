from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)
from .api import ApiError

STATUS_LABELS = {"DRAFT": "Draft", "SUBMITTED": "Submitted", "UNDER_ADVISER_REVIEW": "Under Adviser Review",
                 "UNDER_PANEL_REVIEW": "Under Panel Review", "UNDER_DEAN_REVIEW": "Under Dean Review",
                 "UNDER_HEAD_LIBRARIAN_REVIEW": "Under Head Librarian Review", "RETURNED_FOR_REVISION": "Returned for Revision",
                 "REJECTED": "Rejected", "ARCHIVED": "Archived"}
STATUS_ICON = {"ARCHIVED": "✔", "REJECTED": "✖", "RETURNED_FOR_REVISION": "↩", "DRAFT": "✎"}


def status_text(code: str) -> str:
    """Text + symbol, so status never depends on colour alone."""
    return f"{STATUS_ICON.get(code, '●')} {STATUS_LABELS.get(code, code)}"


def show_error(parent, err) -> None:
    msg = err.message if isinstance(err, ApiError) else f"Unexpected error: {err}"
    QMessageBox.warning(parent, "ResearchVault", msg)


def info(parent, msg: str) -> None:
    QMessageBox.information(parent, "ResearchVault", msg)


def confirm(parent, msg: str) -> bool:
    return QMessageBox.question(parent, "Please confirm", msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes


def h1(text: str) -> QLabel:
    l = QLabel(text); l.setObjectName("h1"); return l


def h2(text: str) -> QLabel:
    l = QLabel(text); l.setObjectName("h2"); return l


def muted(text: str) -> QLabel:
    l = QLabel(text); l.setObjectName("muted"); l.setWordWrap(True); return l


def card() -> QFrame:
    f = QFrame(); f.setObjectName("card"); return f


def button(text: str, kind: str = "", slot=None) -> QPushButton:
    b = QPushButton(text)
    if kind:
        b.setObjectName(kind)
    if slot:
        b.clicked.connect(slot)
    return b


def hbox(*widgets, stretch_end=True) -> QHBoxLayout:
    l = QHBoxLayout()
    for w in widgets:
        l.addWidget(w)
    if stretch_end:
        l.addStretch(1)
    return l


class DataTable(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self._ids: list = []

    def set_data(self, columns, rows, ids=None):
        self.clear()
        self.setColumnCount(len(columns)); self.setHorizontalHeaderLabels(columns); self.setRowCount(len(rows))
        self._ids = list(ids) if ids is not None else list(range(len(rows)))
        for r, row in enumerate(rows):
            for c, v in enumerate(row):
                self.setItem(r, c, QTableWidgetItem("" if v is None else str(v)))
        self.resizeColumnsToContents()
        for c in range(len(columns)):
            if self.columnWidth(c) > 360:
                self.setColumnWidth(c, 360)

    def selected_id(self):
        rows = self.selectionModel().selectedRows()
        return self._ids[rows[0].row()] if rows and rows[0].row() < len(self._ids) else None


class Page(QWidget):
    """Base for navigable pages. Subclasses implement refresh()."""
    title = ""

    def __init__(self, api, main=None):
        super().__init__()
        self.setObjectName("page")
        self.api, self.main = api, main
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(20, 16, 20, 16)

    def refresh(self) -> None:
        pass


class StatCard(QFrame):
    """Dashboard box. Clickable (mouse or Enter/Space) when `clickable`."""
    clicked = Signal()

    def __init__(self, title: str, value, clickable: bool = True):
        super().__init__()
        self.setObjectName("statcard"); self.setMinimumHeight(100); self.clickable = clickable
        lay = QVBoxLayout(self); lay.setContentsMargins(18, 12, 18, 12)
        v = QLabel(str(value)); v.setStyleSheet("font-size: 24pt;")
        t = QLabel(title); t.setObjectName("muted"); t.setWordWrap(True)
        lay.addWidget(v); lay.addWidget(t)
        sh = QGraphicsDropShadowEffect(self); sh.setBlurRadius(18); sh.setOffset(0, 4); sh.setColor(Qt.GlobalColor.gray)
        self.setGraphicsEffect(sh)
        if clickable:
            self.setCursor(Qt.PointingHandCursor); self.setFocusPolicy(Qt.StrongFocus); self.setToolTip("Click to open")

    def mousePressEvent(self, e):
        if self.clickable and e.button() == Qt.LeftButton:
            self.clicked.emit()

    def keyPressEvent(self, e):
        if self.clickable and e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(e)
