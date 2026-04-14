{
  "name": "Rental Apps",
  "summary": "Butuh mobil? rentalin ajah",
  "version": "19.0.1.0.0",
  "author": "thearinazs",
  "license": "LGPL-3",
  "depends": ["base", "fleet", "mail"],
  "data": [
    "security/res_groups.xml",
    "security/ir.model.access.csv",
    "data/rental_request_sequence.xml",
    "data/rental_request_brand_data.xml",
    "data/rental_request_approval_rule_data.xml",
    "data/rental_request_approver_users_data.xml",
    "data/rental_request_approver_mapping_data.xml",
    
    "views/rental_request_views.xml",
    "views/rental_request_approval_action_wizard_views.xml",
    "views/rental_request_delegate_wizard_views.xml",
    "views/rental_request_line_views.xml",
    "views/rental_request_approval_views.xml",
    "views/rental_request_approval_rule_views.xml",
    "views/rental_request_approver_mapping_views.xml",
    "views/rental_request_approver_delegate_views.xml",
    "views/rental_user_views.xml",
    
    "views/rental_menus.xml",
    "data/rental_approval_cron.xml"
  ],
  "application": True
} # pyright: ignore[reportUnusedExpression]