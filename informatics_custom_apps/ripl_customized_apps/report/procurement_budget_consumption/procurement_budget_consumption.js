// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["Procurement Budget Consumption"] = {

	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		},
		{
			fieldname: "fiscal_year",
			label: __("Fiscal Year"),
			fieldtype: "Link",
			options: "Fiscal Year",
		},
		{
			fieldname: "gl_accounts",
			label: __("GL Account"),
			fieldtype: "MultiSelectList",
			get_data: function(txt) {
				return frappe.db.get_link_options("Account", txt);
			}
		},
		{
			fieldname: "plants",
			label: __("Plant"),
			fieldtype: "MultiSelectList",
			get_data: function(txt) {
				return frappe.db.get_link_options("Branch", txt);
			}
		},
		{
			fieldname: "segments",
			label: __("Segment"),
			fieldtype: "MultiSelectList",
			get_data: function(txt) {
				return frappe.db.get_link_options("Segment", txt);
			}
		}
	],

	formatter: function(value, row, column, data, default_formatter) {

		value = default_formatter(value, row, column, data);

		if (!data) {
			return value;
		}

		if (column.fieldname === "mr_amount" && flt(data.mr_amount)) {

			return `
				<a
					class="mr-drilldown"
					data-gl="${data.gl_account || ''}"
					data-cost-center="${data.cost_center || ''}"
					data-plant="${data.plant || ''}"
					data-segment="${data.segment || ''}"
					style="font-weight:bold;"
				>
					${value}
				</a>
			`;
		}

		if (column.fieldname === "po_amount" && flt(data.po_amount)) {

			return `
				<a
					class="po-drilldown"
					data-gl="${data.gl_account || ''}"
					data-cost-center="${data.cost_center || ''}"
					data-plant="${data.plant || ''}"
					data-segment="${data.segment || ''}"
					style="font-weight:bold;"
				>
					${value}
				</a>
			`;
		}

		return value;
	},

	after_datatable_render: function() {

		$(document).off("click", ".mr-drilldown");

		$(document).on("click", ".mr-drilldown", function() {

			frappe.set_route(
				"query-report",
				"Procurement Budget MR Drilldown",
				{
					company: frappe.query_report.get_filter_value("company"),
					fiscal_year: frappe.query_report.get_filter_value("fiscal_year"),
					gl_account: $(this).data("gl"),
					cost_center: $(this).data("cost-center"),
					plant: $(this).data("plant"),
					segment: $(this).data("segment")
				}
			);

		});

		$(document).off("click", ".po-drilldown");

		$(document).on("click", ".po-drilldown", function() {

			frappe.set_route(
				"query-report",
				"Procurement Budget PO Drilldown",
				{
					company: frappe.query_report.get_filter_value("company"),
					fiscal_year: frappe.query_report.get_filter_value("fiscal_year"),
					gl_account: $(this).data("gl"),
					cost_center: $(this).data("cost-center"),
					plant: $(this).data("plant"),
					segment: $(this).data("segment")
				}
			);

		});
	}
};