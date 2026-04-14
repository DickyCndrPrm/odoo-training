from odoo import fields, models

class EstateUser(models.Model):
  _inherit = 'res.users' # type: ignore
  
  property_ids = fields.One2many("estate.property", "user_id", string="Properties",
        domain=[("state", "in", ("new", "received"))])