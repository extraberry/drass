"""Light / dark themes. `apply_theme(app, name)` swaps palette + stylesheet live; the choice is remembered (QSettings)."""
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QPalette, QPixmap, QPainter, QPen
import os
import tempfile

THEMES = {   # light = "Institutional Navy" (approved design A), dark = "Graphite" (design C)
    "light": dict(text="#1B2433", muted="#4B5668", bg="#F4F6FA", panel="#FFFFFF", header="#14284B", dialog="#F4F6FA",
                  input="#FFFFFF", border="#8E9BB3", nav_hover="#EEF2F9", card_hover="#F4F7FC", btn="#FFFFFF", btn_hover="#EEF2F9",
                  btn_disabled="#7A8499", primary="#14284B", primary_hover="#23407A", primary_text="#FFFFFF", table_alt="#F4F6FA",
                  grid="#E1E6F0", th="#14284B", th_text="#FFFFFF", danger="#B00020", select="#14284B", select_text="#FFFFFF",
                  shadow="#7C8AA8", card_border="#D5DCE8", nav_sel="#E8EDF7", header_line="#D9B45A", tick="#FFFFFF",
                  header_btn="#FFFFFF", header_btn_text="#14284B", header_btn_hover="#E8EDF7"),
    "dark": dict(text="#DDE3EF", muted="#9AA7BD", bg="#0F1420", panel="#171E2E", header="#0B101A", dialog="#0F1420",
                 input="#0F1420", border="#5A6884", nav_hover="#1B2438", card_hover="#1E2840", btn="#171E2E", btn_hover="#222C45",
                 btn_disabled="#6C7896", primary="#8FA9E0", primary_hover="#A9BDEA", primary_text="#0C1630", table_alt="#131A29",
                 grid="#27314A", th="#1E2A44", th_text="#E6EBF5", danger="#FF7A8A", select="#8FA9E0", select_text="#0C1630",
                 shadow="#000000", card_border="#2A344B", nav_sel="#1E2A44", header_line="#2A344B", tick="#0C1630",
                 header_btn="#171E2E", header_btn_text="#E6EBF5", header_btn_hover="#222C45"),
}


_TICK = {}


def _tick_url(color: str = "#FFFFFF") -> str:
    """A white check mark (PNG) for ticked boxes, drawn once; QSS cannot draw a tick by itself, so without it a ticked box looks empty."""
    if color not in _TICK:
        try:
            path = os.path.join(tempfile.gettempdir(), f"drass_tick_{color.strip(chr(35))}.png")
            pm = QPixmap(32, 32); pm.fill(QColor(0, 0, 0, 0))
            pt = QPainter(pm); pt.setRenderHint(QPainter.Antialiasing)
            pen = QPen(QColor(color)); pen.setWidth(5); pen.setCapStyle(Qt.RoundCap); pen.setJoinStyle(Qt.RoundJoin); pt.setPen(pen)
            pt.drawLine(7, 17, 13, 23); pt.drawLine(13, 23, 25, 9); pt.end()
            pm.save(path, "PNG")
            _TICK[color] = path.replace("\\", "/")
        except Exception:
            _TICK[color] = ""
    return _TICK[color]


def load_fonts() -> list:
    """Register every .ttf/.otf in resources/fonts (Inter ships with DRASS; add Source Serif 4 there for the serif headings)."""
    from PySide6.QtGui import QFontDatabase
    folder = os.path.join(os.path.dirname(__file__), "resources", "fonts")
    loaded = []
    try:
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith((".ttf", ".otf")) and QFontDatabase.addApplicationFont(os.path.join(folder, name)) >= 0:
                loaded.append(name)
    except OSError:
        pass
    return loaded


def build_qss(t: dict) -> str:
    tick = _tick_url(t['tick'])
    tick_img = f"image: url({tick});" if tick else ""
    return f"""
* {{ font-family: 'Inter', 'Segoe UI', Arial, sans-serif; font-size: 10.5pt; color: {t['text']}; }}
QLabel {{ background: transparent; }}
QMainWindow {{ background: {t['bg']}; }}
QDialog, QMessageBox {{ background: {t['dialog']}; }}
QWidget#login {{ background: {t['dialog']}; }}
QWidget#page {{ background: transparent; }}
QWidget#content {{ background: {t['bg']}; }}
QLabel#h1 {{ font-family: 'Source Serif 4', Georgia, 'Times New Roman', serif; font-size: 20pt; font-weight: 600; color: {t['text']}; }}
QLabel#wordmark {{ font-family: 'Source Serif 4', Georgia, 'Times New Roman', serif; font-size: 22pt; font-weight: 700; color: {t['text']}; }}
QLabel#h2 {{ font-family: 'Source Serif 4', Georgia, 'Times New Roman', serif; font-size: 13pt; font-weight: 600; color: {t['text']}; }}
QLabel#muted {{ color: {t['muted']}; }}
QLabel#error {{ color: {t['danger']}; }}
QLabel#clock {{ color: {t['muted']}; font-size: 9pt; }}
QFrame#header {{ background: {t['header']}; border-bottom: 3px solid {t['header_line']}; }}
QLabel#brand {{ font-family: 'Source Serif 4', Georgia, 'Times New Roman', serif; font-size: 17pt; font-weight: 700; color: #FFFFFF; }}
QFrame#header QLabel {{ color: #FFFFFF; }}
QFrame#header QPushButton {{ background: {t['header_btn']}; color: {t['header_btn_text']}; border: none; border-radius: 6px; padding: 4px 10px; }}
QFrame#header QPushButton:hover {{ background: {t['header_btn_hover']}; }}
QFrame#sidebar {{ background: {t['panel']}; border: none; border-right: 1px solid {t['card_border']}; }}
QListWidget#nav {{ background: transparent; border: none; font-size: 11.5pt; outline: 0; }}
QListWidget#nav::item {{ padding: 8px 17px; color: {t['text']}; border-radius: 6px; border-left: 3px solid transparent; margin: 1px 10px; }}
QListWidget#nav::item:selected {{ background: {t['nav_sel']}; color: {t['text']}; border-left: 3px solid {t['primary']}; font-weight: 600; }}
QListWidget#nav::item:hover {{ background: {t['nav_hover']}; }}
QFrame#card, QFrame#statcard {{ background: {t['panel']}; border: 1px solid {t['card_border']}; border-radius: 8px; }}
QFrame#statcard:hover {{ background: {t['card_hover']}; }}
QFrame#statcard:focus {{ border: 2px solid {t['primary']}; }}
QPushButton {{ color: {t['text']}; background: {t['btn']}; border: 1px solid {t['border']}; border-radius: 6px; padding: 7px 16px; }}
QPushButton:hover {{ background: {t['btn_hover']}; }}
QPushButton:disabled {{ color: {t['btn_disabled']}; }}
QPushButton#primary {{ background: {t['primary']}; color: {t['primary_text']}; border: 1px solid {t['primary']}; }}
QPushButton#primary:hover {{ background: {t['primary_hover']}; }}
QPushButton#danger {{ color: {t['danger']}; background: {t['btn']}; border-color: {t['danger']}; }}
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateEdit, QTextEdit, QListWidget {{ color: {t['text']}; background: {t['input']}; border: 1px solid {t['border']}; border-radius: 6px; padding: 5px; selection-background-color: {t['select']}; selection-color: {t['select_text']}; }}
QComboBox QAbstractItemView {{ color: {t['text']}; background: {t['input']}; selection-background-color: {t['select']}; selection-color: {t['select_text']}; }}
QCheckBox, QRadioButton {{ color: {t['text']}; background: transparent; spacing: 8px; }}
QCheckBox::indicator, QListWidget::indicator, QTableWidget::indicator {{ width: 18px; height: 18px; border: 2px solid {t['text']}; border-radius: 4px; background: {t['input']}; }}
QCheckBox::indicator:hover, QListWidget::indicator:hover, QTableWidget::indicator:hover {{ border-color: {t['primary_hover']}; }}
QCheckBox::indicator:checked, QListWidget::indicator:checked, QTableWidget::indicator:checked {{ background: {t['primary']}; border-color: {t['primary']}; {tick_img} }}
QCheckBox::indicator:indeterminate {{ background: {t['muted']}; border-color: {t['muted']}; }}
QCheckBox::indicator:disabled {{ border-color: {t['btn_disabled']}; }}
QRadioButton::indicator {{ width: 16px; height: 16px; border: 2px solid {t['text']}; border-radius: 10px; background: {t['input']}; }}
QRadioButton::indicator:checked {{ background: {t['primary']}; border-color: {t['primary']}; }}
QTableWidget {{ color: {t['text']}; background: {t['input']}; alternate-background-color: {t['table_alt']}; gridline-color: {t['grid']}; border: 1px solid {t['card_border']}; border-radius: 6px; selection-background-color: {t['select']}; selection-color: {t['select_text']}; }}
QHeaderView::section {{ background: {t['th']}; color: {t['th_text']}; padding: 6px; border: none; }}
QScrollArea {{ background: transparent; border: none; }}
QToolTip {{ color: {t['text']}; background: {t['input']}; border: 1px solid {t['border']}; }}
"""


def _palette(t: dict) -> QPalette:
    p = QPalette()
    for role, key in ((QPalette.Window, "bg"), (QPalette.WindowText, "text"), (QPalette.Base, "input"), (QPalette.AlternateBase, "table_alt"),
                      (QPalette.Text, "text"), (QPalette.Button, "btn"), (QPalette.ButtonText, "text"), (QPalette.ToolTipBase, "input"),
                      (QPalette.ToolTipText, "text"), (QPalette.PlaceholderText, "muted"), (QPalette.Highlight, "select"),
                      (QPalette.HighlightedText, "select_text")):
        p.setColor(role, QColor(t[key]))
    return p


def saved_theme() -> str:
    try:
        st = QSettings("MaryTheQueenCollege", "DRASS")
        v = st.value("theme", "dark") if st.value("theme_v13") else "dark"      # new look: dark (graphite) is the default once
    except Exception:
        v = "dark"
    return v if v in THEMES else "dark"


_current = "dark"


def current_theme() -> str:
    return _current


def apply_theme(app, name: str, remember: bool = True) -> str:
    global _current
    name = name if name in THEMES else "light"
    _current = name
    app.setStyle("Fusion")                       # consistent look; ignores the Windows system theme
    app.setPalette(_palette(THEMES[name]))
    app.setStyleSheet(build_qss(THEMES[name]))
    if remember:
        try:
            st = QSettings("MaryTheQueenCollege", "DRASS"); st.setValue("theme", name); st.setValue("theme_v13", "1")
        except Exception:
            pass
    return name


def toggle_theme(app) -> str:
    return apply_theme(app, "dark" if _current == "light" else "light")


def card_shadow_rgba() -> tuple:
    """Drop-shadow colour for dashboard cards: soft navy in light mode, deeper black in dark mode."""
    return (0, 0, 0, 115) if _current == "dark" else (15, 40, 84, 46)


def theme_button_text() -> str:
    return "☀ Light" if _current == "dark" else "🌙 Dark"
