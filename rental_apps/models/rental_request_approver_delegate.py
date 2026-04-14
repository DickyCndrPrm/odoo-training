from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class RentalRequestApproverDelegate(models.Model):
    _name = "rental.request.approver.delegate"
    _description = "Rental Request Approver Delegate"
    _order = "delegate_start desc, id desc"

    approver_user_id = fields.Many2one('res.users', string="From Approver", required=True)
    delegate_user_id = fields.Many2one('res.users', string="Delegate To", required=True)
    delegate_start = fields.Datetime(string="Delegate Start")
    delegate_end = fields.Datetime(string="Delegate End")
    active = fields.Boolean(default=True)
    is_active_now = fields.Boolean(
        string="Delegate Active",
        compute="_compute_is_active_now",
        search="_search_is_active_now",
    )

    @api.depends('delegate_start', 'delegate_end', 'active')
    def _compute_is_active_now(self):
        now = fields.Datetime.now()
        for record in self:
            record.is_active_now = record._is_active_at(now)

    def _is_active_at(self, dt_value):
        self.ensure_one()
        if not self.active:
            return False
        if self.delegate_start and dt_value < self.delegate_start:
            return False
        if self.delegate_end and dt_value > self.delegate_end:
            return False
        return True

    def _search_is_active_now(self, operator, value):
        now = fields.Datetime.now()
        active_now_domain = [
            ('active', '=', True),
            '|', ('delegate_start', '=', False), ('delegate_start', '<=', now),
            '|', ('delegate_end', '=', False), ('delegate_end', '>=', now),
        ]

        if operator not in ('=', '!='):
            raise ValidationError(_("Unsupported operator for Delegate Active filter."))

        is_true = bool(value)
        if (operator == '=' and is_true) or (operator == '!=' and not is_true):
            return active_now_domain
        return ['!', *active_now_domain]

    @api.model
    def get_effective_user(self, approver_user, dt_value=None):
        if not approver_user:
            return False

        dt_value = dt_value or fields.Datetime.now()
        delegations = self.search([
            ('approver_user_id', '=', approver_user.id),
            ('active', '=', True),
        ])

        for delegation in delegations:
            if delegation._is_active_at(dt_value):
                return delegation.delegate_user_id

        return approver_user

    @api.model
    def sync_pending_approvals(self, roles=None):
        roles = roles or ['l1', 'l2', 'l3']
        mappings = self.env['rental.request.approver.mapping'].search([
            ('active', '=', True),
            ('role', 'in', roles),
        ])
        mapping_by_role = {mapping.role: mapping for mapping in mappings}

        pending_approvals = self.env['rental.request.approval'].search([
            ('state', '=', 'pending'),
            ('role', 'in', roles),
            ('request_id.state', '=', 'waiting'),
        ])

        now = fields.Datetime.now()
        for approval in pending_approvals:
            mapping = mapping_by_role.get(approval.role)
            if not mapping:
                continue

            target_user = self.get_effective_user(mapping.user_id, dt_value=now)
            if not target_user or approval.user_id == target_user:
                continue

            old_user = approval.user_id
            approval.with_context(skip_approval_write_check=True).write({'user_id': target_user.id})
            if approval.request_id:
                approval.request_id.message_post(body=_(
                    "Approver for stage <b>%s</b> is reassigned from <b>%s</b> to <b>%s</b> based on active delegation."
                ) % (
                    approval.role.upper(),
                    old_user.display_name,
                    target_user.display_name,
                ))

        waiting_requests = self.env['rental.request'].search([('state', '=', 'waiting')])
        for request in waiting_requests:
            request._send_next_approver_notification(is_reminder=False)

    @api.constrains('delegate_start', 'delegate_end')
    def _check_delegate_date_range(self):
        for record in self:
            if record.delegate_start and record.delegate_end and record.delegate_end < record.delegate_start:
                raise ValidationError(_("Delegate End must be greater than or equal to Delegate Start."))

    @api.constrains('approver_user_id', 'delegate_user_id')
    def _check_delegate_user(self):
        for record in self:
            if record.approver_user_id == record.delegate_user_id:
                raise ValidationError(_("Delegate user must be different from approver user."))

    @api.constrains('approver_user_id', 'active')
    def _check_single_active_delegate_per_approver(self):
        for record in self.filtered(lambda item: item.active):
            conflict = self.search_count([
                ('id', '!=', record.id),
                ('approver_user_id', '=', record.approver_user_id.id),
                ('active', '=', True),
            ])
            if conflict:
                raise ValidationError(_("Only one active delegate rule is allowed per approver user."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.sync_pending_approvals()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {'approver_user_id', 'delegate_user_id', 'delegate_start', 'delegate_end', 'active'} & set(vals.keys()):
            self.sync_pending_approvals()
        return result

    def unlink(self):
        result = super().unlink()
        self.sync_pending_approvals()
        return result
