{
    'name': 'Accounting Dashboard | Account | Account Dashboard | Dashboard | Dashboard Accounting | invoice | invoice Dashboard',
    'version': '20.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Role-aware accounting dashboard with KPIs, filters, aging and cash charts for the Enterprise Accounting app',
    'description': """
AS Accounting Dashboard
=======================
A modern "My Dashboard" menu inside the Enterprise Accounting app:
KPI cards with period comparison, a 12-month income / expense / net chart,
a "needs attention" list, payment-status donut, aged receivable / payable,
top customers / vendors and a cash & bank balance trend for managers.

Multi-company and multi-currency aware. Data is read with the user's own
rights (no sudo), so Odoo's record rules always apply.
    """,
    'author': 'Arionyx Solutions',
    'company': 'Arionyx Solutions',
    'depends': ['account', 'account_accountant'],
    'data': [
        'security/ir.access.csv',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'as_account_dashboard/static/src/**/*',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
