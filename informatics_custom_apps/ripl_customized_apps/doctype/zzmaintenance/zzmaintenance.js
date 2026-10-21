// Copyright (c) 2026, Dexciss and contributors
// For license information, please see license.txt

frappe.ui.form.on("ZZMaintenance", {
    refresh: function (frm) {
        frm.disable_save();

        frm.set_query("gate_entry", () => ({
            filters: { company: frm.doc.company, branch: frm.doc.branch }
        }));

        frm.set_query("branch", () => {
            const filters = {};
            if (frm.doc.company) filters.company = frm.doc.company;
            return { filters };
        });

        frm.set_query("transporter", () => ({ filters: { is_transporter: 1 } }));
        frm.set_query("supplier", () => ({ filters: { is_transporter: 0 } }));

        frm.set_query("purchase_orders", "purchase_orders", function () {
            if (!frm.doc.company || !frm.doc.branch || !frm.doc.supplier) {
                frappe.show_alert({
                    message: __("Select Company, Plant and Supplier first"),
                    indicator: "orange"
                });
            }

            const existing = (frm.doc.purchase_orders || [])
                .filter(r => r.purchase_orders)
                .map(r => r.purchase_orders);

            // only send filters that have a value
            const filters = { docstatus: 1 };
            if (frm.doc.company) filters.company = frm.doc.company;
            if (frm.doc.branch) filters.branch = frm.doc.branch;
            if (frm.doc.supplier) filters.supplier = frm.doc.supplier;
            if (existing.length) filters.name = ["not in", existing];
            return { filters };
        });

        frm.trigger("set_fields_read_only");
        frm.trigger("make_custom_buttons");
    },

    make_custom_buttons: function (frm) {
        frm.clear_custom_buttons();

        const run = (method) => {
            frm.call({
                method: method,
                doc: frm.doc,
                freeze: true,
                freeze_message: __("Processing..."),
                callback: function (r) {
                    if (r.message) {
                        frappe.show_alert({ message: __("Done ..."), indicator: "green" });
                        frm.reload_doc();
                    }
                }
            });
        };

        if (frm.doc.maintenance_type === "Create") {
            frm.add_custom_button(__("Create"), () => run("create_transaction"));
        } else if (frm.doc.maintenance_type === "Update") {
            frm.add_custom_button(__("Update"), () => run("update_transaction"));
        }
    },

    maintenance_type: function (frm) {
        frm.trigger("make_custom_buttons");
        frm.events.clear_fields(frm);
        frm.events.set_fields_read_only(frm);
    },

    company: function (frm) {
        // drop the plant only if it belongs to a different company
        if (!frm.doc.branch) return;
        frappe.db.get_value("Branch", frm.doc.branch, "company").then(r => {
            if (r.message.company !== frm.doc.company) {
                frm.set_value("branch", null);
                frm.set_value("location", null);
                frm.set_value("abbr", null);
            }
        });
    },

    gate_entry: function (frm) {
        if (frm.doc.gate_entry) {
            frappe.confirm(__("Do you want to map the gate entry data?"), function () {
                frm.call({
                    method: "map_gate_entry_data",
                    doc: frm.doc,
                    freeze: true,
                    freeze_message: __("Mapping Data..."),
                    callback: function (r) {
                        if (r.message) {
                            frm.refresh_fields();
                        }
                    }
                });
            });
        }
    },

    gross_weight: function (frm) {
        frm.events.calculate_net_weight(frm, "gross_weight");
    },

    tare_weight: function (frm) {
        frm.events.calculate_net_weight(frm, "tare_weight");
    },

    calculate_net_weight: function (frm, changed_field) {
        if (frm.doc.gross_weight && frm.doc.tare_weight) {
            const net = frm.doc.gross_weight - frm.doc.tare_weight;
            frm.set_value("net_weight", net);
            if (net <= 0) {
                frm.set_value(changed_field, 0);
                frm.set_value("net_weight", 0);
                frm.refresh_fields();
                frappe.throw(__("Net weight can't be zero"));
            }
        }
    },

    set_fields_read_only: function (frm) {
        const read_only = frm.doc.maintenance_type === "Update";
        ["branch", "company", "location", "entry_type"].forEach(field => {
            frm.set_df_property(field, "read_only", read_only);
        });
    },

    clear_fields: function (frm) {
        const skip_types = ["Section Break", "Column Break", "Tab Break", "Button"];
        const skip_fields = ["maintenance_type", "vehicle_owner", "time", "entry_type"];

        frappe.get_meta(frm.doc.doctype).fields.forEach((df) => {
            if (skip_types.includes(df.fieldtype) || skip_fields.includes(df.fieldname)) return;

            if (df.fieldtype === "Table") {
                frm.clear_table(df.fieldname);
            } else if (df.fieldtype === "Float") {
                frm.set_value(df.fieldname, 0.0);
            } else {
                frm.set_value(df.fieldname, null);
            }
        });
        frm.refresh_fields();
    },

    get_items: function (frm) {
        if (!(frm.doc.purchase_orders || []).length) {
            frappe.throw(__("Purchase order table is empty"));
        }
        frm.call({
            method: "get_item_from_po",
            doc: frm.doc,
            freeze: true,
            freeze_message: __("Mapping PO Items..."),
            callback: function (r) {
                if (r.message) {
                    frm.refresh_field("items");
                }
            }
        });
    }
});

frappe.ui.form.on("Purchase Orders", {
    purchase_orders_remove: function (frm) {
        frm.clear_table("items");
        frm.refresh_field("items");
    },
    purchase_orders_add: function (frm) {
        frm.clear_table("items");
        frm.refresh_field("items");
    }
});

frappe.ui.form.on("Purchase Details", {
    accepted_quantity: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, "received_quantity",
            (row.accepted_quantity || 0) + (row.rejected_quantity || 0));
    },
    rejected_quantity: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, "received_quantity",
            (row.accepted_quantity || 0) + (row.rejected_quantity || 0));
    }
});