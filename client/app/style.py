NAVY, ACCENT, BG = "#1F3864", "#2F5597", "#F4F6FA"
QSS = f"""
* {{ font-family: 'Segoe UI', 'Calibri', sans-serif; font-size: 10.5pt; color: #1B2333; }}
QMainWindow, QDialog, QWidget#page {{ background: {BG}; }}
QLabel#h1 {{ font-size: 17pt; font-weight: 600; color: {NAVY}; }}
QLabel#h2 {{ font-size: 12pt; font-weight: 600; color: {NAVY}; }}
QLabel#muted {{ color: #5a6577; }}
QLabel#error {{ color: #B00020; }}
QFrame#header {{ background: {NAVY}; }}
QFrame#header QLabel {{ color: white; }}
QFrame#sidebar {{ background: white; border-right: 1px solid #d5dbe6; }}
QListWidget#nav {{ border: none; background: white; }}
QListWidget#nav::item {{ padding: 10px 14px; }}
QListWidget#nav::item:selected {{ background: #DCE6F5; color: {NAVY}; font-weight: 600; }}
QFrame#card {{ background: white; border: 1px solid #d5dbe6; border-radius: 6px; }}
QPushButton {{ background: white; border: 1px solid #aab4c6; border-radius: 4px; padding: 6px 14px; }}
QPushButton:hover {{ background: #eef2fa; }}
QPushButton:disabled {{ color: #9aa3b2; }}
QPushButton#primary {{ background: {ACCENT}; color: white; border: 1px solid {ACCENT}; }}
QPushButton#primary:hover {{ background: {NAVY}; }}
QPushButton#danger {{ color: #B00020; border-color: #B00020; }}
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateEdit, QTextEdit {{ background: white; border: 1px solid #aab4c6; border-radius: 4px; padding: 4px; }}
QTableWidget {{ background: white; alternate-background-color: #F7F9FD; gridline-color: #e3e8f1; }}
QHeaderView::section {{ background: {NAVY}; color: white; padding: 5px; border: none; }}
"""
