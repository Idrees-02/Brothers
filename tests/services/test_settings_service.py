import pytest

from app.repositories import settings_repo, users_repo
from app.services import settings_service
from app.services.settings_service import NotAuthorized


def get_admin(conn):
    return users_repo.get_user_by_username(conn, "admin")


def test_admin_can_update_tax_rate(conn):
    admin = get_admin(conn)
    settings_service.update_shop_settings(conn, admin, tax_rate_percent=15.0)
    assert settings_repo.get_settings(conn)["tax_rate_percent"] == 15.0


def test_non_admin_blocked(conn):
    clerk_id = users_repo.create_user(conn, "clerk", "hash", "موظف")
    clerk = users_repo.get_user_by_id(conn, clerk_id)
    with pytest.raises(NotAuthorized):
        settings_service.update_shop_settings(conn, clerk, tax_rate_percent=15.0)


def test_historical_invoice_keeps_original_rate(conn):
    from app.services import invoice_service

    admin = get_admin(conn)
    invoice_id = invoice_service.create_cash_invoice(
        conn,
        admin,
        phone="33330000",
        items=[{"description": "سجادة", "quantity": 1, "unit_price_fils": 10_000}],
        tax_included=False,
        override_password_prompt=lambda: None,
    )
    settings_service.update_shop_settings(conn, admin, tax_rate_percent=20.0)

    from app.repositories import invoices_repo

    old_invoice = invoices_repo.get_invoice(conn, invoice_id)["header"]
    assert old_invoice["tax_rate_percent"] == 10.0  # unaffected by later rate change

    new_invoice_id = invoice_service.create_cash_invoice(
        conn,
        admin,
        phone="33331111",
        items=[{"description": "سجادة", "quantity": 1, "unit_price_fils": 10_000}],
        tax_included=False,
        override_password_prompt=lambda: None,
    )
    new_invoice = invoices_repo.get_invoice(conn, new_invoice_id)["header"]
    assert new_invoice["tax_rate_percent"] == 20.0
