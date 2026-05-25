// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["Procurement Budget MR Drilldown"] = {

filters: [
	{
		fieldname: "company",
		label: __("Company"),
		fieldtype: "Link",
		options: "Company",
		read_only: 1
	},
	{
		fieldname: "fiscal_year",
		label: __("Fiscal Year"),
		fieldtype: "Link",
		options: "Fiscal Year",
		read_only: 1
	},
	{
		fieldname: "gl_account",
		label: __("GL Account"),
		fieldtype: "Link",
		options: "Account",
		read_only: 1
	},
	{
		fieldname: "cost_center",
		label: __("Cost Center"),
		fieldtype: "Link",
		options: "Cost Center",
		read_only: 1
	},
	{
		fieldname: "plant",
		label: __("Plant"),
		fieldtype: "Data",
		read_only: 1
	},
	{
		fieldname: "segment",
		label: __("Segment"),
		fieldtype: "Data",
		read_only: 1
	}
]
};
