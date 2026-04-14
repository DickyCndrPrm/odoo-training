{
  "name": "Real Estate",
  "summary": "Module Real Eestate aih",
  "version": "19.0.1.0.0",
  "author": "thearinazs",
  "license": "LGPL-3",
  "depends": ["base"],
  "data": [
    # Security
    "security/res_groups.xml",
    "security/ir.model.access.csv",
    
    # Views
    "views/estate_property_views.xml",
    "views/estate_property_tag_views.xml",
    "views/estate_property_offer_views.xml",
    "views/estate_property_type_views.xml",
    "views/estate_property_user_views.xml",
    
    # Menu
    "views/estate_menus.xml"
    ],
  "demo": [
    "demo/demo.xml"
  ],
  "application": True
} # pyright: ignore[reportUnusedExpression]