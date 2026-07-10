// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Maintenance Job Request", {
	refresh(frm) {

	},
    company(frm) {
        frm.set_value("plant", null);
        if(frm.doc.company){
            frm.set_query("plant", function() {
                return {
                    filters: {
                        company: frm.doc.company
                    }
                };
            });
        }
    }
});
