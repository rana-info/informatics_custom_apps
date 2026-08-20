frappe.query_reports["Employee Checkin Details"] = {
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