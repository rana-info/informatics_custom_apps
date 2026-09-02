frappe.provide("informatics_custom_apps");

informatics_custom_apps.set_warehouse_query = function (frm) {
    if (!frm.fields_dict.items) return;
    frm.set_query("warehouse", "items", function (doc, cdt, cdn) {
        let row = locals[cdt][cdn];
        let filters = {
            company: doc.company,
            branch: doc.branch || doc.custom_branch,
            segment: row.segment || row.custom_segment,
            item_code: row.item_code
        };
       if (cur_frm.doc.custom_is_capital !== undefined) {
            filters.custom_is_capital = cur_frm.doc.custom_is_capital;
        }
        return {
            query: "informatics_custom_apps.api.warehouse_query",
            filters: filters
        };
    });
};

const TRANSACTION_DOCTYPES = [
    "Purchase Order",
    "Purchase Receipt",
    "Purchase Invoice",
    "Sales Order",
    "Sales Invoice",
    "Delivery Note"

];

TRANSACTION_DOCTYPES.forEach(dt => {
    frappe.ui.form.on(dt, {
        refresh(frm) {
            informatics_custom_apps.set_warehouse_query(frm);
        }
    });
});