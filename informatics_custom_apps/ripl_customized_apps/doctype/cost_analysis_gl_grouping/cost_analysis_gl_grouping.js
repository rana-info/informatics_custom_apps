frappe.ui.form.on('Cost Analysis GL Grouping', {
    refresh(frm) {
        set_section_options(frm);
        set_dynamic_row_options(frm);
        load_account_numbers(frm);
        add_create_per_bl_budget_button(frm);
    }
});

frappe.ui.form.on('Cost Analysis Section', {
    section_name(frm) {
        set_section_options(frm);
        set_dynamic_row_options(frm);
    },
    section_name_add(frm) {
        set_section_options(frm);
        set_dynamic_row_options(frm);
    },
    section_name_remove(frm) {
        set_section_options(frm);
        set_dynamic_row_options(frm);
    }
});

frappe.ui.form.on('Cost Analysis Total Row', {
    row_label(frm) {
        set_dynamic_row_options(frm);
    },
    total_row_add(frm) {
        set_dynamic_row_options(frm);
    },
    total_row_remove(frm) {
        set_dynamic_row_options(frm);
    }
});

function set_section_options(frm) {
    let sections = (frm.doc.section_name || [])
        .map(row => row.section_name)
        .filter(Boolean);
    frm.fields_dict["cost_analysis_gl"].grid.update_docfield_property(
        "section_name", "options", sections.join("\n")
    );
    frm.fields_dict["cost_analysis_gl"].grid.refresh();
}

function set_dynamic_row_options(frm) {
    let sections = (frm.doc.section_name || [])
        .map(row => row.section_name)
        .filter(Boolean);
    let total_rows = (frm.doc.total_row || [])
        .map(row => row.row_label)
        .filter(Boolean);
    let combined = sections.concat(total_rows);

    if (frm.fields_dict["total_row_components"]) {
        let grid = frm.fields_dict["total_row_components"].grid;
        grid.update_docfield_property("row_label", "options", total_rows.join("\n"));
        grid.update_docfield_property("component_name", "options", combined.join("\n"));
        grid.refresh();
    }

    if (frm.fields_dict["row_sequence"]) {
        let grid = frm.fields_dict["row_sequence"].grid;
        grid.update_docfield_property("row_name", "options", combined.join("\n"));
        grid.refresh();
    }
}

function load_account_numbers(frm) {
    frappe.call({
        method: "informatics_custom_apps.ripl_customized_apps.doctype.cost_analysis_gl_grouping.cost_analysis_gl_grouping.get_all_account_numbers",
        callback: function(r) {
            let options = r.message || [];
            frm.fields_dict["cost_analysis_gl"].grid.update_docfield_property(
                "account_number", "options", options
            );
            frm.fields_dict["cost_analysis_gl"].grid.refresh();
        }
    });
}

function add_create_per_bl_budget_button(frm) {
    frm.add_custom_button(__('Create Per BL Budget'), () => {
        create_per_bl_budget_dialog(frm);
    });
}

function create_per_bl_budget_dialog(frm) {
    frappe.call({
        method: 'informatics_custom_apps.ripl_customized_apps.doctype.cost_analysis_gl_grouping.cost_analysis_gl_grouping.get_all_plants',
        callback: function(r) {
            const branches = r.message || [];
            if (!branches.length) {
                frappe.msgprint(__('No Plant (Branch) records found.'));
                return;
            }

            const plant_options = branches.map(b => ({ label: b.name, value: b.name }));
            show_per_bl_budget_dialog(frm, plant_options);
        }
    });
}

function show_per_bl_budget_dialog(frm, plant_options) {
        const d = new frappe.ui.Dialog({
            title: __('Create Per BL Budget'),
            size: 'large',
            fields: [
                {
                    fieldname: 'from_date',
                    label: __('Applicable From'),
                    fieldtype: 'Date',
                    reqd: 1
                },
                {
                    fieldname: 'col_break_1',
                    fieldtype: 'Column Break'
                },
                {
                    fieldname: 'to_date',
                    label: __('Applicable Till'),
                    fieldtype: 'Date',
                    reqd: 1
                },
                {
                    fieldname: 'sec_break_1',
                    fieldtype: 'Section Break',
                    label: __('Select Plant(s)')
                },
                {
                    fieldname: 'plants',
                    label: __('Plants'),
                    fieldtype: 'MultiCheck',
                    options: plant_options,
                    columns: 3
                }
            ],
            primary_action_label: __('Create'),
            primary_action(values) {
                if (!values.plants || !values.plants.length) {
                    frappe.msgprint(__('Please select at least one Plant.'));
                    return;
                }
                if (values.from_date > values.to_date) {
                    frappe.msgprint(__('Applicable From cannot be after Applicable Till.'));
                    return;
                }

                frappe.call({
                    method:
                        'informatics_custom_apps.ripl_customized_apps.doctype.cost_analysis_gl_grouping.cost_analysis_gl_grouping.create_per_bl_budget',
                    args: {
                        from_date: values.from_date,
                        to_date: values.to_date,
                        plants: values.plants
                    },
                    freeze: true,
                    freeze_message: __('Creating Per BL Budget record(s)...'),
                    callback: function (r) {
                        if (r.exc) return;

                        d.hide();
                        const result = r.message || {};
                        const created_docs = result.created || [];
                        const skipped = result.skipped || [];

                        let msg = '';
                        if (created_docs.length) {
                            msg +=
                                '<b>' + __('Created') + ':</b><br>' +
                                created_docs
                                    .map(
                                        row =>
                                            `<a href="/app/per-bl-budget/${encodeURIComponent(row.name)}" target="_blank">${frappe.utils.escape_html(row.plant)}</a>`
                                    )
                                    .join('<br>');
                        }
                        if (skipped.length) {
                            msg +=
                                (msg ? '<br><br>' : '') +
                                '<b>' + __('Skipped') + ':</b><br>' +
                                skipped.map(s => frappe.utils.escape_html(s)).join('<br>');
                        }

                        frappe.msgprint({
                            title: __('Per BL Budget'),
                            message: msg || __('No records created.'),
                            indicator: created_docs.length ? 'green' : 'orange'
                        });
                    }
                });
            }
        });

        d.show();
}