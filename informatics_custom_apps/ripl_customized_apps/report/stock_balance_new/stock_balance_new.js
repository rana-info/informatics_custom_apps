// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors and contributors
// For license information, please see license.txt

frappe.query_reports["Stock Balance New"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			width: "80",
			options: "Company",
			default: frappe.defaults.get_default("company"),
			reqd: 1
		},
		{
			fieldname: "branch", // Change to "plant" if your database field is named differently
			label: __("Plant"), 
			fieldtype: "Link",
			width: "80",
			options: "Branch", 
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			width: "80",
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			width: "80",
			reqd: 1,
		}
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname == "out_qty" && data && data.out_qty > 0) {
			value = "<span style='color:red'>" + value + "</span>";
		} else if (column.fieldname == "in_qty" && data && data.in_qty > 0) {
			value = "<span style='color:green'>" + value + "</span>";
		}

		return value;
	},

	onload: function (report) {
		// Automatically fetch and set the current Financial Year dates
		let company = frappe.query_report.get_filter_value('company') || frappe.defaults.get_default("company");
		
		frappe.call({
			method: "erpnext.accounts.utils.get_fiscal_year",
			args: {
				date: frappe.datetime.get_today(),
				company: company
			},
			callback: function(r) {
				if (r.message) {
					let year_start_date = r.message[1];
					let year_end_date = r.message[2];
					
					frappe.query_report.set_filter_value('from_date', year_start_date);
					// You can set to_date to get_today() or year_end_date depending on preference
					frappe.query_report.set_filter_value('to_date', frappe.datetime.get_today()); 
				}
			}
		});

		report.page.add_inner_button(__("View Stock Ledger"), function () {
			var filters = report.get_values();
			frappe.set_route("query-report", "Stock Ledger", filters);
		});
	},
};

erpnext.utils.add_inventory_dimensions("Stock Balance", 8);