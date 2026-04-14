from odoo import fields, models


class RentalRequest(models.Model):
    _inherit = "rental.request"

    leasing_amortization_ids = fields.One2many(
        "leasing.amortization",
        "rental_request_id",
        string="Leasing Amortizations",
    )
