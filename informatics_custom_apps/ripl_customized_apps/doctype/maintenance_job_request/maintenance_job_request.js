// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Maintenance Job Request", {
	refresh(frm) {
    },
//    work_status(frm){
//     if(frm.doc.work_status != "Completed"){
//         frm.set_value("contractor_invoice_number", null);
//         frm.set_value("contractor_invoice_date", null);
//    }},
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
