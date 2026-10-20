"""Secure reader: shows server-rendered page images. No download, print or save (deterrent, not DRM)."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QPixmap
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSpinBox, QVBoxLayout)
from ..widgets import button, show_error
from ..worker import run_async


class ReaderDialog(QDialog):
    def __init__(self, api, work_id: int, title: str, parent=None):
        super().__init__(parent)
        self.api, self.work_id, self.page, self.pages, self.scale, self.fit = api, work_id, 1, 1, 1.4, None
        self.meta = {"page_width": 612.0, "page_height": 792.0}
        self._gen = 0
        self.setWindowTitle(f"Secure Reader — {title}")
        self.resize(980, 760)
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.first, self.prev = button("⏮ First", slot=lambda: self.go(1)), button("◀ Prev", slot=lambda: self.go(self.page - 1))
        self.next, self.last = button("Next ▶", slot=lambda: self.go(self.page + 1)), button("Last ⏭", slot=lambda: self.go(self.pages))
        self.spin = QSpinBox(); self.spin.setMinimum(1); self.spin.editingFinished.connect(lambda: self.go(self.spin.value()))
        self.count = QLabel("/ …")
        for w in (self.first, self.prev, self.spin, self.count, self.next, self.last):
            bar.addWidget(w)
        bar.addStretch(1)
        for text, slot in (("−", lambda: self.zoom(0.8)), ("+", lambda: self.zoom(1.25)),
                           ("Fit width", lambda: self.set_fit("width")), ("Fit page", lambda: self.set_fit("page"))):
            bar.addWidget(button(text, slot=slot))
        lay.addLayout(bar)
        self.area = QScrollArea(); self.area.setAlignment(Qt.AlignCenter); self.area.setWidgetResizable(False)
        self.label = QLabel("Loading…"); self.label.setAlignment(Qt.AlignCenter)
        self.label.setContextMenuPolicy(Qt.NoContextMenu)          # no right-click save
        self.area.setWidget(self.label)
        lay.addWidget(self.area, 1)
        self.status = QLabel("Reading is monitored. This reader is a deterrent and cannot prevent screenshots.")
        self.status.setObjectName("muted"); lay.addWidget(self.status)
        self.load()

    def go(self, n: int):
        n = max(1, min(self.pages, n))
        if n != self.page or self.label.pixmap() is None:
            self.page = n
            self.load()

    def zoom(self, factor: float):
        self.fit = None
        self.scale = max(0.4, min(4.0, self.scale * factor))
        self.load()

    def set_fit(self, mode: str):
        self.fit = mode
        self.load()

    def _effective_scale(self) -> float:
        if not self.fit:
            return self.scale
        vw, vh = self.area.viewport().width() - 24, self.area.viewport().height() - 24
        sw = vw / self.meta["page_width"]
        s = sw if self.fit == "width" else min(sw, vh / self.meta["page_height"])
        return max(0.4, min(4.0, s))

    def load(self):
        self._gen += 1
        gen, page, scale = self._gen, self.page, self._effective_scale()
        self.label.setText("Loading page…"); self.label.setPixmap(QPixmap())
        self.status.setText("Loading…")
        run_async(lambda: self.api.page_image(self.work_id, page, scale),
                  lambda res: self._show(gen, res), self._fail)

    def _show(self, gen, res):
        if gen != self._gen:
            return                                              # stale response
        png, meta = res
        self.meta, self.pages = meta, meta["page_count"]
        pm = QPixmap(); pm.loadFromData(png)
        self.label.setPixmap(pm); self.label.resize(pm.size())
        self.spin.blockSignals(True); self.spin.setMaximum(self.pages); self.spin.setValue(self.page); self.spin.blockSignals(False)
        self.count.setText(f"/ {self.pages}")
        for b, off in ((self.first, self.page <= 1), (self.prev, self.page <= 1), (self.next, self.page >= self.pages), (self.last, self.page >= self.pages)):
            b.setDisabled(off)
        self.status.setText("Reading is monitored. This reader is a deterrent and cannot prevent screenshots.")

    def _fail(self, err):
        self.label.setText("This page could not be loaded.")
        self.status.setText("Error loading page.")
        show_error(self, err)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Right, Qt.Key_PageDown):
            self.go(self.page + 1)
        elif e.key() in (Qt.Key_Left, Qt.Key_PageUp):
            self.go(self.page - 1)
        elif e.matches(QKeySequence.Print) or e.matches(QKeySequence.Save):
            return                                              # printing/saving intentionally unsupported
        else:
            super().keyPressEvent(e)
