frappe.listview_settings["Purchase Management System"] = {
	get_indicator: function (doc) {
		const status_colors = {
			Draft: "red",
			Pending: "orange",
			Approved: "green",
			Rejected: "red",
			Cancelled: "grey",
		};

		if (doc.status) {
			return [doc.status, status_colors[doc.status] || "grey", `status,=,${doc.status}`];
		}
	},

	formatters: {
		correction_type(value) {
			const correction_colors = {
				"Wrong Accepted Quantity": "dark blue",
				"Wrong Purchase Order": "dark orange",
				"Wrong Purchase Order and Supplier": "grey",
				"Wrong Vehicle Number": "dark purple",
				"Wrong Driver Name": "dark cyan",
				"Wrong Card Number": "dark yellow",
				"Wrong Transporter": "dark pink",
				"Wrong Vehicle Type": "light red",
				"Wrong Weight": "white",
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
	},
};
