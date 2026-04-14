from odoo import api, fields, models

class ProperyType(models.Model):
  _name = "estate.property.type"
  _description = ""
  _order = "sequence, name"
  
  name = fields.Char(string="Name", required=True)
  property_ids = fields.One2many("estate.property", "property_type_id")
  sequence = fields.Integer("Sequence", default=1, help="Used to order stages. Lower is better.")
  offer_ids = fields.One2many("estate.property.offer", "property_type_id")
  offer_count = fields.Integer(compute="_compute_offer_count")
  
  _check_name = models.Constraint(
    'UNIQUE(name)',
    'The type name should be unique'
  )
  
  @api.depends("offer_ids")
  def _compute_offer_count(self):
    for record in self:
      record.offer_count = len(record.property_ids.mapped('offer_ids'))

