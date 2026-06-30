frappe.query_reports["SLE BIN Divergence Tracker"] = {

	filters: [

		{
			fieldname: "company",
			label: "Company",
			fieldtype: "Link",
			options: "Company",
			width: 180
		},

		{
			fieldname: "plant",
			label: "Plant",
			fieldtype: "Link",
			options: "Branch",
			width: 180
		}

	]

};