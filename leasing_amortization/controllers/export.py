import csv
import io
from datetime import datetime

from odoo import http
from odoo.http import request


class LeasingAmortizationExportController(http.Controller):
    @http.route(
        "/leasing_amortization/export/csv/<int:amortization_id>",
        type="http",
        auth="user",
    )
    def export_csv(self, amortization_id, **kwargs):
        amortization = request.env["leasing.amortization"].browse(amortization_id)
        if not amortization.exists():
            return request.not_found()

        amortization.check_access_rights("read")
        amortization.check_access_rule("read")

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "Months",
                "Payment",
                "Interest Rate",
                "Interest Amount",
                "Net Deduction",
                "Remaining Balance",
            ]
        )

        for line in amortization.line_ids:
            formatted_date = ""
            if line.installment_date:
                formatted_date = f"{line.installment_date.day}-{line.installment_date.strftime('%b-%y')}"
            writer.writerow(
                [
                    formatted_date,
                    f"{line.payment_amount:.2f}",
                    f"{line.interest_rate:.12f}",
                    f"{line.interest_amount:.2f}",
                    f"{line.net_deduction:.2f}",
                    f"{line.remaining_balance:.2f}",
                ]
            )

        csv_content = "\ufeff" + buffer.getvalue()
        filename = amortization._get_export_filename("csv")
        headers = [
            ("Content-Type", "text/csv; charset=utf-8"),
            ("Content-Disposition", f'attachment; filename="{filename}"'),
        ]
        return request.make_response(csv_content, headers=headers)

    @http.route(
        "/leasing_amortization/export/xlsx/<int:amortization_id>",
        type="http",
        auth="user",
    )
    def export_xlsx(self, amortization_id, **kwargs):
        amortization = request.env["leasing.amortization"].browse(amortization_id)
        if not amortization.exists():
            return request.not_found()

        amortization.check_access_rights("read")
        amortization.check_access_rule("read")

        try:
            import xlsxwriter
        except ImportError:
            return request.make_response(
                "xlsxwriter library is required for XLSX export.",
                status=500,
                headers=[("Content-Type", "text/plain; charset=utf-8")],
            )

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("Schedule")

        header_format = workbook.add_format({"bold": True, "bg_color": "#D9E1F2", "border": 1})
        money_format = workbook.add_format({"num_format": "#,##0.00", "border": 1})
        rate_format = workbook.add_format({"num_format": "0.000000000000", "border": 1})
        date_format = workbook.add_format({"num_format": "d-mmm-yy", "border": 1})

        headers = [
            "Months",
            "Payment",
            "Interest Rate",
            "Interest Amount",
            "Net Deduction",
            "Remaining Balance",
        ]

        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        worksheet.set_column(0, 0, 14)
        worksheet.set_column(1, 1, 14)
        worksheet.set_column(2, 2, 18)
        worksheet.set_column(3, 5, 18)

        for row, line in enumerate(amortization.line_ids, start=1):
            if line.installment_date:
                worksheet.write_datetime(
                    row,
                    0,
                    datetime.combine(line.installment_date, datetime.min.time()),
                    date_format,
                )
            else:
                worksheet.write(row, 0, "")
            worksheet.write_number(row, 1, line.payment_amount, money_format)
            worksheet.write_number(row, 2, line.interest_rate, rate_format)
            worksheet.write_number(row, 3, line.interest_amount, money_format)
            worksheet.write_number(row, 4, line.net_deduction, money_format)
            worksheet.write_number(row, 5, line.remaining_balance, money_format)

        workbook.close()
        output.seek(0)

        filename = amortization._get_export_filename("xlsx")
        headers = [
            (
                "Content-Type",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            ("Content-Disposition", f'attachment; filename="{filename}"'),
        ]
        return request.make_response(output.getvalue(), headers=headers)
