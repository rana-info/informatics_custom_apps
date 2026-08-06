frappe.pages['dmr'].on_page_load = function(wrapper) {
    new DistilleryProductionReport(wrapper);
};

class DistilleryProductionReport {
    constructor(wrapper) {
        this.wrapper = wrapper;
        this.section_colors = {
            A: '#e3f2fd',
            B: '#fff3e0'
        };
        this.plant_options = [];
        this.segment_options = [];
        this.loading = false;
        this.filters_dirty = true;

        this.page = frappe.ui.make_app_page({
            parent: wrapper,
            title: 'Daily Manufacturing Report',
            single_column: true
        });

        this.page.wrapper.addClass('dmr-full-width-page');

        this.make_filters();
        this.make_table_container();
        this.bind_fullscreen_events();
    }

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
            get_data: (txt) => {
                const q = (txt || '').toLowerCase();
                return this.segment_options
                    .filter(s => s.toLowerCase().includes(q))
                    .map(s => ({ value: s, description: '' }));
            },
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

        this.$show_data_btn.on('click', () => {
            this.enter_fullscreen();
            this.refresh();
        });

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
        `).appendTo(this.page.page_form || this.page.wrapper.find('.page-form'));

        this.$export_excel_btn = this.$export_excel_btn_wrapper.find('.export-excel-btn');
        this.$export_pdf_btn = this.$export_pdf_btn_wrapper.find('.export-pdf-btn');

        this.$export_excel_btn.on('click', () => this.export_report('excel'));
        this.$export_pdf_btn.on('click', () => this.export_report('pdf'));

        this.$fullscreen_btn_wrapper = $(`
            <div class="frappe-control toolbar-btn-wrapper fullscreen-btn-wrapper">
                <div class="control-input-wrapper">
                    <button class="btn btn-sm toolbar-btn fullscreen-btn">
                        <svg class="icon icon-sm fullscreen-icon-enter" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M8 3H5a2 2 0 0 0-2 2v3"></path>
                            <path d="M21 8V5a2 2 0 0 0-2-2h-3"></path>
                            <path d="M3 16v3a2 2 0 0 0 2 2h3"></path>
                            <path d="M16 21h3a2 2 0 0 0 2-2v-3"></path>
                        </svg>
                        <svg class="icon icon-sm fullscreen-icon-exit" style="display:none;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M8 3v3a2 2 0 0 1-2 2H3"></path>
                            <path d="M21 8h-3a2 2 0 0 1-2-2V3"></path>
                            <path d="M3 16h3a2 2 0 0 1 2 2v3"></path>
                            <path d="M16 21v-3a2 2 0 0 1 2-2h3"></path>
                        </svg>
                        <span class="fullscreen-btn-label">Fullscreen</span>
                    </button>
                </div>
            </div>
        `).appendTo(this.page.page_form || this.page.wrapper.find('.page-form'));

        this.$fullscreen_btn = this.$fullscreen_btn_wrapper.find('.fullscreen-btn');
        this.$fullscreen_btn.on('click', () => this.toggle_fullscreen());

        this.load_plant_options();
        this.load_segment_options();
    }

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

    load_segment_options(done) {
        frappe.call({
            method: 'informatics_custom_apps.eth.page.dmr.dmr.get_segment_options',
            callback: (r) => {
                this.segment_options = r.message || [];
                if (done) done();
            }
        });
    }

    reconcile_plant_selection() {
        const selected = this.plant_field.get_value() || [];
        const valid_set = new Set(this.plant_options);
        const still_valid = selected.filter(p => valid_set.has(p));

        if (still_valid.length !== selected.length) {
            this.plant_field.set_value(still_valid);
        }
    }

    _fs_request_fn(el) {
        return el.requestFullscreen || el.webkitRequestFullscreen || el.msRequestFullscreen;
    }

    _fs_exit_fn() {
        return document.exitFullscreen || document.webkitExitFullscreen || document.msExitFullscreen;
    }

    _fs_element() {
        return document.fullscreenElement || document.webkitFullscreenElement || document.msFullscreenElement;
    }

    enter_fullscreen() {
        if (this._fs_element()) return;
        const el = this.page.wrapper[0];
        const fn = this._fs_request_fn(el);
        if (!fn) return;

        try {
            const p = fn.call(el);
            if (p && p.catch) p.catch(() => {});
        } catch (e) {}
    }

    exit_fullscreen() {
        if (!this._fs_element()) return;
        const fn = this._fs_exit_fn();
        if (!fn) return;
        try {
            const p = fn.call(document);
            if (p && p.catch) p.catch(() => {});
        } catch (e) {}
    }

    toggle_fullscreen() {
        if (this._fs_element()) {
            this.exit_fullscreen();
        } else {
            this.enter_fullscreen();
        }
    }

    bind_fullscreen_events() {
        const events = 'fullscreenchange.dmr webkitfullscreenchange.dmr MSFullscreenChange.dmr';
        $(document).on(events, () => {
            this.update_fullscreen_button();
            this.size_table_responsive();
            if (this._fs_element()) this.reset_scroll_to_top();
        });
        this.update_fullscreen_button();
    }

    reset_scroll_to_top() {
        window.scrollTo(0, 0);
        document.documentElement.scrollTop = 0;
        document.body.scrollTop = 0;
        const el = this.page.wrapper[0];
        if (el) el.scrollTop = 0;
    }

    update_fullscreen_button() {
        if (!this.$fullscreen_btn) return;
        const is_fullscreen = !!this._fs_element();
        this.$fullscreen_btn.find('.fullscreen-icon-enter').toggle(!is_fullscreen);
        this.$fullscreen_btn.find('.fullscreen-icon-exit').toggle(is_fullscreen);
        this.$fullscreen_btn.find('.fullscreen-btn-label').text(is_fullscreen ? 'Exit Fullscreen' : 'Fullscreen');
    }

    size_table_responsive() {
        if (!this.$table_scroll || !this.$table_scroll.length) return;

        if (!this._fs_element()) {
            this.$table_scroll.css('max-height', '');
            return;
        }

        if (!this.$card.is(':visible')) return;

        const top = this.$table_scroll[0].getBoundingClientRect().top;
        const bottom_margin = 16;
        const available = Math.max(200, window.innerHeight - top - bottom_margin);
        this.$table_scroll.css('max-height', available + 'px');
    }

    make_table_container() {
        this.$wrapper = $(`<div class="distillery-report-wrapper"></div>`).appendTo(this.page.body);

        this.$message = $(`
            <div class="text-muted" style="padding:20px;">
                Select Company and Date Range, then click <b>Show Data</b>.
            </div>
        `).appendTo(this.$wrapper);

        this.$loading = $(`
            <div class="distillery-loading" style="display:none;">
                <div class="distillery-loading-bar"><div class="distillery-loading-bar-fill"></div></div>
                <div class="distillery-loading-text">Loading report...</div>
            </div>
        `).appendTo(this.$wrapper);

        this.$card = $(`
            <div class="distillery-report-card" style="display:none;">
                <div class="distillery-report-card-title">
                    <span class="unit-badge">Values per section UOM</span>
                    <span class="stale-badge" style="display:none;">Filters changed — click Show Data to refresh</span>
                </div>
                <div class="table-responsive">
                    <table class="distillery-report-table">
                        <thead>
                            <tr class="distillery-head-row"></tr>
                        </thead>
                        <tbody class="distillery-body"></tbody>
                    </table>
                </div>
            </div>
        `).appendTo(this.$wrapper);

        this.$container = this.$card.find('tbody.distillery-body');
        this.$head_row = this.$card.find('tr.distillery-head-row');
        this.$table_scroll = this.$card.find('.table-responsive');
        this.$stale_notice = this.$card.find('.stale-badge');

        this.inject_styles();
        this.bind_item_code_toggle();

        $(window).on('resize.dmr-report', () => {
            if (this.$card && this.$card.is(':visible')) {
                this.sync_frozen_column_offsets();
                this.sync_frozen_section_offsets();
                this.size_table_responsive();
            }
        });
    }

    bind_item_code_toggle() {
        this.$container.on('click', 'td.row-label-col.has-item-codes', (e) => {
            $(e.currentTarget).toggleClass('codes-visible');
            this.sync_frozen_section_offsets();
        });
    }

    inject_styles() {
        if (document.getElementById('distillery-report-style')) return;

        $(`<style id="distillery-report-style">

        .distillery-report-wrapper {
            padding: 10px 0 30px;
        }

        .dmr-full-width-page .container {
            max-width: 100% !important;
            width: 100% !important;
        }

        .dmr-full-width-page:fullscreen,
        .dmr-full-width-page:-webkit-full-screen {
            background: #fff;
            overflow: hidden;
            padding: 0 16px 10px;
            --navbar-height: 0px;
        }

        .dmr-full-width-page:fullscreen .page-head,
        .dmr-full-width-page:-webkit-full-screen .page-head,
        .dmr-full-width-page:fullscreen .page-head-content,
        .dmr-full-width-page:-webkit-full-screen .page-head-content,
        .dmr-full-width-page:fullscreen .container.page-body,
        .dmr-full-width-page:-webkit-full-screen .container.page-body {
            margin-top: 0 !important;
            padding-top: 0 !important;
            top: 0 !important;
        }

        .toolbar-btn-wrapper {
            min-width: 116px;
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

        .fullscreen-btn-wrapper {
            margin-left: 14px;
        }

        .toolbar-btn {
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 7px;
            width: 100%;
            height: 32px;
            padding: 0 15px;
            line-height: 1;
            font-weight: 700;
            font-size: 12.5px;
            letter-spacing: .2px;
            border: 1px solid transparent;
            border-radius: 8px;
            cursor: pointer;
            box-shadow: 0 1px 2px rgba(31,39,46,.06);
            transition: filter .15s ease, transform .12s ease, box-shadow .2s ease, opacity .15s ease;
        }

        .toolbar-btn svg {
            width: 14px;
            height: 14px;
            flex-shrink: 0;
            stroke-width: 2;
        }

        .toolbar-btn:hover:not(:disabled) {
            filter: brightness(0.97);
            transform: translateY(-1px);
            box-shadow: 0 2px 6px rgba(31,39,46,.10);
        }

        .toolbar-btn:active:not(:disabled) {
            transform: translateY(0);
            filter: brightness(0.93);
            box-shadow: none;
        }

        .toolbar-btn:focus-visible {
            outline: 2px solid rgba(0,0,0,.2);
            outline-offset: 2px;
        }

        .show-data-btn {
            background: #e8f1fb;
            color: #2953a8 !important;
            border-color: #cfe1f6;
        }

        .export-excel-btn {
            background: #e6f5ee;
            color: #1f8f5f !important;
            border-color: #c9e8d9;
        }

        .export-pdf-btn {
            background: #fbecea;
            color: #b23c34 !important;
            border-color: #f3d3ce;
        }

        .fullscreen-btn {
            background: #eef1f4;
            color: #46545e !important;
            border-color: #dde3e9;
        }

        .toolbar-btn:disabled {
            opacity: 1;
            cursor: not-allowed;
            transform: none !important;
            box-shadow: none !important;
            color: #a7b1ba !important;
            background: #eef1f4 !important;
            border-color: #dde3e9 !important;
        }

        .distillery-loading {
            padding: 60px 20px;
            text-align: center;
        }

        .distillery-loading-text {
            margin-top: 14px;
            color: #5b7284;
            font-weight: 600;
            font-size: 13px;
        }

        .distillery-loading-bar {
            height: 6px;
            width: 100%;
            max-width: 420px;
            margin: 0 auto;
            background: #e4ecf3;
            border-radius: 6px;
            overflow: hidden;
        }

        .distillery-loading-bar-fill {
            height: 100%;
            width: 40%;
            background: #4f83c4;
            border-radius: 6px;
            animation: distillery-loading-slide 1.1s ease-in-out infinite;
        }

        @keyframes distillery-loading-slide {
            0%   { transform: translateX(-150%); }
            100% { transform: translateX(350%); }
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
            max-height: 90vh;
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
            z-index: 5;
            text-align: right;
        }

        .distillery-report-table thead th.label-head,
        .distillery-report-table thead th.uom-head {
            text-align: left;
        }

        .row-label-col {
            text-align: left !important;
            min-width: 180px;
            font-weight: 700;
            color: #1f2b34;
            background: #f5f7fa !important;
            position: sticky;
            left: 0;
            z-index: 1;
        }

        .row-label-col.has-item-codes {
            cursor: pointer;
        }

        .row-label-col.has-item-codes .toggle-chevron {
            display: inline-block;
            margin-left: 6px;
            color: #8ea0ac;
            font-size: 10px;
            transition: transform .15s ease;
        }

        .row-label-col.has-item-codes.codes-visible .toggle-chevron {
            transform: rotate(90deg);
        }

        .item-code-line {
            display: none;
            margin-top: 3px;
        }

        .row-label-col.codes-visible .item-code-line {
            display: block;
        }

        .distillery-report-table thead th.label-head {
            position: sticky;
            left: 0;
            z-index: 6;
            background: #e8eef4 !important;
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
            background: #f9fbfc !important;
            min-width: 70px;
            position: sticky;
            z-index: 1;
        }

        .distillery-report-table thead th.uom-head {
            position: sticky;
            z-index: 6;
            background: #e8eef4 !important;
        }

        .standard-col {
            min-width: 90px;
            background: #f9fbfc !important;
            border-right: 3px solid #8fa8bb !important;
            position: sticky;
            z-index: 1;
        }

        .distillery-report-table thead th.standard-head {
            position: sticky;
            z-index: 6;
            background: #e8eef4 !important;
            border-right: 3px solid #8fa8bb !important;
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
            position: sticky;
            top: 0;
            z-index: 3;
        }

        tr.section-header-row .row-label-col {
            position: sticky;
            left: 0;
            background: inherit !important;
        }

        tr.section-header-row td.uom-col,
        tr.section-header-row td.standard-col {
            z-index: 4;
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

        tr.frozen-row td {
            position: sticky;
            z-index: 2;
        }

        tr.frozen-row td.row-label-col,
        tr.frozen-row td.uom-col,
        tr.frozen-row td.standard-col {
            z-index: 4;
        }

        tr.frozen-row.data-row:not(.total-row) td:not(.row-label-col):not(.uom-col):not(.standard-col):not(.to-date-col) {
            background: #fff;
        }

        tr.frozen-row-end td {
            border-bottom: 3px solid #8fa8bb !important;
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
            frappe.show_alert({
                message: __('Select at least one Company along with From Date and To Date.'),
                indicator: 'orange'
            });
            this.$loading.hide();
            this.$message.show();
            this.$card.hide();
            return;
        }

        if (this.loading) return;
        this.loading = true;

        this.$message.hide();
        this.$card.hide();
        this.$loading.show();

        frappe.call({
            method: 'informatics_custom_apps.eth.page.dmr.dmr.get_report_data',
            args: {
                companies: companies,
                from_date: from_date,
                to_date: to_date,
                plants: plants && plants.length ? plants : null,
                segments: segments && segments.length ? segments : null
            },
            callback: (r) => {
                this.$loading.hide();
                if (r.message) {
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

        open_url_post(`/api/method/${method}`, args);
    }

    render_table(data) {
        const { meta, columns } = data;
        const last_col_index = columns.length - 1;
        const escape = frappe.utils.escape_html;

        const head_parts = [
            `<th class="row-label-col label-head">Parameters</th>`,
            `<th class="uom-col uom-head">UOM</th>`,
            `<th class="standard-col standard-head">Standard</th>`
        ];
        columns.forEach((col, i) => {
            const cls = i === last_col_index ? 'to-date-col' : '';
            head_parts.push(`<th class="${cls}">${escape(col.label)}</th>`);
        });
        this.$head_row.html(head_parts.join(''));

        const body_parts = [];

        let current_section = null;

        meta.forEach(row => {
            if (row.header) {
                current_section = row.sr;
                const is_frozen = current_section === 'A';
                const color = this.section_colors[row.sr] || '#f5f5f5';
                const row_cls = is_frozen ? 'section-header-row frozen-row' : 'section-header-row';

                body_parts.push(
                    `<tr class="${row_cls}" style="background:${color} !important;">`,
                    `<td class="row-label-col" style="background:${color} !important;">`,
                    `<span class="section-dot"></span>${escape(row.label)}</td>`,
                    `<td class="uom-col" style="background:${color} !important;"></td>`,
                    `<td class="standard-col" style="background:${color} !important;"></td>`
                );

                columns.forEach(() => {
                    body_parts.push(`<td class="section-header-cell" style="background:${color} !important;"></td>`);
                });
                body_parts.push(`</tr>`);
                return;
            }

            const is_frozen = current_section === 'A';
            let row_cls = row.total ? 'data-row total-row' : 'data-row';
            if (is_frozen) row_cls += ' frozen-row';

            const sr_badge_html = row.total ? '' : `<span class="sr-badge">${row.sr}</span>`;

            let item_code_html = '';
            let has_codes = false;
            if (row.item_code) {
                has_codes = true;
                item_code_html = `<span class="item-code-line"><a href="/app/item/${encodeURIComponent(row.item_code)}" class="item-code-badge" target="_blank">${escape(row.item_code)}</a></span>`;
            } else if (row.item_codes && row.item_codes.length) {
                const unique_codes = [...new Set(row.item_codes.map(String))];
                has_codes = true;
                const links = unique_codes
                    .map(c => `<a href="/app/item/${encodeURIComponent(c)}" class="item-code-badge" target="_blank">${escape(c)}</a>`)
                    .join(', ');
                item_code_html = `<span class="item-code-line">${links}</span>`;
            }

            const label_cls = has_codes ? 'row-label-col has-item-codes' : 'row-label-col';
            const chevron_html = has_codes ? `<span class="toggle-chevron">&#9656;</span>` : '';

            body_parts.push(
                `<tr class="${row_cls}">`,
                `<td class="${label_cls}" title="${escape(row.label)}">${sr_badge_html}${escape(row.label)}${chevron_html}${item_code_html}</td>`,
                `<td class="uom-col"><span class="uom-badge">${row.uom || ''}</span></td>`,
                `<td class="num-cell standard-col">${row.standard !== undefined && row.standard !== null ? this.format_value(row.standard) : ''}</td>`
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

        this.$container.find('tr.frozen-row').removeClass('frozen-row-end');
        this.$container.find('tr.frozen-row').last().addClass('frozen-row-end');

        this.sync_frozen_column_offsets();
        this.sync_frozen_section_offsets();
        this.size_table_responsive();

        requestAnimationFrame(() => {
            this.sync_frozen_column_offsets();
            this.sync_frozen_section_offsets();
            this.size_table_responsive();
        });
    }

    sync_frozen_column_offsets() {
        const $label_head = this.$card.find('thead th.label-head');
        const $uom_head = this.$card.find('thead th.uom-head');
        if (!$label_head.length || !$uom_head.length) return;

        const label_w = $label_head.outerWidth();
        const uom_w = $uom_head.outerWidth();
        const uom_left = label_w;
        const standard_left = label_w + uom_w;

        this.$card.find('.uom-col').css('left', uom_left + 'px');
        this.$card.find('.standard-col').css('left', standard_left + 'px');
    }

    sync_frozen_section_offsets() {
        const head_h = this.$head_row.outerHeight() || 0;
        let cumulative = head_h;

        this.$container.find('tr.frozen-row').each((_, el) => {
            const $row = $(el);
            $row.find('> td').css('top', cumulative + 'px');
            cumulative += $row.outerHeight();
        });

        this.$container.find('tr.section-header-row')
            .not('.frozen-row')
            .find('> td')
            .css('top', cumulative + 'px');
    }

    render_cell(val) {
        return this.format_value(val);
    }

    format_value(val) {
        if (val === null || val === undefined || val === '') return '-';
        const n = parseFloat(val);
        if (isNaN(n) || n === 0) return '-';
        const precision = (Math.abs(n) < 0.1) ? 3 : 2;
        return frappe.format(n, { fieldtype: 'Float', precision: precision });
    }
}