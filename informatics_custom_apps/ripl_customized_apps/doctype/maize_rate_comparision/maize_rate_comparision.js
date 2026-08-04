// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

const CHILD_TABLE_FIELDS = [
    "rsl_loukha",
    "buttar_biofuel",
    "eth_biofuel",
    "superior_biofuels",
    "rsl_belwara",
    "karimganj_biofuel",
];

frappe.ui.form.on("Maize Rate Comparision", {
    onload(frm) {
        if (frm.is_new()) {
            frm.trigger("fetch_master_data");
        }
    },

    refresh(frm) {
        frm.trigger("lock_child_tables");
    },

    lock_child_tables(frm) {
        CHILD_TABLE_FIELDS.forEach((fieldname) => {
            const grid = frm.fields_dict[fieldname].grid;
            grid.cannot_add_rows = true;
            grid.cannot_delete_rows = true;

            // hide the buttons/checkboxes outright
            grid.wrapper.find(".grid-add-row").hide();
            grid.wrapper.find(".grid-remove-rows").hide();
            grid.wrapper.find(".grid-remove-all-rows").hide();
            grid.wrapper.find(".grid-append-row").hide();
            grid.wrapper.find(".grid-row-check").hide();
            grid.wrapper.find(".grid-body .grid-row .grid-row-check").hide();

            frm.refresh_field(fieldname);
        });
    },

    fetch_master_data(frm) {
        frappe.call({
            method:
                "informatics_custom_apps.ripl_customized_apps.doctype.maize_rate_comparision.maize_rate_comparision.get_master_plant_rows",
            callback: function (r) {
                if (r.exc || !r.message) return;

                const data = r.message;
                Object.keys(data).forEach((fieldname) => {
                    frm.clear_table(fieldname);
                    data[fieldname].forEach((row) => {
                        frm.add_child(fieldname, row);
                    });
                    frm.refresh_field(fieldname);
                });
            },
        });
    },
});