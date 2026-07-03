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

    let sections = [
        { title: "UNIT PRESSURE", fields: [
            ["raw__water_pump_outlet", "Raw Water Pump Outlet"],
            ["mgf_inlet", "MGF Inlet"],
            ["mgf_outlet", "MGF Outlet"],
            ["mcf_inlet", "MCF Inlet"],
            ["mcf_outlet", "MCF Outlet"],
            ["high_pressure_pump_outlet", "High Pressure Pump Outlet"],
            ["ro_1st_stage", "RO 1st Stage"],
            ["ro_2nd_stage", "RO 2nd Stage"],
            ["ro_reject", "RO Reject"],
            ["pressure_difference", "Pressure Difference"],
            ["dg_pump_outlet", "DG Pump Outlet"],
            ["sac_inlet", "SAC Inlet"],
            ["sac_outlet", "SAC Outlet"],
            ["sba_inlet", "SBA Inlet"],
            ["sba_outlet", "SBA Outlet"],
            ["mb_inlet", "MB Inlet"],
            ["mb_outlet", "MB Outlet"],
        ]},
        { title: "WATER FLOW", fields: [
            ["mgf_inlet1", "MGF Inlet"],
            ["ro_inlet", "RO Inlet"],
            ["ro_outlet", "RO Outlet"],
            ["reject", "Reject"],
            ["mb_outlet1", "MB Outlet"],
            ["recovery", "Recovery"],
        ]},
        { title: "MGF INLET PARAMETERS", fields: [
            ["turbidity", "Turbidity"],
            ["ph", "PH"],
            ["conductivity", "Conductivity"],
            ["total_hardness", "Total Hardness"],
            ["total_alkalinity", "Total Alkalinity"],
            ["silica_as_sio2", "Silica as SiO2"],
            ["iron_as_fe", "Iron as Fe"],
        ]},
        { title: "R.O. INLET PARAMETERS", fields: [
            ["ph1", "PH"],
            ["conductivity1", "Conductivity"],
            ["total_hardness1", "Total Hardness"],
            ["total_alkalinity1", "Total Alkalinity"],
            ["silica_as_sio21", "Silica as SiO2"],
            ["orp", "ORP"],
            ["frc", "FRC"],
        ]},
        { title: "R.O. OUTLET PARAMETERS", fields: [
            ["ph2", "PH"],
            ["conductivity2", "Conductivity"],
            ["total_hardness2", "Total Hardness"],
            ["silica_as_sio22", "Silica as SiO2"],
        ]},
        { title: "SAC OUTLET PARAMETERS", fields: [
            ["ph3", "PH"],
            ["conductivity3", "Conductivity"],
        ]},
        { title: "SBA OUTLET PARAMETERS", fields: [
            ["ph4", "PH"],
            ["conductivity4", "Conductivity"],
            ["silica_as_sio23", "Silica as SiO2"],
        ]},
        { title: "MB OUTLET PARAMETERS", fields: [
            ["ph5", "PH"],
            ["conductivity5", "Conductivity"],
            ["silica_as_sio24", "Silica as SiO2"],
            ["ph_after_morph_dosing", "PH after Morph. Dosing"],
        ]},
        { title: "STORAGE TANK LEVEL", fields: [
            ["dm_water_tank", "DM Water Tank"],
            ["make_up_water_tank", "Make-Up Water Tank"],
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
                maybe_load();
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
            onchange: function () { maybe_load(); }
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
            onchange: function () { maybe_load(); }
        },
        render_input: true
    });
    date_field.set_value(frappe.datetime.get_today());

    // ---------- build the matrix table ----------
    let $table = $(`<table class="table ro-log-table">
        <thead><tr><th>Parameter</th>
        ${time_slots.map((t, i) => `<th class="slot-col-${i}">${t}</th>`).join('')}
        </tr></thead><tbody></tbody></table>`).appendTo(page.body);

    let inputs = {}; // inputs[fieldname][time_slot] = jquery input
    let current_doc_name = null; // set when an existing record is loaded
    let ordered_fieldnames = []; // row order, top to bottom, for keyboard navigation

    sections.forEach(sec => {
        $table.find('tbody').append(
            `<tr class="section-row"><td colspan="${time_slots.length + 1}"><b>${sec.title}</b></td></tr>`
        );
        sec.fields.forEach(([fieldname, label]) => {
            let $row = $(`<tr><td>${label}</td></tr>`).appendTo($table.find('tbody'));
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

    function clear_grid() {
        Object.keys(inputs).forEach(fieldname => {
            time_slots.forEach(ts => inputs[fieldname][ts].val(''));
        });
        current_doc_name = null;
    }

    function fill_grid(rows) {
        clear_grid();
        rows.forEach(row => {
            let ts = row.time_slot;
            Object.keys(inputs).forEach(fieldname => {
                if (row[fieldname] !== undefined && row[fieldname] !== null && inputs[fieldname][ts]) {
                    inputs[fieldname][ts].val(row[fieldname]);
                }
            });
        });
    }

    function maybe_load() {
        let company = company_field.get_value();
        let plant = plant_field.get_value();
        let log_date = date_field.get_value();
        if (!company || !plant || !log_date) {
            clear_grid();
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