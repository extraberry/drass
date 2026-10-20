"""Light / dark themes. `apply_theme(app, name)` swaps palette + stylesheet live; the choice is remembered (QSettings)."""
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QPalette

THEMES = {
    "light": dict(text="#0F2854", muted="#697498", bg="#BBCAE6", panel="#C9D1E0", header="#0F2854", dialog="#EEF2FA",
                  input="#FFFFFF", border="#A9B6D3", nav_hover="#D6DDEB", card_hover="#D8DFEC", btn="#FFFFFF", btn_hover="#EEF2FA",
                  btn_disabled="#8A94AE", primary="#0F2854", primary_hover="#1B3A78", primary_text="#FFFFFF", table_alt="#F3F6FB",
                  grid="#DDE3F0", th="#0F2854", th_text="#FFFFFF", danger="#B00020", select="#0F2854", select_text="#FFFFFF",
                  shadow="#7C8AA8"),
    "dark": dict(text="#E4EAF7", muted="#9AA8C7", bg="#0E1627", panel="#17233B", header="#0A1A3C", dialog="#131E34",
                 input="#0E1627", border="#35476C", nav_hover="#1F2F4F", card_hover="#1F2E4A", btn="#1D2B47", btn_hover="#28395C",
                 btn_disabled="#6C7896", primary="#4B7BE0", primary_hover="#6490EE", primary_text="#FFFFFF", table_alt="#13203A",
                 grid="#27385A", th="#22345A", th_text="#FFFFFF", danger="#FF7A8A", select="#4B7BE0", select_text="#FFFFFF",
                 shadow="#000000"),
}


def build_qss(t: dict) -> str:
    return f"""
* {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: 10.5pt; color: {t['text']}; }}
QLabel {{ background: transparent; }}
QMainWindow {{ background: {t['bg']}; }}
QDialog, QMessageBox {{ background: {t['dialog']}; }}
QWidget#login {{ background: {t['dialog']}; }}
QWidget#page {{ background: transparent; }}
QWidget#content {{ background: {t['bg']}; }}
QLabel#h1 {{ font-size: 19pt; font-weight: 400; color: {t['text']}; }}
QLabel#wordmark {{ font-size: 23pt; font-weight: 700; color: {t['text']}; }}
QLabel#h2 {{ font-size: 12pt; font-weight: 600; color: {t['text']}; }}
QLabel#muted {{ color: {t['muted']}; }}
QLabel#error {{ color: {t['danger']}; }}
QLabel#clock {{ color: {t['muted']}; font-size: 9pt; }}
QFrame#header {{ background: {t['header']}; border-bottom-left-radius: 22px; border-bottom-right-radius: 22px; }}
QFrame#header QLabel {{ color: #FFFFFF; }}
QFrame#header QPushButton {{ background: #FFFFFF; color: #0F2854; border: none; border-radius: 6px; padding: 4px 10px; }}
QFrame#header QPushButton:hover {{ background: #E6ECF8; }}
QFrame#sidebar {{ background: {t['panel']}; border: none; }}
QListWidget#nav {{ background: transparent; border: none; font-size: 11.5pt; outline: 0; }}
QListWidget#nav::item {{ padding: 7px 20px; color: {t['text']}; border-radius: 8px; margin: 0; }}
QListWidget#nav::item:selected {{ background: {t['bg']}; color: {t['text']}; }}
QListWidget#nav::item:hover {{ background: {t['nav_hover']}; }}
QFrame#card, QFrame#statcard {{ background: {t['panel']}; border: none; border-radius: 8px; }}
QFrame#statcard:hover {{ background: {t['card_hover']}; }}
QFrame#statcard:focus {{ border: 2px solid {t['text']}; }}
QPushButton {{ color: {t['text']}; background: {t['btn']}; border: 1px solid {t['border']}; border-radius: 8px; padding: 7px 16px; }}
QPushButton:hover {{ background: {t['btn_hover']}; }}
QPushButton:disabled {{ color: {t['btn_disabled']}; }}
QPushButton#primary {{ background: {t['primary']}; color: {t['primary_text']}; border: 1px solid {t['primary']}; }}
QPushButton#primary:hover {{ background: {t['primary_hover']}; }}
QPushButton#danger {{ color: {t['danger']}; background: {t['btn']}; border-color: {t['danger']}; }}
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateEdit, QTextEdit, QListWidget {{ color: {t['text']}; background: {t['input']}; border: 1px solid {t['border']}; border-radius: 6px; padding: 5px; selection-background-color: {t['select']}; selection-color: {t['select_text']}; }}
QComboBox QAbstractItemView {{ color: {t['text']}; background: {t['input']}; selection-background-color: {t['select']}; selection-color: {t['select_text']}; }}
QCheckBox, QRadioButton {{ color: {t['text']}; background: transparent; spacing: 6px; }}
QTableWidget {{ color: {t['text']}; background: {t['input']}; alternate-background-color: {t['table_alt']}; gridline-color: {t['grid']}; border: none; border-radius: 6px; selection-background-color: {t['select']}; selection-color: {t['select_text']}; }}
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
        v = QSettings("MaryTheQueenCollege", "ResearchVault").value("theme", "light")
    except Exception:
        v = "light"
    return v if v in THEMES else "light"


_current = "light"


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
            QSettings("MaryTheQueenCollege", "ResearchVault").setValue("theme", name)
        except Exception:
            pass
    return name


def toggle_theme(app) -> str:
    return apply_theme(app, "dark" if _current == "light" else "light")


def theme_button_text() -> str:
    return "☀ Light" if _current == "dark" else "🌙 Dark"
