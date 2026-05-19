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

function toggle_deal_correction_mode(frm) {
	const is_deal_mode = frm.doc.deal_correction === 1;

	// Toggle gate_entry / deal visibility
	frm.set_df_property("gate_entry", "hidden", is_deal_mode ? 1 : 0);
	frm.set_df_property("gate_entry", "reqd", is_deal_mode ? 0 : 1);
	frm.set_df_property("deal", "hidden", is_deal_mode ? 0 : 1);
	frm.set_df_property("deal", "reqd", is_deal_mode ? 1 : 0);

	// Hide weighment / gate-entry status fields in deal mode
	const ge_only_fields = [
		"is_completed",
		"is_in_progress",
		"is_manual_weighment",
		"section_break_fgcq",
		"weighment_date",
		"inward_date",
		"outward_date",
		"weight_details_section",
		"tare_weight",
		"gross_weight",
		"net_weight",
	];
	ge_only_fields.forEach((f) => frm.set_df_property(f, "hidden", is_deal_mode ? 1 : 0));

	// Filter correction type dropdown based on current mode
	update_correction_options_for_mode(frm);

	frm.refresh_fields();
}

function update_correction_options_for_mode(frm) {
	if (!frm._all_correction_options) {
		frm._all_correction_options = (frm.fields_dict.correction_type.df.options || "")
			.split("\n")
			.map((opt) => opt.trim())
			.filter(Boolean);
	}

	const is_deal_mode = frm.doc.deal_correction === 1;

	if (is_deal_mode) {
		// Deal mode: only "Wrong Sales Partner"
		frm.set_df_property("correction_type", "options", "Wrong Sales Partner");
		frm.set_value("correction_type", "Wrong Sales Partner");
	} else {
		// Gate entry mode: all options EXCEPT "Wrong Sales Partner"
		const opts = frm._all_correction_options.filter((o) => o !== "Wrong Sales Partner");
		frm.set_df_property("correction_type", "options", opts.join("\n"));
		if (frm.doc.correction_type === "Wrong Sales Partner") {
			frm.set_value("correction_type", "");
		}
		// Apply further gating based on manual/non-manual weighment
		update_correction_options(frm, {
			is_manual_weighment: frm.doc.is_manual_weighment,
			entry_type: "Outward",
			wrong_delivert_note: frm.doc.wrong_delivert_note,
		});
	}

	frm.refresh_field("correction_type");
}

function load_deal_data(frm) {
	if (!frm.doc.deal) return;

	frm.call({
		method: "load_deal_data",
		doc: frm.doc,
		freeze: true,
		callback: (r) => {
			if (!r.message) return;
			const data = r.message;
			if (data.wrong_sales_partner)
				frm.set_value("wrong_sales_partner", data.wrong_sales_partner);
			if (data.company) frm.set_value("company", data.company);
			if (data.plant) frm.set_value("plant", data.plant);
			frappe.show_alert({
				message: __("Deal data loaded successfully"),
				indicator: "green",
			});
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
			let data = r.message;

			frm.set_value("is_completed", data.is_completed || 0);
			frm.set_value("is_in_progress", data.is_in_progress || 0);
			frm.set_value("current_vehicle_no", data.current_vehicle_no);
			frm.set_value("current_driver_name", data.current_driver_name);
			frm.set_value("old_transporter", data.old_transporter);
			frm.set_value("old_transporter_name", data.old_transporter_name);
			frm.set_value("old_card_number", data.old_card_number);
			frm.set_value("wrong_vehicle_type", data.wrong_vehicle_type);
			frm.set_value("wrong_item_group", data.wrong_item_group);
			frm.set_value("wrong_delivert_note", data.wrong_delivert_note);
			frm.set_value("is_manual_weighment", data.is_manual_weighment || 0);

			// Weight values
			frm.set_value("tare_weight", data.tare_weight || 0);
			frm.set_value("gross_weight", data.gross_weight || 0);
			frm.set_value("net_weight", data.net_weight || 0);
			frm.set_value("weighment_date", data.weighment_date);
			frm.set_value("inward_date", data.inward_date);
			frm.set_value("outward_date", data.outward_date);

			toggle_manual_weighment_field(frm, data.is_manual_weighment);
			update_correction_options(frm, data);
			handle_status_logic(frm);

			frappe.show_alert({
				message: __("Outward data loaded successfully"),
				indicator: "green",
			});
		},
	});
}

function apply_card_filter(frm) {
	if (!frm.doc.company || !frm.doc.plant) return;
	frm.set_query("newcorrect_card_number", () => {
		const branches = [frm.doc.plant];
		const gate_entry_location = frm._gate_entry_location || frm.doc.location;
		if (frm.doc.plant === "Superior Biofuels" && gate_entry_location === "Superior Unn") {
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
	frm.set_query("custom_delivery_note", () => {
		return {
			filters: {
				docstatus: 0,
				status: "Draft",
				company: frm.doc.company,
			},
		};
	});
}

function apply_transporter_filter(frm) {
	frm.set_query("newcorrect_transporter", () => {
		return {
			filters: { is_transporter: 1, disabled: 0 },
		};
	});
}

function is_manual_enabled(value) {
	return Number(value || 0) === 1;
}

function toggle_manual_weighment_field(frm, is_manual_weighment) {
	const show_manual = is_manual_enabled(is_manual_weighment);
	frm.set_df_property("is_manual_weighment", "hidden", show_manual ? 0 : 1);
	frm.set_value("is_manual_weighment", show_manual ? 1 : 0);
	frm.refresh_field("is_manual_weighment");
}

function update_correction_options(frm, data = {}) {
	const blocked_manual_outward_options = [
		"Reset Second Weight (Not Manual)",
		"Wrong Item Group",
		"Wrong Delivery Note",
	];
	const blocked_non_manual_outward_options = [
		"Reset Second Weight (Manual)",
		"Inward/Outward Wrong Entry (Manual)",
	];
	const is_manual_outward =
		is_manual_enabled(data.is_manual_weighment) &&
		(data.entry_type || "Outward") === "Outward";
	const is_non_manual_outward =
		!is_manual_enabled(data.is_manual_weighment) &&
		(data.entry_type || "Outward") === "Outward";
	const has_wrong_delivery_note = !!(data.wrong_delivert_note || frm.doc.wrong_delivert_note);

	if (!frm._all_correction_options) {
		frm._all_correction_options = (frm.fields_dict.correction_type.df.options || "")
			.split("\n")
			.map((opt) => opt.trim())
			.filter(Boolean);
	}

	// Always exclude "Wrong Sales Partner" in gate entry mode
	let options = frm._all_correction_options.filter((o) => o !== "Wrong Sales Partner");

	if (is_manual_outward) {
		options = options.filter((opt) => !blocked_manual_outward_options.includes(opt));
	}
	if (is_non_manual_outward) {
		options = options.filter((opt) => !blocked_non_manual_outward_options.includes(opt));
	}
	if (!has_wrong_delivery_note) {
		options = options.filter((opt) => opt !== "Wrong Delivery Note");
	}

	frm.set_df_property("correction_type", "options", options.join("\n"));
	frm.refresh_field("correction_type");

	if (
		(is_manual_outward && blocked_manual_outward_options.includes(frm.doc.correction_type)) ||
		(is_non_manual_outward &&
			blocked_non_manual_outward_options.includes(frm.doc.correction_type)) ||
		(!has_wrong_delivery_note && frm.doc.correction_type === "Wrong Delivery Note")
	) {
		frm.set_value("correction_type", "");
	}
}

frappe.ui.form.on("Sales Management Tool", {
	setup(frm) {
		frm.set_query("gate_entry", () => {
			return {
				filters: { docstatus: 1, entry_type: "Outward" },
			};
		});
		frm.set_query("deal", () => {
			return { filters: { docstatus: 1 } };
		});
	},

	refresh(frm) {
		toggle_deal_correction_mode(frm);

		if (!frm.doc.deal_correction) {
			load_gate_entry_location(frm);
			apply_card_filter(frm);
			apply_delivery_note_filter(frm);
			handle_status_logic(frm);
			apply_transporter_filter(frm);
			toggle_manual_weighment_field(frm, frm.doc.is_manual_weighment);
		}

		if (frm.doc.docstatus == 1 || frm.doc.status === "Approved" || frm.doc.status === "Pending" || frm.doc.status === "Cancelled" ) {
			if (frm.doc.deal_correction == 0) {
				frm.set_df_property("deal_correction", "hidden", 1);
			}
		}

		if (frm.doc.docstatus === 1 && frm.doc.status === "Approved") {
			frm.set_intro(
				__("This correction has been applied to all related Sales documents."),
				"green",
			);
		}
	},

	deal_correction(frm) {
		// Switch modes
		if (frm.doc.deal_correction) {
			// Clear gate-entry related fields WITHOUT triggering gate_entry event
			frm.doc.gate_entry = "";
			frm.refresh_field("gate_entry");
			const ge_fields = [
				"is_completed",
				"is_in_progress",
				"current_vehicle_no",
				"current_driver_name",
				"old_transporter",
				"old_transporter_name",
				"old_card_number",
				"wrong_vehicle_type",
				"wrong_item_group",
				"wrong_delivert_note",
				"is_manual_weighment",
				"tare_weight",
				"gross_weight",
				"net_weight",
				"weighment_date",
				"inward_date",
				"outward_date",
			];
			ge_fields.forEach((f) => {
				frm.doc[f] = null;
				frm.refresh_field(f);
			});
		} else {
			// Clear deal related fields WITHOUT triggering deal event
			frm.doc.deal = "";
			frm.doc.wrong_sales_partner = "";
			frm.doc.new_sales_partner = "";
			frm.doc.correction_type = "";
			frm.refresh_fields([
				"deal",
				"wrong_sales_partner",
				"new_sales_partner",
				"correction_type",
			]);
		}
		toggle_deal_correction_mode(frm);
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
		// If in deal correction mode, gate_entry changes are irrelevant
		if (frm.doc.deal_correction) return;

		if (frm.doc.gate_entry) {
			load_gate_entry_location(frm);
			load_data(frm);
		} else {
			load_gate_entry_location(frm);
			const to_clear = [
				"is_completed",
				"is_in_progress",
				"current_vehicle_no",
				"current_driver_name",
				"old_transporter",
				"old_transporter_name",
				"old_card_number",
				"wrong_vehicle_type",
				"wrong_item_group",
				"wrong_delivert_note",
				"custom_delivery_note",
				"is_manual_weighment",
				"tare_weight",
				"gross_weight",
				"net_weight",
				"weighment_date",
				"inward_date",
				"outward_date",
			];
			to_clear.forEach((f) => frm.set_value(f, null));
			toggle_manual_weighment_field(frm, 0);
			update_correction_options(frm, { is_manual_weighment: 0, entry_type: "Outward" });
			handle_status_logic(frm);
		}
	},

	correction_type(frm) {
		if (!frm.doc.deal_correction) {
			load_data(frm);
		}
	},

	gross_weight(frm) {
		let gross = frm.doc.gross_weight || 0;
		let tare = frm.doc.tare_weight || 0;
		frm.set_value("net_weight", gross - tare);
	},

	tare_weight(frm) {
		let gross = frm.doc.gross_weight || 0;
		let tare = frm.doc.tare_weight || 0;
		frm.set_value("net_weight", gross - tare);
	},

	newcorrect_transporter(frm) {
		if (frm.doc.newcorrect_transporter) {
			frappe.db.get_value(
				"Supplier",
				frm.doc.newcorrect_transporter,
				"supplier_name",
				(r) => {
					if (r) frm.set_value("newcorrect_transporter_name", r.supplier_name);
				},
			);
		}
	},
});
