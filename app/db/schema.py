"""SQLite schema definitions, one string per schema version.

Money is always stored as an integer number of fils (1 BHD = 1000 fils) so
that SQL SUM()/GROUP BY aggregations are exact - never store money as REAL.
"""

SCHEMA_V1_SQL = """
CREATE TABLE users (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    username                    TEXT NOT NULL UNIQUE,
    password_hash               TEXT NOT NULL,
    password_algo               TEXT NOT NULL DEFAULT 'pbkdf2_sha256',
    display_name                TEXT NOT NULL,
    is_admin                    INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0,1)),
    can_create_invoice          INTEGER NOT NULL DEFAULT 0 CHECK (can_create_invoice IN (0,1)),
    can_edit_invoice            INTEGER NOT NULL DEFAULT 0 CHECK (can_edit_invoice IN (0,1)),
    can_view_only               INTEGER NOT NULL DEFAULT 0 CHECK (can_view_only IN (0,1)),
    can_create_voucher          INTEGER NOT NULL DEFAULT 0 CHECK (can_create_voucher IN (0,1)),
    can_register_attendance     INTEGER NOT NULL DEFAULT 0 CHECK (can_register_attendance IN (0,1)),
    is_active                   INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    created_at                  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at                  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE settings (
    id                              INTEGER PRIMARY KEY CHECK (id = 1),
    shop_name_ar                    TEXT NOT NULL DEFAULT 'الإخوة لبيع السجاد',
    shop_name_en                    TEXT NOT NULL DEFAULT 'Brothers for Selling Carpet',
    shop_phone                      TEXT,
    shop_address                    TEXT,
    tax_rate_percent                REAL NOT NULL DEFAULT 10.0,
    override_password_hash          TEXT NOT NULL,
    override_password_algo          TEXT NOT NULL DEFAULT 'pbkdf2_sha256',
    default_installation_fee_fils   INTEGER NOT NULL DEFAULT 0,
    late_fine_amount_fils           INTEGER NOT NULL DEFAULT 0,
    working_days_per_month          INTEGER NOT NULL DEFAULT 26,
    next_cash_invoice_no            INTEGER NOT NULL DEFAULT 1,
    next_installation_invoice_no    INTEGER NOT NULL DEFAULT 1,
    next_expense_voucher_no         INTEGER NOT NULL DEFAULT 1,
    next_purchase_voucher_no        INTEGER NOT NULL DEFAULT 1,
    updated_at                      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE invoices (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_type            TEXT NOT NULL CHECK (invoice_type IN ('cash','installation')),
    invoice_no              TEXT NOT NULL UNIQUE,
    customer_name           TEXT,
    phone                   TEXT NOT NULL,
    address                 TEXT,
    area_region             TEXT,
    status                  TEXT NOT NULL DEFAULT 'completed'
                                CHECK (status IN ('booked','completed','voided')),
    with_installation       INTEGER CHECK (with_installation IN (0,1)),
    subtotal_fils           INTEGER NOT NULL,
    tax_included             INTEGER NOT NULL DEFAULT 0 CHECK (tax_included IN (0,1)),
    tax_rate_percent        REAL NOT NULL,
    tax_amount_fils         INTEGER NOT NULL,
    grand_total_fils        INTEGER NOT NULL,
    deposit_fils            INTEGER NOT NULL DEFAULT 0,
    created_by_user_id      INTEGER NOT NULL REFERENCES users(id),
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now')),
    voided_at                TEXT,
    voided_by_user_id       INTEGER REFERENCES users(id)
);
CREATE INDEX idx_invoices_customer_name ON invoices(customer_name);
CREATE INDEX idx_invoices_phone ON invoices(phone);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_type ON invoices(invoice_type);
CREATE INDEX idx_invoices_created_at ON invoices(created_at);

CREATE TABLE invoice_items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id          INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    description         TEXT NOT NULL,
    quantity            REAL NOT NULL DEFAULT 1,
    unit                TEXT NOT NULL DEFAULT 'piece' CHECK (unit IN ('piece','sqm')),
    unit_price_fils     INTEGER NOT NULL,
    line_total_fils     INTEGER NOT NULL
);
CREATE INDEX idx_invoice_items_invoice_id ON invoice_items(invoice_id);

CREATE TABLE invoice_payments (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id              INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    payment_type            TEXT NOT NULL CHECK (payment_type IN ('deposit','remaining','full')),
    amount_fils             INTEGER NOT NULL,
    paid_at                 TEXT NOT NULL DEFAULT (datetime('now')),
    received_by_user_id     INTEGER NOT NULL REFERENCES users(id)
);
CREATE INDEX idx_invoice_payments_invoice_id ON invoice_payments(invoice_id);

CREATE TABLE expenses (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    voucher_no              TEXT NOT NULL UNIQUE,
    description             TEXT NOT NULL,
    amount_fils             INTEGER NOT NULL,
    expense_date            TEXT NOT NULL,
    note                    TEXT,
    created_by_user_id      INTEGER NOT NULL REFERENCES users(id),
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    voided_at               TEXT,
    voided_by_user_id       INTEGER REFERENCES users(id)
);
CREATE INDEX idx_expenses_date ON expenses(expense_date);

CREATE TABLE purchase_invoices (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    voucher_no              TEXT NOT NULL UNIQUE,
    supplier_name           TEXT NOT NULL,
    total_amount_fils       INTEGER NOT NULL,
    purchase_date           TEXT NOT NULL,
    note                    TEXT,
    created_by_user_id      INTEGER NOT NULL REFERENCES users(id),
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    voided_at               TEXT,
    voided_by_user_id       INTEGER REFERENCES users(id)
);
CREATE INDEX idx_purchase_invoices_date ON purchase_invoices(purchase_date);

CREATE TABLE purchase_invoice_items (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_invoice_id     INTEGER NOT NULL REFERENCES purchase_invoices(id) ON DELETE CASCADE,
    description             TEXT NOT NULL,
    quantity                REAL NOT NULL DEFAULT 1,
    unit_price_fils         INTEGER NOT NULL,
    line_total_fils         INTEGER NOT NULL
);
CREATE INDEX idx_purchase_invoice_items_purchase_id ON purchase_invoice_items(purchase_invoice_id);

CREATE TABLE employees (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name           TEXT NOT NULL,
    phone               TEXT,
    base_salary_fils    INTEGER NOT NULL,
    is_active           INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    hired_at            TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE employee_withdrawals (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id             INTEGER NOT NULL REFERENCES employees(id),
    amount_fils             INTEGER NOT NULL,
    withdrawal_date         TEXT NOT NULL,
    note                    TEXT,
    created_by_user_id      INTEGER NOT NULL REFERENCES users(id),
    created_at              TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_withdrawals_employee_date ON employee_withdrawals(employee_id, withdrawal_date);

CREATE TABLE attendance (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id             INTEGER NOT NULL REFERENCES employees(id),
    work_date               TEXT NOT NULL,
    status                  TEXT NOT NULL CHECK (status IN ('present','absent','late')),
    note                    TEXT,
    recorded_by_user_id     INTEGER NOT NULL REFERENCES users(id),
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(employee_id, work_date)
);
CREATE INDEX idx_attendance_employee_date ON attendance(employee_id, work_date);

CREATE TABLE audit_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at         TEXT NOT NULL DEFAULT (datetime('now')),
    user_id             INTEGER REFERENCES users(id),
    action              TEXT NOT NULL,
    permission          TEXT,
    target_table        TEXT,
    target_id           INTEGER,
    details             TEXT
);
CREATE INDEX idx_audit_log_occurred_at ON audit_log(occurred_at);
CREATE INDEX idx_audit_log_user_id ON audit_log(user_id);

CREATE TABLE schema_migrations (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# Ordered list of (version, sql) pairs applied in sequence by migrations.py.
# Add new (version, sql) tuples here for future schema changes - never edit
# SCHEMA_V1_SQL after it has shipped.
MIGRATIONS: list[tuple[int, str]] = [
    (1, SCHEMA_V1_SQL),
]
