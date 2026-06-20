/* ─── Shared Constants ─── */

const GE_DATA_FIELDS = [
	"is_completed", "is_in_progress", "current_vehicle_no", "current_driver_name",
	"old_transporter", "old_transporter_name", "old_card_number", "wrong_vehicle_type",
	"wrong_item_group", "is_manual_weighment", "tare_weight", "gross_weight",
	"net_weight", "weighment_date", "inward_date", "outward_date",
];

/* ─── Helper Functions ─── */

function recalculate_net_weight(frm) {
	const gross = frm.doc.gross_weight || 0;
	const tare = frm.doc.tare_weight || 0;
	frm.set_value("net_weight", gross - tare);
}

function handle_status_logic(frm) {
	const is_completed = frm.doc.is_completed;
	const is_in_progress = frm.doc.is_in_progress;

	frm.set_df_property("is_completed", "hidden", 0);
	frm.set_df_property("is_in_progress", "hidden", 0);

	if (is_completed) frm.set_df_property("is_in_progress", "hidden", 1);
	if (is_in_progress) frm.set_df_property("is_completed", "hidden", 1);

	frm.refresh_fields(["is_completed", "is_in_progress"]);
}

function is_manual_enabled(value) {
	return Number(value || 0) === 1;
}

function toggle_manual_weighment_field(frm, is_manual_weighment) {
	const show = is_manual_enabled(is_manual_weighment);
	frm.set_df_property("is_manual_weighment", "hidden", show ? 0 : 1);
	frm.set_value("is_manual_weighment", show ? 1 : 0);
	frm.refresh_field("is_manual_weighment");
}

/* ─── Correction Options ─── */

function toggle_deal_correction_mode(frm) {
	const is_deal_mode = frm.doc.deal_correction === 1;

	frm.set_df_property("gate_entry", "hidden", is_deal_mode ? 1 : 0);
	frm.set_df_property("gate_entry", "reqd", is_deal_mode ? 0 : 1);
	frm.set_df_property("deal", "hidden", is_deal_mode ? 0 : 1);
	frm.set_df_property("deal", "reqd", is_deal_mode ? 1 : 0);

	const ge_only_fields = [
		"is_completed", "is_in_progress", "is_manual_weighment",
		"section_break_fgcq", "weighment_date", "inward_date", "outward_date",
		"weight_details_section", "tare_weight", "gross_weight", "net_weight",
	];
	ge_only_fields.forEach((f) => frm.set_df_property(f, "hidden", is_deal_mode ? 1 : 0));

	update_correction_options_for_mode(frm);
	frm.refresh_fields();
}

function toggle_delivery_note_correction_mode(frm) {
	const is_dn_mode = frm.doc.delivery_note_correction === 1;

	frm.set_df_property("delivery_note", "hidden", is_dn_mode ? 0 : 1);
	frm.set_df_property("delivery_note", "reqd",   is_dn_mode ? 1 : 0);

	// Only control gate_entry visibility when deal_correction is NOT active —
	// toggle_deal_correction_mode already owns gate_entry when deal mode is on.
	if (!frm.doc.deal_correction) {
		frm.set_df_property("gate_entry", "hidden", is_dn_mode ? 1 : 0);
		frm.set_df_property("gate_entry", "reqd",   is_dn_mode ? 0 : 1);
	}

	// Hide weighment/gate-entry data fields in DN mode (same as deal mode)
	const ge_only_fields = [
		"is_completed", "is_in_progress", "is_manual_weighment",
		"section_break_fgcq", "weighment_date", "inward_date", "outward_date",
		"weight_details_section", "tare_weight", "gross_weight", "net_weight",
	];
	ge_only_fields.forEach((f) => frm.set_df_property(f, "hidden", is_dn_mode ? 1 : 0));

	update_correction_options_for_mode(frm);
	frm.refresh_fields();
}


function update_correction_options_for_mode(frm) {
	if (!frm._all_correction_options) {
		frm._all_correction_options = (frm.fields_dict.correction_type.df.options || "")
			.split("\n").map((o) => o.trim()).filter(Boolean);
	}

	const saved_ct = frm.doc.correction_type;

	if (frm.doc.deal_correction === 1) {
		// Deal mode: Wrong Sales Partner + Wrong Segment(Deal)
		frm.set_df_property("correction_type", "options", "Wrong Sales Partner\nWrong Segment(Deal)");
	} else if (frm.doc.delivery_note_correction === 1) {
		// DN correction mode: only Unlink Weighment
		frm.set_df_property("correction_type", "options", "Unlink Weighment");
		if (frm.doc.docstatus < 1) {
			frm.set_value("correction_type", "Unlink Weighment");
		}
	} else {
		// Normal gate-entry mode: all options except the mode-specific ones
		const opts = frm._all_correction_options.filter(
			(o) => o !== "Wrong Sales Partner" && o !== "Unlink Weighment" && o !== "Wrong Segment(Deal)"
		);
		frm.set_df_property("correction_type", "options", opts.join("\n"));
		if (frm.doc.docstatus < 1 && ["Wrong Sales Partner", "Unlink Weighment", "Wrong Segment(Deal)"].includes(frm.doc.correction_type)) {
			frm.set_value("correction_type", "");
		}
		update_correction_options(frm, {
			is_manual_weighment: frm.doc.is_manual_weighment,
			entry_type: "Outward",
		});
	}

	if (frm.doc.docstatus >= 1 && saved_ct) {
		frm.doc.correction_type = saved_ct;
	}
	frm.refresh_field("correction_type");
}

function update_correction_options(frm, data = {}) {
	const blocked_manual = [
		"Reset Second Weight (Not Manual)", "Wrong Item Group", "Wrong Delivery Note",
	];
	const blocked_non_manual = [
		"Reset Second Weight (Manual)", "Inward/Outward Wrong Entry (Manual)",
	];

	const is_manual = is_manual_enabled(data.is_manual_weighment) && (data.entry_type || "Outward") === "Outward";
	const is_non_manual = !is_manual_enabled(data.is_manual_weighment) && (data.entry_type || "Outward") === "Outward";

	if (!frm._all_correction_options) {
		frm._all_correction_options = (frm.fields_dict.correction_type.df.options || "")
			.split("\n").map((o) => o.trim()).filter(Boolean);
	}

	let options = frm._all_correction_options.filter(
		(o) => o !== "Wrong Sales Partner" && o !== "Unlink Weighment" && o !== "Wrong Segment(Deal)"
	);

	if (is_manual) options = options.filter((o) => !blocked_manual.includes(o));
	if (is_non_manual) options = options.filter((o) => !blocked_non_manual.includes(o));

	if (frm.doc.correction_type === "Wrong Delivery Note" && !options.includes("Wrong Delivery Note")) {
		options.push("Wrong Delivery Note");
	}

	frm.set_df_property("correction_type", "options", options.join("\n"));
	frm.refresh_field("correction_type");
}

/* ─── Data Loaders ─── */

function load_deal_data(frm) {
	if (!frm.doc.deal) return;
	frm.call({
		method: "load_deal_data",
		doc: frm.doc,
		freeze: true,
		callback: (r) => {
			if (!r.message) return;
			const data = r.message;
			if (data.wrong_sales_partner) frm.set_value("wrong_sales_partner", data.wrong_sales_partner);
			if (data.company) frm.set_value("company", data.company);
			if (data.plant) frm.set_value("plant", data.plant);
			frappe.show_alert({ message: __("Deal data loaded successfully"), indicator: "green" });
		},
	});
}

function load_data(frm) {
	if (!frm.doc.gate_entry) return;
	frm.call({
		method: "load_gate_entry_data",
		doc: frm.doc,
		freeze: true,
		callback: (r) => {
			if (!r.message) return;
			const data = r.message;

			frm.doc.is_completed = data.is_completed || 0;
			frm.doc.is_in_progress = data.is_in_progress || 0;
			frm.doc.current_vehicle_no = data.current_vehicle_no;
			frm.doc.current_driver_name = data.current_driver_name;
			frm.doc.old_transporter = data.old_transporter;
			frm.doc.old_transporter_name = data.old_transporter_name;
			frm.doc.old_card_number = data.old_card_number;
			frm.doc.wrong_vehicle_type = data.wrong_vehicle_type;
			frm.doc.wrong_item_group = data.wrong_item_group;
			frm.doc.wrong_segment = data.wrong_segment;
			frm.doc.is_manual_weighment = data.is_manual_weighment || 0;
			frm.doc.tare_weight = data.tare_weight || 0;
			frm.doc.gross_weight = data.gross_weight || 0;
			frm.doc.net_weight = data.net_weight || 0;
			frm.doc.weighment_date = data.weighment_date;
			frm.doc.inward_date = data.inward_date;
			frm.doc.outward_date = data.outward_date;

			frm.refresh_fields([
				...GE_DATA_FIELDS, "wrong_segment",
			]);

			toggle_manual_weighment_field(frm, data.is_manual_weighment);
			update_correction_options(frm, data);
			handle_status_logic(frm);

			if (frm.doc.correction_type === "Wrong Delivery Note") {
				const linked_dns = data.linked_delivery_notes || [];
				if (!frm.doc.delivery_note_entries || frm.doc.delivery_note_entries.length === 0) {
					linked_dns.forEach((dn) => {
						let row = frm.add_child("delivery_note_entries");
						row.old_delivery_note = dn;
					});
				}
				frm.set_df_property("multi_dn_section", "hidden", 0);
				frm.refresh_fields(["multi_dn_section", "delivery_note_entries"]);
				frm.refresh_field("delivery_note_entries");
				frm.fields_dict.delivery_note_entries.grid.refresh();
			}

			frappe.show_alert({ message: __("Data loaded successfully"), indicator: "blue" });

			if (frm.doc.correction_type) {
				frm.doc.reason = frm.doc.correction_type;
				frm.refresh_field("reason");
			}
		},
	});
}

/* ─── Filter Setup ─── */

function apply_card_filter(frm) {
	if (!frm.doc.company || !frm.doc.plant) return;
	frm.set_query("newcorrect_card_number", () => {
		const branches = [frm.doc.plant];
		const location = frm._gate_entry_location || frm.doc.location;
		if (frm.doc.plant === "Superior Biofuels" && location === "Superior Unn") {
			branches.push("Superior Unn");
		}
		return {
			filters: [
				["Card Details", "branch", "in", branches],
				["Card Details", "status", "=", "Issued"],
				["Card Details", "is_assigned", "=", 0],
			],
		};
	});
}

function load_gate_entry_location(frm) {
	if (!frm.doc.gate_entry) {
		frm._gate_entry_location = null;
		apply_card_filter(frm);
		return;
	}
	frappe.db.get_value("Gate Entry", frm.doc.gate_entry, "location", (r) => {
		frm._gate_entry_location = r ? r.location : null;
		apply_card_filter(frm);
	});
}

function apply_delivery_note_filter(frm) {
	frm.set_query("new_delivery_note", () => ({
		filters: { docstatus: 0, status: "Draft", company: frm.doc.company, branch: frm.doc.plant },
	}));
}

function apply_unlink_dn_filter(frm) {
	frm.set_query("delivery_note", () => ({
		filters: [
			["Delivery Note", "status", "in", ["Draft", "To Bill"]],
			["Delivery Note", "is_return", "=", 0],
		],
	}));
}

function apply_transporter_filter(frm) {
	frm.set_query("newcorrect_transporter", () => ({
		filters: { is_transporter: 1, disabled: 0 },
	}));
}

function setup_delivery_note_child_table(frm) {
	if (!frm.fields_dict.delivery_note_entries) return;

	const grid = frm.fields_dict.delivery_note_entries.grid;

	grid.get_field("new_delivery_note").get_query = function () {
		return {
			filters: { docstatus: 0, status: "Draft", company: frm.doc.company, branch: frm.doc.plant },
		};
	};

	grid.get_field("old_delivery_note").get_query = function () {
		return { filters: { docstatus: ["<", 2] } };
	};

	grid.cannot_add_rows = true;
	frm.get_field("delivery_note_entries").grid.df.cannot_delete_rows = true;
	grid.wrapper.find(".grid-remove-rows").hide();
	grid.wrapper.find(".row-check").hide();
	grid.refresh();
}

/* ─── Section Visibility Helpers ─── */

function toggle_correction_sections(frm) {
	const ct = frm.doc.correction_type;

	const is_wrong_dn = frm.doc.gate_entry && ct === "Wrong Delivery Note";
	frm.set_df_property("multi_dn_section", "hidden", is_wrong_dn ? 0 : 1);
	frm.refresh_field("multi_dn_section");

	const is_wrong_seg = ct === "Wrong Segment";
	frm.set_df_property("segment_correction_section", "hidden", is_wrong_seg ? 0 : 1);
	frm.refresh_fields(["segment_correction_section", "wrong_segment", "new_segment"]);

	const is_tare = ct === "Change First Weight(Tare)";
	frm.set_df_property("tare_weight", "read_only", is_tare ? 0 : 1);
	frm.refresh_field("tare_weight");
}

/* ─── Form Events ─── */

frappe.ui.form.on("Sales Management Tool", {
	setup(frm) {
		frm.set_query("gate_entry", () => ({
			filters: { docstatus: 1, entry_type: "Outward" },
		}));
		frm.set_query("deal", () => ({
			filters: { docstatus: 1 },
		}));
		apply_unlink_dn_filter(frm);
	},

	refresh(frm) {
		toggle_deal_correction_mode(frm);
		toggle_delivery_note_correction_mode(frm);

		if (!frm.doc.deal_correction && !frm.doc.delivery_note_correction) {
			load_gate_entry_location(frm);
			apply_card_filter(frm);
			apply_delivery_note_filter(frm);
			setup_delivery_note_child_table(frm);
			handle_status_logic(frm);
			apply_transporter_filter(frm);
			toggle_manual_weighment_field(frm, frm.doc.is_manual_weighment);
			toggle_correction_sections(frm);
		}

		if (frm.doc.delivery_note_correction) {
			apply_unlink_dn_filter(frm);
		}


		if (frm.doc.docstatus == 1 || frm.doc.status === "Approved" || frm.doc.status === "Pending" || frm.doc.status === "Cancelled") {
			if (frm.doc.deal_correction == 0) {
				frm.set_df_property("deal_correction", "hidden", 1);
			}
		}

		if (frm.doc.docstatus == 1 || frm.doc.status === "Approved" || frm.doc.status === "Pending" || frm.doc.status === "Cancelled") {
			if (frm.doc.delivery_note_correction == 0) {
				frm.set_df_property("delivery_note_correction", "hidden", 1);
			}
		}

		if (frm.doc.status === "Approved" || frm.doc.status === "Pending" || frm.doc.status === "Cancelled") {
			if (frm.doc.correction_type) {
				frm.set_df_property("correction_type", "read_only", 1);
				frm.set_df_property("gate_entry", "read_only", 1);
				frm.refresh_fields(["correction_type", "gate_entry"]);
			}
		}
	},

	deal_correction(frm) {
		if (frm.doc.deal_correction && frm.doc.delivery_note_correction) {
			frm.set_value("deal_correction", 0);
			frappe.throw(__("Deal Correction and Delivery Note Correction cannot be enabled at the same time."));
			return;
		}
		if (frm.doc.deal_correction) {
			frm.doc.gate_entry = "";
			frm.refresh_field("gate_entry");
			GE_DATA_FIELDS.forEach((f) => {
				frm.doc[f] = null;
				frm.refresh_field(f);
			});
		} else {
			frm.doc.deal = "";
			frm.doc.wrong_sales_partner = "";
			frm.doc.new_sales_partner = "";
			frm.doc.new_cost_center = "";
			frm.doc.correction_type = "";
			frm.refresh_fields(["deal", "wrong_sales_partner", "new_sales_partner", "new_cost_center", "correction_type"]);
		}
		toggle_deal_correction_mode(frm);
	},

	delivery_note_correction(frm) {
		if (frm.doc.delivery_note_correction && frm.doc.deal_correction) {
			frm.set_value("delivery_note_correction", 0);
			frappe.throw(__("Delivery Note Correction and Deal Correction cannot be enabled at the same time."));
			return;
		}
		if (frm.doc.delivery_note_correction) {
			// Entering DN correction mode: clear gate_entry fields
			frm.doc.gate_entry = "";
			frm.refresh_field("gate_entry");
			GE_DATA_FIELDS.forEach((f) => {
				frm.doc[f] = null;
				frm.refresh_field(f);
			});
			apply_unlink_dn_filter(frm);
		} else {
			// Leaving DN correction mode: clear DN fields
			frm.set_value("delivery_note", "");
			frm.set_value("correction_type", "");
		}
		toggle_delivery_note_correction_mode(frm);
	},

	deal(frm) {
		if (frm.doc.deal) {
			load_deal_data(frm);
		} else {
			frm.set_value("wrong_sales_partner", "");
			frm.set_value("company", "");
			frm.set_value("plant", "");
		}
	},

	gate_entry(frm) {
		if (frm.doc.deal_correction) return;

		if (frm.doc.gate_entry) {
			load_gate_entry_location(frm);
			load_data(frm);
		} else {
			load_gate_entry_location(frm);
			[...GE_DATA_FIELDS, "new_delivery_note"].forEach((f) => frm.set_value(f, null));
			toggle_manual_weighment_field(frm, 0);
			update_correction_options(frm, { is_manual_weighment: 0, entry_type: "Outward" });
			handle_status_logic(frm);
		}
	},

	correction_type(frm) {
		if (!frm.doc.deal_correction) {
			load_data(frm);
		}

		const ct = frm.doc.correction_type;

		// Wrong Delivery Note child table
		if (ct !== "Wrong Delivery Note") {
			frm.clear_table("delivery_note_entries");
			frm.refresh_field("delivery_note_entries");
			frm.set_df_property("multi_dn_section", "hidden", 1);
			frm.refresh_fields(["multi_dn_section", "delivery_note_entries"]);
		}

		// Wrong Segment section
		const is_wrong_seg = ct === "Wrong Segment";
		frm.set_df_property("segment_correction_section", "hidden", is_wrong_seg ? 0 : 1);
		if (!is_wrong_seg) {
			frm.set_value("wrong_segment", "");
			frm.set_value("new_segment", "");
		}
		frm.refresh_fields(["segment_correction_section", "wrong_segment", "new_segment"]);

		// Tare weight editability
		const is_tare = ct === "Change First Weight(Tare)";
		frm.set_df_property("tare_weight", "read_only", is_tare ? 0 : 1);
		frm.refresh_field("tare_weight");

		frm.doc.reason = ct || "";
		frm.refresh_field("reason");

		// // Cost Center filter for Wrong Segment(Deal)
		// if (ct === "Wrong Segment(Deal)" && frm.doc.company) {
		// 	frm.set_query("new_cost_center", () => ({
		// 		filters: { company: frm.doc.company, is_group: 0 },
		// 	}));
		// }
	},


	gross_weight(frm) {
		recalculate_net_weight(frm);
	},

	tare_weight(frm) {
		if (frm.doc.correction_type === "Change First Weight(Tare)") return;
		recalculate_net_weight(frm);
	},

	newcorrect_transporter(frm) {
		if (frm.doc.newcorrect_transporter) {
			frappe.db.get_value("Supplier", frm.doc.newcorrect_transporter, "supplier_name", (r) => {
				if (r) frm.set_value("newcorrect_transporter_name", r.supplier_name);
			});
		}
	},

	delivery_note(frm) {
		if (!frm.doc.delivery_note_correction) return;

		if (!frm.doc.delivery_note) {
			frm.set_value("company", "");
			frm.set_value("plant", "");
			return;
		}

		frappe.db.get_value(
			"Delivery Note",
			frm.doc.delivery_note,
			["company", "branch", "is_return"],
			(r) => {
				if (!r) return;
				if (r.company) frm.set_value("company", r.company);
				if (r.branch) frm.set_value("plant", r.branch);
				if (r.is_return) {
					frappe.msgprint({
						title: __("Return Delivery Note Selected"),
						message: __(
							"Warning: Delivery Note <b>{0}</b> is a <b>Return</b> entry (Credit Note). "
							+ "Unlinking the weighment from a return DN may have unintended consequences.",
							[frm.doc.delivery_note]
						),
						indicator: "orange",
					});
				}
			}
		);
	},
});

/* ─── Child Table Events: Delivery Note Rotation ─── */

frappe.ui.form.on("Delivery Note Rotation", {
	new_delivery_note(frm, cdt, cdn) {
		const row = locals[cdt][cdn];

		if (row.old_delivery_note && row.new_delivery_note && row.old_delivery_note === row.new_delivery_note) {
			frappe.throw(__("Old and New Delivery Note cannot be same"));
		}

		const duplicates = frm.doc.delivery_note_entries.filter(
			(d) => d.new_delivery_note === row.new_delivery_note
		);
		if (row.new_delivery_note && duplicates.length > 1) {
			frappe.model.set_value(cdt, cdn, "new_delivery_note", "");
			frappe.throw(__("Duplicate New Delivery Note is not allowed"));
		}
	},
});