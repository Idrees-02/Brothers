"""SQL access for employees, employee_withdrawals, and attendance."""

import sqlite3


def create_employee(
    conn: sqlite3.Connection,
    full_name: str,
    base_salary_fils: int,
    phone: str | None = None,
    hired_at: str | None = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO employees (full_name, base_salary_fils, phone, hired_at)
           VALUES (?, ?, ?, ?)""",
        (full_name, base_salary_fils, phone, hired_at),
    )
    conn.commit()
    return cur.lastrowid


def list_employees(conn: sqlite3.Connection, include_inactive: bool = False) -> list[sqlite3.Row]:
    if include_inactive:
        return conn.execute("SELECT * FROM employees ORDER BY full_name").fetchall()
    return conn.execute(
        "SELECT * FROM employees WHERE is_active = 1 ORDER BY full_name"
    ).fetchall()


def get_employee(conn: sqlite3.Connection, employee_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()


def update_employee(
    conn: sqlite3.Connection,
    employee_id: int,
    full_name: str | None = None,
    base_salary_fils: int | None = None,
    phone: str | None = None,
) -> None:
    fields, values = [], []
    if full_name is not None:
        fields.append("full_name = ?")
        values.append(full_name)
    if base_salary_fils is not None:
        fields.append("base_salary_fils = ?")
        values.append(base_salary_fils)
    if phone is not None:
        fields.append("phone = ?")
        values.append(phone)
    if not fields:
        return
    fields.append("updated_at = datetime('now')")
    values.append(employee_id)
    conn.execute(f"UPDATE employees SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()


def set_active(conn: sqlite3.Connection, employee_id: int, is_active: bool) -> None:
    conn.execute(
        "UPDATE employees SET is_active = ?, updated_at = datetime('now') WHERE id = ?",
        (int(is_active), employee_id),
    )
    conn.commit()


def add_withdrawal(
    conn: sqlite3.Connection,
    employee_id: int,
    amount_fils: int,
    withdrawal_date: str,
    created_by_user_id: int,
    note: str | None = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO employee_withdrawals
           (employee_id, amount_fils, withdrawal_date, note, created_by_user_id)
           VALUES (?, ?, ?, ?, ?)""",
        (employee_id, amount_fils, withdrawal_date, note, created_by_user_id),
    )
    conn.commit()
    return cur.lastrowid


def list_withdrawals(
    conn: sqlite3.Connection, employee_id: int, start_date: str, end_date: str
) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT * FROM employee_withdrawals
           WHERE employee_id = ? AND date(withdrawal_date) BETWEEN date(?) AND date(?)
           ORDER BY withdrawal_date""",
        (employee_id, start_date, end_date),
    ).fetchall()


def sum_withdrawals(conn: sqlite3.Connection, employee_id: int, start_date: str, end_date: str) -> int:
    row = conn.execute(
        """SELECT COALESCE(SUM(amount_fils), 0) AS total FROM employee_withdrawals
           WHERE employee_id = ? AND date(withdrawal_date) BETWEEN date(?) AND date(?)""",
        (employee_id, start_date, end_date),
    ).fetchone()
    return row["total"]


def upsert_attendance(
    conn: sqlite3.Connection,
    employee_id: int,
    work_date: str,
    status: str,
    recorded_by_user_id: int,
    note: str | None = None,
) -> None:
    conn.execute(
        """INSERT INTO attendance (employee_id, work_date, status, note, recorded_by_user_id)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(employee_id, work_date)
           DO UPDATE SET status = excluded.status, note = excluded.note,
                         recorded_by_user_id = excluded.recorded_by_user_id,
                         updated_at = datetime('now')""",
        (employee_id, work_date, status, note, recorded_by_user_id),
    )
    conn.commit()


def get_attendance(conn: sqlite3.Connection, employee_id: int, work_date: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM attendance WHERE employee_id = ? AND work_date = ?",
        (employee_id, work_date),
    ).fetchone()


def list_attendance_for_range(
    conn: sqlite3.Connection, employee_id: int, start_date: str, end_date: str
) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT * FROM attendance WHERE employee_id = ?
           AND date(work_date) BETWEEN date(?) AND date(?) ORDER BY work_date""",
        (employee_id, start_date, end_date),
    ).fetchall()


def count_attendance_status(
    conn: sqlite3.Connection, employee_id: int, start_date: str, end_date: str, status: str
) -> int:
    row = conn.execute(
        """SELECT COUNT(*) AS cnt FROM attendance
           WHERE employee_id = ? AND status = ? AND date(work_date) BETWEEN date(?) AND date(?)""",
        (employee_id, status, start_date, end_date),
    ).fetchone()
    return row["cnt"]


def count_present_on_date(conn: sqlite3.Connection, work_date: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM attendance WHERE status = 'present' AND work_date = date(?)",
        (work_date,),
    ).fetchone()
    return row["cnt"]
