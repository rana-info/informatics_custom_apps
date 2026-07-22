// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Warehouse Dump Entry", {
	setup: function (frm) {},

	refresh: function (frm) {
		frm.set_query("transporter", function () {
			return {
				filters: {
					is_transporter: 1
				}
			};
		});

		frm.set_query("supplier", function () {
			return {
				filters: {
					is_transporter: false
				}
			};
		});

		frm.set_query("purchase_orders", "purchase_orders", function () {
			let existing_purchase_orders = [];
			frm.doc.purchase_orders.forEach(element => {
				if (element.purchase_orders) {
					existing_purchase_orders.push(element.purchase_orders);
				}
			});
			return {
				filters: {
					company: frm.doc.company,
					branch: frm.doc.branch,
					supplier: frm.doc.supplier,
					name: ["not in", existing_purchase_orders],
					docstatus: 1
				}
			};
		});

		frm.events.set_po_grid_properties(frm);
		frm.events.set_items_grid_properties(frm);
	},

	branch: function (frm) {
		frm.clear_table("purchase_orders");
		frm.clear_table("items");
		frm.refresh_field("purchase_orders");
		frm.refresh_field("items");
	},

	supplier: function (frm) {
		frm.clear_table("purchase_orders");
		frm.clear_table("items");
		frm.refresh_field("purchase_orders");
		frm.refresh_field("items");
	},

	vehicle_owner: function (frm) {
		if (frm.doc.vehicle_owner !== "Company Owned") {
			frm.set_value("driver", "");
		}
		frm.refresh_field("driver");
	},

	driver: function (frm) {
		if (frm.doc.driver) {
			frappe.db.get_value("Driver", frm.doc.driver, "full_name", (r) => {
				if (r && r.full_name) {
					frm.set_value("driver_name", r.full_name);
				}
			});
		}
	},

	vehicle_number: function (frm) {
		if (frm.doc.vehicle_number) {
			frm.set_value("vehicle_number", frm.doc.vehicle_number.toUpperCase());
		}
	},

	// Purchase Orders table should stay editable (add/select/delete rows),
	// regardless of any read-only setting inherited from the shared child doctype.
	set_po_grid_properties: function (frm) {
		let grid = frm.fields_dict["purchase_orders"] && frm.fields_dict["purchase_orders"].grid;
		if (!grid) return;
		frm.set_df_property("purchase_orders", "read_only", 0);
		grid.cannot_add_rows = true;
		(grid.docfields || []).forEach((df) => {
			if (df.fieldname === "purchase_orders") {
				df.read_only = 0;
			}
		});
		grid.refresh();
	},

	// Items table: only Accepted Qty / Rejected Qty should be user-editable,
	// everything else is fetched from the PO and must stay read-only.
	set_items_grid_properties: function (frm) {
		let grid = frm.fields_dict["items"] && frm.fields_dict["items"].grid;
		if (!grid) return;
		let editable_fields = ["accepted_quantity", "rejected_quantity"];
		grid.cannot_add_rows = true;
		(grid.docfields || []).forEach((df) => {
			if (!["Section Break", "Column Break"].includes(df.fieldtype)) {
				df.read_only = editable_fields.includes(df.fieldname) ? 0 : 1;
			}
		});
		grid.refresh();
	},

	fetch_purchase_orders: function (frm) {
		if (!frm.doc.supplier) {
			frappe.throw("Please select Supplier first");
		}
		if (!frm.doc.branch) {
			frappe.throw("Please select Branch first");
		}
		frm.call({
			method: "fetch_purchase_orders",
			doc: frm.doc,
			freeze: true,
			freeze_message: __("Fetching Purchase Orders..."),
			callback: function (r) {
				if (r.message) {
					frm.refresh_field("purchase_orders");
				}
			}
		});
	},

	gross_weight: function (frm) {
		if (frm.doc.gross_weight && frm.doc.tare_weight) {
			frm.set_value("net_weight", frm.doc.gross_weight - frm.doc.tare_weight);
			if (frm.doc.net_weight <= 0) {
				frm.set_value("gross_weight", 0);
				frm.set_value("net_weight", 0);
				frm.refresh_field("gross_weight");
				frm.refresh_field("net_weight");
				frappe.throw("Net weight can't be zero");
			}
		}
	},

	tare_weight: function (frm) {
		if (frm.doc.gross_weight && frm.doc.tare_weight) {
			frm.set_value("net_weight", frm.doc.gross_weight - frm.doc.tare_weight);
			if (frm.doc.net_weight <= 0) {
				frm.set_value("tare_weight", 0);
				frm.set_value("net_weight", 0);
				frm.refresh_field("tare_weight");
				frm.refresh_field("net_weight");
				frappe.throw("Net weight can't be zero");
			}
		}
	},

	get_items: function (frm) {
		if (!frm.doc.purchase_orders || !frm.doc.purchase_orders.length) {
			frappe.throw("Purchase order table is empty");
		}
		if (frm.doc.purchase_orders.length > 1) {
			frappe.throw("Please keep exactly 1 Purchase Order in the table before fetching items");
		}
		frm.call({
			method: "get_item_from_po",
			doc: frm.doc,
			freeze: true,
			freeze_message: __("Mapping Po Items..."),
			callback: function (r) {
				if (r.message) {
					frm.refresh_field("items");
					frm.events.set_items_grid_properties(frm);
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
		const child = locals[cdt][cdn];
		child.received_quantity = child.accepted_quantity + child.rejected_quantity;
		refresh_field("received_quantity", cdn, "items");
	},
	rejected_quantity: function (frm, cdt, cdn) {
		const child = locals[cdt][cdn];
		child.received_quantity = child.accepted_quantity + child.rejected_quantity;
		refresh_field("received_quantity", cdn, "items");
	}
});