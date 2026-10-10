from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .dashboard_utils import month_starts, pct_delta, resolve_period, to_int

OUT_TYPES = ['out_invoice', 'out_refund']
IN_TYPES = ['in_invoice', 'in_refund']
TOP_LIMIT = 5


class AsAccountDashboard(models.AbstractModel):
    _name = 'as.account.dashboard'
    _description = 'Accounting Dashboard Data'

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------
    @api.model
    def _get_dashboard_role(self):
        user = self.env.user
        if user.has_group('account.group_account_manager'):
            return 'manager'
        if user.has_group('account.group_account_user'):
            return 'accountant'
        if user.has_group('account.group_account_invoice'):
            return 'billing'
        if user.has_group('account.group_account_readonly'):
            return 'readonly'
        return False

    # ------------------------------------------------------------------
    # Aggregation helpers (multi-company + multi-currency safe)
    # ------------------------------------------------------------------
    @api.model
    def _grouped(self, model, domain, field, groupby, date):
        """Sum `field` grouped by `groupby`; every amount is converted from the
        company currency to the currency of the *current* company.
        Returns {tuple_of_group_keys: amount}."""
        target = self.env.company.currency_id
        rows = self.env[model]._read_group(
            domain, ['company_id', *groupby], [f'{field}:sum'])
        result = {}
        for row in rows:
            company, *keys, amount = row
            value = company.currency_id._convert(
                amount or 0.0, target, self.env.company, date)
            key = tuple(keys)
            result[key] = result.get(key, 0.0) + value
        return result

    @api.model
    def _sum_moves(self, domain, field, date):
        return sum(self._grouped('account.move', domain, field, [], date).values())

    # ------------------------------------------------------------------
    # Pieces of the dashboard
    # ------------------------------------------------------------------
    @api.model
    def _aging(self, base_dom, sign, today):
        t = fields.Date.to_string
        due = 'invoice_date_due'
        specs = [
            ('not_due', self.env._("Not due"), 'success',
             ['|', (due, '>=', t(today)), (due, '=', False)]),
            ('d1_30', '1-30', 'info',
             [(due, '<', t(today)), (due, '>=', t(today - relativedelta(days=30)))]),
            ('d31_60', '31-60', 'warning',
             [(due, '<', t(today - relativedelta(days=30))),
              (due, '>=', t(today - relativedelta(days=60)))]),
            ('d61_90', '61-90', 'orange',
             [(due, '<', t(today - relativedelta(days=60))),
              (due, '>=', t(today - relativedelta(days=90)))]),
            ('d90', '90+', 'danger',
             [(due, '<', t(today - relativedelta(days=90)))]),
        ]
        cd = [('company_id', 'in', self.env.companies.ids)]
        buckets = []
        for key, label, tone, dom in specs:
            value = sign * self._sum_moves(
                cd + base_dom + dom, 'amount_residual_signed', today)
            buckets.append({'key': key, 'label': label, 'tone': tone,
                            'value': value, 'domain': base_dom + dom})
        top = max([abs(b['value']) for b in buckets] + [1])
        for b in buckets:
            b['pct'] = round(abs(b['value']) * 100 / top, 1)
        return buckets

    @api.model
    def _top_partners(self, base_dom, sign, today):
        cd = [('company_id', 'in', self.env.companies.ids)]
        grouped = self._grouped('account.move', cd + base_dom,
                                'amount_residual_signed', ['partner_id'], today)
        rows = []
        for (partner,), value in grouped.items():
            rows.append((partner, sign * value))
        rows.sort(key=lambda r: r[1], reverse=True)
        rows = [r for r in rows if r[1] > 0][:TOP_LIMIT]
        top = max([r[1] for r in rows] + [1])
        return [{
            'id': partner.id if partner else 0,
            'name': partner.display_name if partner else self.env._("Unknown"),
            'value': value,
            'pct': round(value * 100 / top, 1),
            'domain': base_dom + [('partner_id', '=', partner.id if partner else False)],
        } for partner, value in rows]

    # ------------------------------------------------------------------
    # Public method called by the OWL client action
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_data(self, filters=None):
        role = self._get_dashboard_role()
        if not role:
            raise AccessError(self.env._("You are not allowed to see this dashboard."))

        filters = filters or {}
        t = fields.Date.to_string
        today = fields.Date.context_today(self)
        per = resolve_period(filters, today)
        start, end = per['start'], per['end']
        compare = bool(filters.get('compare', True))
        journal_id = to_int(filters.get('journal_id'))
        user_id = to_int(filters.get('user_id'))

        companies = self.env.companies            # follows the company switcher
        cd = [('company_id', 'in', companies.ids)]
        main_currency = self.env.company.currency_id

        # Everything below runs with the user's rights (no sudo): standard
        # record rules and multi-company rules are applied by the ORM.
        journal_dom = [('journal_id', '=', journal_id)] if journal_id else []
        out_x = journal_dom + ([('invoice_user_id', '=', user_id)] if user_id else [])
        in_x = journal_dom

        open_dom = [('state', '=', 'posted'),
                    ('payment_state', 'in', ['not_paid', 'partial'])]
        recv_dom = open_dom + [('move_type', 'in', OUT_TYPES)] + out_x
        pay_dom = open_dom + [('move_type', 'in', IN_TYPES)] + in_x
        overdue_dom = recv_dom + [('invoice_date_due', '<', t(today))]
        soon_dom = pay_dom + [('invoice_date_due', '>=', t(today)),
                              ('invoice_date_due', '<=', t(today + relativedelta(days=7)))]
        draft_out_dom = [('state', '=', 'draft'), ('move_type', '=', 'out_invoice')] + out_x
        draft_in_dom = [('state', '=', 'draft'), ('move_type', '=', 'in_invoice')] + in_x

        def period_dom(s, e, types, extra):
            return [('state', '=', 'posted'), ('invoice_date', '>=', t(s)),
                    ('invoice_date', '<', t(e)), ('move_type', 'in', types)] + extra

        def flow(s, e):
            inc = self._sum_moves(cd + period_dom(s, e, OUT_TYPES, out_x),
                                  'amount_total_signed', today)
            exp = -self._sum_moves(cd + period_dom(s, e, IN_TYPES, in_x),
                                   'amount_total_signed', today)
            return inc, exp

        receivable = self._sum_moves(cd + recv_dom, 'amount_residual_signed', today)
        payable = -self._sum_moves(cd + pay_dom, 'amount_residual_signed', today)
        overdue = self._sum_moves(cd + overdue_dom, 'amount_residual_signed', today)
        income, expense = flow(start, end)
        net = income - expense
        if compare:
            p_income, p_expense = flow(per['prev_start'], per['prev_end'])
            p_net = p_income - p_expense

        # ---- payment status of customer invoices issued in the period
        status_map = {
            'paid': (self.env._("Paid"), 'success', ['paid', 'in_payment']),
            'partial': (self.env._("Partially paid"), 'warning', ['partial']),
            'not_paid': (self.env._("Not paid"), 'danger', ['not_paid', 'blocked']),
        }
        out_period = period_dom(start, end, OUT_TYPES, out_x)
        by_state = self._grouped('account.move', cd + out_period,
                                 'amount_total_signed', ['payment_state'], today)
        payment_status = []
        for key, (label, tone, states) in status_map.items():
            value = sum(by_state.get((s,), 0.0) for s in states)
            payment_status.append({
                'key': key, 'label': label, 'tone': tone, 'value': max(value, 0.0),
                'domain': out_period + [('payment_state', 'in', states)]})
        total_invoiced = sum(p['value'] for p in payment_status)
        paid_value = next(p['value'] for p in payment_status if p['key'] == 'paid')
        collection_rate = paid_value * 100 / total_invoiced if total_invoiced else 0.0

        # ---- KPI cards
        def kpi(key, label, kind, value, domain=False, tone='primary',
                cur=None, prev=None, up_good=True):
            delta = pct_delta(cur, prev) if (compare and cur is not None) else None
            return {
                'key': key, 'label': label, 'kind': kind, 'value': value,
                'domain': domain, 'tone': tone,
                'has_delta': delta is not None, 'delta': delta or 0.0,
                'delta_good': (delta or 0.0) >= 0 if up_good else (delta or 0.0) <= 0,
            }

        kpis = [
            kpi('income', self.env._("Income"), 'money', income,
                period_dom(start, end, OUT_TYPES, out_x), 'success',
                income, p_income if compare else None),
            kpi('expense', self.env._("Expenses"), 'money', expense,
                period_dom(start, end, IN_TYPES, in_x), 'warning',
                expense, p_expense if compare else None, up_good=False),
            kpi('net', self.env._("Net result"), 'money', net, False,
                'purple' if net >= 0 else 'danger',
                net, p_net if compare else None),
            kpi('collection', self.env._("Collection rate"), 'percent',
                collection_rate, out_period,
                ('info' if not total_invoiced else
                 'success' if collection_rate >= 80 else
                 'warning' if collection_rate >= 50 else 'danger')),
            kpi('receivable', self.env._("Receivable"), 'money', receivable,
                recv_dom, 'primary'),
            kpi('overdue', self.env._("Overdue"), 'money', overdue,
                overdue_dom, 'danger' if overdue > 0 else 'success'),
            kpi('payable', self.env._("Payable"), 'money', payable,
                pay_dom, 'orange'),
        ]

        # ---- cash & bank: Adviser / Manager group only
        show_cash = role == 'manager'
        cash_list, cash_total = [], 0.0
        if show_cash:
            journals = self.env['account.journal'].search(
                cd + [('type', 'in', ('bank', 'cash'))])
            info = {j.default_account_id.id: (j.id, j.name)
                    for j in journals if j.default_account_id}
            if info:
                bal = self._grouped(
                    'account.move.line',
                    [('account_id', 'in', list(info)), ('parent_state', '=', 'posted')],
                    'balance', ['account_id'], today)
                rows = sorted(
                    ((info[a.id][1], v, info[a.id][0]) for (a,), v in bal.items() if a.id in info),
                    key=lambda r: abs(r[1]), reverse=True)
                cash_total = sum(r[1] for r in rows)
                top = max([abs(r[1]) for r in rows] + [1])
                cash_list = [{'journal_id': r[2], 'name': r[0], 'value': r[1],
                              'pct': round(abs(r[1]) * 100 / top, 1)}
                             for r in rows[:6]]
            kpis.append(kpi('cash', self.env._("Cash & Bank"), 'money', cash_total,
                            False, 'teal'))

        # ---- needs attention
        Move = self.env['account.move']
        attention = [
            {'key': 'overdue', 'label': self.env._("Overdue customer invoices"),
             'count': Move.search_count(cd + overdue_dom), 'domain': overdue_dom,
             'tone': 'danger'},
            {'key': 'soon', 'label': self.env._("Vendor bills due in 7 days"),
             'count': Move.search_count(cd + soon_dom), 'domain': soon_dom,
             'tone': 'warning'},
            {'key': 'draft_out', 'label': self.env._("Draft customer invoices"),
             'count': Move.search_count(cd + draft_out_dom), 'domain': draft_out_dom,
             'tone': 'secondary'},
            {'key': 'draft_in', 'label': self.env._("Draft vendor bills"),
             'count': Move.search_count(cd + draft_in_dom), 'domain': draft_in_dom,
             'tone': 'secondary'},
        ]
        # reconciliation is a daily accountant task, not a balance: keep it
        # visible to Accountants as well as Managers
        if role in ('manager', 'accountant'):
            try:
                BSL = self.env['account.bank.statement.line']
                if 'is_reconciled' in BSL._fields:
                    dom = [('is_reconciled', '=', False)]
                    attention.append({
                        'key': 'unreconciled',
                        'label': self.env._("Bank lines to reconcile"),
                        'count': BSL.search_count(cd + dom), 'domain': dom,
                        'res_model': 'account.bank.statement.line', 'tone': 'info'})
            except AccessError:
                pass

        # ---- 12 months trend (ending with the month of the selected period)
        months_list = month_starts(end, 12)
        first, last_excl = months_list[0], months_list[-1] + relativedelta(months=1)

        def month_map(types, extra):
            dom = cd + [('state', '=', 'posted'), ('invoice_date', '>=', t(first)),
                        ('invoice_date', '<', t(last_excl)), ('move_type', 'in', types)] + extra
            grouped = self._grouped('account.move', dom, 'amount_total_signed',
                                    ['invoice_date:month'], today)
            return {(k[0].year, k[0].month): v for k, v in grouped.items() if k[0]}

        inc_map = month_map(OUT_TYPES, out_x)
        exp_map = month_map(IN_TYPES, in_x)
        months = []
        for m in months_list:
            ym = (m.year, m.month)
            months.append({'label': m.strftime('%b %y'),
                           'income': inc_map.get(ym, 0.0),
                           'expense': -exp_map.get(ym, 0.0)})

        # ---- filter options (read with the user's own rights)
        journal_recs = self.env['account.journal'].search(
            cd + [('type', 'in', ('sale', 'purchase'))])
        multi = len(companies) > 1
        journals = [{'id': j.id,
                     'name': f"{j.name} ({j.company_id.name})" if multi else j.name}
                    for j in journal_recs]
        users = []
        for (u,), _v in self._grouped(
                'account.move',
                cd + [('state', '=', 'posted'), ('move_type', 'in', OUT_TYPES),
                      ('invoice_user_id', '!=', False)],
                'amount_total_signed', ['invoice_user_id'], today).items():
            if u:
                users.append({'id': u.id, 'name': u.name})
        users.sort(key=lambda u: u['name'])

        return {
            'role': role,
            'show_cash': show_cash,
            'currency_name': main_currency.name,
            'mixed_currencies': len(companies.currency_id) > 1,
            'companies': companies.mapped('name'),
            'resolved': {
                'period': per['period'],
                'date_from': t(start), 'date_to': t(end - relativedelta(days=1)),
                'prev_from': t(per['prev_start']),
                'prev_to': t(per['prev_end'] - relativedelta(days=1)),
            },
            'options': {'journals': journals, 'users': users},
            'kpis': kpis,
            'attention': attention,
            'months': months,
            'payment_status': payment_status,
            'aging_receivable': self._aging(recv_dom, 1, today),
            'aging_payable': self._aging(pay_dom, -1, today),
            'top_customers': self._top_partners(recv_dom, 1, today),
            'top_vendors': self._top_partners(pay_dom, -1, today),
            'cash': cash_list,
        }

    # ------------------------------------------------------------------
    # Balance trend of one bank / cash journal (opened by clicking a row of
    # the "Cash & Bank by journal" widget). Adviser / Manager group only.
    # ------------------------------------------------------------------
    @api.model
    def get_cash_trend(self, journal_id, months=12):
        if self._get_dashboard_role() != 'manager':
            raise AccessError(self.env._("You are not allowed to see this chart."))

        t = fields.Date.to_string
        journal = self.env['account.journal'].search([
            ('id', '=', to_int(journal_id)),
            ('type', 'in', ('bank', 'cash')),
            ('company_id', 'in', self.env.companies.ids),
        ], limit=1)
        account = journal.default_account_id
        if not journal or not account:
            raise UserError(self.env._("This journal cannot be displayed."))

        today = fields.Date.context_today(self)
        end = today.replace(day=1) + relativedelta(months=1)
        starts = month_starts(end, max(2, min(int(months or 12), 36)))
        base = [('account_id', '=', account.id), ('parent_state', '=', 'posted'),
                ('company_id', '=', journal.company_id.id)]

        opening = sum(self._grouped(
            'account.move.line', base + [('date', '<', t(starts[0]))],
            'balance', [], today).values())
        moves = self._grouped(
            'account.move.line',
            base + [('date', '>=', t(starts[0])), ('date', '<', t(end))],
            'balance', ['date:month'], today)
        by_month = {(k[0].year, k[0].month): v for k, v in moves.items() if k[0]}

        running, points = opening, []
        for m in starts:
            change = by_month.get((m.year, m.month), 0.0)
            running += change
            points.append({'label': m.strftime('%b %y'), 'balance': running,
                           'change': change})
        balances = [p['balance'] for p in points]
        return {
            'journal_id': journal.id,
            'name': journal.name,
            'currency_name': self.env.company.currency_id.name,
            'months': points,
            'current': balances[-1],
            'highest': max(balances),
            'lowest': min(balances),
            'change': balances[-1] - opening,
            'domain': [('account_id', '=', account.id), ('parent_state', '=', 'posted')],
        }
