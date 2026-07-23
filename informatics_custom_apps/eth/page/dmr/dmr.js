frappe.pages['dmr'].on_page_load = function(wrapper) {
    new DistilleryProductionReport(wrapper);
};

class DistilleryProductionReport {
    constructor(wrapper) {
        this.wrapper = wrapper;
        this.section_colors = {
            A: '#e3f2fd', B: '#fff3e0', C: '#e8f5e9', D: '#f3e5f5',
            E: '#e0f7fa', F: '#fce4ec', G: '#fff8e1', H: '#efebe9',
            I: '#e8eaf6', J: '#f1f8e9', K: '#e0f2f1', L: '#fbe9e7',
            M: '#ede7f6', N: '#e1f5fe'
        };
        this.page = frappe.ui.make_app_page({
            parent: wrapper,
            title: 'Daily Manufacturing Report',
            single_column: true
        });
        this.make_filters();
        this.make_table_container();
    }

    make_filters() {
        this.company_field = this.page.add_field({
            fieldname: 'company',
            label: 'Company',
            fieldtype: 'MultiSelectList',
            get_data: function(txt) {
                return frappe.db.get_link_options('Company', txt);
            },
            change: () => {
                this.load_plant_options(() => this.reconcile_plant_selection());
            }
        });

        this.plant_field = this.page.add_field({
            fieldname: 'plant',
            label: 'Plant',
            fieldtype: 'MultiSelectList',
            get_data: (txt) => {
                return (this.plant_options || [])
                    .filter(p => p.toLowerCase().includes((txt || '').toLowerCase()))
                    .map(p => ({ value: p, description: '' }));
            },
            change: () => this.refresh()
        });

        this.segment_field = this.page.add_field({
            fieldname: 'segment',
            label: 'Segment',
            fieldtype: 'MultiSelectList',
            get_data: function(txt) {
                // Segment is its own doctype, not Cost Center.
                return frappe.db.get_link_options('Segment', txt);
            },
            change: () => this.refresh()
        });

        this.from_date_field = this.page.add_field({
            fieldname: 'from_date',
            label: 'From Date',
            fieldtype: 'Date',
            default: frappe.datetime.get_today(),
            change: () => this.refresh()
        });

        this.to_date_field = this.page.add_field({
            fieldname: 'to_date',
            label: 'To Date',
            fieldtype: 'Date',
            default: frappe.datetime.get_today(),
            change: () => this.refresh()
        });

        this.page.add_inner_button('Refresh', () => this.refresh());
        this.load_plant_options();
    }

    load_plant_options(done) {
        const companies = this.company_field.get_value();
        frappe.call({
            method: 'informatics_custom_apps.eth.page.dmr.dmr.get_plant_options',
            args: { companies: companies && companies.length ? companies : null },
            callback: (r) => {
                this.plant_options = r.message || [];
                if (done) done();
            }
        });
    }

    // Drops any currently-selected plants that are no longer valid for the
    // newly-selected company(ies), then refreshes the report. Prevents a
    // stale plant filter from one company silently zeroing out the report
    // after the company selection changes.
    reconcile_plant_selection() {
        const selected = this.plant_field.get_value() || [];
        const valid_set = new Set(this.plant_options || []);
        const still_valid = selected.filter(p => valid_set.has(p));

        if (still_valid.length !== selected.length) {
            this.plant_field.set_value(still_valid);
            // set_value triggers the plant field's own change handler,
            // which calls refresh() — avoid double-refreshing.
            return;
        }
        this.refresh();
    }

    make_table_container() {
        this.$wrapper = $(`<div class="distillery-report-wrapper"></div>`).appendTo(this.page.body);

        this.$message = $(`<div class="text-muted" style="padding:20px;">Select Company and Date Range</div>`)
            .appendTo(this.$wrapper);

        this.$card = $(`
            <div class="distillery-report-card">
                <div class="distillery-report-card-title">
                    Daily Manufacturing Report
                    <span class="unit-badge">Values per section UOM</span>
                </div>
                <div class="table-responsive">
                    <table class="distillery-report-table">
                        <thead><tr class="distillery-head-row"></tr></thead>
                        <tbody class="distillery-body"></tbody>
                    </table>
                </div>
            </div>
        `).appendTo(this.$wrapper);

        this.$container = this.$card.find('tbody.distillery-body');
        this.$head_row = this.$card.find('tr.distillery-head-row');

        this.inject_styles();
        this.refresh();
    }

    inject_styles() {
        if (document.getElementById('distillery-report-style')) return;

        $(`<style id="distillery-report-style">

        .distillery-report-wrapper {
            padding: 10px 0 30px;
        }

        .distillery-report-card {
            background: #fff;
            border: 2px solid #d5dde5;
            border-radius: 14px;
            padding: 18px;
            box-shadow: 0 3px 10px rgba(31,39,46,.06);
            overflow-x: auto;
        }

        .distillery-report-card-title {
            font-size: 17px;
            font-weight: 700;
            margin-bottom: 14px;
            color: #24313b;
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }

        .unit-badge {
            font-size: 12px;
            padding: 3px 10px;
            border-radius: 30px;
            font-weight: 600;
            background: #e8f1fb;
            color: #2962a8;
            border: 1px solid #cfe1f6;
        }

        .table-responsive {
            overflow-x: auto;
            overflow-y: auto;
            max-height: 75vh;
            -webkit-overflow-scrolling: touch;
            border-radius: 10px;
            border: 2px solid #aab8c3;
        }

        table.distillery-report-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            font-size: 13px;
            border: none;
            margin: 0;
        }

        .distillery-report-table th,
        .distillery-report-table td {
            padding: 8px 14px;
            border-right: 1px solid #d0dbe4;
            border-bottom: 1px solid #dde5ec;
            text-align: right;
            white-space: nowrap;
        }

        .distillery-report-table th:last-child,
        .distillery-report-table td:last-child {
            border-right: none;
        }

        .distillery-report-table thead th {
            position: sticky;
            top: 0;
            background: #e8eef4;
            color: #36474f;
            font-weight: 700;
            border-bottom: 2px solid #aab8c3;
            z-index: 2;
            text-align: right;
        }

        .distillery-report-table thead th.label-head,
        .distillery-report-table thead th.uom-head {
            text-align: left;
        }

        .row-label-col {
            text-align: left !important;
            min-width: 220px;
            font-weight: 700;
            color: #1f2b34;
            background: #f5f7fa !important;
            border-right: 3px solid #8fa8bb !important;
            position: sticky;
            left: 0;
            z-index: 1;
        }

        .distillery-report-table thead th.label-head {
            position: sticky;
            left: 0;
            z-index: 3;
            background: #e8eef4 !important;
            border-right: 3px solid #8fa8bb !important;
        }

        .sr-badge {
            display: inline-block;
            min-width: 30px;
            font-weight: 700;
            color: #5b7284;
            background: #e4ecf3;
            border-radius: 20px;
            padding: 1px 8px;
            font-size: 11px;
            margin-right: 8px;
        }

        .uom-col {
            text-align: center !important;
            font-weight: 600;
            color: #74838f;
            border-right: 3px solid #8fa8bb !important;
            background: #f9fbfc !important;
            min-width: 70px;
        }

        .uom-badge {
            color: #6b7f8c;
            font-size: 11px;
            font-weight: 600;
            background: #eef2f5;
            border-radius: 20px;
            padding: 1px 8px;
        }

        .num-cell {
            font-variant-numeric: tabular-nums;
            font-weight: 600;
            color: #2d3942;
        }

        .item-code-badge {
            color: #8ea0ac;
            font-size: 11px;
            font-weight: 600;
        }

        .to-date-col {
            background: #e4ecf4 !important;
            font-weight: 800 !important;
            color: #11263a !important;
            border-left: 4px solid #6b8fa8 !important;
        }

        th.to-date-col {
            background: #d0dfe9 !important;
            white-space: normal !important;
            line-height: 1.3;
            min-width: 130px;
        }

        tr.section-header-row td {
            font-weight: 800;
            padding: 8px 14px;
            border-top: 2px solid #b0bec5;
            border-bottom: 2px solid #b0bec5;
            color: #1a1a1a;
        }

        tr.section-header-row .row-label-col {
            position: sticky;
            left: 0;
            background: inherit !important;
        }

        .section-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 10px;
            background: rgba(0,0,0,0.25);
        }

        tr.data-row:hover td:not(.row-label-col) {
            filter: brightness(0.96);
        }

        tr.data-row:hover td.row-label-col {
            background: #eef2f6 !important;
        }

        tr.data-row:nth-child(even) td:not(.row-label-col) {
            filter: brightness(0.99);
        }

        /* Total rows — inserted after each section's data rows */
        tr.total-row td {
            font-weight: 800;
            background: #eef3f7 !important;
            border-top: 2px solid #b0bec5;
        }

        tr.total-row td.row-label-col {
            background: #e4ecf3 !important;
        }

        tr.total-row:hover td:not(.row-label-col) {
            filter: brightness(0.97);
        }

        tr.total-row td.to-date-col {
            background: #d7e2ec !important;
        }

        /* Ideal vs Actual split cell (Section I.11-I.18) */
        .ideal-actual-cell {
            display: flex;
            align-items: stretch;
            justify-content: flex-end;
            gap: 0;
            white-space: nowrap;
        }

        .ideal-actual-cell .ia-half {
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            padding: 0 10px;
        }

        .ideal-actual-cell .ia-half:first-child {
            padding-left: 0;
        }

        .ideal-actual-cell .ia-half:last-child {
            padding-right: 0;
        }

        .ideal-actual-cell .ia-divider {
            width: 0;
            border-left: 2px solid #b6c3cd;
            margin: 0 2px;
        }

        .ideal-actual-cell .ia-num {
            font-size: 13px;
            font-weight: 700;
            color: #2d3942;
            margin-top: 2px;
        }

        .ideal-actual-cell .ia-actual .ia-num {
            color: #45596a;
        }

        .ideal-actual-cell .ia-tag {
            display: inline-block;
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: .3px;
            color: #6b7f8c;
            background: #eef2f5;
            border-radius: 20px;
            padding: 1px 7px;
        }

        </style>`).appendTo('head');
    }

    refresh() {
        const companies = this.company_field.get_value();
        const plants = this.plant_field.get_value();
        const segments = this.segment_field.get_value();
        const from_date = this.from_date_field.get_value();
        const to_date = this.to_date_field.get_value();

        if (!companies || !companies.length || !from_date || !to_date) {
            this.$message.show();
            this.$card.hide();
            return;
        }
        this.$message.hide();
        this.$card.show();

        frappe.call({
            method: 'informatics_custom_apps.eth.page.dmr.dmr.get_report_data',
            args: {
                companies: companies,
                from_date: from_date,
                to_date: to_date,
                plants: plants && plants.length ? plants : null,
                segments: segments && segments.length ? segments : null
            },
            freeze: true,
            callback: (r) => {
                if (r.message) {
                    this.render_table(r.message);
                }
            }
        });
    }

    render_table(data) {
        const { meta, columns } = data;
        const last_col_index = columns.length - 1;

        // ── Header row ──────────────────────────────────────────────────
        let head = `<th class="row-label-col label-head">Parameters</th>`;
        head += `<th class="uom-col uom-head">UOM</th>`;
        head += `<th>Standard</th>`;
        columns.forEach((col, i) => {
            const cls = i === last_col_index ? 'to-date-col' : '';
            head += `<th class="${cls}">${frappe.utils.escape_html(col.label)}</th>`;
        });
        this.$head_row.html(head);

        // ── Body rows ───────────────────────────────────────────────────
        let body = '';

        meta.forEach(row => {
            if (row.header) {
                const color = this.section_colors[row.sr] || '#f5f5f5';
                body += `<tr class="section-header-row" style="background:${color};">
                    <td class="row-label-col" style="background:${color};">
                        <span class="section-dot"></span>${frappe.utils.escape_html(row.label)}
                    </td>
                    <td colspan="${2 + columns.length}"></td>
                </tr>`;
                return;
            }

            // Total rows (inserted server-side by _add_section_totals) get
            // their own row class so they can be styled distinctly from
            // regular data rows.
            const row_cls = row.total ? 'data-row total-row' : 'data-row';

            const item_code_html = row.item_code
                ? ` <span class="item-code-badge">(${frappe.utils.escape_html(row.item_code)})</span>`
                : '';
            body += `<tr class="${row_cls}">
                <td class="row-label-col">
                    <span class="sr-badge">${row.sr}</span>${frappe.utils.escape_html(row.label)}${item_code_html}
                </td>
                <td class="uom-col"><span class="uom-badge">${row.uom || ''}</span></td>
                <td class="num-cell"></td>`;
            columns.forEach((col, i) => {
                const val = col.values[row.sr];
                let cls = i === last_col_index ? 'num-cell to-date-col' : 'num-cell';
                if (row.total) cls += ' total-cell';
                body += `<td class="${cls}">${this.render_cell(val)}</td>`;
            });
            body += `</tr>`;
        });

        this.$container.html(body);
    }


    render_cell(val) {
        if (val && typeof val === 'object' && ('ideal' in val || 'actual' in val)) {
            return `<div class="ideal-actual-cell">
                <div class="ia-half ia-ideal">
                    <span class="ia-tag">Ideal</span>
                    <span class="ia-num">${this.format_value_labeled(val.ideal)}</span>
                </div>
                <div class="ia-divider"></div>
                <div class="ia-half ia-actual">
                    <span class="ia-tag">Actual</span>
                    <span class="ia-num">${this.format_value_labeled(val.actual)}</span>
                </div>
            </div>`;
        }
        return this.format_value(val);
    }

    format_value_labeled(val) {
        if (val === null || val === undefined || val === '') return 'No data';
        const n = parseFloat(val);
        if (isNaN(n)) return 'No data';
        const precision = (Math.abs(n) < 0.1 && n !== 0) ? 3 : 2;
        return frappe.format(n, { fieldtype: 'Float', precision: precision });
    }

    format_value(val) {
        if (val === null || val === undefined || val === '') return '-';
        const n = parseFloat(val);
        if (isNaN(n) || n === 0) return '-';
        const precision = (Math.abs(n) < 0.1) ? 3 : 2;
        return frappe.format(n, { fieldtype: 'Float', precision: precision });
    }
}