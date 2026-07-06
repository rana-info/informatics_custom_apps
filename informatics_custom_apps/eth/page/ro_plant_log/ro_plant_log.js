frappe.pages['ro-plant-log'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'RO Plant Log Entry',
        single_column: true
    });

    let time_slots = [
        "9:30 AM-1:30 PM", "1:30 PM-5:30 PM", "5:30 PM-9:30 PM",
        "9:30 PM-1:30 AM", "1:30 AM-5:30 AM", "5:30 AM-9:30 AM"
    ];

    // each field: [fieldname, label, unit-or-null]
    let sections = [
        { title: "UNIT PRESSURE", fields: [
            ["raw__water_pump_outlet", "Raw Water Pump Outlet", "Kg/Cm2"],
            ["mgf_inlet", "MGF Inlet", "Kg/Cm2"],
            ["mgf_outlet", "MGF Outlet", "Kg/Cm2"],
            ["mcf_inlet", "MCF Inlet", "Kg/Cm2"],
            ["mcf_outlet", "MCF Outlet", "Kg/Cm2"],
            ["high_pressure_pump_outlet", "High Pressure Pump Outlet", "Kg/Cm2"],
            ["ro_1st_stage", "RO 1st Stage", "Kg/Cm2"],
            ["ro_2nd_stage", "RO 2nd Stage", "Kg/Cm2"],
            ["ro_reject", "RO Reject", "Kg/Cm2"],
            ["pressure_difference", "Pressure Difference", "Kg/Cm2"],
            ["dg_pump_outlet", "DG Pump Outlet", "Kg/Cm2"],
            ["sac_inlet", "SAC Inlet", "Kg/Cm2"],
            ["sac_outlet", "SAC Outlet", "Kg/Cm2"],
            ["sba_inlet", "SBA Inlet", "Kg/Cm2"],
            ["sba_outlet", "SBA Outlet", "Kg/Cm2"],
            ["mb_inlet", "MB Inlet", "Kg/Cm2"],
            ["mb_outlet", "MB Outlet", "Kg/Cm2"],
        ]},
        { title: "WATER FLOW", fields: [
            ["mgf_inlet1", "MGF Inlet", "TPH"],
            ["ro_inlet", "RO Inlet", "TPH"],
            ["ro_outlet", "RO Outlet", "TPH"],
            ["reject", "Reject", "TPH"],
            ["mb_outlet1", "MB Outlet", "TPH"],
            ["recovery", "Recovery", "%"],
        ]},
        { title: "MGF INLET PARAMETERS", fields: [
            ["turbidity", "Turbidity", "NTU"],
            ["ph", "PH", null],
            ["conductivity", "Conductivity", "µs/cm"],
            ["total_alkalinity", "Total Alkalinity", "PPM"],
            ["silica_as_sio2", "Silica as SiO2", "PPM"],
        ]},
        { title: "R.O. INLET PARAMETERS", fields: [
            ["ph1", "PH", null],
            ["total_hardness1", "Total Hardness", "PPM"],
            ["total_alkalinity1", "Total Alkalinity", "PPM"],
            ["silica_as_sio21", "Silica as SiO2", "PPM"],
            ["orp", "ORP", "PPM"],
        ]},
        { title: "R.O. OUTLET PARAMETERS", fields: [
            ["ph2", "PH", null],
            ["conductivity2", "Conductivity", "µs/cm"],
            ["total_hardness2", "Total Hardness", "PPM"],
            ["silica_as_sio22", "Silica as SiO2", "PPM"],
        ]},
        { title: "STORAGE TANK LEVEL", fields: [
            ["dm_water_tank", "DM Water Tank", "%"],
            ["make_up_water_tank", "Make-Up Water Tank", "%"],
        ]},
    ];

    // ---------- inject styles once ----------
    if (!$('#ro-plant-log-style').length) {
        $(`<style id="ro-plant-log-style">
            .ro-log-table { border-collapse: collapse; width: 100%; }
            .ro-log-table th, .ro-log-table td {
                border: 1px solid var(--border-color, #d1d8dd);
                padding: 4px 6px;
                text-align: center;
                vertical-align: middle;
            }
            .ro-log-table td:first-child, .ro-log-table th:first-child {
                text-align: left;
                font-weight: 500;
                background: var(--fg-color, #fafbfc);
                position: sticky;
                left: 0;
                z-index: 2;
            }
            .ro-log-table .section-row td {
                background: var(--gray-200, #e7eaec);
                font-weight: 600;
                text-align: left;
                padding: 6px 8px;
            }
            .ro-uom {
                color: var(--text-muted, #8d99a6);
                font-size: 11px;
                font-weight: 400;
            }
            /* distinct colour per time-slot column */
            .ro-log-table th.slot-col-0, .ro-log-table td.slot-col-0 { background-color: #eaf4ff; }
            .ro-log-table th.slot-col-1, .ro-log-table td.slot-col-1 { background-color: #eafff1; }
            .ro-log-table th.slot-col-2, .ro-log-table td.slot-col-2 { background-color: #fff9ea; }
            .ro-log-table th.slot-col-3, .ro-log-table td.slot-col-3 { background-color: #fff0ea; }
            .ro-log-table th.slot-col-4, .ro-log-table td.slot-col-4 { background-color: #f5eaff; }
            .ro-log-table th.slot-col-5, .ro-log-table td.slot-col-5 { background-color: #eafffb; }
            .ro-log-table td.slot-col-0, .ro-log-table td.slot-col-1,
            .ro-log-table td.slot-col-2, .ro-log-table td.slot-col-3,
            .ro-log-table td.slot-col-4, .ro-log-table td.slot-col-5 {
                transition: outline 0.1s ease-in-out;
            }
            .ro-log-table input.form-control {
                border: none;
                background: transparent;
                text-align: center;
                width: 100%;
            }
            .ro-log-table td:hover {
                outline: 2px solid var(--primary, #2490ef);
                outline-offset: -2px;
            }
            .ro-log-table input.form-control:focus {
                background: #fff;
                box-shadow: none;
            }
            .log-header { align-items: flex-end; }
        </style>`).appendTo(document.head);
    }

    // ---------- state (declared before any control that could fire onchange during setup) ----------
    let inputs = {}; // inputs[fieldname][time_slot] = jquery input
    let current_doc_name = null; // set when an existing record is loaded
    let ordered_fieldnames = []; // row order, top to bottom, for keyboard navigation

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
    let $table = $(`<table class="table ro-log-table">
        <thead><tr><th>Parameter</th>
        ${time_slots.map((t, i) => `<th class="slot-col-${i}">${t}</th>`).join('')}
        </tr></thead><tbody></tbody></table>`).appendTo(page.body);

    sections.forEach(sec => {
        $table.find('tbody').append(
            `<tr class="section-row"><td colspan="${time_slots.length + 1}"><b>${sec.title}</b></td></tr>`
        );
        sec.fields.forEach(([fieldname, label, uom]) => {
            let label_html = uom
                ? `${label} <span class="ro-uom">(${uom})</span>`
                : label;
            let $row = $(`<tr><td>${label_html}</td></tr>`).appendTo($table.find('tbody'));
            inputs[fieldname] = {};
            ordered_fieldnames.push(fieldname);
            time_slots.forEach((ts, i) => {
                let $td = $(`<td class="slot-col-${i}"></td>`).appendTo($row);
                let $input = $('<input type="number" step="0.01" class="form-control input-sm">').appendTo($td);
                inputs[fieldname][ts] = $input;
            });
        });
    });

    // ---------- keyboard navigation: Enter / Tab move down the same column ----------
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
                    // reached top/bottom of this column - jump to the
                    // first/last row of the next/previous time slot
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

    // map of normalized time-slot string -> the exact string used as a key in `inputs`
    let ts_lookup = {};
    time_slots.forEach(ts => { ts_lookup[normalize_ts(ts)] = ts; });

    function clear_grid() {
        Object.keys(inputs).forEach(fieldname => {
            time_slots.forEach(ts => inputs[fieldname][ts].val(''));
        });
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
        });
        if (unmatched.length) {
            console.warn('RO Plant Log: could not match these saved time_slot values to a column:', unmatched);
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
            method: "informatics_custom_apps.api.get_ro_plant_log",
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
            method: "informatics_custom_apps.api.save_ro_plant_log",
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