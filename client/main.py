"""ResearchVault desktop client entry point:  python client/main.py"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # repo root for `client.app...`
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from client.app.api import ApiClient
from client.app.login import LoginWindow
from client.app.main_window import MainWindow
from client.app.brand import APP_NAME, res
from client.app.style import apply_theme, saved_theme
from client.app.worker import bus


class Controller:
    def __init__(self):
        self.api, self.win, self.login = ApiClient(), None, None
        bus.session_expired.connect(lambda: self.show_login("Session expired.\nPlease log in again."))
        self.open_guest()

    def _close_all(self):
        if self.win is not None:
            self.win.timer.stop(); self.win.close(); self.win = None
        if self.login is not None:
            self.login.close(); self.login = None

    def open_guest(self):
        """App opens straight into guest mode: Repository + Semantic Search, no login needed."""
        self._close_all()
        self.api.enter_guest()
        self.win = MainWindow(self.api)
        self.win.sign_in_requested.connect(lambda: self.show_login(""))
        self.win.show()

    def show_login(self, msg: str):
        self._close_all()
        self.api.token = self.api.user = None
        self.login = LoginWindow(self.api, msg)
        self.login.logged_in.connect(self.open_main)
        self.login.guest_requested.connect(self.open_guest)
        self.login.show()

    def open_main(self):
        self.login.close(); self.login = None
        self.win = MainWindow(self.api)
        self.win.logged_out.connect(lambda msg: self.show_login(msg))
        self.win.show()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME); app.setOrganizationName("MaryTheQueenCollege")
    app.setWindowIcon(QIcon(res("app_icon.png")))
    apply_theme(app, saved_theme(), remember=False)   # Fusion style + light/dark palette (ignores Windows theme)
    ctl = Controller()   # noqa: F841 keep reference
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
