from odoo import models, fields, api

class RentalRequestLine(models.Model):
  _name = "rental.request.line"
  _description = "Rental Request Line Item"
  
  request_id = fields.Many2one('rental.request', string="Rental Request", ondelete='cascade')
  
  brand_id = fields.Many2one('fleet.vehicle.model.brand', string="Product Brand", required=True)
  model_id = fields.Many2one(
    'fleet.vehicle.model',
    string="Product Model",
    required=True,
    domain="[('brand_id', '=', brand_id)]",
  )
  
  quantity = fields.Integer(string="Quantity", default=1, required=True)

  @api.onchange('brand_id')
  def _onchange_brand_id(self):
    if self.model_id and self.model_id.brand_id != self.brand_id:
      self.model_id = False