frappe.ui.form.on('Cost Analysis GL Grouping', {
    refresh(frm) {
        set_section_options(frm);
        load_account_numbers(frm);
    }
});

frappe.ui.form.on('Cost Analysis Section', {
    section_name(frm) {
        set_section_options(frm);
    },
    section_name_add(frm) {
        set_section_options(frm);
    },
    section_name_remove(frm) {
        set_section_options(frm);
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