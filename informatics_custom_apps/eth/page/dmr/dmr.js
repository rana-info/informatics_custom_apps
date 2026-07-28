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
        this.plant_options = [];
        this.loading = false;
        this.filters_dirty = true; // true until a successful load happens for current filters

        this.page = frappe.ui.make_app_page({
            parent: wrapper,
            title: 'Daily Manufacturing Report',
            single_column: true
        });

        this.make_filters();
        this.make_table_container();
    }

    // ── Filters ─────────────────────────────────────────────────────────

    make_filters() {
        this.company_field = this.page.add_field({
            fieldname: 'company',
            label: 'Company',
            fieldtype: 'MultiSelectList',
            get_data: (txt) => frappe.db.get_link_options('Company', txt),
            change: () => {
                this.mark_dirty();
                this.load_plant_options(() => this.reconcile_plant_selection());
            }
        });

        this.plant_field = this.page.add_field({
            fieldname: 'plant',
            label: 'Plant',
            fieldtype: 'MultiSelectList',
            get_data: (txt) => {
                const q = (txt || '').toLowerCase();
                return this.plant_options
                    .filter(p => p.toLowerCase().includes(q))
                    .map(p => ({ value: p, description: '' }));
            },
            change: () => this.mark_dirty()
        });

        this.segment_field = this.page.add_field({
            fieldname: 'segment',
            label: 'Segment',
            fieldtype: 'MultiSelectList',
            hidden:1,
            // Segment is its own doctype, not Cost Center.
            get_data: (txt) => frappe.db.get_link_options('Segment', txt),
            change: () => this.mark_dirty()
        });

        this.from_date_field = this.page.add_field({
            fieldname: 'from_date',
            label: 'From Date',
            fieldtype: 'Date',
            default: frappe.datetime.get_today(),
            change: () => this.mark_dirty()
        });

        this.to_date_field = this.page.add_field({
            fieldname: 'to_date',
            label: 'To Date',
            fieldtype: 'Date',
            default: frappe.datetime.get_today(),
            change: () => this.mark_dirty()
        });

        // Explicit trigger — filters no longer auto-refresh the report.
        // Note: these page filters render their label as placeholder text
        // inside the input itself (no separate label row above), so each
        // button just needs to sit in its own input-wrapper, bottom-aligned
        // with the row — no extra label spacer needed.
        this.$show_data_btn_wrapper = $(`
            <div class="frappe-control toolbar-btn-wrapper show-data-btn-wrapper">
                <div class="control-input-wrapper">
                    <button class="btn btn-sm toolbar-btn show-data-btn">
                        <svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                            <polygon points="6 3 20 12 6 21 6 3"></polygon>
                        </svg>
                        <span>Show Data</span>
                    </button>
                </div>
            </div>
        `).appendTo(this.page.page_form || this.page.wrapper.find('.page-form'));

        this.$show_data_btn = this.$show_data_btn_wrapper.find('.show-data-btn');
        this.$show_data_btn.on('click', () => this.refresh());

        // Export buttons — disabled until a successful Show Data load, and
        // re-disabled the moment any filter changes (see mark_dirty), so an
        // export can never be triggered against a payload that doesn't
        // match what's currently rendered on screen. Each toolbar button
        // has its own color identity and icon so the three actions read as
        // distinct at a glance rather than a uniform row of grey buttons.
        this.$export_excel_btn_wrapper = $(`
            <div class="frappe-control toolbar-btn-wrapper export-btn-wrapper excel-btn-wrapper">
                <div class="control-input-wrapper">
                    <button class="btn btn-sm toolbar-btn export-excel-btn" disabled>
                        <svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                            <rect x="3" y="3" width="18" height="18" rx="2"></rect>
                            <line x1="3" y1="9" x2="21" y2="9"></line>
                            <line x1="3" y1="15" x2="21" y2="15"></line>
                            <line x1="9" y1="3" x2="9" y2="21"></line>
                            <line x1="15" y1="3" x2="15" y2="21"></line>
                        </svg>
                        <span>Excel</span>
                    </button>
                </div>
            </div>
        `).appendTo(this.page.page_form || this.page.wrapper.find('.page-form'));

        this.$export_pdf_btn_wrapper = $(`
            <div class="frappe-control toolbar-btn-wrapper export-btn-wrapper pdf-btn-wrapper">
                <div class="control-input-wrapper">
                    <button class="btn btn-sm export-pdf-btn toolbar-btn" disabled>
                        <svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                            <polyline points="14 2 14 8 20 8"></polyline>
                            <line x1="9" y1="15" x2="15" y2="15"></line>
                            <line x1="9" y1="18" x2="12" y2="18"></line>
                        </svg>
                        <span>PDF</span>
                    </button>
                </div>
            </div>
        `).appendTo(this.page.page_form || this.page.wrapper.find('.page-form'));

        this.$export_excel_btn = this.$export_excel_btn_wrapper.find('.export-excel-btn');
        this.$export_pdf_btn = this.$export_pdf_btn_wrapper.find('.export-pdf-btn');

        this.$export_excel_btn.on('click', () => this.export_report('excel'));
        this.$export_pdf_btn.on('click', () => this.export_report('pdf'));

        this.load_plant_options();
    }

    // Any filter change invalidates the currently-shown data so the user
    // isn't left looking at results that no longer match their filters.
    // Export buttons are disabled at the same time, for the same reason.
    mark_dirty() {
        this.filters_dirty = true;
        this.set_export_buttons_enabled(false);
        if (this.$card && this.$card.is(':visible')) {
            this.show_stale_notice();
        }
    }

    set_export_buttons_enabled(enabled) {
        this.$export_excel_btn && this.$export_excel_btn.prop('disabled', !enabled);
        this.$export_pdf_btn && this.$export_pdf_btn.prop('disabled', !enabled);
    }

    show_stale_notice() {
        if (!this.$stale_notice) return;
        this.$stale_notice.show();
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
    // newly-selected company(ies). Does NOT trigger a refresh — the user
    // must press "Show Data" explicitly.
    reconcile_plant_selection() {
        const selected = this.plant_field.get_value() || [];
        const valid_set = new Set(this.plant_options);
        const still_valid = selected.filter(p => valid_set.has(p));

        if (still_valid.length !== selected.length) {
            this.plant_field.set_value(still_valid);
        }
    }

    // ── Table shell ─────────────────────────────────────────────────────

    make_table_container() {
        this.$wrapper = $(`<div class="distillery-report-wrapper"></div>`).appendTo(this.page.body);

        this.$message = $(`
            <div class="text-muted" style="padding:20px;">
                Select Company and Date Range, then click <b>Show Data</b>.
            </div>
        `).appendTo(this.$wrapper);

        this.$card = $(`
            <div class="distillery-report-card" style="display:none;">
                <div class="distillery-report-card-title">
                    Daily Manufacturing Report
                    <span class="unit-badge">Values per section UOM</span>
                    <span class="stale-badge" style="display:none;">Filters changed — click Show Data to refresh</span>
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
        this.$stale_notice = this.$card.find('.stale-badge');

        this.inject_styles();
        // No auto-load on page open — wait for the user to press "Show Data".
    }

    inject_styles() {
        if (document.getElementById('distillery-report-style')) return;

        $(`<style id="distillery-report-style">

        .distillery-report-wrapper {
            padding: 10px 0 30px;
        }

        /* ── Toolbar buttons (Show Data / Excel / PDF) ─────────────────── */

        .toolbar-btn-wrapper {
            /* Matches the width Frappe gives other filter controls so the
               button doesn't stretch full-width or collapse to text width. */
            min-width: 116px;
            /* Bottom-align with the input row regardless of whatever
               align-items the parent filter row uses, since this wrapper
               has no label row above it while some other fields might. */
            align-self: flex-end;
            display: flex;
        }

        .toolbar-btn-wrapper .control-input-wrapper {
            display: flex;
            align-items: flex-end;
            width: 100%;
        }

        .export-btn-wrapper {
            margin-left: 14px;
        }

        .pdf-btn-wrapper {
            margin-left: 8px;
        }

        .toolbar-btn {
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 7px;
            width: 100%;
            height: 32px;
            padding: 0 16px;
            line-height: 1;
            font-weight: 600;
            font-size: 13px;
            letter-spacing: .1px;
            color: #fff !important;
            border: none !important;
            border-radius: 8px;
            cursor: pointer;
            background-size: 100% 200%;
            background-position: top;
            box-shadow: 0 1px 2px rgba(16,24,32,.12), 0 2px 6px -2px rgba(16,24,32,.18);
            transition: background-position .25s ease, transform .12s ease, box-shadow .2s ease, opacity .15s ease;
        }

        .toolbar-btn svg {
            width: 15px;
            height: 15px;
            flex-shrink: 0;
        }

        .toolbar-btn:hover:not(:disabled) {
            background-position: bottom;
            transform: translateY(-1px);
            box-shadow: 0 3px 8px rgba(16,24,32,.16), 0 4px 12px -3px rgba(16,24,32,.22);
        }

        .toolbar-btn:active:not(:disabled) {
            transform: translateY(0);
            box-shadow: 0 1px 2px rgba(16,24,32,.14) inset;
        }

        .toolbar-btn:focus-visible {
            outline: 2px solid rgba(0,0,0,.25);
            outline-offset: 2px;
        }

        /* Show Data — indigo/blue, the "primary" action */
        .show-data-btn {
            background-image: linear-gradient(180deg, #4f6bf0 0%, #3d55d1 100%);
        }

        /* Excel — emerald green, evokes the Excel brand without copying it */
        .export-excel-btn {
            background-image: linear-gradient(180deg, #22a06b 0%, #168554 100%);
        }

        /* PDF — warm red/coral, evokes the PDF brand without copying it */
        .export-pdf-btn {
            background-image: linear-gradient(180deg, #ef5350 0%, #d8342f 100%);
        }

        .toolbar-btn:disabled {
            opacity: .42;
            cursor: not-allowed;
            transform: none !important;
            box-shadow: none !important;
            background-image: linear-gradient(180deg, #aab4bd 0%, #8f99a3 100%) !important;
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

        .stale-badge {
            font-size: 12px;
            padding: 3px 10px;
            border-radius: 30px;
            font-weight: 600;
            background: #fff3e0;
            color: #a15c00;
            border: 1px solid #f3d9a8;
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

        /* Standard vs Actual split cell (Section I.11-I.18) */
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
            align-items: center;
            /* min-width (not a fixed width) keeps Standard/Actual columns
               visually aligned for typical values, but still lets the box
               grow when a value is wider than that — e.g. large Indian-
               format numbers like "1,18,49,220" — instead of clipping or
               spilling past the cell edge. */
            min-width: 86px;
            padding: 0 6px;
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
            margin: 0 4px;
            align-self: stretch;
        }

        .ideal-actual-cell .ia-num {
            display: block;
            width: 100%;
            text-align: right;
            font-size: 13px;
            font-weight: 700;
            color: #2d3942;
            margin-top: 3px;
            white-space: nowrap;
        }

        .ideal-actual-cell .ia-actual .ia-num {
            color: #45596a;
        }

        .ideal-actual-cell .ia-tag {
            /* inline-block sized to its own text (not stretched to the
               half's full width) so the pill background always wraps the
               text exactly, regardless of "STANDARD" vs "ACTUAL" length. */
            display: inline-block;
            white-space: nowrap;
            font-size: 9px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: .2px;
            color: #6b7f8c;
            background: #eef2f5;
            border-radius: 20px;
            padding: 1px 7px;
        }

        </style>`).appendTo('head');
    }

    // ── Data loading ────────────────────────────────────────────────────

    refresh() {
        const companies = this.company_field.get_value();
        const plants = this.plant_field.get_value();
        const segments = this.segment_field.get_value();
        const from_date = this.from_date_field.get_value();
        const to_date = this.to_date_field.get_value();

        if (!companies || !companies.length || !from_date || !to_date) {
            frappe.show_alert({
                message: __('Select at least one Company along with From Date and To Date.'),
                indicator: 'orange'
            });
            this.$message.show();
            this.$card.hide();
            return;
        }

        // Guard against duplicate concurrent requests (e.g. rapid double-click).
        if (this.loading) return;
        this.loading = true;

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
            freeze_message: __('Loading report...'),
            callback: (r) => {
                if (r.message) {
                    this.$message.hide();
                    this.$card.show();
                    this.$stale_notice.hide();
                    this.filters_dirty = false;
                    this.set_export_buttons_enabled(true);
                    this.render_table(r.message);
                }
            },
            always: () => {
                this.loading = false;
            }
        });
    }

    // ── Export ──────────────────────────────────────────────────────────

    export_report(kind) {
        if (this.filters_dirty) {
            frappe.show_alert({
                message: __('Filters have changed — click Show Data before exporting.'),
                indicator: 'orange'
            });
            return;
        }

        const companies = this.company_field.get_value();
        const plants = this.plant_field.get_value();
        const segments = this.segment_field.get_value();
        const from_date = this.from_date_field.get_value();
        const to_date = this.to_date_field.get_value();

        if (!companies || !companies.length || !from_date || !to_date) {
            frappe.show_alert({
                message: __('Select at least one Company along with From Date and To Date.'),
                indicator: 'orange'
            });
            return;
        }

        const method = kind === 'pdf'
            ? 'informatics_custom_apps.eth.page.dmr.dmr.export_pdf'
            : 'informatics_custom_apps.eth.page.dmr.dmr.export_excel';

        const args = {
            companies: JSON.stringify(companies),
            from_date: from_date,
            to_date: to_date,
            plants: plants && plants.length ? JSON.stringify(plants) : '',
            segments: segments && segments.length ? JSON.stringify(segments) : ''
        };

        // open_url_post builds a hidden form and submits it as a real POST,
        // so the browser's native download handling picks up the
        // binary/file response that export_excel/export_pdf set on
        // frappe.response — frappe.call's XHR can't hand that off to a
        // save-file dialog the way a form submission can.
        open_url_post(`/api/method/${method}`, args);
    }

    // ── Rendering ───────────────────────────────────────────────────────

    render_table(data) {
        const { meta, columns } = data;
        const last_col_index = columns.length - 1;
        const escape = frappe.utils.escape_html;

        // ── Header row ──────────────────────────────────────────────────
        const head_parts = [
            `<th class="row-label-col label-head">Parameters</th>`,
            `<th class="uom-col uom-head">UOM</th>`,
            `<th>Standard</th>`
        ];
        columns.forEach((col, i) => {
            const cls = i === last_col_index ? 'to-date-col' : '';
            head_parts.push(`<th class="${cls}">${escape(col.label)}</th>`);
        });
        this.$head_row.html(head_parts.join(''));

        // ── Body rows ───────────────────────────────────────────────────
        // Building an array and joining once is significantly faster than
        // repeated string concatenation for large tables (many sections x
        // many date columns), and avoids intermediate string reallocation.
        const body_parts = [];

        meta.forEach(row => {
            if (row.header) {
                const color = this.section_colors[row.sr] || '#f5f5f5';
                body_parts.push(
                    `<tr class="section-header-row" style="background:${color};">`,
                    `<td class="row-label-col" style="background:${color};">`,
                    `<span class="section-dot"></span>${escape(row.label)}</td>`,
                    `<td colspan="${2 + columns.length}"></td></tr>`
                );
                return;
            }

            // Total rows (inserted server-side by _add_section_totals) get
            // their own row class so they can be styled distinctly from
            // regular data rows.
            const row_cls = row.total ? 'data-row total-row' : 'data-row';
            const item_code_html = row.item_code
                ? ` <span class="item-code-badge">(${escape(row.item_code)})</span>`
                : '';

            body_parts.push(
                `<tr class="${row_cls}">`,
                `<td class="row-label-col"><span class="sr-badge">${row.sr}</span>${escape(row.label)}${item_code_html}</td>`,
                `<td class="uom-col"><span class="uom-badge">${row.uom || ''}</span></td>`,
                `<td class="num-cell"></td>`
            );

            columns.forEach((col, i) => {
                const val = col.values[row.sr];
                let cls = i === last_col_index ? 'num-cell to-date-col' : 'num-cell';
                if (row.total) cls += ' total-cell';
                body_parts.push(`<td class="${cls}">${this.render_cell(val)}</td>`);
            });

            body_parts.push(`</tr>`);
        });

        this.$container.html(body_parts.join(''));
    }

    render_cell(val) {
        if (val && typeof val === 'object' && ('ideal' in val || 'actual' in val)) {
            return `<div class="ideal-actual-cell">
                <div class="ia-half ia-ideal">
                    <span class="ia-tag">Standard</span>
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