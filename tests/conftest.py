import pytest

from app.db.connection import connect_memory
from app.db.seed import seed_if_empty


@pytest.fixture
def conn():
    connection = connect_memory()
    seed_if_empty(connection, default_override_password="0000")
    yield connection
    connection.close()


@pytest.fixture
def admin_user_id(conn):
    row = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
    return row["id"]
