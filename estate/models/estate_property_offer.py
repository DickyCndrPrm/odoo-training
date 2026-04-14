from datetime import timedelta

from odoo import api, fields, models, exceptions
from odoo.tools import float_compare, float_is_zero, float_round
from odoo.exceptions import ValidationError

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .estate_property import EstateProperty

class PropertyOffer(models.Model):
    _name = "estate.property.offer"
    _description = "Estate Property Offer"
    _order = "price"

    price = fields.Float()
    status = fields.Selection(
        selection=[
            ("accept", "Accepted"),
            ("refuse", "Refused"),
        ]  # pyright: ignore[reportArgumentType]
    )

    partner_id = fields.Many2one("res.partner")
    property_id = fields.Many2one("estate.property")
    property_type_id = fields.Many2one(
        "estate.property.type", 
        related="property_id.property_type_id", 
        string="Property Type",
        store=True
    )

    validity = fields.Integer(default=7)
    date_deadline = fields.Date(compute="_compute_deadline", inverse="_inverse_deadline", store=True)
    
    _check_price = models.Constraint(
        'CHECK(price >= 0)',
        'Price offer cannot be lower than 0'
    )
    
    @api.model_create_multi
    def create(self, vals_list):
      for vals in vals_list:
          
          property_record = self.env['estate.property'].browse(vals['property_id'])
          
          if property_record.offer_ids: # type: ignore
              max_offer = max(property_record.offer_ids.mapped('price')) # type: ignore
              if float_compare(vals['price'], max_offer, precision_digits=2) == -1:
                  raise exceptions.UserError(f"Penawaran harus lebih tinggi dari {max_offer}!")

          property_record.state = 'received' # type: ignore

      return super().create(vals_list)
    
    @api.constrains("price")
    def _check_offer_price(self):
      for record in self:
        minimum_price = record.property_id.expected_price * 0.9 # type: ignore
        if not float_is_zero(record.price, precision_digits=2):
          if float_compare(record.price, minimum_price, precision_digits=2) == -1:
            raise ValidationError('Minimum offer price is 90% of expected price')

    @api.depends("create_date", "validity")
    def _compute_deadline(self):
        for record in self:
            create_dt = getattr(record, "create_date", False)
            base_date = fields.Date.to_date(create_dt) or fields.Date.today()
            record.date_deadline = base_date + timedelta(days=record.validity)

    def _inverse_deadline(self):
        for record in self:
            if record.date_deadline:
                create_dt = getattr(record, "create_date", False)
                base_date = fields.Date.to_date(create_dt) or fields.Date.today()
                record.validity = (record.date_deadline - base_date).days
            else:
                record.validity = 7

    @api.constrains("status", "property_id")
    def _check_only_one_accepted_offer(self):
        """Ensure only one offer can be accepted per property."""
        for record in self:
            if record.status == "accept":
                accepted_count = self.search_count([
                    ("status", "=", "accept"),
                    ("property_id", "=", record.property_id.id),
                    ("id", "!=", record.id),
                ])
                if accepted_count > 0:
                    raise exceptions.ValidationError(
                        "Only one offer can be accepted for a property!"
                    )

    def action_accept_offer(self):
        """Accept the offer and update the property with buyer and selling price."""
        for record in self:
            other_offers = self.search([
                ("property_id", "=", record.property_id.id),
                ("status", "!=", "refuse"),
                ("id", "!=", record.id),
            ])
            other_offers.write({"status": "refuse"})

            record.property_id.write({
                "partner_id": record.partner_id.id,
                "selling_price": record.price,
                "state": "accepted",
            })
            record.status = "accept"
        return True

    def action_refuse_offer(self):
        """Refuse the offer."""
        for record in self:
            record.status = "refuse"
        return True