from odoo import models, fields
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class RentalRequestDelegateWizard(models.TransientModel):
    _name = "rental.request.delegate.wizard"
    _description = "Rental Request Delegate Wizard"

    request_id = fields.Many2one('rental.request', string="Rental Request", required=True, readonly=True)
    approval_id = fields.Many2one('rental.request.approval', string="Approval Line", required=True, readonly=True)
    current_user_id = fields.Many2one('res.users', string="Current Approver", related='approval_id.user_id', readonly=True)
    delegate_user_id = fields.Many2one(
        'res.users',
        string="Delegate To",
        required=True,
        domain="[('active', '=', True), ('share', '=', False), ('id', '!=', current_user_id)]",
    )

    def action_confirm(self):
        self.ensure_one()

        if self.approval_id.request_id != self.request_id: # type: ignore
            raise ValidationError(_("Selected approval line does not belong to this request."))

        self.approval_id.action_delegate_to(self.delegate_user_id) # type: ignore
        return {'type': 'ir.actions.act_window_close'}
