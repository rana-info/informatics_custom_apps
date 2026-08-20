// Copyright (c) 2023, Dexciss Technology Pvt Ltd and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["zzDaily Absent"] = {
	"filters": [
		{
			"fieldname": "worklocation",
			"label": __("WorkLocation"),
			"fieldtype": "Link",
			"options": "Location",
			"reqd": 1
		},
		{
			"fieldname": "date",
			"label": __("Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		},
		{
			"fieldname": "status",
			"label": __("Status"),
			"fieldtype": "Select",
			"options": "\nPresent\nAbsent\nLate\nOn Leave",
			"default": ""
		}
	],

	onload: function(report) {
		report.refresh();
	},

	onchange: function(report) {
		report.refresh();
	}
};