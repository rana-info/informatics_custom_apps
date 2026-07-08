// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.ui.form.on("DMR Technical Lab Parameters", {
	refresh(frm) {

	},
    company(frm){
        frm.set_value("plant", "");
        frm.set_query("plant", function() {
            return {
                filters: {
                    company: frm.doc.company
                }
            };
        });
    },
    date(frm){
        if(frm.doc.date> frappe.datetime.nowdate()){
            frappe.msgprint("Date cannot be in the future");
            frm.set_value("date", frappe.datetime.nowdate());
        }
    }
});
