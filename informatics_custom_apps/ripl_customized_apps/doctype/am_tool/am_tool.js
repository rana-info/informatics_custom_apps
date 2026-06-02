// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.ui.form.on("AM Tool", {
    asset_category_update(frm) {
        if (!frm.doc.asset_category_update) {
            frm.set_value({
                item_code: "",
                item_name: "",
                asset_category: "",
                wrong_account: "",
                correct_account: ""
            });
        }
    },

    accounting_dimension_update(frm) {
        if (!frm.doc.accounting_dimension_update) {
            frm.set_value({
                wrong_cost_center: "",
                correct_cost_center: "",
                segment: "",
                section: ""
            });
        }
    }
});