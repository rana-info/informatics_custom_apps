function handle_status_logic(frm) {
	let is_completed = frm.doc.is_completed;
	let is_in_progress = frm.doc.is_in_progress;

	frm.set_df_property("is_completed", "hidden", 0);
	frm.set_df_property("is_in_progress", "hidden", 0);

	if (is_completed) {
		frm.set_df_property("is_in_progress", "hidden", 1);
	}

	if (is_in_progress) {
		frm.set_df_property("is_completed", "hidden", 1);
	}

	frm.refresh_fields(["is_completed", "is_in_progress"]);
}

function toggle_ge_type_checkboxes(frm, is_manual, is_stock, set_values = true) {

	const has_manual = Number(is_manual || 0) === 1;
	const has_stock  = Number(is_stock  || 0) === 1;

	frm.set_df_property("is_manual_weighment", "hidden", has_manual ? 0 : 1);
	frm.set_df_property("is_stock_transfer",   "hidden", has_stock  ? 0 : 1);

	if (set_values) {
		frm.set_value("is_manual_weighment", has_manual ? 1 : 0);
		frm.set_value("is_stock_transfer",   has_stock  ? 1 : 0);
	}

	frm.refresh_fields(["is_manual_weighment", "is_stock_transfer"]);
}

function load_data(frm) {
	// Do not re-populate fields on submitted/approved documents — it dirties the form
	if (!frm.doc.gate_entry || !frm.doc.correction_type || frm.doc.docstatus !== 0) {
		return;
	}

	frm.clear_table("items");

	frm.call({
		method: "load_gate_entry_data",
		doc: frm.doc,
		args: {
			correction_type: frm.doc.correction_type,
		},
		freeze: true,

		callback: (r) => {
			if (!r.message) return;

			let data = r.message;

			frm.doc.__is_stock_transfer = data.is_stock_transfer || 0;
			frm.doc.__is_manual_weighment = data.is_manual_weighment || 0;
			frm.doc.__entry_type = data.entry_type || frm.doc.__entry_type || "";
			frm.doc.__is_weighment_required = data.is_weighment_required ?? 1;

			frm.set_value("is_manual_weighment", data.is_manual_weighment || 0);
			frm.set_value("is_stock_transfer", data.is_stock_transfer || 0);

			frm.set_value("is_completed", data.is_completed || 0);
			frm.set_value("is_in_progress", data.is_in_progress || 0);

			frm.clear_table("items");

			(data.items || []).forEach((d) => {
				let row = frm.add_child("items");

				row.item_code = d.item_code;
				row.item_name = d.item_name;
				row.purchase_order = d.purchase_order;
				row.purchase_order_item = d.purchase_order_item;
				row.accepted_qty = d.accepted_qty;
				row.new_accepted_qty = d.new_accepted_qty;
				row.uom = d.uom;
				row.po_item_qty = d.po_item_qty;
				row.gate_entry_item = d.gate_entry_item;
			});

			frm.refresh_field("items");

			toggle_new_qty_readonly(frm);
			toggle_weight_readonly(frm);
			toggle_outward_sections(frm);
			filter_correction_type_options(frm);
			apply_purchase_order_filter(frm);
			apply_manual_entry_po_filter(frm);

			if (data.old_purchase_order) {
				frm.set_value("old_purchase_order", data.old_purchase_order);
			}

			// Auto-fill old_segment from Gate Entry
			frm.set_value("old_segment", data.old_segment || "");

			let no_weighment =
				frm.doc.__is_weighment_required === "No" || frm.doc.__is_weighment_required === 0;

			// For in-progress manual weighment + Wrong Weight: show weight section so user can set both weights
			let is_manual_inprogress_weight =
				frm.doc.__is_manual_weighment &&
				frm.doc.is_in_progress &&
				frm.doc.correction_type === "Wrong Weight";

			if (!no_weighment || is_manual_inprogress_weight) {
				toggle_status_section(frm, true);
				handle_status_logic(frm);
			} else {
				toggle_status_section(frm, false);
			}

			frappe.show_alert({
				message: __("Gate Entry data loaded"),
				indicator: "blue",
			});

			if (frm.doc.correction_type) {
				frm.doc.reason = frm.doc.correction_type;
				frm.refresh_field("reason");
			}
		},
	});
}

function toggle_new_qty_readonly(frm) {
	let make_readonly =
		frm.doc.correction_type === "Wrong Purchase Order" ||
		frm.doc.correction_type === "Wrong Purchase Order and Supplier";

	frm.fields_dict.items.grid.update_docfield_property(
		"new_accepted_qty",
		"read_only",
		make_readonly ? 1 : 0,
	);

	frm.refresh_field("items");
}

function toggle_weight_readonly(frm) {
	let make_readonly =
		frm.doc.correction_type === "Wrong Purchase Order" ||
		frm.doc.correction_type === "Wrong Purchase Order and Supplier";

	// Wrong Weight should always have editable weights
	if (frm.doc.correction_type === "Wrong Weight") {
		make_readonly = false;
	}

	frm.set_df_property("gross_weight", "read_only", make_readonly ? 1 : 0);
	frm.set_df_property("tare_weight", "read_only", make_readonly ? 1 : 0);

	frm.refresh_fields(["gross_weight", "tare_weight"]);
}

function toggle_outward_sections(frm) {
	let is_outward = frm.doc.__entry_type === "Outward";

	const QTY_DEPENDS =
		'eval:doc.correction_type == "Wrong Accepted Quantity" || doc.correction_type == "Wrong Purchase Order" || doc.correction_type == "Wrong Purchase Order and Supplier"';
	const WEIGHT_SECTION_DEPENDS =
		'eval:doc.correction_type == "Wrong Accepted Quantity" || doc.correction_type == "Wrong Purchase Order" || doc.correction_type == "Wrong Purchase Order and Supplier" || doc.correction_type == "Wrong Weight"';
	const PO_DEPENDS =
		"eval:doc.correction_type == 'Wrong Purchase Order' || doc.correction_type == 'Wrong Purchase Order and Supplier'";
	const VEHICLE_DEPENDS =
		"eval:doc.correction_type == 'Wrong Vehicle Number' || doc.correction_type == 'Wrong Driver Name'";
	const TRANSPORTER_DEPENDS = "eval:doc.correction_type == 'Wrong Transporter'";
	const SUPPLIER_DEPENDS = "eval:doc.correction_type == 'Wrong Purchase Order and Supplier'";
	const VEHICLE_TYPE_DEPENDS = "eval:doc.correction_type == 'Wrong Vehicle Type'";

	frm.set_df_property(
		"section_qty_correction",
		"depends_on",
		is_outward ? "eval:0" : QTY_DEPENDS,
	);
	frm.set_df_property("items", "depends_on", is_outward ? "eval:0" : QTY_DEPENDS);
	frm.set_df_property("section_po_correction", "depends_on", is_outward ? "eval:0" : PO_DEPENDS);
	frm.set_df_property(
		"supplier_correction_section",
		"depends_on",
		is_outward ? "eval:0" : SUPPLIER_DEPENDS,
	);
	frm.set_df_property(
		"section_vehicle_correction",
		"depends_on",
		is_outward ? "eval:0" : VEHICLE_DEPENDS,
	);
	frm.set_df_property(
		"section_break_fgcq",
		"depends_on",
		is_outward ? "eval:0" : WEIGHT_SECTION_DEPENDS,
	);
	frm.set_df_property(
		"weight_details_section",
		"depends_on",
		is_outward ? "eval:0" : WEIGHT_SECTION_DEPENDS,
	);
	frm.set_df_property(
		"transporter_correction_section",
		"depends_on",
		is_outward ? "eval:0" : TRANSPORTER_DEPENDS,
	);
	frm.set_df_property(
		"vehicle_type_correction_section",
		"depends_on",
		is_outward ? "eval:0" : VEHICLE_TYPE_DEPENDS,
	);

	frm.refresh_fields([
		"section_qty_correction",
		"items",
		"section_po_correction",
		"supplier_correction_section",
		"section_vehicle_correction",
		"section_break_fgcq",
		"weight_details_section",
		"transporter_correction_section",
		"vehicle_type_correction_section",
	]);
}

const ALL_CORRECTION_TYPES = [
	"Wrong Accepted Quantity",
	"Wrong Purchase Order",
	"Wrong Purchase Order and Supplier",
	"Wrong Vehicle Number",
	"Wrong Driver Name",
	"Wrong Card Number",
	"Wrong Transporter",
	"Wrong Vehicle Type",
	"Wrong Weight",
	"Wrong Segment",
];

const RESTRICTED_CORRECTION_TYPES = [
	"Wrong Accepted Quantity",
	"Wrong Purchase Order",
	"Wrong Purchase Order and Supplier",
];

const SPECIAL_WEIGHT_TYPES = ["Wrong Weight"];

// Only visible for Manual Weighment gate entries
const MANUAL_ONLY_TYPES = [
	"Inward/Outward Wrong Entry (Manual)",
	"Wrong Manual Entry"
];

const OUTWARD_ONLY_TYPES = ["Wrong Card Number", "Wrong Vehicle Type"];

const NO_WEIGHMENT_TYPES = [
	"Wrong Driver Name",
	"Wrong Vehicle Number",
	"Wrong Transporter",
	"Wrong Vehicle Type",
	"Wrong Segment",
];

function filter_correction_type_options(frm) {
	let is_outward = frm.doc.__entry_type === "Outward";
	let is_stock_transfer = frm.doc.__is_stock_transfer;
	let is_manual_weighment = frm.doc.__is_manual_weighment;
	let no_weighment =
		frm.doc.__is_weighment_required === "No" || frm.doc.__is_weighment_required === 0;

	let allowed;
	if (is_outward) {
		allowed = OUTWARD_ONLY_TYPES;
	} else if (no_weighment) {
		allowed = NO_WEIGHMENT_TYPES;
	} else if (is_manual_weighment || is_stock_transfer) {
		// Manual weighment or Stock transfer: hide RESTRICTED but show Wrong Weight
		// Manual weighment also gets the entry-flow swap type
		let base = ALL_CORRECTION_TYPES.filter((t) => !RESTRICTED_CORRECTION_TYPES.includes(t));
		if (is_manual_weighment) {
			base = base.concat(MANUAL_ONLY_TYPES);
		}
		allowed = base;
	} else {
		// Normal: show all except special weight types
		allowed = ALL_CORRECTION_TYPES.filter((t) => !SPECIAL_WEIGHT_TYPES.includes(t));
	}

	frm.set_df_property("correction_type", "options", allowed.join("\n"));

	// Only clear on draft docs — submitted/approved docs must never lose their correction_type
	// due to the async race where __is_manual_weighment isn't set yet on refresh
	if (frm.doc.docstatus === 0 && frm.doc.correction_type && !allowed.includes(frm.doc.correction_type)) {
		frm.set_value("correction_type", "");
	}

	// Hide is_completed / is_in_progress when weighment is not required
	if (no_weighment) {
		frm.set_df_property("is_completed", "hidden", 1);
		frm.set_df_property("is_in_progress", "hidden", 1);
	}

	frm.refresh_field("correction_type");
}

// ---------------- TOGGLE STATUS ---------------- //
function toggle_status_section(frm, show) {
	frm.set_df_property("is_completed", "hidden", show ? 0 : 1);
	frm.set_df_property("is_in_progress", "hidden", show ? 0 : 1);

	frm.refresh_fields(["is_completed", "is_in_progress"]);
}

// ---------------- GATE ENTRY FILTER ---------------- //
function set_gate_entry_filter(frm) {
	frm.set_query("gate_entry", () => {
		return {
			filters: [
				["Gate Entry", "docstatus", "=", 1],
				["Gate Entry", "entry_type", "=", "Inward"],
			],
		};
	});
}

// ---------------- APPLY CARD FILTER ---------------- //
function apply_card_filter(frm) {
	if (!frm.doc.company || !frm.doc.plant) return;

	frm.set_query("newcorrect_card_number", () => {
		return {
			filters: {
				branch: frm.doc.plant,
				status: "Issued",
			},
		};
	});
}

//-------------apply purchase order filter------------------//
function apply_purchase_order_filter(frm) {
	if (!frm.doc.company || !frm.doc.plant) return;

	let existing_purchase_orders = [];

	// Collect existing POs from child table
	(frm.doc.items || []).forEach((row) => {
		if (row.purchase_order) {
			existing_purchase_orders.push(row.purchase_order);
		}
	});

	// Remove duplicates
	existing_purchase_orders = [...new Set(existing_purchase_orders)];

	frm.set_query("new_purchase_order", () => {
		return {
			query: "informatics_custom_apps.ripl_customized_apps.doctype.purchase_management_system.purchase_management_system.get_filtered_purchase_orders",
			filters: {
				company: frm.doc.company,
				plant: frm.doc.plant,
				status: ["not in", ["Closed", "Completed"]],
				existing_pos: existing_purchase_orders,
			},
		};
	});
}

// ---------------- APPLY TRANSPORTER FILTER ---------------- //
function apply_transporter_filter(frm) {
	frm.set_query("newcorrect_transporter", () => {
		return {
			filters: {
				is_transporter: 1,
				disabled: 0
			}
		};
	});
}

// ---------------- APPLY MANUAL ENTRY PO FILTER ---------------- //
function apply_manual_entry_po_filter(frm) {
	if (!frm.doc.company || !frm.doc.plant) return;

	let ge_supplier = frm.doc.__ge_supplier || null;
	let ge_segment  = frm.doc.__ge_segment  || null;

	frm.set_query("manual_entry_new_purchase_order", () => {
		let filters = {
			company:  frm.doc.company,
			branch:   frm.doc.plant,
			docstatus: 1,
			status: ["not in", ["Closed", "Completed"]],
		};

		// Restrict to same supplier as the Gate Entry
		if (ge_supplier) {
			filters.supplier = ge_supplier;
		}

		// Restrict to same segment as the Gate Entry
		if (ge_segment) {
			filters.segment = ge_segment;
		}

		return { filters };
	});
}

// function apply_purchase_order_filter(frm) {
// 	if (!frm.doc.company || !frm.doc.plant) return;

// 	let existing_purchase_orders = [];

// 	(frm.doc.items || []).forEach((element) => {
// 		if (element.purchase_order) {
// 			existing_purchase_orders.push(element.purchase_order);
// 		}
// 	});

// 	frm.set_query("new_purchase_order", () => {
// 		return {
// 			filters: {
// 				company: frm.doc.company,
// 				branch: frm.doc.plant,
// 				docstatus: 1,
// 				name: [
// 					"not in",
// 					existing_purchase_orders.length ? existing_purchase_orders : [""],
// 				],
// 			},
// 		};
// 	});
// }

// ---------------- MAIN ---------------- //
frappe.ui.form.on("Purchase Management System", {
	items_on_form_rendered(frm) {
		apply_purchase_order_filter(frm);
		toggle_new_qty_readonly(frm);
	},

	refresh(frm) {
		// Only enable free editing on draft documents
		if (frm.doc.docstatus === 0) {
			frm.enable_save();
		}

		apply_transporter_filter(frm);

		toggle_status_section(frm, !!frm.doc.gate_entry);
		handle_status_logic(frm);

		frm.set_query("gate_entry", () => {
			return {
				filters: {
					entry_type: "Inward",
					docstatus: 1,
				},
			};
		});

		set_gate_entry_filter(frm);

		apply_card_filter(frm);
		apply_purchase_order_filter(frm);

		if (frm.doc.gate_entry) {
			frappe.db.get_value(
				"Gate Entry",
				frm.doc.gate_entry,
				[
					"is_stock_transfer",
					"is_manual_weighment",
					"entry_type",
					"is_weighment_required",
				],
				(ge) => {
					frm.doc.__is_stock_transfer = ge.is_stock_transfer || 0;
					frm.doc.__is_manual_weighment = ge.is_manual_weighment || 0;
					frm.doc.__entry_type = ge.entry_type || "";
					frm.doc.__is_weighment_required = ge.is_weighment_required ?? 1;

					// Visibility always updates; values only update on draft to avoid dirtying submitted forms
					toggle_ge_type_checkboxes(frm, ge.is_manual_weighment, ge.is_stock_transfer, frm.doc.docstatus === 0);
					toggle_new_qty_readonly(frm);
					toggle_weight_readonly(frm);
					toggle_outward_sections(frm);
					filter_correction_type_options(frm);
				},
			);
		} else {
			toggle_ge_type_checkboxes(frm, 0, 0);
			toggle_new_qty_readonly(frm);
			toggle_weight_readonly(frm);
			toggle_outward_sections(frm);
			filter_correction_type_options(frm);
		}

		if (frm.doc.status === "Approved" || frm.doc.status === "Pending" || frm.doc.status === "Cancelled") {
			if (frm.doc.correction_type) {
				frm.set_df_property("correction_type", "read_only", 1);
				frm.set_df_property("gate_entry", "read_only", 1);
				frm.refresh_fields(["correction_type", "gate_entry"]);
			}
		}
	},
	fetch_po_details(frm) {

	if (!frm.doc.manual_entry_new_purchase_order) {
		frappe.throw("Please select Purchase Order");
	}

	frappe.call({
		method:
		"informatics_custom_apps.ripl_customized_apps.doctype.purchase_management_system.purchase_management_system.fetch_po_details",

		args: {
			purchase_order: frm.doc.manual_entry_new_purchase_order
		},

		callback(r) {

			frm.clear_table("manual_entry_items");

			// Determine which auto-fill scenario applies
			let is_completed      = frm.doc.is_completed;
			let is_in_progress    = frm.doc.is_in_progress;
			let is_manual         = frm.doc.__is_manual_weighment;

			// is_completed → use net_weight; is_in_progress + manual → use gross_weight
			let auto_qty    = is_completed  ? (frm.doc.net_weight   || 0)
			                : (is_in_progress && is_manual) ? (frm.doc.gross_weight || 0)
			                : 0;
			let make_readonly = is_completed || (is_in_progress && is_manual);

			(r.message || []).forEach(d => {

				let row = frm.add_child("manual_entry_items");

				row.item_code          = d.item_code;
				row.item_name          = d.item_name;
				row.purchase_order_item = d.purchase_order_item;
				row.qty                = d.qty;
				row.uom                = d.uom;

				if (auto_qty) {
					row.new_accepted_qty = auto_qty;
				}
			});

			frm.refresh_field("manual_entry_items");

			// Set read-only property on the grid column
			frm.fields_dict.manual_entry_items.grid
				.update_docfield_property(
					"new_accepted_qty",
					"read_only",
					make_readonly ? 1 : 0
				);
		}
	});
},

	gate_entry(frm) {
		if (frm.doc.gate_entry) {
			frappe.db.get_value(
				"Gate Entry",
				frm.doc.gate_entry,
				[
					"is_stock_transfer",
					"is_manual_weighment",
					"is_completed",
					"is_in_progress",
					"entry_type",
					"is_weighment_required",
					"supplier",
					"segment",
				],
				(ge) => {
					frm.doc.__is_stock_transfer = ge.is_stock_transfer || 0;
					frm.doc.__is_manual_weighment = ge.is_manual_weighment || 0;
					frm.doc.__is_weighment_required = ge.is_weighment_required ?? 1;
					frm.doc.__ge_supplier = ge.supplier || null;
					frm.doc.__ge_segment  = ge.segment  || null;
					frm.set_value("is_completed", ge.is_completed || 0);
					frm.set_value("is_in_progress", ge.is_in_progress || 0);
					frm.doc.__entry_type = ge.entry_type || "";
					toggle_ge_type_checkboxes(frm, ge.is_manual_weighment, ge.is_stock_transfer);
					filter_correction_type_options(frm);
					toggle_outward_sections(frm);
					apply_manual_entry_po_filter(frm);
				},
			);
		} else {
			frm.doc.__is_stock_transfer = 0;
			frm.doc.__is_manual_weighment = 0;
			frm.doc.__is_weighment_required = 1;
			frm.doc.__entry_type = "";
			toggle_ge_type_checkboxes(frm, 0, 0);
			filter_correction_type_options(frm);
			toggle_outward_sections(frm);
		}
		load_data(frm);
		apply_purchase_order_filter(frm);
		apply_manual_entry_po_filter(frm);
	},

	correction_type(frm) {
		load_data(frm);

		const ct = frm.doc.correction_type;

		frm.doc.reason = ct || "";
		frm.refresh_field("reason");

		apply_purchase_order_filter(frm);
		apply_manual_entry_po_filter(frm);
	},

	new_purchase_order(frm) {
		if (frm.doc.new_purchase_order) {
			frappe.db.get_value(
				"Purchase Order",
				frm.doc.new_purchase_order,
				["supplier", "supplier_name"],
				(po) => {
					frm.set_value("newcorrect_supplier", po.supplier);
					frm.set_value("newcorrect_supplier_name", po.supplier_name);
				},
			);
		} else {
			frm.set_value("newcorrect_supplier", "");
			frm.set_value("newcorrect_supplier_name", "");
		}
	},

	is_completed(frm) {
		if (frm.doc.is_completed) {
			frm.set_value("is_in_progress", 0);
		}
		handle_status_logic(frm);
	},

	is_in_progress(frm) {
		if (frm.doc.is_in_progress) {
			frm.set_value("is_completed", 0);
		}
		handle_status_logic(frm);
	},

	company(frm) {
		apply_card_filter(frm);
	},

	plant(frm) {
		apply_card_filter(frm);
	},

	gross_weight(frm) {
		let gross = frm.doc.gross_weight || 0;
		let tare = frm.doc.tare_weight || 0;
		let net = gross - tare;

		frm.set_value("net_weight", net);
		if (tare === 0 && gross > 0) {
			// If tare not yet entered, leave it for the user
		} else {
			frm.set_value("tare_weight", tare);
			refresh_field("tare_weight", "net_weight");
		}
	},

	tare_weight(frm) {
		let gross = frm.doc.gross_weight || 0;
		let tare = frm.doc.tare_weight || 0;
		let net = gross - tare;

		frm.set_value("net_weight", net);
		refresh_field("gross_weight", "net_weight");
	},

	after_workflow_action(frm) {
		frm.reload_doc();
	},
});

// ---------------- VALIDATION ---------------- //
frappe.ui.form.on("PMS Correction Item Details", {
	item_code(frm) {
		apply_purchase_order_filter(frm);
	},

	new_accepted_qty(frm, cdt, cdn) {
		let row = locals[cdt][cdn];

		if (!frm.doc.is_completed) {
			frappe.msgprint("Gate Entry must be completed first");
			frappe.model.set_value(cdt, cdn, "new_accepted_qty", row.accepted_qty);
			return;
		}

		if (row.new_accepted_qty < 0) {
			frappe.msgprint("Negative quantity not allowed");
			frappe.model.set_value(cdt, cdn, "new_accepted_qty", row.accepted_qty);
			return;
		}

		if (row.new_accepted_qty > row.po_item_qty) {
			frappe.msgprint("Cannot exceed PO quantity");
			frappe.model.set_value(cdt, cdn, "new_accepted_qty", row.accepted_qty);
		}

		// Validate against over_delivery_receipt_allowance from Item
		if (row.item_code && row.purchase_order_item) {
			frappe.db.get_value(
				"Item",
				row.item_code,
				"over_delivery_receipt_allowance",
				(item) => {
					let allowance = item.over_delivery_receipt_allowance || 0;
					let max_allowed_pct = 100 + allowance;

					let delta = (row.new_accepted_qty || 0) - (row.accepted_qty || 0);
					let new_received = (row.current_gate_entry_received_qty || 0) + delta;
					let percentage = row.po_item_qty ? (new_received / row.po_item_qty) * 100 : 0;

					if (percentage > max_allowed_pct) {
						frappe.msgprint(
							`Received percentage (${percentage.toFixed(2)}%) for item ${row.item_code} ` +
								`exceeds the allowed limit (${max_allowed_pct.toFixed(2)}%) based on ` +
								`Over Delivery/Receipt Allowance (${allowance}%).`,
						);
						frappe.model.set_value(cdt, cdn, "new_accepted_qty", row.accepted_qty);
					}
				},
			);
		}
		// Validate against Rake Bill Billed Qty
		if (row.purchase_order) {
			frappe.db.get_value("Purchase Order", row.purchase_order, "incoterm", (po) => {
				if (po && ["Rail Rack", "RRB", "Rail Rake"].includes(po.incoterm)) {
					frappe.db.get_value("Rake Bill", {purchase_order: row.purchase_order, docstatus: ["<", 2]}, 
						["name", "billed_qty", "gate_entry_received_qty"], (rb) => {
							if (rb) {
								let delta = (row.new_accepted_qty || 0) - (row.accepted_qty || 0);
								let new_rb_received = (rb.gate_entry_received_qty || 0) + delta;
								if (new_rb_received > (rb.billed_qty || 0)) {
									frappe.msgprint(`Gate Entry Received Qty (${new_rb_received}) for PO ${row.purchase_order} ` +
										`exceeds Billed Qty (${rb.billed_qty}) on Rake Bill ${rb.name}`);
									frappe.model.set_value(cdt, cdn, "new_accepted_qty", row.accepted_qty);
								}
							}
						});
				}
			});
		}
	},
});
