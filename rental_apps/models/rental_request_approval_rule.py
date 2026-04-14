from odoo import models, fields, api
from odoo.exceptions import ValidationError


class RentalRequestApprovalRule(models.Model):
    _name = "rental.request.approval.rule"
    _description = "Rental Request Approval Rule"
    _order = "sequence, min_quantity, max_quantity, required_level, id"

    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="Rule Name", compute="_compute_name", store=True)
    brand_ids = fields.Many2many('fleet.vehicle.model.brand', string="Brands")
    min_quantity = fields.Integer(string="Min Quantity", required=True, default=1)
    max_quantity = fields.Integer(string="Max Quantity")
    is_default = fields.Boolean(string="Default Rule", default=False)
    required_level = fields.Selection([
        ('l1', 'Level 1 (Manager)'),
        ('l2', 'Level 2 (Senior Manager)'),
        ('l3', 'Level 3 (Director)'),
    ], string="Required Approval Level", required=True, default='l1') # pyright: ignore[reportArgumentType]
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('rental_rule_qty_min_check', 'CHECK(min_quantity > 0)', 'Min quantity must be greater than zero.'),
        ('rental_rule_qty_range_check', 'CHECK(max_quantity IS NULL OR max_quantity >= min_quantity)', 'Max quantity must be greater than or equal to min quantity.'),
    ]

    @api.constrains('is_default', 'brand_ids')
    def _check_brand_required_for_non_default(self):
        for rule in self:
            if not rule.is_default and not rule.brand_ids:
                raise ValidationError("Please set at least one brand for non-default rule.")

    @api.depends('brand_ids', 'min_quantity', 'max_quantity', 'required_level', 'is_default')
    def _compute_name(self):
        level_label = {
            'l1': 'L1',
            'l2': 'L2',
            'l3': 'L3',
        }
        for rule in self:
            if rule.is_default:
                rule.name = f"DEFAULT | {level_label.get(rule.required_level, '')}"
                continue
            max_qty = rule.max_quantity if rule.max_quantity else '∞'
            brand_names = ', '.join(rule.brand_ids.mapped('name')) or '-'
            rule.name = f"{brand_names} | Qty {rule.min_quantity}-{max_qty} | {level_label.get(rule.required_level, '')}"
