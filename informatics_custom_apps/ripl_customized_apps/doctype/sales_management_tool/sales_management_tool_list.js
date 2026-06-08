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
			const correction_colors = {
				"Wrong Vehicle Number": "blue",
				"Wrong Driver Name": "green",
				"Wrong Transporter": "grey",
				"Wrong Card Number": "yellow",
				"Wrong Vehicle Type": "pink",

				"Reset Second Weight (Not Manual)": "custom-orange",
				"Reset Second Weight (Manual)": "custom-sky",

				"Wrong Item Group": "cyan",
				"Wrong Delivery Note": "purple",

				"Inward/Outward Wrong Entry (Manual)": "red",

				"Wrong Sales Partner": "custom-darkgreen",

				"Change First Weight(Tare)": "custom-magenta",

				"Wrong Segment": "custom-teal",

				"Unlink Weighment": "custom-brown",
			};

			if (!value) return "";

			const color = correction_colors[value] || "grey";

			return `
				<span class="filterable indicator-pill ellipsis ${color}"
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