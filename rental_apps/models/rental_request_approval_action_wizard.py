from odoo import models, fields, _
from odoo.exceptions import ValidationError


class RentalRequestApprovalActionWizard(models.TransientModel):
    _name = "rental.request.approval.action.wizard"
    _description = "Rental Request Approval Action Wizard"

    action_type = fields.Selection([
        ('approve', 'Approve'),
        ('reject', 'Reject'),
    ], string="Action", required=True, default='approve') # pyright: ignore[reportArgumentType]
    request_id = fields.Many2one('rental.request', string="Rental Request", required=True)
    approval_id = fields.Many2one('rental.request.approval', string="Approval Line", required=True)
    remarks = fields.Text(string="Notes / Remarks")
    attachment_ids = fields.Many2many('ir.attachment', string="PDF Attachments")

    def action_confirm(self):
        self.ensure_one()

        invalid_attachments = self.attachment_ids.filtered(
            lambda attachment: attachment.mimetype and attachment.mimetype != 'application/pdf'
        )
        if invalid_attachments:
            raise ValidationError(_("Only PDF files are allowed as attachments."))

        self.approval_id.write({
            'remarks': self.remarks,
            'attachment_ids': [(6, 0, self.attachment_ids.ids)],
        })

        if self.action_type == 'approve':
            self.approval_id.action_approve()
        else:
            self.approval_id.action_reject()

        return {'type': 'ir.actions.act_window_close'}
