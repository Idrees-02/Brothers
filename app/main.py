"""Entry point: python -m app.main"""

import sys

from app.config import db_path
from app.db.connection import connect
from app.ui.app import build_application
from app.ui.login_screen import LoginScreen
from app.ui.main_window import MainWindow


def main() -> int:
    conn = connect(db_path())
    application = build_application()

    login_screen = LoginScreen(conn)
    main_window_holder: dict = {}

    def on_login(user):
        main_window = MainWindow(conn, user)
        main_window_holder["window"] = main_window
        main_window.show()
        login_screen.close()

    login_screen.login_succeeded.connect(on_login)
    login_screen.show()

    return application.exec()


if __name__ == "__main__":
    sys.exit(main())
