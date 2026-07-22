"""Generic RTL HTML print helper for vouchers, voucher lists, and financial
reports - same QTextDocument + QPrinter + QPrintDialog approach already used
for invoices in app/ui/invoices/invoice_print.py, just with a plain
key/value or tabular HTML body instead of an invoice-shaped one."""

from html import escape

from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QWidget


def _wrap_document(shop_name_ar: str, title: str, body_html: str) -> str:
    return f"""
    <html dir="rtl">
    <body style="font-family: sans-serif;">
    <h2>{escape(shop_name_ar)}</h2>
    <h3>{escape(title)}</h3>
    {body_html}
    </body>
    </html>
    """


def key_value_table_fragment(fields: list[tuple[str, str]]) -> str:
    rows = "".join(
        f"<tr><td><b>{escape(str(label))}</b></td><td>{escape(str(value))}</td></tr>"
        for label, value in fields
    )
    return f'<table border="1" cellspacing="0" cellpadding="4" width="100%">{rows}</table>'


def data_table_fragment(headers: list[str], rows: list[list[str]]) -> str:
    header_html = "".join(f"<th>{escape(str(h))}</th>" for h in headers)
    body_html = "".join(
        "<tr>" + "".join(f"<td>{escape(str(cell))}</td>" for cell in row) + "</tr>" for row in rows
    )
    return (
        '<table border="1" cellspacing="0" cellpadding="4" width="100%">'
        f"<tr>{header_html}</tr>{body_html}</table>"
    )


def build_key_value_html(shop_name_ar: str, title: str, fields: list[tuple[str, str]]) -> str:
    return _wrap_document(shop_name_ar, title, key_value_table_fragment(fields))


def build_table_html(
    shop_name_ar: str,
    title: str,
    headers: list[str],
    rows: list[list[str]],
    subtitle: str | None = None,
) -> str:
    subtitle_html = f"<p>{escape(subtitle)}</p>" if subtitle else ""
    return _wrap_document(shop_name_ar, title, subtitle_html + data_table_fragment(headers, rows))


def build_report_html(shop_name_ar: str, title: str, sections: list[str]) -> str:
    """sections: raw HTML fragments (e.g. key_value_table_fragment/
    data_table_fragment results, or a plain <p>...</p>) stacked in order -
    used for reports combining a stats summary with a detailed ledger."""
    return _wrap_document(shop_name_ar, title, "<br>".join(sections))


def show_print_dialog_html(parent: QWidget, html: str) -> None:
    document = QTextDocument()
    document.setHtml(html)

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    dialog = QPrintDialog(printer, parent)
    if dialog.exec() == QPrintDialog.DialogCode.Accepted:
        document.print_(printer)


def export_html_pdf(html: str, output_path: str) -> None:
    document = QTextDocument()
    document.setHtml(html)

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(output_path)
    document.print_(printer)
