import { Component, onWillStart, proxy } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// Owl 3 component: proxy() instead of useState, no static props,
// template members are prefixed with "this.".
export class AsAccountDashboard extends Component {
    static template = "as_account_dashboard.Dashboard";

    periods = [
        { value: "this_month", label: "This month" },
        { value: "last_month", label: "Last month" },
        { value: "this_quarter", label: "This quarter" },
        { value: "last_quarter", label: "Last quarter" },
        { value: "this_year", label: "This year" },
        { value: "last_year", label: "Last year" },
        { value: "last_30", label: "Last 30 days" },
        { value: "custom", label: "Custom range" },
    ];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = proxy({
            loading: true,
            filters: {
                period: "this_month",
                date_from: "",
                date_to: "",
                journal_id: false,
                user_id: false,
                compare: true,
            },
            data: {},
            cashDetail: null,
        });
        onWillStart(() => this.load());
    }

    // ------------------------------------------------------------ data
    async load() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "as.account.dashboard",
                "get_dashboard_data",
                [],
                { filters: { ...this.state.filters } }
            );
            // seed the custom range with the resolved dates
            if (!this.state.filters.date_from) {
                this.state.filters.date_from = data.resolved.date_from;
                this.state.filters.date_to = data.resolved.date_to;
            }
            this.state.data = data;
        } finally {
            this.state.loading = false;
        }
    }

    async setFilter(name, value) {
        if (name === "journal_id" || name === "user_id") {
            value = value ? parseInt(value, 10) : false;
        }
        this.state.filters[name] = value;
        if (name === "period" && value !== "custom") {
            this.state.filters.date_from = "";
            this.state.filters.date_to = "";
        }
        await this.load();
    }

    // ------------------------------------------------------------ format
    money(value) {
        return new Intl.NumberFormat(undefined, {
            style: "currency",
            currency: this.state.data.currency_name || "USD",
            currencyDisplay: "narrowSymbol", // "$" instead of "US$"
            maximumFractionDigits: 0,
        }).format(value || 0);
    }

    compact(value) {
        return new Intl.NumberFormat(undefined, {
            notation: "compact",
            maximumFractionDigits: 1,
        }).format(value || 0);
    }

    kpiValue(kpi) {
        if (kpi.kind === "percent") {
            return `${(kpi.value || 0).toFixed(1)}%`;
        }
        return this.money(kpi.value);
    }

    deltaText(kpi) {
        const arrow = kpi.delta >= 0 ? "▲" : "▼";
        return `${arrow} ${Math.abs(kpi.delta)}%`;
    }

    spark(key) {
        const months = this.state.data.months || [];
        const pick = {
            income: (m) => m.income,
            expense: (m) => m.expense,
            net: (m) => m.income - m.expense,
        }[key];
        if (!pick || months.length < 2) {
            return "";
        }
        const vals = months.map(pick);
        const lo = Math.min(...vals);
        const hi = Math.max(...vals);
        const span = hi - lo || 1;
        return vals
            .map((v, i) => `${((i * 100) / (vals.length - 1)).toFixed(1)},${(28 - ((v - lo) / span) * 26).toFixed(1)}`)
            .join(" ");
    }

    get periodLabel() {
        const r = this.state.data.resolved || {};
        return `${r.date_from} → ${r.date_to}`;
    }

    get compareLabel() {
        const r = this.state.data.resolved || {};
        return `${r.prev_from} → ${r.prev_to}`;
    }

    // ------------------------------------------------------------ charts
    _nice(value) {
        if (value <= 0) {
            return 1;
        }
        const exp = Math.pow(10, Math.floor(Math.log10(value)));
        const f = value / exp;
        const nf = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10;
        return nf * exp;
    }

    get trend() {
        const months = this.state.data.months || [];
        const W = 640, H = 250, L = 46, R = 10, T = 12, B = 28;
        const innerW = W - L - R;
        const innerH = H - T - B;
        const nets = months.map((m) => m.income - m.expense);
        const hi = this._nice(Math.max(1, ...months.map((m) => Math.max(m.income, m.expense))));
        const lowRaw = Math.min(0, ...nets);
        const lo = lowRaw < 0 ? -this._nice(-lowRaw) : 0;
        const y = (v) => T + innerH * (1 - (v - lo) / (hi - lo));
        const step = innerW / Math.max(months.length, 1);
        const bw = Math.max(4, Math.min(14, step / 3));
        const zero = y(0);
        const bars = months.map((m, i) => {
            const cx = L + step * i + step / 2;
            const yi = y(m.income);
            const ye = y(m.expense);
            return {
                label: m.label,
                cx,
                xi: cx - bw - 1,
                xe: cx + 1,
                w: bw,
                yi: Math.min(yi, zero),
                hInc: Math.abs(zero - yi),
                ye: Math.min(ye, zero),
                hExp: Math.abs(zero - ye),
                ny: y(m.income - m.expense),
                title: `${m.label}\nIncome: ${this.money(m.income)}\nExpenses: ${this.money(m.expense)}\nNet: ${this.money(m.income - m.expense)}`,
            };
        });
        const ticks = [0, 1, 2, 3, 4].map((k) => {
            const v = lo + ((hi - lo) * k) / 4;
            return { y: y(v), label: this.compact(v) };
        });
        return {
            viewBox: `0 0 ${W} ${H}`,
            left: L,
            right: W - R,
            labelY: H - 8,
            bars,
            ticks,
            zero,
            line: bars.map((b) => `${b.cx},${b.ny}`).join(" "),
        };
    }

    get donut() {
        const segs = this.state.data.payment_status || [];
        const total = segs.reduce((s, x) => s + x.value, 0);
        let acc = 0;
        const arcs = segs.map((s) => {
            const pct = total ? (s.value * 100) / total : 0;
            const arc = {
                key: s.key,
                label: s.label,
                tone: s.tone,
                value: s.value,
                pct: pct.toFixed(1),
                dash: `${pct} ${100 - pct}`,
                offset: 25 - acc,
                domain: s.domain,
            };
            acc += pct;
            return arc;
        });
        return { total, arcs };
    }

    get cashChart() {
        const d = this.state.cashDetail;
        const months = (d && d.months) || [];
        const W = 640, H = 240, L = 52, R = 12, T = 14, B = 28;
        const innerW = W - L - R;
        const innerH = H - T - B;
        const vals = months.map((m) => m.balance);
        const hiRaw = Math.max(0, ...vals);
        const loRaw = Math.min(0, ...vals);
        const hi = hiRaw > 0 ? this._nice(hiRaw) : 0;
        const lo = loRaw < 0 ? -this._nice(-loRaw) : 0;
        const span = hi - lo || 1;
        const y = (v) => T + innerH * (1 - (v - lo) / span);
        const step = innerW / Math.max(months.length - 1, 1);
        const pts = months.map((m, i) => ({
            x: L + step * i,
            y: y(m.balance),
            label: m.label,
            title: `${m.label}\nBalance: ${this.money(m.balance)}\nMovement: ${this.money(m.change)}`,
        }));
        const zero = y(0);
        const ticks = [0, 1, 2, 3, 4].map((k) => {
            const v = lo + (span * k) / 4;
            return { y: y(v), label: this.compact(v) };
        });
        return {
            viewBox: `0 0 ${W} ${H}`,
            left: L,
            right: W - R,
            labelY: H - 8,
            zero,
            ticks,
            pts,
            line: pts.map((q) => `${q.x},${q.y}`).join(" "),
            area: pts.length
                ? `${pts[0].x},${zero} ${pts.map((q) => `${q.x},${q.y}`).join(" ")} ${pts[pts.length - 1].x},${zero}`
                : "",
        };
    }

    // ------------------------------------------------------------ actions
    async openCash(item) {
        this.state.cashDetail = { loading: true, name: item.name, months: [] };
        try {
            const detail = await this.orm.call(
                "as.account.dashboard",
                "get_cash_trend",
                [item.journal_id]
            );
            this.state.cashDetail = { loading: false, ...detail };
        } catch (error) {
            this.state.cashDetail = null;
            throw error;
        }
    }

    closeCash() {
        this.state.cashDetail = null;
    }

    onOverlayClick(ev) {
        if (ev.target === ev.currentTarget) {
            this.closeCash();
        }
    }

    openCashEntries() {
        const d = this.state.cashDetail;
        if (!d || !d.domain) {
            return;
        }
        this.openRecords({
            label: d.name,
            domain: d.domain,
            res_model: "account.move.line",
        });
        this.closeCash();
    }

    openRecords(item) {
        if (!item.domain) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: item.label || item.name,
            res_model: item.res_model || "account.move",
            views: [[false, "list"], [false, "form"]],
            domain: item.domain,
            target: "current",
        });
    }
}

registry.category("actions").add("as_account_dashboard", AsAccountDashboard);
