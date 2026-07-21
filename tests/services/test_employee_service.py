from app.repositories import employees_repo, settings_repo, users_repo
from app.services import employee_service


def get_admin(conn):
    return users_repo.get_user_by_username(conn, "admin")


def test_generate_salary_report(conn):
    admin = get_admin(conn)
    employee_id = employees_repo.create_employee(conn, "خالد", 260_000)
    settings_repo.update_settings(conn, working_days_per_month=26, late_fine_amount_fils=2_000)

    employee_service.add_withdrawal(conn, admin, employee_id, 10_000, "2026-07-05")
    employee_service.register_attendance(
        conn, admin, employee_id, "2026-07-01", "absent", override_password_prompt=lambda: None
    )
    employee_service.register_attendance(
        conn, admin, employee_id, "2026-07-02", "late", override_password_prompt=lambda: None
    )

    breakdown = employee_service.generate_salary_report(conn, employee_id, "2026-07-01", "2026-07-31")
    assert breakdown.daily_rate_fils == 10_000  # 260000 / 26
    assert breakdown.absence_deduction_fils == 10_000
    assert breakdown.late_deduction_fils == 2_000
    assert breakdown.final_pay_fils == 260_000 - 10_000 - 10_000 - 2_000


def test_generate_salary_report_all(conn):
    admin = get_admin(conn)
    employees_repo.create_employee(conn, "خالد", 260_000)
    employees_repo.create_employee(conn, "سالم", 300_000)

    results = employee_service.generate_salary_report_all(conn, "2026-07-01", "2026-07-31")
    assert len(results) == 2
    assert {r[0]["full_name"] for r in results} == {"خالد", "سالم"}
