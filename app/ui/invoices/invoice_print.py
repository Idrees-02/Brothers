"""Builds a printable invoice as an RTL HTML QTextDocument and sends it to
QPrinter. Qt's text engine (HarfBuzz-based) handles Arabic shaping/BiDi
natively, so no extra dependencies (reportlab/arabic_reshaper) are needed.
"""

from html import escape

from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QWidget

from app.domain.money import fils_to_bhd_str
from app.services.invoice_service import PAYMENT_METHOD_LABELS_AR

_TYPE_LABEL = {"cash": "فاتورة قطع جاهزة", "installation": "فاتورة تركيب وتفصيل"}


def build_invoice_html(invoice: dict, shop_name_ar: str) -> str:
    header = invoice["header"]
    items = invoice["items"]
    payments = invoice["payments"]

    rows = "".join(
        f"<tr><td>{escape(item['description'])}</td>"
        f"<td>{item['quantity']}</td>"
        f"<td>{fils_to_bhd_str(item['unit_price_fils'])}</td>"
        f"<td>{fils_to_bhd_str(item['line_total_fils'])}</td></tr>"
        for item in items
    )
    payment_rows = "".join(
        f"<tr><td>{p['payment_type']}</td><td>{fils_to_bhd_str(p['amount_fils'])}</td>"
        f"<td>{p['paid_at']}</td></tr>"
        for p in payments
    )
    paid_total = sum(p["amount_fils"] for p in payments)
    remaining = header["grand_total_fils"] - paid_total

    return f"""
    <html dir="rtl">
    <body style="font-family: sans-serif;">
    <h2>{escape(shop_name_ar)}</h2>
    <h3>{_TYPE_LABEL.get(header['invoice_type'], header['invoice_type'])} - {header['invoice_no']}</h3>
    <p>الزبون: {escape(header['customer_name'] or '')}<br>
       الهاتف: {escape(header['phone'])}<br>
       {"المنطقة: " + escape(header['area_region']) + "<br>" if header['area_region'] else ""}
       طريقة الدفع: {PAYMENT_METHOD_LABELS_AR.get(header['payment_method'], '')}<br>
       التاريخ: {header['created_at']}</p>
    <table border="1" cellspacing="0" cellpadding="4" width="100%">
        <tr><th>الوصف</th><th>الكمية</th><th>سعر الوحدة</th><th>الإجمالي</th></tr>
        {rows}
    </table>
    <p>
        المجموع الفرعي: {fils_to_bhd_str(header['subtotal_fils'])} د.ب<br>
        الضريبة ({header['tax_rate_percent']}%){' (شاملة)' if header['tax_included'] else ''}:
            {fils_to_bhd_str(header['tax_amount_fils'])} د.ب<br>
        <b>الإجمالي الكلي: {fils_to_bhd_str(header['grand_total_fils'])} د.ب</b><br>
        {"المقدم: " + fils_to_bhd_str(header['deposit_fils']) + " د.ب<br>" if header['deposit_fils'] else ""}
        المدفوع: {fils_to_bhd_str(paid_total)} د.ب<br>
        المتبقي: {fils_to_bhd_str(remaining)} د.ب
    </p>
    <table border="1" cellspacing="0" cellpadding="4" width="100%">
        <tr><th>نوع الدفعة</th><th>المبلغ</th><th>التاريخ</th></tr>
        {payment_rows}
    </table>
    </body>
    </html>
    """


def show_print_dialog(parent: QWidget, invoice: dict, shop_name_ar: str) -> None:
    document = QTextDocument()
    document.setHtml(build_invoice_html(invoice, shop_name_ar))

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    dialog = QPrintDialog(printer, parent)
    if dialog.exec() == QPrintDialog.DialogCode.Accepted:
        document.print_(printer)


def export_invoice_pdf(invoice: dict, shop_name_ar: str, output_path: str) -> None:
    document = QTextDocument()
    document.setHtml(build_invoice_html(invoice, shop_name_ar))

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(output_path)
    document.print_(printer)
