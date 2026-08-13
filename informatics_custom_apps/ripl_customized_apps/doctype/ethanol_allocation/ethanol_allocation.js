// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Ethanol Allocation", {
    onload: async function(frm) {
        if (!frm.is_new()) return;

        // Skip if already populated
        if (frm.doc.ethanol_supply_year || (frm.doc.allocation || []).length) {
            return;
        }

        // Get active Ethanol Supply Year
        const years = await frappe.db.get_list("Ethanol Supply Year", {
            filters: {
                disabled: 0
            },
            fields: ["name"],
            order_by: "year_start_date desc",
            limit: 1
        });

        if (!years.length) {
            frappe.msgprint(__("No active Ethanol Supply Year found."));
            return;
        }

        await frm.set_value("ethanol_supply_year", years[0].name);

        // Fetch complete document
        const doc = await frappe.db.get_doc(
            "Ethanol Supply Year",
            years[0].name
        );

        frm.clear_table("allocation");

        (doc.ethanol_supply_quarter || []).forEach(row => {
            let child = frm.add_child("allocation");

            // Replace 'quarter' with your actual fieldname
            child.quarter = row.quarter;
        });

        frm.refresh_field("allocation");
    }
});
