// Copyright (c) 2025, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.ui.form.on("zzProduction Overview", {
    refresh(frm) {
        if (!frm.is_new() && frm.doc.docstatus==0) {
            frm.add_custom_button(__("Calculate Values"), function() {
                frappe.call({
                    method: "informatics_custom_apps.ripl_customized_apps.doctype.zzproduction_overview.zzproduction_overview.calculate_values",
                    args: {
                        docname: frm.doc.name
                    },
                    callback: function(r) {
                        frm.reload_doc();
                        frappe.msgprint("Values calculated successfully.");
                    }
                });
            }).addClass("btn-primary");
        }
    }
});
