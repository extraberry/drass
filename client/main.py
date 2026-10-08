"""DRASS desktop client entry point:  python client/main.py"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # repo root for `client.app...`
from PySide6.QtWidgets import QApplication
from client.app.api import ApiClient
from client.app.login import LoginWindow
from client.app.main_window import MainWindow
from client.app.style import QSS
from client.app.worker import bus
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


class Controller:
    def __init__(self):
        self.api, self.win, self.login = ApiClient(), None, None
        bus.session_expired.connect(lambda: self.back_to_login("Session expired.\nPlease log in again."))
        self.back_to_login("")

    def back_to_login(self, msg: str):
        if self.win is not None:
            self.win.timer.stop(); self.win.close(); self.win = None
        self.api.token = self.api.user = None
        if self.login is not None:
            self.login.close()
        self.login = LoginWindow(self.api, msg); self.login.logged_in.connect(self.open_main); self.login.show()

    def open_main(self):
        self.login.close()
        self.win = MainWindow(self.api); self.win.logged_out.connect(self.back_to_login); self.win.show()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    pal = QPalette()
    for role, color in ((QPalette.Window, "#F4F6FA"), (QPalette.WindowText, "#1B2333"), (QPalette.Base, "#FFFFFF"),
                    (QPalette.AlternateBase, "#F7F9FD"), (QPalette.Text, "#1B2333"), (QPalette.Button, "#FFFFFF"),
                    (QPalette.ButtonText, "#1B2333"), (QPalette.PlaceholderText, "#6B7487"),
                    (QPalette.Highlight, "#2F5597"), (QPalette.HighlightedText, "#FFFFFF")):
        pal.setColor(role, QColor(color))
    app.setPalette(pal)
    app.setStyleSheet(QSS)
    ctl = Controller()   # noqa: F841 keep reference
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
