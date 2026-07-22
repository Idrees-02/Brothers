"""Entry point: python -m app.main"""

import sys

from app.config import db_path
from app.db.connection import connect
from app.repositories import settings_repo
from app.ui.app import build_application
from app.ui.login_screen import LoginScreen
from app.ui.main_window import MainWindow


def main() -> int:
    conn = connect(db_path())
    application = build_application()
    shop_name = settings_repo.get_settings(conn)["shop_name_ar"]
    state: dict = {}

    def show_login() -> None:
        login_screen = LoginScreen(conn, shop_name)
        state["login_screen"] = login_screen
        login_screen.login_succeeded.connect(on_login)
        login_screen.show()

    def on_login(user) -> None:
        main_window = MainWindow(conn, user)
        state["window"] = main_window
        main_window.logout_requested.connect(on_logout)
        main_window.show()
        state["login_screen"].close()

    def on_logout() -> None:
        state["window"].close()
        show_login()

    show_login()
    return application.exec()


if __name__ == "__main__":
    sys.exit(main())
