from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    leasing_vendor_bill_journal_id = fields.Many2one(
        "account.journal",
        string="Default Leasing Journal",
        domain="[('type', 'in', ('purchase', 'general')), ('company_id', '=', id)]",
    )
    leasing_interest_expense_account_id = fields.Many2one(
        "account.account",
        string="Default Leasing Interest Expense",
        domain="[('company_ids', 'in', id)]",
    )
    leasing_lease_payable_account_id = fields.Many2one(
        "account.account",
        string="Default Lease Payable",
        domain="[('company_ids', 'in', id)]",
    )
    leasing_accounts_payable_account_id = fields.Many2one(
        "account.account",
        string="Default Lease Accounts Payable",
        domain="[('company_ids', 'in', id)]",
    )
