# AS Accounting Dashboard (Odoo 20)  -  v20.0.1.1.0

Requires Odoo Enterprise: depends on `account_accountant` (the Enterprise Accounting app).
Install: copy `as_account_dashboard` to your addons path, update the apps list,
install "AS Accounting Dashboard". Menu: Accounting app > My Dashboard
(first menu item, so it opens by default).
The parent menu is found automatically from the menus of `account_accountant`
(see models/ir_ui_menu.py), so no root-menu external id is hard-coded. The chosen root is
written in the Odoo log: "as_account_dashboard: menu placed under root ...".
If you prefer a fixed parent, replace the `parent_id` eval in views/menu.xml with ref="...".

## Filters
- Period: this/last month, quarter, year, last 30 days, custom range
- Journal (sales / purchase journals)
- Salesperson (applies to the customer side only; vendor bills have no salesperson)
- Compare with previous period (shows the % change on Income / Expenses / Net)
- Company switcher of Odoo (multi-company) - amounts are converted to the current company currency

## Widgets
KPI cards, 12-month Income / Expenses / Net chart, "Needs attention" list,
payment-status donut, aged receivable, aged payable, top 5 customers, top 5 vendors,
cash & bank by journal (accounting roles only). Everything is clickable and opens the
filtered records.

## Security
Cash & Bank (KPI card + "by journal" widget): Adviser / Manager group only.
"Bank lines to reconcile": Accountants and Managers.
Everything else: Billing, Accountant, Adviser and read-only users.
Data is read WITHOUT sudo, so Odoo's own record rules and the company switcher apply.
Charts are plain SVG/CSS (no Chart.js, no refs) to stay compatible with Owl 3.
