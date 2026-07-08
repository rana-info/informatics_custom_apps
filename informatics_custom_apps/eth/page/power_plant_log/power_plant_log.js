frappe.pages['power-plant-log'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Power Plant Log Entry',
        single_column: true
    });

    let time_slots = [
        "9:30 AM", "1:30 PM", "5:30 PM", "9:30 PM", "1:30 AM", "5:30 AM"
    ];

    // each field: [fieldname, label, unit-or-null]
    let sections = [
        { title: "FEED WATERS", fields: [
            ["ph", "PH", null],
            ["conductivity", "Conductivity (Max)", null],
            ["silica", "Silica (Max)", "ppm"],
            ["residual_oxygen_scavenger", "Residual Oxygen Scavenger", "ppm"],
            ["iron_as_fe", "Iron as Fe (Max)", "ppm"],
            ["dissolve_oxygen", "Dissolve Oxygen", "ppm"],
            ["total_hardness", "Total Hardness", "ppm"],
        ]},
        { title: "BOILER WATER", fields: [
            ["ph1", "PH", null],
            ["conductivity1", "Conductivity (Max)", null],
            ["tds", "TDS (Max)", "ppm"],
            ["silica1", "Silica (Max)", "ppm"],
            ["phosphate_as_po4", "Phosphate as PO4", "ppm"],
            ["p_alkalinity", "P Alkalinity (Max)", "ppm"],
            ["total_hardness1", "Total Hardness", "ppm"],
            ["chloride_as_caco3", "Chloride as CaCO3", "ppm"],
        ]},
        { title: "STEAM QUALITY", fields: [
            ["ph2", "PH", null],
            ["conductivity2", "Conductivity (Max)", null],
            ["silica2", "Silica (Max)", "ppm"],
            ["iron_as_fe1", "Iron as Fe (Max)", "ppm"],
        ]},
        { title: "TURBINE CONDENSATE", fields: [
            ["ph3", "PH", null],
            ["conductivity3", "Conductivity (Max)", "ppm"],
            ["silica3", "Silica (Max)", "ppm"],
        ]},
        { title: "COMMON EXHAUST CONDENSATE", fields: [
            ["ph4", "PH", null],
            ["conductivity4", "Conductivity (Max)", null],
            ["silica4", "Silica (Max)", "ppm"],
            ["total_hardness2", "Total Hardness", "ppm"],
            ["iron_as_fe2", "Iron as Fe (Max)", "ppm"],
        ]},
        { title: "D.M PLANT", fields: [
            ["dm_plant_running_hours", "DM Plant Running Hours/Day", null],
            ["dm_water_consumption", "DM Water Consumption/Day", null],
        ]},
        { title: "COOLING TOWER WATER", fields: [
            ["ph5", "PH", null],
            ["conductivity5", "Conductivity (Max)", "ppm"],
            ["tds1", "TDS (Max)", "ppm"],
            ["t_hardness", "T.Hardness (Max)", "ppm"],
            ["calcium_hardness", "Calcium Hardness (Max)", "ppm"],
            ["magnesium_hardness", "Magnesium Hardness (Max)", null],
            ["chloride_as_caco31", "Chloride as CaCO3", null],
            ["sulphate_as_so4", "Sulphate as SO4 (Max)", null],
            ["silica5", "Silica (Max)", null],
            ["cw_inlet_pressure", "CW Inlet Pressure", "Kg/Cm2"],
            ["cw_outlet_pressure", "CW Outlet Pressure", "Kg/Cm2"],
            ["cw_inlet_temperature", "CW Inlet Temperature", "Deg.C"],
            ["cw_outlet_temperature", "CW Outlet Temperature", "Deg.C"],
            ["turbine_condensate_temperature", "Turbine Condensate Temperature", "Deg.C"],
            ["vacuum_in_condensor", "Vacuum In Condensor", "Kg/Cm2"],
        ]},
        { title: "FUEL", fields: [
            ["moisture", "Moisture", "%"],
            ["g_cal_value", "G.Cal. Value", "Kcal/Kg"],
            ["dust", "Dust", "%"],
        ]},
    ];

    // ---------- inject styles once ----------
    if (!$('#power-plant-log-style').length) {
        $(`<style id="power-plant-log-style">
            .ppl-log-table { border-collapse: collapse; width: 100%; }
            .ppl-log-table th, .ppl-log-table td {
                border: 1px solid var(--border-color, #d1d8dd);
                padding: 4px 6px;
                text-align: center;
                vertical-align: middle;
            }
            .ppl-log-table td:first-child, .ppl-log-table th:first-child {
                text-align: left;
                font-weight: 500;
                background: var(--fg-color, #fafbfc);
                position: sticky;
                left: 0;
                z-index: 2;
            }
            .ppl-log-table .section-row td {
                background: var(--gray-200, #e7eaec);
                font-weight: 600;
                text-align: left;
                padding: 6px 8px;
            }
            .ppl-uom {
                color: var(--text-muted, #8d99a6);
                font-size: 11px;
                font-weight: 400;
            }
            .ppl-log-table th.slot-col-0, .ppl-log-table td.slot-col-0 { background-color: #eaf4ff; }
            .ppl-log-table th.slot-col-1, .ppl-log-table td.slot-col-1 { background-color: #eafff1; }
            .ppl-log-table th.slot-col-2, .ppl-log-table td.slot-col-2 { background-color: #fff9ea; }
            .ppl-log-table th.slot-col-3, .ppl-log-table td.slot-col-3 { background-color: #fff0ea; }
            .ppl-log-table th.slot-col-4, .ppl-log-table td.slot-col-4 { background-color: #f5eaff; }
            .ppl-log-table th.slot-col-5, .ppl-log-table td.slot-col-5 { background-color: #eafffb; }
            .ppl-log-table input.form-control, .ppl-log-table textarea.form-control {
                border: none;
                background: transparent;
                text-align: center;
                width: 100%;
            }
            .ppl-log-table td:hover {
                outline: 2px solid var(--primary, #2490ef);
                outline-offset: -2px;
            }
            .ppl-log-table input.form-control:focus, .ppl-log-table textarea.form-control:focus {
                background: #fff;
                box-shadow: none;
            }
            .log-header { align-items: flex-end; }
        </style>`).appendTo(document.head);
    }

    // ---------- state (declared before any control that could fire onchange during setup) ----------
    let inputs = {}; // inputs[fieldname][time_slot] = jquery input
    let current_doc_name = null;
    let ordered_fieldnames = [];
    let remarks_inputs = {};

    // Frappe fires a control's onchange through more than one internal path
    // (e.g. the datepicker's own change event AND the model set_value cycle),
    // so a single user action can trigger the handler twice. Debouncing
    // collapses those into a single execution.
    let handle_filter_change = frappe.utils.debounce(function () { maybe_load(); }, 300);
    let handle_date_change = frappe.utils.debounce(function () {
        let selected = date_field.get_value();
        if (selected && selected > frappe.datetime.get_today()) {
            frappe.msgprint(__('Future dates are not allowed. Resetting to today.'));
            date_field.set_value(frappe.datetime.get_today());
            return; // set_value above will re-trigger this handler with a valid date
        }
        maybe_load();
    }, 300);

    // ---------- strict float-only input filtering ----------
    // Keeps only digits, a single decimal point, and an optional leading
    // minus sign (needed for fields like Vacuum In Condensor that can
    // legitimately go negative). Anything else typed or pasted is dropped
    // immediately - no warning, it simply never appears, same as a DB
    // float/int column would enforce. Remarks stays free text, untouched.
    function sanitize_float_string(value) {
        let negative = value.charAt(0) === '-';
        let body = value.replace(/-/g, '').replace(/[^0-9.]/g, '');
        let firstDot = body.indexOf('.');
        if (firstDot !== -1) {
            body = body.slice(0, firstDot + 1) + body.slice(firstDot + 1).replace(/\./g, '');
        }
        return (negative ? '-' : '') + body;
    }

    function bind_float_sanitizer($input) {
        $input.on('input', function () {
            let el = this;
            let original = el.value;
            let sanitized = sanitize_float_string(original);
            if (sanitized !== original) {
                let pos = el.selectionStart - (original.length - sanitized.length);
                el.value = sanitized;
                if (pos < 0) pos = 0;
                try { el.setSelectionRange(pos, pos); } catch (e) { /* ignore on unsupported input types */ }
            }
        });
        // final safety net in case a browser fires neither 'input' on paste
        $input.on('blur', function () {
            this.value = sanitize_float_string(this.value);
        });
    }

    // ---------- header controls ----------
    let $filters = $(`<div class="log-header" style="display:flex; gap:10px; margin-bottom:15px;"></div>`).appendTo(page.body);

    let company_field = frappe.ui.form.make_control({
        parent: $filters,
        df: {
            fieldtype: 'Link',
            options: 'Company',
            label: 'Company',
            reqd: 1,
            onchange: function () {
                plant_field.set_value('');
                plant_field.df.get_query = () => {
                    return { filters: { company: company_field.get_value() } };
                };
                plant_field.refresh();
                handle_filter_change();
            }
        },
        render_input: true
    });

    let plant_field = frappe.ui.form.make_control({
        parent: $filters,
        df: {
            fieldtype: 'Link',
            options: 'Branch',
            label: 'Plant',
            reqd: 1,
            get_query: () => {
                return { filters: { company: company_field.get_value() } };
            },
            onchange: function () { handle_filter_change(); }
        },
        render_input: true
    });

    let date_field = frappe.ui.form.make_control({
        parent: $filters,
        df: {
            fieldtype: 'Date',
            label: 'Date',
            default: 'Today',
            reqd: 1,
            onchange: function () { handle_date_change(); }
        },
        render_input: true
    });
    date_field.set_value(frappe.datetime.get_today());

    // ---------- build the matrix table ----------
    let $table = $(`<table class="table ppl-log-table">
        <thead><tr><th>Parameter</th>
        ${time_slots.map((t, i) => `<th class="slot-col-${i}">${t}</th>`).join('')}
        </tr></thead><tbody></tbody></table>`).appendTo(page.body);

    sections.forEach(sec => {
        $table.find('tbody').append(
            `<tr class="section-row"><td colspan="${time_slots.length + 1}"><b>${sec.title}</b></td></tr>`
        );
        sec.fields.forEach(([fieldname, label, uom]) => {
            let label_html = uom
                ? `${label} <span class="ppl-uom">(${uom})</span>`
                : label;
            let $row = $(`<tr><td>${label_html}</td></tr>`).appendTo($table.find('tbody'));
            inputs[fieldname] = {};
            ordered_fieldnames.push(fieldname);
            time_slots.forEach((ts, i) => {
                let $td = $(`<td class="slot-col-${i}"></td>`).appendTo($row);
                let $input = $('<input type="text" inputmode="decimal" autocomplete="off" class="form-control input-sm">').appendTo($td);
                bind_float_sanitizer($input);
                inputs[fieldname][ts] = $input;
            });
        });
    });

    // ---------- remarks row (Small Text, one per shift) ----------
    $table.find('tbody').append(
        `<tr class="section-row"><td colspan="${time_slots.length + 1}"><b>REMARKS</b></td></tr>`
    );
    let $remarks_row = $(`<tr><td>Remarks</td></tr>`).appendTo($table.find('tbody'));
    time_slots.forEach((ts, i) => {
        let $td = $(`<td class="slot-col-${i}"></td>`).appendTo($remarks_row);
        let $input = $('<textarea rows="1" class="form-control input-sm"></textarea>').appendTo($td);
        remarks_inputs[ts] = $input;
    });

    // ---------- keyboard navigation: Enter moves down the same column ----------
    function focus_cell(fieldname, ts) {
        let $inp = inputs[fieldname] && inputs[fieldname][ts];
        if ($inp) {
            $inp.trigger('focus');
            $inp.trigger('select');
        }
    }

    ordered_fieldnames.forEach((fieldname, row_idx) => {
        time_slots.forEach(ts => {
            inputs[fieldname][ts].on('keydown', function (e) {
                if (e.key !== 'Enter') return; // Tab keeps native browser behaviour

                e.preventDefault();
                let next_idx = e.shiftKey ? row_idx - 1 : row_idx + 1;

                if (next_idx >= 0 && next_idx < ordered_fieldnames.length) {
                    focus_cell(ordered_fieldnames[next_idx], ts);
                } else {
                    let ts_idx = time_slots.indexOf(ts);
                    let next_ts_idx = e.shiftKey ? ts_idx - 1 : ts_idx + 1;
                    if (next_ts_idx >= 0 && next_ts_idx < time_slots.length) {
                        let edge_row = e.shiftKey ? ordered_fieldnames.length - 1 : 0;
                        focus_cell(ordered_fieldnames[edge_row], time_slots[next_ts_idx]);
                    }
                }
            });
        });
    });

    function normalize_ts(s) {
        return (s || '').replace(/\s+/g, ' ').trim().toUpperCase();
    }

    let ts_lookup = {};
    time_slots.forEach(ts => { ts_lookup[normalize_ts(ts)] = ts; });

    function clear_grid() {
        Object.keys(inputs).forEach(fieldname => {
            time_slots.forEach(ts => inputs[fieldname][ts].val(''));
        });
        time_slots.forEach(ts => remarks_inputs[ts].val(''));
    }

    function fill_grid(rows) {
        clear_grid();
        let unmatched = [];
        rows.forEach(row => {
            let ts = ts_lookup[normalize_ts(row.time_slot)];
            if (!ts) {
                unmatched.push(row.time_slot);
                return;
            }
            Object.keys(inputs).forEach(fieldname => {
                if (row[fieldname] !== undefined && row[fieldname] !== null && inputs[fieldname][ts]) {
                    inputs[fieldname][ts].val(row[fieldname]);
                }
            });
            if (row.remarks && remarks_inputs[ts]) {
                remarks_inputs[ts].val(row.remarks);
            }
        });
        if (unmatched.length) {
            console.warn('Power Plant Log: could not match these saved time_slot values to a column:', unmatched);
            frappe.show_alert({
                message: __('Some saved rows had a Time Slot value that didn\'t match a column and were skipped. Check the browser console for details.'),
                indicator: 'orange'
            });
        }
    }

    function maybe_load() {
        let company = company_field.get_value();
        let plant = plant_field.get_value();
        let log_date = date_field.get_value();
        if (!company || !plant || !log_date) {
            clear_grid();
            current_doc_name = null;
            return;
        }
        frappe.call({
            method: "informatics_custom_apps.api.get_power_plant_log",
            args: { company, plant, log_date },
            callback: function (r) {
                if (r.message) {
                    current_doc_name = r.message.name;
                    fill_grid(r.message.rows);
                    frappe.show_alert({ message: __('Existing entry loaded — edit and save to update.'), indicator: 'blue' });
                } else {
                    clear_grid();
                    current_doc_name = null;
                }
            }
        });
    }

    // ---------- save ----------
    page.set_primary_action('Save', function () {
        let company = company_field.get_value();
        let plant = plant_field.get_value();
        let log_date = date_field.get_value();

        if (!company || !plant || !log_date) {
            frappe.msgprint(__('Please select Company, Plant and Date before saving.'));
            return;
        }

        let rows = time_slots.map(ts => {
            let row = { time_slot: ts };
            let has_value = false;
            Object.keys(inputs).forEach(fieldname => {
                let val = inputs[fieldname][ts].val();
                row[fieldname] = val === '' ? null : val;
                if (val) has_value = true;
            });
            let remark_val = remarks_inputs[ts].val();
            row.remarks = remark_val || null;
            if (remark_val) has_value = true;
            row.__has_value = has_value;
            return row;
        }).filter(r => r.__has_value).map(r => {
            delete r.__has_value;
            return r;
        });

        if (!rows.length) {
            frappe.msgprint(__('Please enter at least one reading before saving.'));
            return;
        }

        frappe.call({
            method: "informatics_custom_apps.api.save_power_plant_log",
            args: { company, plant, log_date, rows },
            freeze: true,
            callback: function (r) {
                if (r.message) {
                    current_doc_name = r.message;
                    frappe.show_alert({ message: __('Saved: {0}', [r.message]), indicator: 'green' });
                }
            }
        });
    }, 'octicon octicon-check');
};