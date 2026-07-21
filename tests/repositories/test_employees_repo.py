from datetime import date

from app.repositories import employees_repo


def test_attendance_upsert_replaces_same_day(conn, admin_user_id):
    employee_id = employees_repo.create_employee(conn, "خالد", 300_000)
    today = date.today().isoformat()

    employees_repo.upsert_attendance(conn, employee_id, today, "absent", admin_user_id)
    employees_repo.upsert_attendance(conn, employee_id, today, "late", admin_user_id)

    row = employees_repo.get_attendance(conn, employee_id, today)
    assert row["status"] == "late"
    count = employees_repo.count_attendance_status(conn, employee_id, today, today, "late")
    assert count == 1


def test_sum_withdrawals(conn, admin_user_id):
    employee_id = employees_repo.create_employee(conn, "خالد", 300_000)
    employees_repo.add_withdrawal(conn, employee_id, 10_000, "2026-07-01", admin_user_id)
    employees_repo.add_withdrawal(conn, employee_id, 5_000, "2026-07-15", admin_user_id)

    total = employees_repo.sum_withdrawals(conn, employee_id, "2026-07-01", "2026-07-31")
    assert total == 15_000


def test_count_attendance_status_over_range(conn, admin_user_id):
    employee_id = employees_repo.create_employee(conn, "خالد", 300_000)
    employees_repo.upsert_attendance(conn, employee_id, "2026-07-01", "absent", admin_user_id)
    employees_repo.upsert_attendance(conn, employee_id, "2026-07-02", "absent", admin_user_id)
    employees_repo.upsert_attendance(conn, employee_id, "2026-07-03", "late", admin_user_id)

    absent_count = employees_repo.count_attendance_status(
        conn, employee_id, "2026-07-01", "2026-07-31", "absent"
    )
    late_count = employees_repo.count_attendance_status(
        conn, employee_id, "2026-07-01", "2026-07-31", "late"
    )
    assert absent_count == 2
    assert late_count == 1
