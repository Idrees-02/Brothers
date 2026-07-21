from app.repositories import settings_repo


def test_get_default_settings(conn):
    settings = settings_repo.get_settings(conn)
    assert settings["tax_rate_percent"] == 10.0
    assert settings["working_days_per_month"] == 26


def test_update_settings(conn):
    settings_repo.update_settings(conn, tax_rate_percent=15.0, working_days_per_month=24)
    settings = settings_repo.get_settings(conn)
    assert settings["tax_rate_percent"] == 15.0
    assert settings["working_days_per_month"] == 24


def test_reserve_next_number_sequential_per_type(conn):
    first_cash = settings_repo.reserve_next_number(conn, "invoice", "cash")
    second_cash = settings_repo.reserve_next_number(conn, "invoice", "cash")
    first_install = settings_repo.reserve_next_number(conn, "invoice", "installation")

    assert first_cash == "CASH-000001"
    assert second_cash == "CASH-000002"
    assert first_install == "INST-000001"  # independent counter per type
