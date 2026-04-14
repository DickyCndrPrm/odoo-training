from odoo import fields, models
from odoo.exceptions import AccessError

class EstateProperty(models.Model):
  _inherit = "estate.property" # type: ignore
  
  def action_sold_property(self):
    if not self.env['account.move'].check_access_rights('create', False):
        try:
            self.check_access_rights("write")
            self.check_access_rule("write")
        except AccessError:
            return self.env['account.move']
    
    res = super().action_sold_property() # type: ignore

    for record in self:
        if record.partner_id: # type: ignore
            self.env['account.move'].create({
                'partner_id': record.partner_id.id, # type: ignore
                'move_type': 'out_invoice',
            })

    return res