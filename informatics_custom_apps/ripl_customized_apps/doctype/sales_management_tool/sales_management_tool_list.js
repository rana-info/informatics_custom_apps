frappe.listview_settings["Sales Management Tool"] = {
	get_indicator: function (doc) {
		const status_colors = {
			Draft: "red",
			Pending: "orange",
			Approved: "green",
			Rejected: "red",
			Cancelled: "grey",
		};

		if (doc.status) {
			return [
				doc.status,
				status_colors[doc.status] || "grey",
				`status,=,${doc.status}`
			];
		}
	},

	formatters: {
		correction_type(value) {

		const correction_classes = {
			"Wrong Vehicle Number": "smt-ct-vehicle",
			"Wrong Driver Name": "smt-ct-driver",
			"Wrong Transporter": "smt-ct-transporter",
			"Wrong Card Number": "smt-ct-card",
			"Wrong Vehicle Type": "smt-ct-vehicle-type",
			"Reset Second Weight (Not Manual)": "smt-ct-reset-auto",
			"Reset Second Weight (Manual)": "smt-ct-reset-manual",
			"Wrong Item Group": "smt-ct-item",
			"Wrong Delivery Note": "smt-ct-delivery",
			"Inward/Outward Wrong Entry (Manual)": "smt-ct-inout",
			"Wrong Sales Partner": "smt-ct-sales-partner",
			"Change First Weight(Tare)": "smt-ct-first-weight",
			"Wrong Segment": "smt-ct-segment",
			"Unlink Weighment": "smt-ct-unlink",
			"Wrong Segment(Deal)": "smt-ct-segment-deal",
			"Wrong Weight(Sale)": "smt-ct-weight-sale",
		};

		if (!value) return "";

		const cls = correction_classes[value] || "smt-ct-default";

		return `
			<span class="filterable indicator-pill ellipsis smt-correction-tag ${cls}"
				data-filter="correction_type,=,${value}">
				<span class="indicator-dot"></span>
				${value}
			</span>
		`;
	},

		deal_correction(value) {
			if (!value) return "";

			return `
				<span class="indicator-pill green">
					<span class="indicator-dot"></span>
					Deal Mode
				</span>
			`;
		},
	},
};