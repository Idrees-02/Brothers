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


def test_reserve_next_number_invoices_share_one_plain_sequence(conn):
    # Cash and installation invoices share a single plain-numbered sequence
    # (no letters) - interleaving the two types still just counts up.
    first_cash = settings_repo.reserve_next_number(conn, "invoice", "cash")
    first_install = settings_repo.reserve_next_number(conn, "invoice", "installation")
    second_cash = settings_repo.reserve_next_number(conn, "invoice", "cash")

    assert first_cash == "1"
    assert first_install == "2"
    assert second_cash == "3"


def test_reserve_next_number_vouchers_keep_their_prefix(conn):
    first_expense = settings_repo.reserve_next_number(conn, "voucher", "expense")
    second_expense = settings_repo.reserve_next_number(conn, "voucher", "expense")
    assert first_expense == "EXP-000001"
    assert second_expense == "EXP-000002"
