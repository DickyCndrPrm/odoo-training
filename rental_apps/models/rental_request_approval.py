from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools.translate import _

class RentalRequestApproval(models.Model):
    _name = "rental.request.approval"
    _description = "Rental Request Approver Log"
    _order = "request_id, role"

    request_id = fields.Many2one('rental.request', string="Rental Request", ondelete='cascade')

    user_id = fields.Many2one("res.users", string="Approver", required=True)

    role = fields.Selection([
        ('l1', 'Manager'),
        ('l2', 'Senior Manager'),
        ('l3', 'Director')
    ], string="Role", required=True) # pyright: ignore[reportArgumentType]

    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled')
    ], string="Status", default='pending') # pyright: ignore[reportArgumentType]
    action_date = fields.Datetime(string="Action Date")
    remarks = fields.Text(string="Remarks")
    attachment_ids = fields.Many2many('ir.attachment', string="Attachments")
    approval_cycle = fields.Integer(string="Approval Cycle", default=1, required=True)
    can_current_user_delegate = fields.Boolean(
        string="Can Current User Delegate",
        compute="_compute_can_current_user_delegate",
    )

    @api.depends('state', 'user_id')
    def _compute_can_current_user_delegate(self):
        current_user = self.env.user
        is_admin = current_user.has_group('base.group_system')
        for approval in self:
            approval.can_current_user_delegate = bool(
                approval.state == 'pending'
                and (
                    approval.user_id == current_user
                    or is_admin
                )
            )

    @api.constrains('attachment_ids')
    def _check_attachments_pdf_only(self):
        for approval in self:
            invalid_attachments = approval.attachment_ids.filtered(
                lambda attachment: attachment.mimetype and attachment.mimetype != 'application/pdf'
            )
            if invalid_attachments:
                raise ValidationError(_("Only PDF files are allowed for approval attachments."))

    def _check_assigned_approver(self):
        for approval in self:
            if approval.user_id != self.env.user:
                raise ValidationError(_("Only the assigned approver can approve or reject this stage."))

    def write(self, vals):
        protected_fields = {'state', 'action_date', 'user_id', 'role', 'remarks', 'attachment_ids'}
        if (
            not self.env.su
            and not self.env.context.get('skip_approval_write_check')
            and protected_fields.intersection(vals.keys())
        ):
            self._check_assigned_approver()
        return super().write(vals)

    def _open_action_wizard(self, action_type):
        self.ensure_one()
        self._check_assigned_approver()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Approval Action'),
            'res_model': 'rental.request.approval.action.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_request_id': self.request_id.id,
                'default_approval_id': self.id,
                'default_action_type': action_type,
            },
        }

    def action_open_approve_wizard(self):
        self.ensure_one()
        return self._open_action_wizard('approve')

    def action_open_reject_wizard(self):
        self.ensure_one()
        return self._open_action_wizard('reject')

    def action_open_delegate_wizard(self):
        self.ensure_one()
        is_admin = self.env.user.has_group('base.group_system')
        if self.user_id != self.env.user and not is_admin:
            raise ValidationError(_("Only the assigned approver or administrator can delegate this stage."))
        if self.state != 'pending':
            raise ValidationError(_("Only pending approval stage can be delegated."))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Delegate Approval'),
            'res_model': 'rental.request.delegate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_request_id': self.request_id.id,
                'default_approval_id': self.id,
            },
        }

    def action_delegate_to(self, delegate_user):
        self.ensure_one()

        if self.state != 'pending':
            raise ValidationError(_("Only pending approval stage can be delegated."))

        is_admin = self.env.user.has_group('base.group_system')
        if self.user_id != self.env.user and not is_admin:
            raise ValidationError(_("Only the assigned approver or administrator can delegate this stage."))

        if not delegate_user or not delegate_user.active or delegate_user.share:
            raise ValidationError(_("Please select a valid internal active user for delegation."))

        if self.user_id == delegate_user:
            raise ValidationError(_("Delegate user must be different from current approver."))

        old_approver_name = self.user_id.display_name
        self.with_context(skip_approval_write_check=True).write({'user_id': delegate_user.id})

        if self.request_id:
            self.request_id.message_post(body=_(
                "Approval stage <b>%s</b> delegated from <b>%s</b> to <b>%s</b>."
            ) % (self.role.upper(), old_approver_name, delegate_user.display_name))
            self.request_id._send_next_approver_notification(is_reminder=False)

    def _get_approver_group_map(self):
        return {
            'l1': 'rental_apps.group_rental_approver_l1',
            'l2': 'rental_apps.group_rental_approver_l2',
            'l3': 'rental_apps.group_rental_approver_l3',
        }

    def action_approve(self):
        role_order = {'l1': 1, 'l2': 2, 'l3': 3}
        approver_group_map = self._get_approver_group_map()
        for approval in self:
            request = approval.request_id
            if not request:
                continue

            group_xml_id = approver_group_map.get(approval.role)
            if group_xml_id and not self.env.user.has_group(group_xml_id):
                raise ValidationError(_("You do not have access to approve this level."))

            approval._check_assigned_approver()

            pending_approvals = request.approver_ids.filtered(lambda item: item.state == 'pending').sorted( # type: ignore
                key=lambda item: role_order.get(item.role, 99)
            )
            current_step = pending_approvals[:1]
            if current_step and current_step != approval:
                raise ValidationError(_("Current approver stage is %s.") % current_step.user_id.display_name)

            approval.write({
                'state': 'approved',
                'action_date': fields.Datetime.now(),
            })

            if request.approver_ids.filtered(lambda item: item.state == 'pending'): # type: ignore
                request.state = 'waiting' # type: ignore
                request._send_next_approver_notification(is_reminder=False) # type: ignore
            else:
                request.state = 'approved' # type: ignore

    def action_reject(self):
        role_order = {'l1': 1, 'l2': 2, 'l3': 3}
        approver_group_map = self._get_approver_group_map()
        for approval in self:
            request = approval.request_id

            group_xml_id = approver_group_map.get(approval.role)
            if group_xml_id and not self.env.user.has_group(group_xml_id):
                raise ValidationError(_("You do not have access to reject this level."))

            approval._check_assigned_approver()

            approval.write({
                'state': 'rejected',
                'action_date': fields.Datetime.now(),
            })

            if request:
                current_rank = role_order.get(approval.role, 0)

                upper_pending_approvals = request.approver_ids.filtered(
                    lambda item: role_order.get(item.role, 0) > current_rank and item.state == 'pending' # type: ignore
                )
                if upper_pending_approvals:
                    upper_pending_approvals.with_context(skip_approval_write_check=True).write({
                        'state': 'cancelled',
                        'action_date': fields.Datetime.now(),
                    })

                request.state = 'new' # type: ignore
                request.message_post(body=_(
                    "Approval was rejected at stage <b>%s</b>. Upper approval stages are cancelled, lower stages are kept as log, and request is reset to draft for re-submission."
                ) % approval.role.upper())