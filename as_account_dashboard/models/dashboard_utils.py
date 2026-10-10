"""Pure helpers (no Odoo import) so they can be unit-tested easily."""
from datetime import date, datetime

from dateutil.relativedelta import relativedelta

PERIODS = (
    'this_month', 'last_month', 'this_quarter', 'last_quarter',
    'this_year', 'last_year', 'last_30', 'custom',
)


def to_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


def to_int(value):
    try:
        return int(value) if value else False
    except (TypeError, ValueError):
        return False


def resolve_period(filters, today):
    """Return start (inclusive), end (exclusive) and the previous period."""
    period = (filters or {}).get('period') or 'this_month'
    if period not in PERIODS:
        period = 'this_month'

    if period == 'custom':
        d_from = to_date(filters.get('date_from')) or today.replace(day=1)
        d_to = to_date(filters.get('date_to')) or today
        if d_to < d_from:
            d_from, d_to = d_to, d_from
        start, end = d_from, d_to + relativedelta(days=1)
        prev_start, prev_end = start - (end - start), start
    elif period == 'last_30':
        start, end = today - relativedelta(days=29), today + relativedelta(days=1)
        prev_start, prev_end = start - (end - start), start
    else:
        if period.endswith('month'):
            base, step = today.replace(day=1), relativedelta(months=1)
        elif period.endswith('quarter'):
            base = today.replace(month=3 * ((today.month - 1) // 3) + 1, day=1)
            step = relativedelta(months=3)
        else:
            base, step = today.replace(month=1, day=1), relativedelta(years=1)
        if period.startswith('last_'):
            base = base - step
        start, end = base, base + step
        prev_start, prev_end = start - step, start

    return {
        'period': period,
        'start': start, 'end': end,
        'prev_start': prev_start, 'prev_end': prev_end,
    }


def pct_delta(current, previous):
    if not previous:
        return None
    return round((current - previous) * 100.0 / abs(previous), 1)


def month_starts(end_exclusive, count=12):
    """First day of the `count` months ending with the month before `end_exclusive`."""
    last = (end_exclusive - relativedelta(days=1)).replace(day=1)
    first = last - relativedelta(months=count - 1)
    return [first + relativedelta(months=i) for i in range(count)]
