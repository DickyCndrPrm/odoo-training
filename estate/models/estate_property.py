from odoo import api, fields, models
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError

class EstateProperty(models.Model):
    _name = "estate.property"
    _description = "Test model"
    _order = "id"
    
    def _default_acceptance_date(self):
        return date.today() + relativedelta(months=3)

    name = fields.Char(required=True, default="Unknown")
    description = fields.Text()
    postcode = fields.Char()
    date_availability = fields.Date(copy=False, default=_default_acceptance_date)
    expected_price = fields.Float(required=True)
    selling_price = fields.Float(copy=False)
    bedrooms = fields.Integer(default=2)
    living_area = fields.Integer()
    facades = fields.Integer()
    garage = fields.Boolean()
    garden = fields.Boolean(onchange="_onchange_garden")
    garden_area = fields.Integer()
    garden_orientation = fields.Selection(
        selection=[('n', 'North'), ('s', 'South'), ('w', 'West'), ('e', 'East')], # type: ignore
        string="Garden Orientation"
    )
    active = fields.Boolean(default=True, invisible=True)
    state = fields.Selection(
        selection=[
            ("new", "New"),
            ("received", "Offer Received"),
            ("accepted", "Offer Accepted"),
            ("sold", "Sold"),
            ("canceled", "Canceled")
        ], # pyright: ignore[reportArgumentType]
        required=True,
        copy=False,
        default="new"
    )
    
    total_area = fields.Float(compute="_compute_total_area")
    best_offer = fields.Float(compute="_compute_best_offer")
    
    property_type_id = fields.Many2one("estate.property.type", can_write=False)
    partner_id = fields.Many2one("res.partner", string="Partner")
    user_id = fields.Many2one("res.users", string="User")
    
    tag_ids = fields.Many2many("estate.property.tag", string="Tags")
    offer_ids = fields.One2many("estate.property.offer","property_id", string="Offers")
    
    _check_expected_price = models.Constraint(
        'CHECK(expected_price >= 0)',
        'Expected Price cannot be lower than 0'
    )
    
    _check_selling_price = models.Constraint(
        'CHECK(selling_price >= 0)',
        'Expected Price cannot be lower than 0'
    )
    
    @api.onchange("garden")
    def _onchange_garden(self):
        self.garden_area = 10
        self.garden_orientation = "n"
    
    @api.depends("garden_area", "living_area")
    def _compute_total_area(self):
        for record in self:
            record.total_area = record.garden_area + record.living_area
            
    @api.depends('offer_ids.price')
    def _compute_best_offer(self):
        for record in self:
            prices = record.offer_ids.mapped('price')
            
            if prices:
                record.best_offer = max(prices)
            else:
                record.best_offer = 0.0
    
    @api.ondelete(at_uninstall=False)
    def ondelete(self):
        for record in self:
            if record.state in ("new", "canceled"):
                raise UserError("Cannot delete on offer property!")
    
    def action_cancel_property(self):
        for record in self:
            record.state = "canceled"
        return True

    def action_sold_property(self):
        for record in self:
            if self.state == "canceled":
                raise UserError("Canceled property cannot be sold")
            
            record.state = "sold"
        return True