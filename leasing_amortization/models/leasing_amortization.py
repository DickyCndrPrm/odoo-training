from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class LeasingAmortization(models.Model):
    _name = "leasing.amortization"
    _description = "Leasing Amortization"
    _order = "id desc"

    name = fields.Char(required=True, default="New")
    state = fields.Selection([
        ("draft", "Draft"),
        ("confirmed", "Confirmed"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    ], default="draft", required=True) # pyright: ignore[reportArgumentType]

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company.id,
    )
    rental_request_id = fields.Many2one(
        "rental.request",
        string="Rental Request",
        ondelete="restrict",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        default=lambda self: self.env.company.partner_id.id,
    )
    journal_entry_count = fields.Integer(compute="_compute_journal_entry_count")

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )

    principal = fields.Monetary(required=True, default=200000.0, currency_field="currency_id")
    term_years = fields.Integer(required=True, default=2)
    number_of_months = fields.Integer(compute="_compute_number_of_months", store=True)

    annual_rate = fields.Float(
        required=True,
        default=7.0,
        digits=(16, 4),
        help="Annual rate in percentage",
    )
    monthly_rate = fields.Float(compute="_compute_monthly_rate", store=True, digits=(16, 12))

    start_date = fields.Date(required=True, default=fields.Date.today)
    end_date = fields.Date(compute="_compute_end_date", store=True)

    use_manual_payment = fields.Boolean(string="Manual Monthly Payment")
    manual_monthly_payment = fields.Monetary(string="Manual Payment Amount", currency_field="currency_id")
    monthly_payment = fields.Monetary(compute="_compute_monthly_payment", store=True, currency_field="currency_id")

    vendor_bill_journal_id = fields.Many2one(
        "account.journal",
        string="Vendor Bill Journal",
        domain="[('type', '=', 'purchase'), ('company_id', '=', company_id)]",
        default=lambda self: self.env.company.leasing_vendor_bill_journal_id.id,
    )
    interest_expense_account_id = fields.Many2one(
        "account.account",
        string="Interest Expense Account",
        domain="[('company_ids', 'in', company_id)]",
        default=lambda self: self.env.company.leasing_interest_expense_account_id.id,
    )
    lease_payable_account_id = fields.Many2one(
        "account.account",
        string="Lease Payable Account",
        domain="[('company_ids', 'in', company_id)]",
        default=lambda self: self.env.company.leasing_lease_payable_account_id.id,
    )
    accounts_payable_account_id = fields.Many2one(
        "account.account",
        string="Lease Accounts Payable",
        domain="[('company_ids', 'in', company_id)]",
        default=lambda self: self.env.company.leasing_accounts_payable_account_id.id,
    )
    posting_scope = fields.Selection([
        ("all", "All Schedule Lines"),
        ("up_to_date", "Up To Date"),
    ], string="Posting Scope", required=True, default="up_to_date") # pyright: ignore[reportArgumentType]
    posting_until_date = fields.Date(string="Posting Until Date", default=fields.Date.today)
    note = fields.Text(string="Notes")

    line_ids = fields.One2many(
        "leasing.amortization.line",
        "amortization_id",
        string="Amortization Schedule",
        copy=False,
    )

    @api.depends("line_ids.move_id")
    def _compute_journal_entry_count(self):
        for record in self:
            record.journal_entry_count = len(record.line_ids.mapped("move_id"))

    @api.onchange("rental_request_id")
    def _onchange_rental_request_id_set_customer(self):
        for record in self:
            if record.rental_request_id and record.rental_request_id.customer_id: # pyright: ignore[reportAttributeAccessIssue]
                record.partner_id = record.rental_request_id.customer_id # pyright: ignore[reportAttributeAccessIssue]

    @api.onchange("company_id")
    def _onchange_company_id_set_accounting_defaults(self):
        for record in self:
            record._apply_company_accounting_defaults()

    @api.depends("term_years")
    def _compute_number_of_months(self):
        for record in self:
            record.number_of_months = max(record.term_years * 12, 0)

    @api.depends("annual_rate")
    def _compute_monthly_rate(self):
        for record in self:
            record.monthly_rate = record.annual_rate / 100.0 / 12.0

    @api.depends("start_date", "number_of_months")
    def _compute_end_date(self):
        for record in self:
            if record.start_date and record.number_of_months > 0:
                record.end_date = record.start_date + relativedelta(months=record.number_of_months - 1)
            else:
                record.end_date = False

    @api.constrains("annual_rate")
    def _check_annual_rate_range(self):
        for record in self:
            if record.annual_rate < 0 or record.annual_rate > 100:
                raise UserError("Annual rate must be between 0 and 100. Use 7 for 7%.")

    @api.depends(
        "principal",
        "number_of_months",
        "monthly_rate",
        "use_manual_payment",
        "manual_monthly_payment",
    )
    def _compute_monthly_payment(self):
        for record in self:
            if record.use_manual_payment and record.manual_monthly_payment > 0:
                record.monthly_payment = record.manual_monthly_payment
                continue

            principal = record.principal
            months = record.number_of_months
            rate = record.monthly_rate

            if principal <= 0 or months <= 0:
                record.monthly_payment = 0.0
                continue

            if rate == 0:
                record.monthly_payment = principal / months
                continue

            factor = (1 + rate) ** months
            record.monthly_payment = principal * ((rate * factor) / (factor - 1))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            company = self.env["res.company"].browse(vals.get("company_id") or self.env.company.id)

            if not vals.get("vendor_bill_journal_id"):
                vals["vendor_bill_journal_id"] = company.leasing_vendor_bill_journal_id.id
            if not vals.get("interest_expense_account_id"):
                vals["interest_expense_account_id"] = company.leasing_interest_expense_account_id.id
            if not vals.get("lease_payable_account_id"):
                vals["lease_payable_account_id"] = company.leasing_lease_payable_account_id.id
            if not vals.get("accounts_payable_account_id"):
                vals["accounts_payable_account_id"] = company.leasing_accounts_payable_account_id.id

            if not vals.get("name") or vals.get("name") == "New":
                sequence_number = self.env["ir.sequence"].next_by_code("leasing.amortization") or "00000"
                sequence_tail = str(sequence_number).split("/")[-1]
                amortization_date_value = vals.get("start_date") or fields.Date.context_today(self)
                amortization_date = fields.Date.to_date(amortization_date_value)
                formatted_date = amortization_date.strftime("%Y%m%d")
                vals["name"] = f"LA/{formatted_date}/{sequence_tail}"
        return super().create(vals_list)

    def _apply_company_accounting_defaults(self):
        for record in self:
            company = record.company_id or self.env.company
            if not record.vendor_bill_journal_id:
                record.vendor_bill_journal_id = company.leasing_vendor_bill_journal_id
            if not record.interest_expense_account_id:
                record.interest_expense_account_id = company.leasing_interest_expense_account_id
            if not record.lease_payable_account_id:
                record.lease_payable_account_id = company.leasing_lease_payable_account_id
            if not record.accounts_payable_account_id:
                record.accounts_payable_account_id = company.leasing_accounts_payable_account_id

    def action_generate_schedule(self):
        for record in self:
            if record.state not in ("draft", "confirmed"):
                raise UserError("Schedule can only be generated from Draft or Confirmed state.")
            if any(record.line_ids.mapped("move_id")):
                raise UserError("Cannot regenerate schedule because some lines are already posted to accounting.")

            if record.principal <= 0:
                raise UserError("Principal must be greater than 0.")
            if record.number_of_months <= 0:
                raise UserError("Term must be greater than 0 month.")
            if not record.start_date:
                raise UserError("Start date is required.")

            payment = record.monthly_payment
            if payment <= 0:
                raise UserError("Monthly payment must be greater than 0.")

            commands = [fields.Command.clear()]
            remaining_balance = record.principal

            for installment_no in range(1, record.number_of_months + 1):
                interest_amount = remaining_balance * record.monthly_rate
                net_deduction = payment - interest_amount

                if installment_no == record.number_of_months or net_deduction > remaining_balance:
                    net_deduction = remaining_balance
                    payment_for_line = net_deduction + interest_amount
                else:
                    payment_for_line = payment

                remaining_after = remaining_balance - net_deduction
                if remaining_after < 0:
                    remaining_after = 0.0

                installment_date = record.start_date + relativedelta(months=installment_no - 1)
                commands.append(
                    fields.Command.create(
                        {
                            "installment_date": installment_date,
                            "payment_amount": payment_for_line,
                            "interest_rate": record.monthly_rate,
                            "interest_amount": interest_amount,
                            "net_deduction": net_deduction,
                            "remaining_balance": remaining_after,
                            "sequence": installment_no,
                        }
                    )
                )
                remaining_balance = remaining_after

            record.line_ids = commands
            record.state = "confirmed"

    def action_confirm(self):
        for record in self:
            if record.state == "draft":
                record.state = "confirmed"

    def action_set_draft(self):
        for record in self:
            if any(record.line_ids.mapped("move_id")):
                raise UserError("Cannot reset to draft because vendor bills already exist.")
            record.state = "draft"

    def action_cancel(self):
        for record in self:
            record.state = "cancelled"

    def action_generate_vendor_bills(self):
        for record in self:
            if record.state not in ("confirmed", "done"):
                raise UserError("Please confirm amortization first before generating vendor bills.")
            if not record.line_ids:
                raise UserError("Please generate amortization schedule first.")
            if not record.vendor_bill_journal_id:
                raise UserError("Vendor Bill Journal is required.")
            if not record.interest_expense_account_id:
                raise UserError("Interest Expense Account is required.")
            if not record.lease_payable_account_id:
                raise UserError("Lease Payable Account is required.")
            if not record.partner_id:
                raise UserError("Customer/Partner is required.")

            lines_to_post = record.line_ids.filtered(lambda amort_line: not amort_line.move_id)
            if record.posting_scope == "up_to_date":
                if not record.posting_until_date:
                    raise UserError("Posting Until Date is required for Up To Date posting scope.")
                lines_to_post = lines_to_post.filtered(
                    lambda amort_line: amort_line.installment_date and amort_line.installment_date <= record.posting_until_date
                )

            if not lines_to_post:
                raise UserError("No schedule lines match the selected posting scope.")

            for line in lines_to_post:
                move = self.env["account.move"].create({
                    "move_type": "in_invoice",
                    "journal_id": record.vendor_bill_journal_id.id,
                    "date": line.installment_date,
                    "invoice_date": line.installment_date,
                    "partner_id": record.partner_id.id,
                    "ref": f"{record.name} / Installment {line.sequence}",
                    "invoice_line_ids": [
                        fields.Command.create({
                            "name": f"{record.name} Principal {line.sequence}",
                            "account_id": record.lease_payable_account_id.id,
                            "quantity": 1.0,
                            "price_unit": line.net_deduction,
                        }),
                        fields.Command.create({
                            "name": f"{record.name} Interest {line.sequence}",
                            "account_id": record.interest_expense_account_id.id,
                            "quantity": 1.0,
                            "price_unit": line.interest_amount,
                        }),
                    ],
                })
                line.move_id = move.id

            record.state = "done" if all(line.move_id for line in record.line_ids) else "confirmed"

    def action_view_journal_entries(self):
        self.ensure_one()
        move_ids = self.line_ids.mapped("move_id").ids
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_in_invoice_type")
        action["domain"] = [("id", "in", move_ids)]
        action["context"] = {"create": False, "default_move_type": "in_invoice"}
        return action

    def _get_export_filename(self, extension):
        self.ensure_one()
        safe_name = (self.name or "amortization_schedule").strip().replace(" ", "_")
        return f"{safe_name}.{extension}"

    def action_export_csv(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/leasing_amortization/export/csv/{self.id}",
            "target": "self",
        }

    def action_export_xlsx(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/leasing_amortization/export/xlsx/{self.id}",
            "target": "self",
        }


class LeasingAmortizationLine(models.Model):
    _name = "leasing.amortization.line"
    _description = "Leasing Amortization Line"
    _order = "sequence asc, id asc"

    amortization_id = fields.Many2one("leasing.amortization", required=True, ondelete="cascade")
    sequence = fields.Integer(default=1)

    currency_id = fields.Many2one("res.currency", related="amortization_id.currency_id", store=True)

    installment_date = fields.Date(required=True)
    payment_amount = fields.Monetary(required=True, currency_field="currency_id")
    interest_rate = fields.Float(required=True, digits=(16, 12))
    interest_amount = fields.Monetary(required=True, currency_field="currency_id")
    net_deduction = fields.Monetary(required=True, currency_field="currency_id")
    remaining_balance = fields.Monetary(required=True, currency_field="currency_id")
    move_id = fields.Many2one("account.move", string="Vendor Bill", readonly=True, copy=False)
