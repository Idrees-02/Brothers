"""Attendance, withdrawals, and end-of-month salary report generation."""

import sqlite3

from app.domain.permissions import Permission
from app.domain.salary import SalaryBreakdown, compute_salary
from app.repositories import employees_repo, settings_repo
from app.services.permission_service import OverridePrompt, require_permission


def register_attendance(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    employee_id: int,
    work_date: str,
    status: str,
    override_password_prompt: OverridePrompt,
    note: str | None = None,
) -> None:
    require_permission(
        conn, user, Permission.REGISTER_ATTENDANCE, "تسجيل الحضور والانصراف", override_password_prompt
    )
    if status not in ("present", "absent", "late"):
        raise ValueError("حالة حضور غير صالحة")
    employees_repo.upsert_attendance(conn, employee_id, work_date, status, user["id"], note)


def add_withdrawal(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    employee_id: int,
    amount_fils: int,
    withdrawal_date: str,
    note: str | None = None,
) -> int:
    if amount_fils <= 0:
        raise ValueError("المبلغ يجب أن يكون أكبر من صفر")
    return employees_repo.add_withdrawal(conn, employee_id, amount_fils, withdrawal_date, user["id"], note)


def generate_salary_report(
    conn: sqlite3.Connection, employee_id: int, start_date: str, end_date: str
) -> SalaryBreakdown:
    employee = employees_repo.get_employee(conn, employee_id)
    if employee is None:
        raise ValueError("الموظف غير موجود")
    settings = settings_repo.get_settings(conn)

    withdrawals_fils = employees_repo.sum_withdrawals(conn, employee_id, start_date, end_date)
    absent_days = employees_repo.count_attendance_status(conn, employee_id, start_date, end_date, "absent")
    late_occurrences = employees_repo.count_attendance_status(conn, employee_id, start_date, end_date, "late")

    return compute_salary(
        base_salary_fils=employee["base_salary_fils"],
        withdrawals_fils=withdrawals_fils,
        absent_days=absent_days,
        working_days_per_month=settings["working_days_per_month"],
        late_occurrences=late_occurrences,
        late_fine_amount_fils=settings["late_fine_amount_fils"],
    )


def generate_salary_report_all(
    conn: sqlite3.Connection, start_date: str, end_date: str
) -> list[tuple[sqlite3.Row, SalaryBreakdown]]:
    results = []
    for employee in employees_repo.list_employees(conn):
        breakdown = generate_salary_report(conn, employee["id"], start_date, end_date)
        results.append((employee, breakdown))
    return results
