// Copyright (c) 2026, Rana Informatics and contributors
// License: MIT / proprietary — adjust as per your app's license header

frappe.query_reports["Ledger vs Balance"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "MultiSelectList",
			get_data: function (txt) {
				return frappe.db.get_link_options("Item", txt);
			},
		},
		{
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group",
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "MultiSelectList",
			get_data: function (txt) {
				return frappe.db.get_link_options("Warehouse", txt);
			},
		},
		{
			fieldname: "qty_tolerance",
			label: __("Qty Tolerance"),
			fieldtype: "Float",
			default: 0.001,
			description: __("Differences smaller than this are ignored as rounding noise"),
		},
		{
			fieldname: "value_tolerance",
			label: __("Value Tolerance"),
			fieldtype: "Currency",
			default: 1,
			description: __("Differences smaller than this are ignored as rounding noise"),
		},
		{
			fieldname: "show_all_divergent_rows",
			label: __("Show All Divergent Rows (not just first break)"),
			fieldtype: "Check",
			default: 0,
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (["qty_diff", "value_diff"].includes(column.fieldname) && data && data[column.fieldname]) {
			value = `<span style="color: var(--red-600); font-weight: 600;">${value}</span>`;
		}

		if (column.fieldname === "voucher_no" && data && data.voucher_no) {
			value = `<a href="/app/${frappe.router.slug(data.voucher_type)}/${data.voucher_no}" target="_blank">${data.voucher_no}</a>`;
		}

		return value;
	},

	get_datatable_options(options) {
    return Object.assign(options, {
        checkboxColumn: true,
    });
},

	onload: function (report) {
		report.page.add_inner_button(__("Create Repost Entry"), function () {
			const checked = report.datatable.rowmanager.getCheckedRows();

			if (!checked || !checked.length) {
				frappe.msgprint(__("Select a divergent row first (checkbox on the left)."));
				return;
			}
			if (checked.length > 1) {
				frappe.msgprint(__("Select only one row at a time to create a Repost entry."));
				return;
			}

			const row_index = checked[0];
			const row_data = report.data[row_index];

			frappe.confirm(
				__(
					"Create a Repost Item Valuation for {0} at {1}, starting {2} {3}? It will be created as a draft for you to review before submitting.",
					[row_data.item_code, row_data.warehouse, row_data.posting_date, row_data.posting_time]
				),
				function () {
					frappe.call({
						method:
							"informatics_custom_apps.ripl_customized_apps.report.ledger_vs_balance.ledger_vs_balance.create_repost_entry",
						args: {
							item_code: row_data.item_code,
							warehouse: row_data.warehouse,
							posting_date: row_data.posting_date,
							posting_time: row_data.posting_time,
							company: row_data.company,
						},
						freeze: true,
						freeze_message: __("Creating Repost Item Valuation..."),
						callback: function (r) {
							if (r.message) {
								frappe.show_alert({
									message: __("Repost Item Valuation {0} created as draft.", [r.message]),
									indicator: "green",
								});
								frappe.set_route("Form", "Repost Item Valuation", r.message);
							}
						},
					});
				}
			);
		});
	},
};