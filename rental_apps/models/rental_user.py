from odoo import fields, models


class RentalUser(models.Model):
  _inherit = 'res.users' # type: ignore

  rental_approval_level = fields.Selection([
    ('none', 'No Approval Level'),
    ('l1', 'Manager'),
    ('l2', 'Senior Manager'),
    ('l3', 'Director'),
  ], string="Rental Approval Level", compute="_compute_rental_approval_level", inverse="_inverse_rental_approval_level") # pyright: ignore[reportArgumentType]

  def _get_rental_group_by_level(self):
    return {
      'l1': self.env.ref('rental_apps.group_rental_approver_l1', raise_if_not_found=False),
      'l2': self.env.ref('rental_apps.group_rental_approver_l2', raise_if_not_found=False),
      'l3': self.env.ref('rental_apps.group_rental_approver_l3', raise_if_not_found=False),
    }

  def _compute_rental_approval_level(self):
    group_by_level = self._get_rental_group_by_level()
    group_l1 = group_by_level.get('l1')
    group_l2 = group_by_level.get('l2')
    group_l3 = group_by_level.get('l3')

    for user in self:
      level = 'none'
      user_groups = user.group_ids # type: ignore
      if group_l3 and group_l3 in user_groups:
        level = 'l3'
      elif group_l2 and group_l2 in user_groups:
        level = 'l2'
      elif group_l1 and group_l1 in user_groups:
        level = 'l1'

      user.rental_approval_level = level

  def _inverse_rental_approval_level(self):
    group_by_level = self._get_rental_group_by_level()
    all_groups = [group for group in group_by_level.values() if group]

    for user in self:
      commands = [(3, group.id) for group in all_groups]
      selected_level = user.rental_approval_level or 'none'
      target_group = group_by_level.get(selected_level)
      if target_group:
        commands.append((4, target_group.id))

      user.write({'group_ids': commands})
  
