from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class RentalRequest(models.Model):
    _name = "rental.request"
    _description = "Rental Request Form"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Reference", default="New", readonly=True, copy=False)

    date = fields.Date(string="Date", default=fields.Date.context_today, required=True, tracking=True)
    customer_id = fields.Many2one("res.partner", string="Customer/Partner", tracking=True)

    request_type = fields.Selection([
        ('temporary', 'Replacement Car Temporary'),
        ('new', 'Replacement Car New')
    ], string="Type of Request", tracking=True) # pyright: ignore[reportArgumentType]

    required_date = fields.Date(string="Required Date", tracking=True)

    state = fields.Selection([
        ('new', 'Draft'),
        ('waiting', 'Waiting for Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string="Status", default='new', tracking=True) # pyright: ignore[reportArgumentType]

    note = fields.Text(string="Log Notes / Remarks", tracking=True)
    note_attachment_ids = fields.Many2many('ir.attachment', string="Note Attachments")
    next_approver_id = fields.Many2one(
        "res.users",
        string="Current Approver",
        compute="_compute_next_approver",
        store=True,
        tracking=True,
    )
    approver_stage = fields.Selection([
        ('none', 'No Stage'),
        ('l1', 'Manager Stage'),
        ('l2', 'Senior Manager Stage'),
        ('l3', 'Director Stage'),
        ('done', 'Completed'),
    ], string="Approval Stage", compute="_compute_next_approver", store=True) # pyright: ignore[reportArgumentType]
    can_current_user_approve = fields.Boolean(
        string="Can Current User Approve",
        compute="_compute_current_user_approval",
    )
    can_current_user_delegate = fields.Boolean(
        string="Can Current User Delegate",
        compute="_compute_current_user_approval",
    )
    current_user_approval_id = fields.Many2one(
        'rental.request.approval',
        string="Current User Approval",
        compute="_compute_current_user_approval",
    )
    current_pending_approval_id = fields.Many2one(
        'rental.request.approval',
        string="Current Pending Approval",
        compute="_compute_current_user_approval",
    )

    line_ids = fields.One2many('rental.request.line', 'request_id', string="Request Lines")
    approver_ids = fields.One2many('rental.request.approval', 'request_id', string="Approver Logs")

    @api.constrains('note_attachment_ids')
    def _check_note_attachments_pdf_only(self):
        for request in self:
            invalid_attachments = request.note_attachment_ids.filtered(
                lambda attachment: attachment.mimetype and attachment.mimetype != 'application/pdf'
            )
            if invalid_attachments:
                raise ValidationError(_("Only PDF files are allowed in request notes attachments."))

    def _get_approver_group_map(self):
        return {
            'l1': 'rental_apps.group_rental_approver_l1',
            'l2': 'rental_apps.group_rental_approver_l2',
            'l3': 'rental_apps.group_rental_approver_l3',
        }

    def _resolve_approver_user_by_role(self, role):
        approver_group_map = self._get_approver_group_map()
        mapping_model = self.env['rental.request.approver.mapping']
        delegate_model = self.env['rental.request.approver.delegate']

        mapping = mapping_model.search([
            ('role', '=', role),
            ('active', '=', True),
        ], limit=1)
        effective_user = delegate_model.get_effective_user(mapping.user_id) if mapping else False
        if effective_user and effective_user.login != 'admin':
            return effective_user

        group_xml_id = approver_group_map.get(role)
        group = self.env.ref(group_xml_id, raise_if_not_found=False) if group_xml_id else False
        if not group:
            raise ValidationError(_("Approver group for %s is not configured.") % role.upper())

        role_users = group.user_ids.filtered(
            lambda user: user.active and user.share is False and user.login != 'admin'
        ).sorted(key=lambda user: user.id)

        if not role_users:
            raise ValidationError(_("No active non-admin user found for approval level %s.") % role.upper())

        approver_user = role_users[0]

        if not mapping:
            mapping_model.create({
                'role': role,
                'user_id': approver_user.id,
                'active': True,
            })

        return approver_user

    def _generate_approval_lines_from_rules(self):
        role_order = {'l1': 1, 'l2': 2, 'l3': 3}
        level_to_roles = {
            'l1': ['l1'],
            'l2': ['l1', 'l2'],
            'l3': ['l1', 'l2', 'l3'],
        }
        for request in self:
            if not request.line_ids:
                raise ValidationError(_("Please add request lines before submitting for approval."))

            required_level_rank = 0
            default_rule = self.env['rental.request.approval.rule'].search([
                ('active', '=', True),
                ('is_default', '=', True),
            ], limit=1)

            for line in request.line_ids:
                rule = self.env['rental.request.approval.rule'].search([
                    ('active', '=', True),
                    ('is_default', '=', False),
                    ('brand_ids', 'in', line.brand_id.id),
                    ('min_quantity', '<=', line.quantity),
                    '|', ('max_quantity', '=', False), ('max_quantity', '>=', line.quantity),
                ], order='sequence asc, min_quantity desc, id asc', limit=1)

                if not rule:
                    if not default_rule:
                        raise ValidationError(_(
                            "No approval rule found for brand %s with quantity %s, and no default rule is configured."
                        ) % (line.brand_id.display_name, line.quantity))
                    rule = default_rule

                required_level_rank = max(required_level_rank, role_order.get(rule.required_level, 0))

            if required_level_rank == 0:
                raise ValidationError(_("Unable to determine approval level from rules."))

            target_level = [key for key, rank in role_order.items() if rank == required_level_rank][0]
            next_cycle = (max(request.approver_ids.mapped('approval_cycle')) if request.approver_ids else 0) + 1

            approver_vals = []
            for role in level_to_roles[target_level]:
                approver_user = request._resolve_approver_user_by_role(role)

                approver_vals.append((0, 0, {
                    'user_id': approver_user.id,
                    'role': role,
                    'state': 'pending',
                    'approval_cycle': next_cycle,
                }))

            request.write({'approver_ids': approver_vals})

    @api.model_create_multi
    def create(self, vals_list):
        type_code_map = {
            'temporary': 'TEMP',
            'new': 'NEW',
        }

        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                sequence_number = self.env['ir.sequence'].next_by_code('rental.request') or '00000'
                request_type_code = type_code_map.get(vals.get('request_type'), 'GEN')

                request_date_value = vals.get('date') or fields.Date.context_today(self)
                request_date = fields.Date.to_date(request_date_value)
                formatted_date = request_date.strftime('%Y%m%d')

                vals['name'] = f"RR/{request_type_code}/{formatted_date}/{sequence_number}"

        return super().create(vals_list)

    def copy(self, default=None):
        default = dict(default or {})
        default['name'] = 'New'
        return super().copy(default)

    @api.depends('approver_ids.state', 'approver_ids.role', 'approver_ids.user_id', 'state')
    def _compute_next_approver(self):
        role_order = {'l1': 1, 'l2': 2, 'l3': 3}
        for request in self:
            pending_approvers = request.approver_ids.filtered(
                lambda approver: approver.state == 'pending' # type: ignore
            ).sorted(key=lambda approver: role_order.get(approver.role, 99))

            next_approver = pending_approvers[:1]
            request.next_approver_id = next_approver.user_id if next_approver else False # type: ignore

            if request.state == 'approved':
                request.approver_stage = 'done'
            elif next_approver:
                request.approver_stage = next_approver.role # type: ignore
            else:
                request.approver_stage = 'none'

    @api.depends('approver_ids.state', 'approver_ids.role', 'approver_ids.user_id', 'state')
    def _compute_current_user_approval(self):
        role_order = {'l1': 1, 'l2': 2, 'l3': 3}
        current_user = self.env.user
        is_admin = current_user.has_group('base.group_system')
        for request in self:
            next_pending = request.approver_ids.filtered(
                lambda approver: approver.state == 'pending' # type: ignore
            ).sorted(key=lambda approver: role_order.get(approver.role, 99))[:1]

            request.current_pending_approval_id = next_pending or False # type: ignore

            if request.state == 'waiting' and next_pending and next_pending.user_id == current_user: # type: ignore
                request.can_current_user_approve = True
                request.current_user_approval_id = next_pending # type: ignore
            else:
                request.can_current_user_approve = False
                request.current_user_approval_id = False

            request.can_current_user_delegate = bool(
                request.state == 'waiting'
                and next_pending
                and (
                    next_pending.user_id == current_user # type: ignore
                    or is_admin
                )
            )

    def _open_approval_action_wizard(self, action_type):
        self.ensure_one()
        if not self.can_current_user_approve or not self.current_user_approval_id:
            raise ValidationError(_("You are not allowed to process this request at the current stage."))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Approval Action'),
            'res_model': 'rental.request.approval.action.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_request_id': self.id,
                'default_approval_id': self.current_user_approval_id.id,
                'default_action_type': action_type,
            },
        }

    def action_open_accept_wizard(self):
        self.ensure_one()
        return self._open_approval_action_wizard('approve')

    def action_open_reject_wizard(self):
        self.ensure_one()
        return self._open_approval_action_wizard('reject')

    def action_open_delegate_wizard(self):
        self.ensure_one()

        if not self.current_pending_approval_id:
            raise ValidationError(_("No pending approval stage found for this request."))

        is_admin = self.env.user.has_group('base.group_system')
        if self.current_pending_approval_id.user_id != self.env.user and not is_admin:
            raise ValidationError(_("Only the assigned approver or administrator can delegate this stage."))

        if self.state != 'waiting':
            raise ValidationError(_("Delegation is only available when request is waiting for approval."))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Delegate Approval'),
            'res_model': 'rental.request.delegate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_request_id': self.id,
                'default_approval_id': self.current_pending_approval_id.id,
            },
        }

    def action_submit_for_approval(self):
        for request in self:
            request._generate_approval_lines_from_rules()
            request.state = 'waiting'
            request._send_next_approver_notification(is_reminder=False)

    def action_send_notification_to_current_approver(self):
        if not self.env.user.has_group('base.group_system'):
            raise ValidationError(_("Only administrator can send manual approval notifications."))

        for request in self:
            if request.state != 'waiting':
                continue
            request._send_next_approver_notification(is_reminder=True)

    def action_admin_reject_request(self):
        if not self.env.user.has_group('base.group_system'):
            raise ValidationError(_("Only administrator can manually reject request."))

        for request in self:
            pending_approvals = request.approver_ids.filtered(
                lambda approver: approver.state == 'pending' # type: ignore
            )
            if pending_approvals:
                pending_approvals.with_context(skip_approval_write_check=True).write({
                    'state': 'rejected',
                    'action_date': fields.Datetime.now(),
                })

            request.state = 'rejected'
            request.message_post(body=_(
                "Request was manually rejected by administrator."
            ))

    def _send_next_approver_notification(self, is_reminder=False):
        self.ensure_one()
        if self.state not in ('waiting', 'new'):
            return

        role_order = {'l1': 1, 'l2': 2, 'l3': 3}
        next_approval = self.approver_ids.filtered(
            lambda approver: approver.state == 'pending' # type: ignore
        ).sorted(key=lambda approver: role_order.get(approver.role, 99))[:1]

        if not next_approval or not next_approval.user_id.partner_id: # type: ignore
            return

        title = _("Reminder: Approval Needed for %s") if is_reminder else _("Approval Needed for %s")
        self.message_notify( # type: ignore
            partner_ids=[next_approval.user_id.partner_id.id], # type: ignore
            subject=title % self.display_name,
            body=_(
                "Rental request <b>%s</b> is awaiting your approval at stage <b>%s</b>."
            ) % (self.display_name, next_approval.role.upper()), # type: ignore
        )

    @api.model
    def _cron_send_pending_approval_reminders(self):
        self.env['rental.request.approver.delegate'].sync_pending_approvals()
        
        batch_size = 100
        offset = 0
        
        while True:
            waiting_requests = self.search([
                ('state', '=', 'waiting'),
                ('approver_ids.state', '=', 'pending'),
            ], limit=batch_size, offset=offset)
            
            if not waiting_requests:
                break
            
            for request in waiting_requests:
                request._send_next_approver_notification(is_reminder=True)
            
            offset += batch_size