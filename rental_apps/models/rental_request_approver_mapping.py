from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class RentalRequestApproverMapping(models.Model):
    _name = "rental.request.approver.mapping"
    _description = "Rental Request Approver Mapping"
    _order = "role"

    role = fields.Selection([
        ('l1', 'Manager'),
        ('l2', 'Senior Manager'),
        ('l3', 'Director')
    ], string="Approval Level", required=True) # pyright: ignore[reportArgumentType]
    user_id = fields.Many2one('res.users', string="Approver User", required=True)
    active = fields.Boolean(default=True)

    @api.constrains('role', 'active')
    def _check_single_active_mapping_per_role(self):
        for mapping in self.filtered(lambda record: record.active):
            existing_count = self.search_count([
                ('id', '!=', mapping.id),
                ('role', '=', mapping.role),
                ('active', '=', True),
            ])
            if existing_count:
                raise ValidationError(_("Only one active mapping is allowed for each approval level."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env['rental.request.approver.delegate'].sync_pending_approvals(records.mapped('role'))
        return records

    def write(self, vals):
        result = super().write(vals)
        if {'role', 'user_id', 'active'} & set(vals.keys()):
            self.env['rental.request.approver.delegate'].sync_pending_approvals(self.mapped('role'))
        return result
