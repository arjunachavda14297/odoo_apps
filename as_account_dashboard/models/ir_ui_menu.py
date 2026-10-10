import logging
from collections import Counter

from odoo import api, models

_logger = logging.getLogger(__name__)


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _as_dashboard_parent_id(self):
        """Find the root of the Enterprise Accounting app (module
        `account_accountant`) without hard-coding its external id.

        Every menu defined by `account_accountant` is looked up, the root menu
        of each one is computed, and the most common root wins. If the module
        has no menu at all, fall back to the Invoicing root (account.menu_finance).
        """
        data = self.env['ir.model.data'].sudo().search([
            ('module', '=', 'account_accountant'),
            ('model', '=', 'ir.ui.menu'),
        ])
        menus = self.sudo().browse(data.mapped('res_id')).exists()
        roots = Counter(
            int(menu.parent_path.split('/')[0])
            for menu in menus if menu.parent_path
        )
        if roots:
            root = self.sudo().browse(roots.most_common(1)[0][0])
            _logger.info(
                "as_account_dashboard: menu placed under root '%s' (id %s)",
                root.name, root.id)
            return root.id
        fallback = self.env.ref('account.menu_finance')
        _logger.warning(
            "as_account_dashboard: no account_accountant menu found, "
            "using '%s' as parent", fallback.name)
        return fallback.id

    @api.model
    def _as_dashboard_place_menu(self):
        """Called from views/menu.xml (<function>) on every install / upgrade:
        move 'My Dashboard' under the root of the Enterprise Accounting app."""
        menu = self.env.ref(
            'as_account_dashboard.menu_as_account_dashboard',
            raise_if_not_found=False)
        if not menu:
            return
        parent_id = self._as_dashboard_parent_id()
        if menu.parent_id.id != parent_id:
            menu.sudo().write({'parent_id': parent_id})
