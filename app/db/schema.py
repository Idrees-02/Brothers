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
    shop_name_ar                    TEXT NOT NULL DEFAULT 'الاخوين لبيع السجاد',
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

# v2: receipt vouchers (سندات قبض) + installation scheduling (تاريخ التركيب,
# حالة التركيب, الفني المسؤول). Additive only (ALTER TABLE ADD COLUMN /
# CREATE TABLE) so it applies cleanly on top of any existing v1 database
# without touching existing rows, plus a one-time fix-up for the shop name
# default that shipped before the correct Arabic name was confirmed.
SCHEMA_V2_SQL = """
ALTER TABLE invoices ADD COLUMN installation_date TEXT;
ALTER TABLE invoices ADD COLUMN installation_status TEXT
    CHECK (installation_status IN ('pending','installed','postponed','cancelled'));
ALTER TABLE invoices ADD COLUMN assigned_employee_id INTEGER REFERENCES employees(id);
CREATE INDEX idx_invoices_installation_date ON invoices(installation_date);

CREATE TABLE receipts (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    voucher_no              TEXT NOT NULL UNIQUE,
    description             TEXT NOT NULL,
    amount_fils             INTEGER NOT NULL,
    receipt_date            TEXT NOT NULL,
    note                    TEXT,
    created_by_user_id      INTEGER NOT NULL REFERENCES users(id),
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    voided_at               TEXT,
    voided_by_user_id       INTEGER REFERENCES users(id)
);
CREATE INDEX idx_receipts_date ON receipts(receipt_date);

ALTER TABLE settings ADD COLUMN next_receipt_voucher_no INTEGER NOT NULL DEFAULT 1;

UPDATE settings SET shop_name_ar = 'الاخوين لبيع السجاد' WHERE shop_name_ar = 'الإخوة لبيع السجاد';
"""

# v3: required payment method on invoices (cash / بنفت باي / ماستركارد / شيك).
SCHEMA_V3_SQL = """
ALTER TABLE invoices ADD COLUMN payment_method TEXT
    CHECK (payment_method IN ('cash','benefit_pay','mastercard','cheque'));
"""

# v4: chart of accounts for vouchers (سندات الصرف والقبض) - lets the shop
# track which account money moved through (cash box / bank / owner) and
# produce a per-account statement. account_id is nullable at the DB level
# so this migration never breaks existing rows; the service layer requires
# it for all newly created vouchers.
SCHEMA_V4_SQL = """
CREATE TABLE accounts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO accounts (name) VALUES ('الصندوق النقدي'), ('البنك'), ('المالك');

ALTER TABLE expenses ADD COLUMN account_id INTEGER REFERENCES accounts(id);
ALTER TABLE receipts ADD COLUMN account_id INTEGER REFERENCES accounts(id);
CREATE INDEX idx_expenses_account_id ON expenses(account_id);
CREATE INDEX idx_receipts_account_id ON receipts(account_id);
"""

# v5: invoices.created_at/updated_at and invoice_payments.paid_at defaulted
# to datetime('now'), which is UTC - every "today" boundary in the app
# (dashboard counts, tax/financial reports) is computed from the shop's
# local calendar day. In a timezone ahead of UTC (e.g. Bahrain, UTC+3),
# anything recorded between local midnight and the UTC rollover got stamped
# with the *previous* day and vanished from "today" until the report window
# widened. Rebuilds both tables with datetime('now','localtime') defaults,
# following SQLite's documented recreate-and-rename procedure for schema
# changes ALTER TABLE can't express directly (changing a column default).
SCHEMA_V5_SQL = """
PRAGMA foreign_keys = OFF;

CREATE TABLE invoices_v5 (
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
    created_at              TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    voided_at                TEXT,
    voided_by_user_id       INTEGER REFERENCES users(id),
    installation_date       TEXT,
    installation_status     TEXT CHECK (installation_status IN ('pending','installed','postponed','cancelled')),
    assigned_employee_id    INTEGER REFERENCES employees(id),
    payment_method          TEXT CHECK (payment_method IN ('cash','benefit_pay','mastercard','cheque'))
);

INSERT INTO invoices_v5 (
    id, invoice_type, invoice_no, customer_name, phone, address, area_region,
    status, with_installation, subtotal_fils, tax_included, tax_rate_percent,
    tax_amount_fils, grand_total_fils, deposit_fils, created_by_user_id,
    created_at, updated_at, voided_at, voided_by_user_id,
    installation_date, installation_status, assigned_employee_id, payment_method
)
SELECT
    id, invoice_type, invoice_no, customer_name, phone, address, area_region,
    status, with_installation, subtotal_fils, tax_included, tax_rate_percent,
    tax_amount_fils, grand_total_fils, deposit_fils, created_by_user_id,
    created_at, updated_at, voided_at, voided_by_user_id,
    installation_date, installation_status, assigned_employee_id, payment_method
FROM invoices;

DROP TABLE invoices;
ALTER TABLE invoices_v5 RENAME TO invoices;

CREATE INDEX idx_invoices_customer_name ON invoices(customer_name);
CREATE INDEX idx_invoices_phone ON invoices(phone);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_type ON invoices(invoice_type);
CREATE INDEX idx_invoices_created_at ON invoices(created_at);
CREATE INDEX idx_invoices_installation_date ON invoices(installation_date);

CREATE TABLE invoice_payments_v5 (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id              INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    payment_type            TEXT NOT NULL CHECK (payment_type IN ('deposit','remaining','full')),
    amount_fils             INTEGER NOT NULL,
    paid_at                 TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    received_by_user_id     INTEGER NOT NULL REFERENCES users(id)
);

INSERT INTO invoice_payments_v5 (id, invoice_id, payment_type, amount_fils, paid_at, received_by_user_id)
SELECT id, invoice_id, payment_type, amount_fils, paid_at, received_by_user_id
FROM invoice_payments;

DROP TABLE invoice_payments;
ALTER TABLE invoice_payments_v5 RENAME TO invoice_payments;
CREATE INDEX idx_invoice_payments_invoice_id ON invoice_payments(invoice_id);

PRAGMA foreign_keys = ON;
"""

# v6: inventory (المخزون) - items with a denormalized quantity_on_hand for
# cheap listing, plus stock_movements as the append-only audit trail
# explaining every change (سند إدخال / سند إخراج, or an automatic 'sale'
# movement when an invoice line item matches an inventory item by name).
SCHEMA_V6_SQL = """
CREATE TABLE items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL UNIQUE,
    unit                TEXT NOT NULL DEFAULT 'piece' CHECK (unit IN ('piece','sqm')),
    unit_price_fils     INTEGER NOT NULL DEFAULT 0,
    quantity_on_hand    REAL NOT NULL DEFAULT 0,
    is_active           INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    created_at          TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE stock_movements (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    voucher_no              TEXT NOT NULL UNIQUE,
    movement_type           TEXT NOT NULL CHECK (movement_type IN ('in','out')),
    item_id                 INTEGER NOT NULL REFERENCES items(id),
    quantity                REAL NOT NULL,
    reason                  TEXT,
    note                    TEXT,
    movement_date           TEXT NOT NULL,
    source                  TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual','sale')),
    reference_invoice_id    INTEGER REFERENCES invoices(id),
    created_by_user_id      INTEGER NOT NULL REFERENCES users(id),
    created_at              TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    voided_at               TEXT,
    voided_by_user_id       INTEGER REFERENCES users(id)
);
CREATE INDEX idx_stock_movements_item_id ON stock_movements(item_id);
CREATE INDEX idx_stock_movements_date ON stock_movements(movement_date);

ALTER TABLE settings ADD COLUMN next_stock_in_voucher_no INTEGER NOT NULL DEFAULT 1;
ALTER TABLE settings ADD COLUMN next_stock_out_voucher_no INTEGER NOT NULL DEFAULT 1;
"""

# v7: tax on purchase invoices, matching how sales invoices already snapshot
# subtotal/rate/tax amount alongside the grand total (kept as
# total_amount_fils for backward compatibility with existing report
# queries). Historical rows default to 0/0% since the pre-tax split can't be
# reconstructed retroactively - only new purchases populate these correctly.
SCHEMA_V7_SQL = """
ALTER TABLE purchase_invoices ADD COLUMN subtotal_fils INTEGER NOT NULL DEFAULT 0;
ALTER TABLE purchase_invoices ADD COLUMN tax_included INTEGER NOT NULL DEFAULT 0 CHECK (tax_included IN (0,1));
ALTER TABLE purchase_invoices ADD COLUMN tax_rate_percent REAL NOT NULL DEFAULT 0;
ALTER TABLE purchase_invoices ADD COLUMN tax_amount_fils INTEGER NOT NULL DEFAULT 0;
"""

# v8: one shared plain-numbered sequence for both invoice types (cash and
# installation invoices used to have separate CASH-/INST- prefixed counters;
# now every invoice - regardless of type - just gets the next number in a
# single sequence, e.g. 1, 2, 3, ...). The old next_cash_invoice_no /
# next_installation_invoice_no columns are left in place, just unused.
SCHEMA_V8_SQL = """
ALTER TABLE settings ADD COLUMN next_invoice_no INTEGER NOT NULL DEFAULT 1;
"""

# Ordered list of (version, sql) pairs applied in sequence by migrations.py.
# Add new (version, sql) tuples here for future schema changes - never edit
# a SCHEMA_VN_SQL string after it has shipped, since existing databases at
# that version will never re-run it.
MIGRATIONS: list[tuple[int, str]] = [
    (1, SCHEMA_V1_SQL),
    (2, SCHEMA_V2_SQL),
    (3, SCHEMA_V3_SQL),
    (4, SCHEMA_V4_SQL),
    (5, SCHEMA_V5_SQL),
    (6, SCHEMA_V6_SQL),
    (7, SCHEMA_V7_SQL),
    (8, SCHEMA_V8_SQL),
]
