{
    'name': 'Sales Quotation Feedback',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Ask customers why a quotation was not accepted, using a survey',
    'description': """
Sales Quotation Feedback
========================
Automatically sends a short survey to customers who did not answer a quotation
(or who rejected it online), links the answers to the sale order and gives the
sales team a report of the reasons why quotations are lost.
    """,
    'author': 'Arionyx Solutions',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'survey'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/survey_data.xml',
        'data/mail_template_data.xml',
        'data/ir_cron_data.xml',
        'views/sale_quote_feedback_views.xml',
        'views/sale_order_views.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'sequence': 1,
    'price': 25,
    'currency': 'USD',
}
