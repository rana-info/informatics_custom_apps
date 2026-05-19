// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Procurement Budget", {

    setup(frm) {

        frm.set_query("gl", function () {
            return {
                filters: {
                    company: frm.doc.company,
                    is_group: 0
                }
            };
        });

    },

    company(frm) {

        frm.fields_dict["budget_details"].grid.get_field("cost_center").get_query =
            function () {
                return {
                    filters: {
                        company: frm.doc.company
                    }
                };
            };

        
            frm.fields_dict["budget_details"].grid.get_field("plant").get_query =
            function () {
                return {
                    filters: {
                        company: frm.doc.company
                    }
                };
            };

    }

});


