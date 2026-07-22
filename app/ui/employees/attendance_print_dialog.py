"""Per-employee attendance print/PDF dialog - pick a date range, then either
print or export a PDF summarizing that employee's attendance over it."""

import sqlite3

from PySide6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app.repositories import employees_repo, settings_repo
from app.ui.vouchers.voucher_print import build_report_html, data_table_fragment, export_html_pdf, show_print_dialog_html
from app.ui.widgets.date_range_picker import DateRangePicker

_STATUS_LABEL = {"present": "حضور", "absent": "غياب", "late": "تأخير"}


class AttendancePrintDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, employee_id: int, employee_name: str, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._employee_id = employee_id
        self._employee_name = employee_name

        self.setWindowTitle(f"طباعة حضور: {employee_name}")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"اختر الفترة لطباعة سجل حضور {employee_name}"))

        self.date_range = DateRangePicker()
        layout.addWidget(self.date_range)

        buttons_row = QHBoxLayout()
        print_button = QPushButton("طباعة")
        print_button.clicked.connect(self._print)
        buttons_row.addWidget(print_button)

        export_button = QPushButton("تصدير PDF")
        export_button.setObjectName("secondaryButton")
        export_button.clicked.connect(self._export_pdf)
        buttons_row.addWidget(export_button)

        cancel_button = QPushButton("إغلاق")
        cancel_button.setObjectName("secondaryButton")
        cancel_button.clicked.connect(self.reject)
        buttons_row.addWidget(cancel_button)
        layout.addLayout(buttons_row)

    def _build_html(self) -> str:
        start = self.date_range.start_date_str()
        end = self.date_range.end_date_str()
        records = employees_repo.list_attendance_for_range(self._conn, self._employee_id, start, end)

        summary_fragment = data_table_fragment(
            ["حضور", "غياب", "تأخير"],
            [
                [
                    str(employees_repo.count_attendance_status(self._conn, self._employee_id, start, end, "present")),
                    str(employees_repo.count_attendance_status(self._conn, self._employee_id, start, end, "absent")),
                    str(employees_repo.count_attendance_status(self._conn, self._employee_id, start, end, "late")),
                ]
            ],
        )
        details_fragment = data_table_fragment(
            ["التاريخ", "الحالة"],
            [[r["work_date"], _STATUS_LABEL.get(r["status"], r["status"])] for r in records],
        )

        shop_name = settings_repo.get_settings(self._conn)["shop_name_ar"]
        return build_report_html(
            shop_name,
            f"سجل حضور: {self._employee_name} (من {start} إلى {end})",
            [summary_fragment, details_fragment],
        )

    def _print(self) -> None:
        show_print_dialog_html(self, self._build_html())

    def _export_pdf(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "تصدير PDF", "attendance.pdf", "PDF (*.pdf)")
        if not path:
            return
        export_html_pdf(self._build_html(), path)
